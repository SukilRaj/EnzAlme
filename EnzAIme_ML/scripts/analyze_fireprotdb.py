import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIREPROTDB_PATH = PROJECT_ROOT / "fireprotdb_20251015-164116.csv"
PROJECT_DATASET_PATH = PROJECT_ROOT / "data" / "tpa_pet_ml_dataset.csv"
REPORT_PATH = PROJECT_ROOT / "reports" / "results" / "fireprotdb_analysis.json"
MATCHED_MUTATIONS_PATH = PROJECT_ROOT / "data" / "fireprotdb_matched_mutations.csv"
CHUNK_SIZE = 100_000
TOP_VALUE_COUNT = 50

REQUIRED_FIREPROTDB_COLUMNS = {
    "SUBSTITUTION",
    "DDG",
    "STABILIZING",
    "UNIPROTKB",
    "PH",
    "EXP_TEMPERATURE",
    "SOURCE_DATASET",
}


def is_non_empty(series):
    return series.fillna("").astype(str).str.strip().ne("")


def display_value(value):
    value = str(value).strip()
    return value if value else "(empty)"


def top_values(counter):
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(TOP_VALUE_COUNT)
    ]


def split_accessions(value):
    return {
        accession.strip().upper()
        for accession in re.split(r"[;,|/\s]+", str(value))
        if accession.strip()
    }


def load_project_proteins():
    header = pd.read_csv(PROJECT_DATASET_PATH, nrows=0).columns.tolist()
    required_columns = ["protein_id", "protein_name"]
    has_accessions = "uniprot_accessions" in header
    if has_accessions:
        required_columns.append("uniprot_accessions")

    project_df = pd.read_csv(
        PROJECT_DATASET_PATH,
        usecols=required_columns,
        dtype=str,
        keep_default_na=False,
    )
    project_df = project_df.drop_duplicates(subset=["protein_id"])

    proteins = []
    accession_to_proteins = defaultdict(list)
    for row in project_df.to_dict("records"):
        accession = row.get("uniprot_accessions", "").strip().upper()
        protein = {
            "protein_id": row["protein_id"].strip(),
            "protein_name": row["protein_name"].strip(),
            "uniprot_accession": accession or None,
        }
        proteins.append(protein)
        if accession:
            for value in split_accessions(accession):
                accession_to_proteins[value].append(protein)

    return proteins, accession_to_proteins, has_accessions


def analyze():
    project_proteins, accession_to_proteins, has_project_accessions = (
        load_project_proteins()
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MATCHED_MUTATIONS_PATH.exists():
        MATCHED_MUTATIONS_PATH.unlink()

    total_rows = 0
    substitution_rows = 0
    ddg_rows = 0
    substitution_ddg_rows = 0
    substitution_stabilizing_rows = 0
    stabilizing_values = Counter()
    substitution_values = Counter()
    uniprot_rows = 0
    ph_rows = 0
    temperature_rows = 0
    source_datasets = Counter()
    matching_rows = 0
    matching_mutation_rows = 0
    matched_proteins = {}
    matched_mutations_written = False

    try:
        reader = pd.read_csv(
            FIREPROTDB_PATH,
            chunksize=CHUNK_SIZE,
            dtype=str,
            keep_default_na=False,
            low_memory=True,
        )
        first_chunk = True
        for chunk_number, chunk in enumerate(reader, start=1):
            if first_chunk:
                missing_columns = REQUIRED_FIREPROTDB_COLUMNS - set(chunk.columns)
                if missing_columns:
                    raise ValueError(
                        "FireProtDB is missing required columns: "
                        + ", ".join(sorted(missing_columns))
                    )
                first_chunk = False

            total_rows += len(chunk)
            substitution_mask = is_non_empty(chunk["SUBSTITUTION"])
            ddg_mask = is_non_empty(chunk["DDG"])
            stabilizing_mask = is_non_empty(chunk["STABILIZING"])

            substitution_count = int(substitution_mask.sum())
            substitution_rows += substitution_count
            ddg_rows += int(ddg_mask.sum())
            substitution_ddg_rows += int((substitution_mask & ddg_mask).sum())
            substitution_stabilizing_rows += int(
                (substitution_mask & stabilizing_mask).sum()
            )

            stabilizing_values.update(
                chunk.loc[substitution_mask, "STABILIZING"].map(display_value)
            )
            substitution_values.update(
                chunk.loc[substitution_mask, "SUBSTITUTION"].map(display_value)
            )
            uniprot_rows += int(
                (substitution_mask & is_non_empty(chunk["UNIPROTKB"])).sum()
            )
            ph_rows += int((substitution_mask & is_non_empty(chunk["PH"])).sum())
            temperature_rows += int(
                (substitution_mask & is_non_empty(chunk["EXP_TEMPERATURE"])).sum()
            )
            source_datasets.update(
                chunk.loc[substitution_mask, "SOURCE_DATASET"].map(display_value)
            )

            if has_project_accessions:
                row_accessions = chunk["UNIPROTKB"].map(split_accessions)
                matching_mask = row_accessions.map(
                    lambda values: bool(values & set(accession_to_proteins))
                )
                matching_chunk = chunk.loc[matching_mask]
                matching_rows += len(matching_chunk)
                matching_mutation_mask = matching_mask & substitution_mask
                matching_mutation_rows += int(matching_mutation_mask.sum())

                for row_index in chunk.index[matching_mask]:
                    row = chunk.loc[row_index]
                    row_matches = row_accessions.loc[row_index] & set(
                        accession_to_proteins
                    )
                    for accession in row_matches:
                        for protein in accession_to_proteins[accession]:
                            summary = matched_proteins.setdefault(
                                protein["protein_id"],
                                {
                                    **protein,
                                    "fireprotdb_rows": 0,
                                    "substitution_rows": 0,
                                    "substitution_ddg_rows": 0,
                                },
                            )
                            summary["fireprotdb_rows"] += 1
                            if substitution_mask.loc[row_index]:
                                summary["substitution_rows"] += 1
                                if ddg_mask.loc[row_index]:
                                    summary["substitution_ddg_rows"] += 1

                matching_mutations = chunk.loc[matching_mutation_mask]
                if not matching_mutations.empty:
                    matching_mutations.to_csv(
                        MATCHED_MUTATIONS_PATH,
                        mode="a",
                        header=not matched_mutations_written,
                        index=False,
                    )
                    matched_mutations_written = True

            if chunk_number % 10 == 0:
                print(f"Processed {total_rows:,} FireProtDB rows...")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"FireProtDB file not found: {FIREPROTDB_PATH}") from error

    mutation_denominator = substitution_rows or 1
    report = {
        "source_file": FIREPROTDB_PATH.name,
        "chunk_size": CHUNK_SIZE,
        "project_dataset": PROJECT_DATASET_PATH.name,
        "project_protein_count": len(project_proteins),
        "fireprotdb_statistics": {
            "total_rows": total_rows,
            "substitution_rows": substitution_rows,
            "ddg_rows": ddg_rows,
            "substitution_and_ddg_rows": substitution_ddg_rows,
            "substitution_and_stabilizing_rows": substitution_stabilizing_rows,
            "stabilizing_for_substitution_rows": {
                "unique_value_count": len(stabilizing_values),
                "most_common": top_values(stabilizing_values),
            },
            "substitution_values": {
                "unique_value_count": len(substitution_values),
                "most_common": top_values(substitution_values),
            },
            "mutation_row_percentages": {
                "with_uniprotkb": 100 * uniprot_rows / mutation_denominator,
                "with_ph": 100 * ph_rows / mutation_denominator,
                "with_exp_temperature": 100 * temperature_rows / mutation_denominator,
            },
            "common_source_dataset_values": top_values(source_datasets),
        },
        "project_proteins": project_proteins,
        "project_accession_comparison": {
            "status": (
                "complete"
                if has_project_accessions
                else "unavailable_missing_uniprot_accessions_column"
            ),
            "matching_note": (
                None
                if has_project_accessions
                else "The project dataset has no uniprot_accessions column; no accessions or matches were inferred."
            ),
            "matching_fireprotdb_rows": matching_rows,
            "matching_mutation_rows": matching_mutation_rows,
            "unique_matching_proteins": len(matched_proteins),
            "matched_proteins": list(matched_proteins.values()),
        },
        "scientific_note": (
            "DDG and stabilizing values describe mutation stability or thermodynamic evidence. "
            "They are not direct PET activity measurements and are not used to alter activity predictions."
        ),
    }

    with REPORT_PATH.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)
        report_file.write("\n")

    print(f"Completed analysis of {total_rows:,} FireProtDB rows.")
    print(f"Wrote summary: {REPORT_PATH}")
    if matched_mutations_written:
        print(f"Wrote matched mutations: {MATCHED_MUTATIONS_PATH}")
    elif has_project_accessions:
        print("No matched mutation rows; no filtered mutation file was created.")
    else:
        print("No filtered mutation file was created because project accessions are unavailable.")
    return report


if __name__ == "__main__":
    try:
        analyze()
    except Exception as error:
        print(f"FireProtDB analysis failed: {error}", file=sys.stderr)
        raise SystemExit(1)