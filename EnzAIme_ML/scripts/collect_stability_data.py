"""Download sequence-linked wild-type Tm evidence using FireProtDB's documented API.

No TPA labels, mutant dTm, or inferred measurements are substituted for Tm.
Caches every response and saves exclusions. Run locally or on Kaggle.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = "https://loschmidt.chemi.muni.cz/fireprotdb/"
AA = set("ACDEFGHIKLMNPQRSTVWY")


def fetch_json(url, path):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            with urlopen(url, timeout=45) as response:
                result = json.load(response)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".partial")
            temporary.write_text(json.dumps(result), encoding="utf-8")
            temporary.replace(path)
            return result
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/stability")
    parser.add_argument("--max-pages", type=int, default=40)
    args = parser.parse_args()
    out = Path(args.output)
    cache = out / "raw"
    query = {"tree": {"operator": "AND", "children": [
        {"variable": "TM", "operator": "IS_EMPTY", "value": False},
        {"variable": "MUTATED_POSITION", "operator": "IS_EMPTY", "value": True}]}}
    entries = []
    complete = False
    for page in range(args.max_pages):
        url = BASE + "api/search?" + urlencode({"query": json.dumps(query), "limit": 500, "offset": page*500, "format": "json"})
        batch = fetch_json(url, cache / f"wt_tm_page_{page}.json")
        entries.extend(batch)
        print(f"Fetched page {page}: {len(batch)} entries", flush=True)
        if len(batch) < 500:
            complete = True
            break
    sequences = {int(e["sequence"]["id"]): e["sequence"] for e in entries if e.get("sequence")}
    errors = []

    def get_sequence(sid):
        try:
            result = fetch_json(BASE+f"api/sequences/{sid}/sequence", cache / f"sequence_{sid}.json")
            return sid, result, None
        except (OSError, ValueError) as error:
            return sid, None, str(error)

    mapped = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for sid, sequence, error in pool.map(get_sequence, sorted(sequences)):
            if error:
                errors.append({"sequence_id": sid, "reason": error})
            else:
                mapped[sid] = sequence
    records, seen = [], set()
    for entry in entries:
        record = entry.get("sequence")
        if not record:
            continue
        sid, exp = record["id"], record["experiment"]
        sequence = mapped.get(sid)
        if not isinstance(sequence, str) or not sequence or set(sequence)-AA or len(sequence) > 1022 or len(sequence) != record["length"]:
            errors.append({"sequence_id": sid, "reason": "Missing, nonstandard, too-long or length-mismatched sequence"})
            continue
        annotation = {r["type"]: r.get("numValue") if r.get("numValue") is not None else r.get("strValue") for r in exp["annotations"]}
        proteins = [p["protein"] for p in record["proteinLinks"]]
        accessions = [r["accession"] for p in proteins for r in p["references"] if r["type"] == "UNIPROTKB"]
        for measure in exp["measurements"]:
            if measure["type"] != "TM" or measure["id"] in seen:
                continue
            value = measure.get("numValue")
            if not isinstance(value, (int, float)) or not 0 < value < 150:
                errors.append({"measurement_id": measure["id"], "reason": "Tm outside accepted Celsius range (0,150)"})
                continue
            seen.add(measure["id"])
            records.append({"record_id": str(measure["id"]), "experiment_id": exp["id"],
                "protein_id": f"fireprot_{sid}", "sequence_id": sid, "sequence": sequence,
                "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                "protein_name": "; ".join(p.get("name") or f"Protein {p['id']}" for p in proteins),
                "family_group": ";".join(sorted(str(p["id"]) for p in proteins)) or f"sequence_{sid}",
                "uniprot_accessions": accessions, "target_kind": "Tm", "target_unit": "degC", "tm_c": value,
                "ph": annotation.get("PH"), "method": annotation.get("METHOD"), "measure": annotation.get("MEASURE"),
                "publication_doi": (exp.get("publication") or {}).get("doi"), "source_dataset": exp["dataset"],
                "source_url": BASE+f"api/sequences/{sid}", "sequence_mapping_verified": True})
    out.mkdir(parents=True, exist_ok=True)
    (out / "records.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (out / "exclusions.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    report = {"fetched_at": datetime.now(timezone.utc).isoformat(), "source": BASE,
        "search_exhausted": complete, "records": len(records), "sequences": len({r["sequence_sha256"] for r in records}),
        "protein_groups": len({r["family_group"] for r in records}), "exclusions": len(errors),
        "scope": "Sequence entries with measured Tm; mutants excluded. Protein groups are database entities, not homology clusters.",
        "unit_note": "FireProtDB thermal measurements interpreted as degrees C; source papers remain the assay authority."}
    (out / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
