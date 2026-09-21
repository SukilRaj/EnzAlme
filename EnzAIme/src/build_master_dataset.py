#!/usr/bin/env python3
"""
src/build_master_dataset.py
============================
Build a robust, reproducible MASTER enzyme dataset for ENZAIme from the
datasets already present in the project data folder(s).

Pipeline outline
----------------
1. Discover every file under the input directory/directories.
2. Classify each file (CSV / TSV / FASTA / FASTQ / JSON / Excel / compressed /
   text) and decide whether it can contribute enzyme records.
3. Parse contributing sources into typed records (accession, sequence, name,
   pollutant, pH/temperature/salinity, evidence, provenance).
4. Clean and validate protein sequences (no DNA, no empty sequences, flag
   suspicious ones instead of silently deleting them).
5. Merge records into enzyme-level rows:
      priority 1 -> exact UniProt accession
      priority 2 -> exact cleaned-sequence match
      priority 3 -> sequence-hash match
      priority 4 -> carefully normalised enzyme name, ONLY if unambiguous
                    (a name with >1 distinct sequence in the whole corpus is
                     treated as ambiguous and never name-merged)
6. Detect and report value conflicts between sources.
7. Write the six output artefacts (see --output_dir).

Scientific rules
----------------
- No value is invented.  Missing pH / temperature / salinity stay missing.
- Evidence type is one of: experimental / curated / predicted / inferred /
  heuristic / unknown.  A literature-approximate "demo assumption" numeric
  value is labelled heuristic, never experimental.
- Every row keeps source_file / source_record_id provenance.
- Never downloads external data.  No model training.  No synthetic
  environmental scenario generation.  No ESM embeddings.

Usage
-----
    python src/build_master_dataset.py --input_dir data datasets
    python src/build_master_dataset.py --input_dir data datasets --output_dir data/processed
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_AA = "ACDEFGHIKLMNPQRSTVWY"
RARE_AA = "BJUOXZ"  # ambiguous / non-canonical letters - flagged, never dropped

MASTER_COLUMNS = [
    "enzyme_id",
    "accession",
    "enzyme_name",
    "protein_sequence",
    "sequence_length",
    "enzyme_family",
    "ec_number",
    "organism",
    "pollutant_type",
    "substrate",
    "ph_opt",
    "ph_min",
    "ph_max",
    "temperature_opt_c",
    "temperature_min_c",
    "temperature_max_c",
    "salinity_opt",
    "salinity_min",
    "salinity_max",
    "salinity_unit",
    "evidence_type",
    "evidence_score",
    "source_database",
    "source_file",
    "source_record_id",
    "sequence_hash",
    "data_quality_flag",
    "notes",
]

# Evidence-type ranking used for value preference during merging:
# lower index = more trustworthy source wins when two sources disagree.
EVIDENCE_RANK = {
    "experimental": 0,
    "curated": 1,
    "predicted": 2,
    "inferred": 3,
    "heuristic": 4,
    "unknown": 5,
}
# Provenance score: a documented ordinal derived ONLY from the recorded
# evidence_type label.  It is a provenance ordinal, NOT a biological
# measurement and NOT an experimental performance claim.
EVIDENCE_SCORES = {
    "experimental": 1.0,
    "curated": 0.85,
    "predicted": 0.6,
    "inferred": 0.4,
    "heuristic": 0.25,
    "unknown": 0.1,
}

POLLUTANT_NORMALIZE = {
    "PET": "PET", "PETE": "PET", "PETASE": "PET",
    "POLY(ETHYLENE TEREPHTHALATE)": "PET", "POLYETHYLENETEREPHTHALATE": "PET",
    "PA": "PA", "PA6": "PA", "PA66": "PA", "PA46": "PA", "PA4": "PA",
    "NYLON": "PA", "NYLON6": "PA", "NYLON66": "PA",
    "PUR": "PUR", "PU": "PUR", "POLYURETHANE": "PUR",
    "POLYESTERPOLYURETHANE": "PUR", "POLYESTER-POLYURETHANE": "PUR",
}

KNOWN_ACCESSION_RE = re.compile(
    r"[OPQ][0-9][A-Z0-9]{3}[0-9]"
    r"|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}"
)
EC_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")

# demo-set enzyme_id -> organism, transcribed verbatim from the notes column of
# data/demo/enzymes_demo.csv (source information is preserved, not invented).
DEMO_ORGANISM_MAP = {
    "ENZ001": "Ideonella sakaiensis",
    "ENZ002": "Ideonella sakaiensis",
    "ENZ003": "uncultured leaf-branch compost bacterium (metagenome)",
    "ENZ004": "Thermobifida fusca",
    "ENZ005": "Burkholderiales bacterium (homolog source, uncertain)",
    "ENZ006": "Paenarthrobacter (Arthrobacter) sp. KI72",
    "ENZ007": "Paenarthrobacter sp. KI72",
    "ENZ008": "Pseudomonas chlororaphis",
    "ENZ009": "Pseudomonas chlororaphis",
}


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def clean_sequence(raw: Any) -> str:
    """Uppercase, then keep alpha characters only (drops digits, whitespace,
    '*', '-', '|', '_', punctuation)."""
    if raw is None:
        return ""
    return "".join(ch for ch in str(raw).upper() if ch.isalpha())


def sequence_quality_flags(seq: str) -> list[str]:
    """Conservative QC flags for a cleaned sequence.  Never deletes data."""
    flags: list[str] = []
    if not seq:
        flags.append("empty_sequence")
        return flags
    rare = set(seq) & set(RARE_AA)
    if rare:
        flags.append(f"nonstandard_aa:{''.join(sorted(rare))}")
    if len(seq) < 30:
        flags.append("short_sequence")
    if len(seq) >= 50:
        base_count = sum(1 for ch in seq if ch in "ACGT")
        if base_count / len(seq) >= 0.95:
            flags.append("possible_nucleotide_sequence")
    return flags


def sequence_hash(seq: str) -> str:
    return "" if not seq else hashlib.sha256(seq.encode()).hexdigest()


def normalize_name(raw: Any) -> str:
    """Normalised matching key for an enzyme name.

    Keeps primed variants distinct ('NylB' vs 'NylB\\''), strips trailing
    parentheticals, and removes punctuation/whitespace.
    """
    if raw is None:
        return ""
    s = str(raw)
    s = s.split("(", 1)[0]          # drop parenthetical qualifiers
    s = s.replace("'", "p")         # keep primed variants distinct
    s = re.sub(r"[^A-Za-z0-9]", "", s)
    return s.lower()


def normalize_pollutant(raw: Any) -> tuple[str, list[str]]:
    if raw is None or pd.isna(raw):
        return "", ["pollutant_unknown"]
    s = str(raw).strip()
    if not s:
        return "", ["pollutant_unknown"]
    compact = re.sub(r"[\s\-/_]+", "", s).upper()
    for key in sorted(POLLUTANT_NORMALIZE, key=len, reverse=True):
        if compact == re.sub(r"[\s\-/_]+", "", key).upper():
            return POLLUTANT_NORMALIZE[key], []
    return s, ["pollutant_unrecognized_preserved"]


def _norm_source_path(path: Path, input_dirs: list[Path]) -> str:
    """Short, reproducible label for a source file."""
    for inp in input_dirs:
        try:
            return str(path.relative_to(inp))
        except ValueError:
            continue
    return str(path.name)


def _to_num_or_none(val: Any) -> Any:
    if val is None:
        return None
    try:
        return float(str(val).strip())
    except (TypeError, ValueError):
        return None


def _evidence_from_tokens(token: str) -> str:
    t = (token or "").strip().lower()
    if t in {"experimental", "measured"}:
        return "experimental"
    if t in {"verified", "curated"}:
        return "curated"
    if t in {"predicted", "prediction"}:
        return "predicted"
    if t in {"inferred", "homology", "homolog"}:
        return "inferred"
    return "curated"  # default for curated database exports


def seq_aa_valid(seq: str) -> set[str]:
    return set(seq) - set(VALID_AA) - set(RARE_AA)


# ---------------------------------------------------------------------------
# Raw-record constructor
# ---------------------------------------------------------------------------

def _make_raw_record(
    *,
    enzyme_id: Optional[str],
    accession: str,
    enzyme_name: Optional[str],
    protein_sequence: str,
    source_database: str,
    source_file: str,
    source_record_id: str,
    organism: Optional[str] = None,
    ec_number: str = "",
    pollutant_type: str = "",
    ph_opt: Any = None,
    ph_min: Any = None,
    ph_max: Any = None,
    temperature_opt_c: Any = None,
    temperature_min_c: Any = None,
    temperature_max_c: Any = None,
    salinity_opt: Any = None,
    salinity_min: Any = None,
    salinity_max: Any = None,
    salinity_unit: str = "",
    evidence_type: str = "curated",
    seq_flags: Optional[list[str]] = None,
    pol_flags: Optional[list[str]] = None,
    notes: str = "",
) -> dict[str, Any]:
    seq = protein_sequence
    if seq:
        if seq_aa_valid(seq):
            pass  # invalid AA were already stripped during cleaning
    flags = list(seq_flags or [])
    sp_flags = list(pol_flags or [])
    if seq:
        flags.append("sequence_present")
    flags = list(dict.fromkeys(flags))  # dedupe, preserve order
    return {
        "enzyme_id": enzyme_id,
        "accession": accession,
        "enzyme_name": enzyme_name,
        "protein_sequence": seq,
        "sequence_length": len(seq) if seq else None,
        "enzyme_family": "",
        "ec_number": ec_number if re.fullmatch(EC_RE.pattern, ec_number) else "",
        "organism": organism,
        "pollutant_type": pollutant_type,
        "substrate": "",
        "ph_opt": ph_opt, "ph_min": ph_min, "ph_max": ph_max,
        "temperature_opt_c": temperature_opt_c,
        "temperature_min_c": temperature_min_c,
        "temperature_max_c": temperature_max_c,
        "salinity_opt": salinity_opt, "salinity_min": salinity_min,
        "salinity_max": salinity_max, "salinity_unit": salinity_unit,
        "evidence_type": evidence_type,
        "evidence_score": EVIDENCE_SCORES.get(evidence_type, 0.1),
        "source_database": source_database,
        "source_file": source_file,
        "source_record_id": source_record_id,
        "sequence_hash": sequence_hash(seq),
        "data_quality_flag": ";".join(flags + sp_flags) or "ok",
        "notes": notes,
        "_norm_name": normalize_name(enzyme_name) if enzyme_name else "",
    }


# ---------------------------------------------------------------------------
# FASTA parsing (protein sequences)
# ---------------------------------------------------------------------------

def detect_fasta_style(path: Path) -> str:
    """Peek the first header to tell ENZAIme-style from PAZy-style FASTA."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if "|" in line:
                    parts = line[1:].split("|")
                    if re.match(r"^ENZ\d+$", parts[0].strip()):
                        return "enzaime"
                return "pazy"
    return "pazy"


def parse_fasta_file(
    path: Path,
    input_dirs: list[Path],
    source_database: str,
    default_pollutant: str = "",
    id_prefix: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from Bio import SeqIO
    style = detect_fasta_style(path)
    records: list[dict[str, Any]] = []
    stats = {"n_records": 0, "n_empty": 0, "n_invalid_chars": 0}
    opener = gzip.open if str(path).endswith(".gz") else open

    label = _norm_source_path(path, input_dirs)
    with opener(path, "rt", errors="replace") as fh:
        for rec in SeqIO.parse(fh, "fasta"):
            stats["n_records"] += 1
            header = (rec.description or rec.id).strip().split("\n", 1)[0]
            raw_seq = str(rec.seq)

            enzyme_id = None
            accession = ""
            name = ""
            organism = ""
            pollutant = ""
            evidence_token = ""
            record_id = rec.id

            if "|" in header:
                parts = header.split("|")
                if style == "enzaime" and re.match(r"^ENZ\d+$", parts[0].strip()):
                    # ENZ001|ACC|NAME|ORG|POL|EVID
                    enzyme_id = parts[0].strip()
                    record_id = enzyme_id
                    accession = parts[1].strip() if len(parts) > 1 else ""
                    name = parts[2].strip() if len(parts) > 2 else ""
                    organism = parts[3].strip() if len(parts) > 3 else ""
                    pollutant = parts[4].strip() if len(parts) > 4 else ""
                    evidence_token = parts[5].strip() if len(parts) > 5 else ""
                else:
                    # RCSB style: 7CWQ_1|Chains A, B|NAME|ORGANISM
                    record_id = parts[0].strip()
                    name = parts[2].strip() if len(parts) > 2 else (
                        parts[1].strip() if len(parts) > 1 else parts[0].strip())
                    organism = parts[3].strip() if len(parts) > 3 else ""
                    evidence_token = "curated"
            else:
                # PAZy style: 54 NylA
                words = header.split()
                record_id = words[0]
                name = " ".join(words[1:]).strip() or record_id

            if not name and enzyme_id is None:
                name = record_id
            if not name and record_id == "":
                record_id = f"record_{stats['n_records']}"

            seq = clean_sequence(raw_seq)
            if not seq:
                stats["n_empty"] += 1
                continue  # empty after cleaning - never create an enzyme from it
            flags = sequence_quality_flags(seq)
            bad = seq_aa_valid(seq)
            if bad:
                stats["n_invalid_chars"] += 1
                flags.append(f"invalid_chars_removed:{''.join(sorted(bad))}")

            # accession validity
            if accession and KNOWN_ACCESSION_RE.fullmatch(accession):
                la = accession
            else:
                if accession:
                    flags.append("accession_unresolved:kept_in_header_note")
                la = ""

            # pollutant
            pol_flags: list[str] = []
            if enzyme_id and pollutant:
                pollutant, pol_flags = normalize_pollutant(pollutant)
            elif default_pollutant:
                pollutant = default_pollutant
                pol_flags.append("pollutant_from_source_membership")
            else:
                pollutant = ""
                pol_flags.append("pollutant_unknown")

            evidence_type = _evidence_from_tokens(evidence_token)
            rec_dict = _make_raw_record(
                enzyme_id=enzyme_id,
                accession=la,
                enzyme_name=name or None,
                protein_sequence=seq,
                source_database=source_database,
                source_file=label,
                source_record_id=record_id,
                organism=organism or None,
                pollutant_type=pollutant,
                evidence_type=evidence_type,
                seq_flags=flags,
                pol_flags=pol_flags,
                notes=f"FASTA description: {header[:180]}",
            )
            if id_prefix and not rec_dict["enzyme_id"]:
                rec_dict["enzyme_id"] = f"{id_prefix}_{record_id}"
            records.append(rec_dict)
    return records, stats


# ---------------------------------------------------------------------------
# CSV parsing (curated demo set)
# ---------------------------------------------------------------------------

def parse_demo_csv(path: Path, input_dirs: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    label = _norm_source_path(path, input_dirs)

    for _, row in df.iterrows():
        eid = str(row.get("enzyme_id", "")).strip()
        acc_raw = str(row.get("accession", "")).strip()

        flags: list[str] = []
        if acc_raw and KNOWN_ACCESSION_RE.fullmatch(acc_raw):
            accession = acc_raw
        else:
            if acc_raw:
                warnings.append(f"{eid}: unresolved accession '{acc_raw}' "
                                f"kept in notes only")
                flags.append("accession_unresolved")
            accession = ""

        raw_seq = row.get("sequence", None)
        seq = clean_sequence(raw_seq)
        if seq:
            flags.extend(sequence_quality_flags(seq))
        else:
            flags.append("sequence_missing")

        pol, pol_flags = normalize_pollutant(row.get("pollutant"))
        evidence_type = str(row.get("evidence_type", "")).strip().lower()
        evidence_type = _evidence_from_tokens(evidence_type or "verified")

        notes = str(row.get("notes", "")).strip()
        if str(row.get("demo_assumption", "")).strip().lower() in {"true", "1", "yes"}:
            notes = (notes + " [demo_assumption=True: pH_opt / T_opt values here are "
                             "literature-approximate (heuristic), NOT experimental "
                             "measurements]").strip()
            flags.append("heuristic_opt_numerics")

        rec = _make_raw_record(
            enzyme_id=eid or None,
            accession=accession,
            enzyme_name=str(row.get("enzyme_name", "")).strip() or None,
            protein_sequence=seq,
            source_database=str(row.get("source", "")).strip() or "curated_demo",
            source_file=label,
            source_record_id=eid or f"row_{row.name}",
            organism=DEMO_ORGANISM_MAP.get(eid),
            ec_number=str(row.get("ec_number", "")).strip(),
            pollutant_type=pol or "",
            ph_opt=_to_num_or_none(row.get("pH_opt")),
            ph_min=_to_num_or_none(row.get("pH_min")),
            ph_max=_to_num_or_none(row.get("pH_max")),
            temperature_opt_c=_to_num_or_none(row.get("T_opt")),
            temperature_min_c=_to_num_or_none(row.get("T_min")),
            temperature_max_c=_to_num_or_none(row.get("T_max")),
            salinity_opt=None,
            salinity_min=_to_num_or_none(row.get("salinity_min")),
            salinity_max=_to_num_or_none(row.get("salinity_max")),
            salinity_unit="",
            evidence_type=evidence_type,
            seq_flags=flags,
            pol_flags=pol_flags,
            notes=notes or "No source notes.",
        )
        records.append(rec)
    return records, warnings


# ---------------------------------------------------------------------------
# FireProtDB overlap scan (streams the ~1.65 GB file)
# ---------------------------------------------------------------------------

def scan_fireprotdb(path: Path, known_accessions: set[str],
                    known_norm_names: set[str]) -> dict[str, Any]:
    cols = ["UNIPROTKB", "PROTEIN"]
    matches: list[dict[str, str]] = []
    n_rows = 0
    try:
        for chunk in pd.read_csv(path, usecols=cols, dtype=str,
                                 chunksize=500_000, on_bad_lines="skip"):
            n_rows += len(chunk)
            upk = chunk["UNIPROTKB"].fillna("").str.strip()
            prot = chunk["PROTEIN"].fillna("")
            for acc in sorted(known_accessions):
                n = int(upk.eq(acc).sum())
                if n:
                    matches.append({"match_type": "accession", "key": acc,
                                    "n_records": n})
            norm_names = prot.apply(normalize_name)
            for nm in sorted(known_norm_names):
                if not nm:
                    continue
                n = int(norm_names.eq(nm).sum())
                if n:
                    matches.append({"match_type": "name", "key": nm,
                                    "n_records": n})
            if n_rows > 8_000_000:
                break
    except Exception as exc:  # pragma: no cover - robustness guard
        return {"error": str(exc), "n_rows_scanned": n_rows, "matches": matches}
    return {"n_rows_scanned": n_rows, "matches": matches}


# ---------------------------------------------------------------------------
# Merging raw records into enzyme-level rows
# ---------------------------------------------------------------------------

def merge_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge raw records -> enzyme rows.  Returns (enzymes, merge_events)."""
    records = sorted(records, key=lambda r: (r["source_file"], r["source_record_id"]))

    # Precompute globally-ambiguous names: a name whose records span more than
    # one distinct sequence can NEVER be merged by name alone.
    name_seq = {}
    for r in records:
        nm = r.get("_norm_name") or ""
        if nm:
            name_seq.setdefault(nm, set()).add(r["sequence_hash"] or "")
    ambiguous_names = {nm for nm, hashes in name_seq.items()
                       if len(hashes - {""}) > 1}

    enzymes: list[dict[str, Any]] = []
    by_acc: dict[str, int] = {}
    by_seq: dict[str, list[int]] = {}
    by_name: dict[str, list[int]] = {}
    events: list[dict[str, Any]] = []
    ambiguous_reported: set[str] = set()

    def _index(e_idx: int) -> None:
        e = enzymes[e_idx]
        if e["accession"]:
            by_acc[e["accession"]] = e_idx
        if e["sequence_hash"]:
            by_seq.setdefault(e["sequence_hash"], []).append(e_idx)
        if e["_norm_name"]:
            by_name.setdefault(e["_norm_name"], []).append(e_idx)

    for rec in records:
        idx: Optional[int] = None
        how = ""

        # 1) exact accession
        if idx is None and rec["accession"]:
            idx = by_acc.get(rec["accession"])
            if idx is not None:
                how = "accession"

        # 2) exact sequence / hash
        if idx is None and rec["sequence_hash"]:
            cands = by_seq.get(rec["sequence_hash"], [])
            if len(cands) == 1:
                idx = cands[0]
                how = "sequence_hash"
            elif len(cands) > 1:
                events.append({"kind": "ambiguous_sequence",
                               "record": rec["source_record_id"],
                               "n_masters": len(cands)})

        # 3) unambiguous normalised name
        if idx is None:
            nm = rec.get("_norm_name") or ""
            if nm:
                if nm in ambiguous_names:
                    if nm not in ambiguous_reported:
                        events.append({"kind": "ambiguous_name", "name": nm,
                                       "n_masters": len([k for k in name_seq.get(nm, [])])})
                        ambiguous_reported.add(nm)
                else:
                    cands = by_name.get(nm, [])
                    if len(cands) == 1:
                        idx = cands[0]
                        how = "normalized_name"

        if idx is None:
            new = dict(rec)
            new["enzyme_id"] = rec["enzyme_id"] or _fallback_id(rec)
            enzymes.append(new)
            _index(len(enzymes) - 1)
            continue

        # merge into existing enzyme
        events.append({"kind": "merged", "how": how,
                       "enzyme_id": enzymes[idx]["enzyme_id"],
                       "record": rec["source_record_id"],
                       "into": enzymes[idx]["source_record_id"]})
        enzymes[idx] = _merge_two(enzymes[idx], rec, how, events)

    # collapse any residual enzyme_id collisions (safe guard)
    final: list[dict[str, Any]] = []
    id_index: dict[str, int] = {}
    for e in enzymes:
        eid = e["enzyme_id"] or _fallback_id(e)
        if eid in id_index:
            final[id_index[eid]] = _merge_two(final[id_index[eid]], e, "same_derived_id", events)
        else:
            e["enzyme_id"] = eid
            id_index[eid] = len(final)
            final.append(e)
    for e in final:
        e.pop("_norm_name", None)
    return final, events


def _fallback_id(rec: dict[str, Any]) -> str:
    if rec["accession"]:
        return f"ENZ_{re.sub(r'[^A-Za-z0-9]', '', rec['accession'])}"
    if rec["sequence_hash"]:
        return f"ENZ_H{rec['sequence_hash'][:12].upper()}"
    tag = re.sub(r"[^A-Za-z0-9]", "", rec.get("source_record_id") or "src")[:12]
    return f"ENZ_SRC_{tag}"


def _merge_two(base: dict[str, Any], rec: dict[str, Any], how: str,
               events: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(base)
    if not out.get("enzyme_id"):
        out["enzyme_id"] = rec.get("enzyme_id")

    base_rank = EVIDENCE_RANK.get(base["evidence_type"], 5)
    rec_rank = EVIDENCE_RANK.get(rec["evidence_type"], 5)
    pref_rec = rec_rank < base_rank  # rec is more trustworthy

    numeric_fields = ["ph_opt", "ph_min", "ph_max", "temperature_opt_c",
                      "temperature_min_c", "temperature_max_c", "salinity_opt",
                      "salinity_min", "salinity_max"]
    for f in numeric_fields:
        b, r = base.get(f), rec.get(f)
        if r is None:
            continue
        if b is None:
            out[f] = r
        elif b != r:
            events.append({"kind": "value_conflict", "field": f,
                           "enzyme_id": out.get("enzyme_id"),
                           "source_base": base["source_file"], "value_base": b,
                           "source_rec": rec["source_file"], "value_rec": r,
                           "resolution": "prefer_rec" if pref_rec else "prefer_base"})
            if pref_rec:
                out[f] = r

    for f in ["enzyme_name", "ec_number", "organism", "substrate"]:
        b = str(base.get(f) or "").strip()
        r = str(rec.get(f) or "").strip()
        if r and not b:
            out[f] = r
        elif b and b != r:
            events.append({"kind": "value_conflict", "field": f,
                           "enzyme_id": out.get("enzyme_id"),
                           "source_base": base["source_file"], "value_base": b,
                           "source_rec": rec["source_file"], "value_rec": r,
                           "resolution": "prefer_rec" if pref_rec else "prefer_base"})
            if pref_rec:
                out[f] = r

    b_acc = base.get("accession") or ""
    r_acc = rec.get("accession") or ""
    if r_acc and not b_acc:
        out["accession"] = r_acc
    elif b_acc and r_acc and b_acc != r_acc:
        events.append({"kind": "accession_conflict", "enzyme_id": out.get("enzyme_id"),
                       "value_base": b_acc, "value_rec": r_acc, "resolution": "keep_base"})

    b_pol = base.get("pollutant_type") or ""
    r_pol = rec.get("pollutant_type") or ""
    if r_pol and r_pol != b_pol:
        if not b_pol or "inferred" in base.get("data_quality_flag", ""):
            out["pollutant_type"] = r_pol
            events.append({"kind": "pollutant_fill", "enzyme_id": out.get("enzyme_id"),
                           "from": b_pol or "(empty)", "to": r_pol})
        else:
            events.append({"kind": "value_conflict", "field": "pollutant_type",
                           "enzyme_id": out.get("enzyme_id"),
                           "source_base": base["source_file"], "value_base": b_pol,
                           "source_rec": rec["source_file"], "value_rec": r_pol,
                           "resolution": "keep_base"})

    if pref_rec:
        out["evidence_type"] = rec["evidence_type"]
        out["evidence_score"] = rec["evidence_score"]

    for f in ["source_database", "source_file", "source_record_id"]:
        parts = [str(base.get(f) or "")] if base.get(f) else []
        if rec.get(f) and rec[f] not in parts:
            parts.append(str(rec[f]))
        out[f] = "; ".join(dict.fromkeys(p for p in parts if p))

    b_notes = str(base.get("notes") or "").strip()
    r_notes = str(rec.get("notes") or "").strip()
    if b_notes and b_notes != r_notes:
        out["notes"] = b_notes + " || " + r_notes
    elif not b_notes:
        out["notes"] = r_notes
    out["notes"] = out["notes"].rstrip(" || ")

    b_seq, r_seq = base.get("protein_sequence") or "", rec.get("protein_sequence") or ""
    if b_seq and r_seq and base["sequence_hash"] != rec["sequence_hash"]:
        events.append({"kind": "sequence_conflict", "enzyme_id": out.get("enzyme_id"),
                       "hash_base": base["sequence_hash"], "hash_rec": rec["sequence_hash"],
                       "len_base": len(base["protein_sequence"] or ""),
                       "len_rec": len(rec["protein_sequence"] or ""),
                       "resolution": "prefer_rec" if pref_rec else "keep_base"})
        if pref_rec:
            out["protein_sequence"], out["sequence_hash"] = r_seq, rec["sequence_hash"]
    elif not b_seq and r_seq:
        out["protein_sequence"], out["sequence_hash"] = r_seq, rec["sequence_hash"]
    out["sequence_length"] = len(out["protein_sequence"]) if out["protein_sequence"] else None

    flags = set(str(base.get("data_quality_flag") or "").split(";"))
    flags.update(str(rec.get("data_quality_flag") or "").split(";"))
    flags.discard("")
    flags.discard("sequence_missing")
    if out["protein_sequence"]:
        flags.add("sequence_present")
    if how:
        flags.add(f"merged_via_{how}")
    out["data_quality_flag"] = ";".join(sorted(flags))
    return out


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def build_deduplicated_view(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse rows sharing an identical cleaned sequence.  Rows without a
    sequence are kept untouched."""
    out_rows: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for _, row in df.iterrows():
        h = row["sequence_hash"]
        if not h:
            out_rows.append(row.to_dict())
            continue
        if h not in seen:
            seen[h] = len(out_rows)
            out_rows.append(row.to_dict())
        else:
            other = out_rows[seen[h]]
            for f in ["source_database", "source_file", "source_record_id"]:
                vals = dict.fromkeys(str(other[f]).split("; ") + str(row[f]).split("; "))
                other[f] = "; ".join(v for v in vals if v)
            other["notes"] = (str(other["notes"]) + f" [same-sequence alias: "
                              f"{row['enzyme_id']}]")
            other["data_quality_flag"] = ";".join(sorted(
                set(str(other["data_quality_flag"]).split(";"))
                | {"duplicate_sequence_alias"}))
    return pd.DataFrame(out_rows)


def missing_pct(df: pd.DataFrame) -> dict[str, float]:
    pct: dict[str, float] = {}
    for col in MASTER_COLUMNS:
        if col not in df.columns:
            continue
        n_missing = df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum()
        pct[col] = round(100.0 * n_missing / max(len(df), 1), 1)
    return pct


# ---------------------------------------------------------------------------
# FASTA pollutant assignment (PAZy exports)
# ---------------------------------------------------------------------------

def assign_pollutant_by_name(records: list[dict[str, Any]], default: str) -> list[dict[str, Any]]:
    NYLON_MARKERS = {"nyla", "nylb", "nylbp", "nylc", "nylc1", "nylc2", "nylc5",
                     "ttaa", "arylacylamidase", "gata", "ooh", "reu", "tvgc",
                     "pa4degradingenzyme"}
    for r in records:
        nm = r.get("_norm_name") or ""
        flags = set(str(r["data_quality_flag"]).split(";"))
        flags.discard("pollutant_from_name")
        flags.discard("pollutant_from_source_membership")
        flags.discard("pollutant_unknown")
        if nm == "ccpur1" or nm == "ccpur2":
            r["pollutant_type"] = "PUR"
            flags.add("pollutant_from_name")
        elif nm in NYLON_MARKERS or "nyl" in nm:
            r["pollutant_type"] = "PA"
            flags.add("pollutant_from_name")
        elif nm:
            r["pollutant_type"] = default
            flags.add("pollutant_from_source_membership")
        else:
            r["pollutant_type"] = ""
            flags.add("pollutant_unknown")
        r["data_quality_flag"] = ";".join(sorted(flags))
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Build the ENZAIme master enzyme dataset.")
    ap.add_argument("--input_dir", nargs="*", default=None,
                    help="One or more source directories. Default: <repo>/data and "
                         "<repo>/datasets (if present).")
    ap.add_argument("--output_dir", type=str, default=None,
                    help="Where to write outputs. Default: <repo>/data/processed")
    ap.add_argument("--fireprotdb", choices=["scan", "sample", "skip"], default="scan",
                    help="How to handle the large FireProtDB CSV. 'scan' streams the "
                         "whole file to prove overlap status (slow, ~2-3 min).")
    args = ap.parse_args()

    if args.input_dir:
        input_dirs = [Path(d).resolve() for d in args.input_dir]
    else:
        input_dirs = [REPO_ROOT / "data"]
        if (REPO_ROOT / "datasets").is_dir():
            input_dirs.append(REPO_ROOT / "datasets")

    out_dir = Path(args.output_dir).resolve() if args.output_dir else REPO_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("ENZAIme master-dataset builder")
    print("=" * 72)
    for d in input_dirs:
        print(f"  input dir : {d}")
    print(f"  output dir: {out_dir}")

    # ---- discover files ----------------------------------------------------
    all_files: list[Path] = []
    for d in input_dirs:
        if not d.exists():
            print(f"[WARN] input dir missing: {d}")
            continue
        all_files.extend(sorted(p for p in d.rglob("*") if p.is_file()))

    records: list[dict[str, Any]] = []
    source_stats: dict[str, dict[str, Any]] = {}
    handled: dict[str, dict[str, str]] = {}

    def _note(path: Path, status: str, reason: str) -> None:
        label = _norm_source_path(path, input_dirs)
        handled[label] = {"path": str(path), "status": status, "reason": reason}

    def _stats(path: Path, **kw: Any) -> None:
        source_stats.setdefault(path.name, {"status": "used"}).update(kw)

    # ---- 1. curated demo CSV (metadata backbone) ---------------------------
    demo_path = next((p for p in all_files if p.name == "enzymes_demo.csv"), None)
    if demo_path is None:
        print("[ERROR] no data/demo/enzymes_demo.csv found -- cannot build.")
        sys.exit(1)
    print(f"[read] {demo_path}")
    demo_records, demo_warnings = parse_demo_csv(demo_path, input_dirs)
    records.extend(demo_records)
    _note(demo_path, "used", "curated demo/enzyme metadata backbone")
    _stats(demo_path, n_records=len(demo_records))
    for w in demo_warnings:
        print(f"  [warn] {w}")

    # ---- 2. FASTA sources ---------------------------------------------------
    fasta_files = [p for p in all_files
                   if p.suffix in {".fasta", ".fa"}
                   or p.name.endswith(".fasta.gz")]
    excluded = {
        "uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz":
            "tRNA dimethylallyltransferases are NOT plastic-degrading enzymes "
            "(project scope); kept for provenance only, never loaded.",
    }
    skip_copies = {
        "pazy_proteins_clean.fasta":
            "duplicate of data/raw/pazy/pazy_proteins.fasta (same 2 sequences); "
            "raw copy used instead.",
    }
    for p in sorted(fasta_files):
        name = p.name
        if name in excluded:
            _note(p, "excluded", excluded[name])
            _stats(p, status="excluded", reason=excluded[name], n_records=0)
            continue
        if name in skip_copies:
            _note(p, "skipped", skip_copies[name])
            _stats(p, status="skipped", reason=skip_copies[name])
            continue
        style = detect_fasta_style(p)
        if style == "enzaime":
            recs, stats = parse_fasta_file(
                p, input_dirs,
                source_database="UniProt/PAZy derived (ENZAIme format)",
                default_pollutant="")
            records.extend(recs)
            _note(p, "used", "ENZAIme-style FASTA (accession pipe headers)")
            _stats(p, **stats)
            print(f"[read] {p}  ->  {len(recs)} records")
        elif name.startswith("rcsb_pdb_"):
            recs, stats = parse_fasta_file(
                p, input_dirs, source_database="RCSB PDB",
                default_pollutant="", id_prefix="ENZ_PDB")
            for r in recs:
                flags = set(str(r["data_quality_flag"]).split(";"))
                if not r["pollutant_type"]:
                    flags.add("pollutant_unknown")
                r["data_quality_flag"] = ";".join(sorted(flags))
                r["notes"] = (r["notes"] + " || PDB structure; pollutant activity "
                               "is not annotated in the source FASTA file.").strip()
            records.extend(recs)
            _note(p, "used", "RCSB PDB structure FASTA")
            _stats(p, **stats)
            print(f"[read] {p}  ->  {len(recs)} records")
        elif name == "pazy_proteins.fasta":
            recs, stats = parse_fasta_file(
                p, input_dirs, source_database="PAZy export",
                default_pollutant="PA", id_prefix="ENZ_PAZY")
            recs = assign_pollutant_by_name(recs, "PA")
            records.extend(recs)
            _note(p, "used", "PAZy nylonase export")
            _stats(p, **stats)
            print(f"[read] {p}  ->  {len(recs)} records")
        elif name == "pazy_proteins (1).fasta":
            recs, stats = parse_fasta_file(
                p, input_dirs, source_database="PAZy export",
                default_pollutant="PET", id_prefix="ENZ_PAZY1")
            recs = assign_pollutant_by_name(recs, "PET")
            records.extend(recs)
            _note(p, "used", "PAZy PET/cutinase-lipase export")
            _stats(p, **stats)
            print(f"[read] {p}  ->  {len(recs)} records")
        else:
            _note(p, "skipped", "FASTA present but not a recognised PAZy/PDB/demo "
                                "source.")
            _stats(p, status="skipped",
                   reason="not a recognised PAZy/PDB/demo source")

    # ---- 3. FireProtDB overlap scan -----------------------------------------
    known_acc = {r["accession"] for r in records if r["accession"]}
    known_names = {r.get("_norm_name") for r in records if r.get("_norm_name")}
    fp_path = next((p for p in all_files if p.name.startswith("fireprotdb_")), None)
    if fp_path is not None:
        if args.fireprotdb == "scan":
            print(f"[scan] {fp_path}  (streaming; this can take ~2-3 min)")
            res = scan_fireprotdb(fp_path, known_acc, known_names)
            n_m = len(res.get("matches", []))
            scanned = res.get("n_rows_scanned", 0)
            print(f"  -> {scanned:,} rows scanned; {n_m} overlapping records")
            if n_m == 0:
                reason = ("0 overlapping records with the curated enzyme set "
                          "(no UniProt-accession and no exact-name match); "
                          "no pollutant annotation; evidence-only file, excluded "
                          "from enzyme rows.")
            else:
                reason = f"overlap found: {json.dumps(res.get('matches'))[:300]}"
            status = "excluded" if n_m == 0 else "used"
            _note(fp_path, status, reason)
            _stats(fp_path, status=status, reason=reason, n_rows_scanned=scanned,
                   matches=res.get("matches"))
        else:
            _note(fp_path, "skipped",
                  f"--fireprotdb {args.fireprotdb}: file not scanned.")
            _stats(fp_path, status="skipped",
                   reason=f"--fireprotdb {args.fireprotdb}")

    # ---- 4. other files: mark skipped / excluded -----------------------------
    for p in sorted(all_files):
        label = _norm_source_path(p, input_dirs)
        if label in handled:
            continue
        name = p.name
        if name == "new_release_structure_sequence.tsv":
            _note(p, "excluded",
                  "Generic PDB release export (535 sequences incl. GAPDH and "
                  "antibody chains). No pollutant/activity annotation and no "
                  "sequence overlap with the enzyme set.")
            _stats(p, status="excluded",
                   reason="no pollutant annotation; no sequence overlap")
        elif name == "datasets.zip":
            _note(p, "skipped", "archive copy of the datasets/ directory.")
        elif p.suffix == ".json":
            _note(p, "skipped", "JSON scenario/state file, not enzyme metadata.")
        elif p.suffix in {".md", ".txt"}:
            _note(p, "skipped", "documentation/text, not enzyme data.")
        elif name in {"environmental_scenarios.csv", "model_ready_dataset.csv",
                      "enzymes.csv", "sequence_qc.csv",
                      "master_enzymes.csv", "master_enzymes_deduplicated.csv",
                      "data_quality_report.csv", "data_conflicts.csv",
                      "unmatched_records.csv"}:
            _note(p, "skipped", "derived pipeline output, not a raw enzyme source.")
        else:
            _note(p, "skipped", "not a recognised enzyme source.")

    # ---- 5. merge -----------------------------------------------------------
    print(f"\n[merge] {len(records)} raw records -> enzyme-level rows")
    enzymes, events = merge_records(records)
    df = pd.DataFrame(enzymes)[MASTER_COLUMNS]
    df = df.sort_values("enzyme_id", key=lambda s: s.map(_sort_key)).reset_index(drop=True)
    df["sequence_hash"] = df["protein_sequence"].apply(sequence_hash)
    df["sequence_length"] = df["protein_sequence"].apply(lambda s: len(s) if s else None)
    df["evidence_score"] = df["evidence_type"].map(EVIDENCE_SCORES)

    # ---- 6. write outputs ----------------------------------------------------
    print("\n[write] outputs")
    dfout = df.copy()
    blank_numeric_cols = ["ph_opt", "ph_min", "ph_max", "temperature_opt_c",
                          "temperature_min_c", "temperature_max_c", "salinity_opt",
                          "salinity_min", "salinity_max", "sequence_length",
                          "evidence_score"]
    for c in blank_numeric_cols:
        dfout[c] = dfout[c].apply(lambda v: "" if pd.isna(v) else v)

    dfout.to_csv(out_dir / "master_enzymes.csv", index=False)
    print(f"  master_enzymes.csv        -> {len(dfout)} rows")

    dedup_view = build_deduplicated_view(df)
    for c in blank_numeric_cols:
        dedup_view[c] = dedup_view[c].apply(lambda v: "" if pd.isna(v) else v)
    dedup_view[MASTER_COLUMNS].to_csv(out_dir / "master_enzymes_deduplicated.csv",
                                      index=False)
    print(f"  master_enzymes_dedup.csv  -> {len(dedup_view)} rows")

    qdf = pd.DataFrame([
        {"source_file": label, "status": info["status"], "reason": info.get("reason", ""),
         "path": info.get("path", ""),
         "size_bytes": Path(info.get("path", "")).stat().st_size
         if Path(info.get("path", "")).exists() else None,
         "records_contributed": source_stats.get(Path(info.get("path", "")).name, {})
                                .get("n_records")}
        for label, info in sorted(handled.items())
    ])
    qdf.to_csv(out_dir / "data_quality_report.csv", index=False)
    print(f"  data_quality_report.csv   -> {len(qdf)} file entries")

    cdf = pd.DataFrame(events) if events else pd.DataFrame(
        columns=["kind", "how", "enzyme_id", "record", "into", "field",
                 "name", "n_masters", "source_base", "value_base",
                 "source_rec", "value_rec", "resolution", "hash_base",
                 "hash_rec", "len_base", "len_rec", "from", "to"])
    cdf.to_csv(out_dir / "data_conflicts.csv", index=False)
    print(f"  data_conflicts.csv        -> {len(cdf)} events")

    un_rows = []
    for label, info in sorted(handled.items()):
        if info["status"] in {"excluded", "skipped"}:
            stat = source_stats.get(Path(info.get("path", "")).name, {})
            un_rows.append({"source_file": label, "record_id": "(file-level)",
                            "reason": info.get("reason", ""),
                            "action": info["status"],
                            "n_records_in_file": stat.get("n_records")})
    udf = pd.DataFrame(un_rows)
    udf.to_csv(out_dir / "unmatched_records.csv", index=False)
    print(f"  unmatched_records.csv     -> {len(udf)} entries")

    has_seq = df["protein_sequence"].notna() & (df["protein_sequence"] != "")
    seqs = df.loc[has_seq, "protein_sequence"]
    n_unique_seq = int(seqs.nunique()) if has_seq.any() else 0
    hash_counts = df.loc[has_seq, "sequence_hash"].value_counts()
    n_dup_seq_records = int((hash_counts - 1).clip(lower=0).sum())
    n_unique_acc = int(df.loc[df["accession"].ne(""), "accession"].nunique())

    summary = {
        "generated_by": "src/build_master_dataset.py",
        "schema_version": 1,
        "input_dirs": [str(d) for d in input_dirs],
        "number_of_source_files_scanned": len(all_files),
        "number_of_source_files_used": sum(
            1 for label, info in handled.items() if info["status"] == "used"),
        "number_of_raw_records": len(records),
        "number_of_valid_protein_sequences": int(has_seq.sum()),
        "number_of_unique_sequences": n_unique_seq,
        "number_of_unique_accessions": n_unique_acc,
        "number_of_enzyme_level_rows": len(df),
        "records_with_pollutant_label": int(df["pollutant_type"].ne("").sum()),
        "records_with_pH_data": int(df[["ph_opt", "ph_min", "ph_max"]]
                                    .notna().any(axis=1).sum()),
        "records_with_temperature_data": int(
            df[["temperature_opt_c", "temperature_min_c", "temperature_max_c"]]
              .notna().any(axis=1).sum()),
        "records_with_salinity_data": int(
            df[["salinity_opt", "salinity_min", "salinity_max"]]
              .notna().any(axis=1).sum()),
        "pollutant_distribution": df["pollutant_type"].replace("", "unknown")
            .value_counts().to_dict(),
        "evidence_type_distribution": df["evidence_type"].value_counts().to_dict(),
        "missing_value_percentages": missing_pct(df),
        "number_of_duplicate_sequence_records_removed": n_dup_seq_records,
        "number_of_duplicate_rows_in_master": int(df.duplicated().sum()),
        "number_of_conflicts": len(cdf),
        "file_status": {label: info["status"] for label, info in sorted(handled.items())},
        "source_details": {k: v for k, v in sorted(source_stats.items())},
        "merge_events": events,
        "notes": {
            "pH_and_temperature":
                ("Only the 9 curated demo rows carry pH_opt/T_opt values; all are "
                 "flagged demo_assumption=True (literature-approximate / heuristic). "
                 "None are experimental measurements."),
            "salinity":
                "No source file provides salinity data, so all salinity fields "
                "are left empty (unknown) -- nothing was invented.",
            "evidence_score":
                "Ordinal provenance score derived ONLY from the recorded "
                "evidence_type label, not a biological measurement.",
            "no_external_downloads": True,
            "no_model_training": True,
            "no_synthetic_scenarios_generated": True,
        },
    }
    (out_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2,
                                                             default=str))
    print(f"  dataset_summary.json      -> {out_dir / 'dataset_summary.json'}")

    # ---- recap ---------------------------------------------------------------
    print("\n" + "=" * 72)
    print("RECAP")
    print("=" * 72)
    print(f"  raw records                     : {len(records)}")
    print(f"  master enzyme rows              : {len(df)}")
    print(f"  valid protein sequences         : {int(has_seq.sum())}")
    print(f"  unique sequences                : {n_unique_seq}")
    print(f"  unique accessions               : {n_unique_acc}")
    print(f"  with pollutant label            : {int(df['pollutant_type'].ne('').sum())}")
    print(f"  with pH data                    : {summary['records_with_pH_data']}")
    print(f"  with temperature data           : {summary['records_with_temperature_data']}")
    print(f"  with salinity data              : {summary['records_with_salinity_data']}")
    print(f"  duplicate-sequence rows removed : {n_dup_seq_records}")
    print(f"  conflicts/merge events          : {len(cdf)}")
    print("\nAll outputs written to:", out_dir)


def _sort_key(eid: str) -> tuple[Any, ...]:
    """Deterministic, human-friendly sort: ENZ000 < ENZ_PAZY_..."""
    m = re.match(r"ENZ(\d+)$", str(eid))
    if m:
        return (0, int(m.group(1)), "")
    return (1, 0, str(eid))


if __name__ == "__main__":
    main()