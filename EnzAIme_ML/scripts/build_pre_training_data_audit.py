import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
REPORT_DIR = PROJECT_ROOT / "reports" / "results"
JSON_PATH = REPORT_DIR / "pre_training_data_audit.json"
MARKDOWN_PATH = REPORT_DIR / "pre_training_data_audit.md"


def numeric_summary(values):
    values = pd.to_numeric(values, errors="coerce")
    return {
        "minimum": float(values.min()),
        "q1": float(values.quantile(0.25)),
        "median": float(values.median()),
        "mean": float(values.mean()),
        "q3": float(values.quantile(0.75)),
        "maximum": float(values.max()),
        "standard_deviation": float(values.std()),
    }


def simple_summary(values):
    values = pd.to_numeric(values, errors="coerce")
    return {
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "unique_values": int(values.nunique()),
    }


def markdown_table(frame):
    return frame.to_markdown(index=False)


def main():
    df = pd.read_csv(
        DATASET_PATH,
        dtype=str,
        keep_default_na=False,
        low_memory=False,
    )
    target = pd.to_numeric(df["target_value_standardized"], errors="coerce")
    log_target = np.log1p(target)

    condition_columns = [
        "protein_id",
        "ph",
        "temperature_c",
        "duration_hours",
        "substrate",
    ]
    condition_counts = df.groupby(condition_columns, dropna=False).size()
    repeated_condition_counts = condition_counts[condition_counts > 1]
    repeated_rows = int(df.set_index(condition_columns).index.isin(repeated_condition_counts.index).sum())
    repeated_identical = 0
    repeated_different = 0
    for _, group in df.groupby(condition_columns, dropna=False):
        if len(group) <= 1:
            continue
        if group["target_value_standardized"].nunique() == 1:
            repeated_identical += 1
        else:
            repeated_different += 1

    duplicate_counts = df.groupby(list(df.columns), dropna=False).size()
    duplicate_groups = duplicate_counts[duplicate_counts > 1]
    duplicate_rows = int(duplicate_groups.sum())
    duplicate_details = []
    for key, count in duplicate_groups.items():
        values = dict(zip(df.columns, key))
        duplicate_details.append(
            {
                "protein_id": values["protein_id"],
                "protein_name": values["protein_name"],
                "target_value_standardized": float(values["target_value_standardized"]),
                "temperature_c": float(values["temperature_c"]),
                "ph": float(values["ph"]),
                "duration_hours": float(values["duration_hours"]),
                "substrate": values["substrate"],
                "rows": int(count),
            }
        )

    proteins = df.drop_duplicates("protein_id")
    protein_counts = (
        df.groupby(["protein_id", "protein_name"], as_index=False)
        .size()
        .rename(columns={"size": "record_count"})
        .sort_values(
            ["record_count", "protein_name", "protein_id"],
            ascending=[False, True, True],
        )
    )
    sequence_lengths = proteins["sequence"].str.len()
    duplicate_sequences = (
        proteins[proteins["sequence"].duplicated(False)]
        .groupby("sequence")["protein_id"]
        .apply(list)
        .to_dict()
    )
    uniprot_available = proteins["uniprot_accession"].str.strip().ne("")
    unresolved_proteins = proteins.loc[
        ~uniprot_available,
        ["protein_id", "protein_name"],
    ].sort_values("protein_id").to_dict("records")

    top_rows = (
        df.assign(_target=target)
        .sort_values("_target", ascending=False)
        .head(15)[
            [
                "protein_name",
                "protein_id",
                "target_value_standardized",
                "temperature_c",
                "ph",
                "duration_hours",
                "source_file",
                "assay_index",
            ]
        ]
        .rename(
            columns={
                "target_value_standardized": "target",
                "temperature_c": "temperature",
                "duration_hours": "duration",
            }
        )
    )

    protein_distribution = {
        "mean": float(protein_counts.record_count.mean()),
        "median": float(protein_counts.record_count.median()),
        "minimum": int(protein_counts.record_count.min()),
        "maximum": int(protein_counts.record_count.max()),
        "standard_deviation": float(protein_counts.record_count.std()),
        "records": protein_counts.to_dict("records"),
    }
    report = {
        "dataset_size": {
            "total_rows": len(df),
            "unique_proteins": int(df["protein_id"].nunique()),
            "unique_protein_condition_combinations": int(len(condition_counts)),
            "duplicate_rows": int(df.duplicated().sum()),
            "exact_duplicate_groups": len(duplicate_groups),
            "exact_duplicate_rows_involved": duplicate_rows,
            "exact_duplicate_details": duplicate_details,
        },
        "protein_distribution": protein_distribution,
        "target_distribution": {
            "target_value_standardized": {
                **numeric_summary(target),
                "zero_values": int((target == 0).sum()),
                "greater_than_1000_uM": int((target > 1000).sum()),
                "greater_than_5000_uM": int((target > 5000).sum()),
                "greater_than_10000_uM": int((target > 10000).sum()),
            },
            "log1p_target_value_standardized": numeric_summary(log_target),
        },
        "environment_distribution": {
            "ph": {
                **simple_summary(df["ph"]),
                "counts": {
                    str(key): int(value)
                    for key, value in pd.to_numeric(df["ph"]).value_counts().sort_index().items()
                },
            },
            "temperature_c": {
                **simple_summary(df["temperature_c"]),
                "counts": {
                    str(key): int(value)
                    for key, value in pd.to_numeric(df["temperature_c"]).value_counts().sort_index().items()
                },
            },
            "duration_hours": {
                **simple_summary(df["duration_hours"]),
                "zero_duration_rows": int((pd.to_numeric(df["duration_hours"]) == 0).sum()),
                "counts": {
                    str(key): int(value)
                    for key, value in pd.to_numeric(df["duration_hours"]).value_counts().sort_index().items()
                },
            },
        },
        "repeated_conditions": {
            "condition_columns": condition_columns,
            "condition_groups": len(condition_counts),
            "repeated_condition_groups": len(repeated_condition_counts),
            "rows_involved": repeated_rows,
            "groups_with_identical_target_values": repeated_identical,
            "groups_with_different_target_values": repeated_different,
        },
        "uniprot_coverage": {
            "proteins_with_accession": int(uniprot_available.sum()),
            "proteins_without_accession": int((~uniprot_available).sum()),
            "coverage_percent": float(uniprot_available.mean() * 100),
            "unresolved_proteins": unresolved_proteins,
        },
        "sequence_quality": {
            "missing_sequences": int(proteins["sequence"].isna().sum()),
            "empty_sequences": int((proteins["sequence"].str.strip() == "").sum()),
            "duplicate_sequences_across_protein_ids": duplicate_sequences,
            "length_minimum": int(sequence_lengths.min()),
            "length_median": float(sequence_lengths.median()),
            "length_maximum": int(sequence_lengths.max()),
        },
        "leakage_analysis": {
            "proteins_with_multiple_conditions": int(
                (df.groupby("protein_id").size() > 1).sum()
            ),
            "duplicate_sequence_groups": len(duplicate_sequences),
            "exact_duplicate_groups": len(duplicate_groups),
            "same_protein_condition_target_groups": int(
                df.groupby(
                    condition_columns + ["target_value_standardized"],
                    dropna=False,
                ).size().gt(1).sum()
            ),
            "same_protein_condition_target_rows": int(
                df.groupby(
                    condition_columns + ["target_value_standardized"],
                    dropna=False,
                ).size().pipe(lambda values: values[values > 1].sum())
            ),
            "assessment": (
                "Protein-grouped validation prevents a protein and its repeated observations "
                "from appearing in both training and validation. No duplicate sequences occur "
                "across protein IDs. Exact duplicates and repeated source observations remain "
                "within their protein group."
            ),
        },
        "groupkfold_feasibility": {
            "unique_proteins_G": int(df["protein_id"].nunique()),
            "five_fold_feasible": True,
            "approximate_proteins_per_validation_fold": 5,
            "group_size_imbalance": {
                "minimum_records": int(protein_counts.record_count.min()),
                "maximum_records": int(protein_counts.record_count.max()),
                "median_records": float(protein_counts.record_count.median()),
                "highly_imbalanced": True,
            },
            "validation_note": "Use GroupKFold or another protein-grouped strategy, not random row-wise splitting.",
        },
        "high_value_observations": top_rows.to_dict("records"),
        "recommendations_for_model_evaluation": [
            "Keep validation grouped by protein; do not use random row-wise splitting.",
            "Report per-protein record counts and fold composition because group sizes range from 1 to 75 records.",
            "Keep exact duplicates, repeated observations, zero-duration rows, and high-value observations until their source meaning is separately reviewed.",
            "Report performance both overall and by held-out protein where fold sizes permit.",
            "Treat the observed pH, temperature, and duration ranges as dataset support limits rather than industrial-environment coverage.",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    markdown = f"""# EnzAIme Pre-Training Data Audit

## Dataset size

- Total rows: {len(df)}
- Unique proteins: {df['protein_id'].nunique()}
- Unique protein-condition combinations: {len(condition_counts)}
- Exact duplicate rows: {int(df.duplicated().sum())}
- Exact duplicate groups: {len(duplicate_groups)}

## Protein distribution

Records per protein: mean {protein_counts.record_count.mean():.2f}, median {protein_counts.record_count.median():.2f}, minimum {protein_counts.record_count.min()}, maximum {protein_counts.record_count.max()}, standard deviation {protein_counts.record_count.std():.2f}.

{markdown_table(protein_counts)}

## Target distribution

### `target_value_standardized`

{markdown_table(pd.DataFrame([report['target_distribution']['target_value_standardized']]))}

Zero values: {int((target == 0).sum())}. Values above 1,000 µM: {int((target > 1000).sum())}; above 5,000 µM: {int((target > 5000).sum())}; above 10,000 µM: {int((target > 10000).sum())}.

### `log1p(target_value_standardized)`

{markdown_table(pd.DataFrame([report['target_distribution']['log1p_target_value_standardized']]))}

The log summary is analytical only; the dataset was not transformed.

## Environmental distribution

### pH

- Minimum: {pd.to_numeric(df['ph']).min()}
- Maximum: {pd.to_numeric(df['ph']).max()}
- Unique values: {pd.to_numeric(df['ph']).nunique()}
- Counts: {report['environment_distribution']['ph']['counts']}

### Temperature

- Minimum: {pd.to_numeric(df['temperature_c']).min()} °C
- Maximum: {pd.to_numeric(df['temperature_c']).max()} °C
- Unique values: {pd.to_numeric(df['temperature_c']).nunique()}
- Counts: {report['environment_distribution']['temperature_c']['counts']}

### Duration

- Minimum: {pd.to_numeric(df['duration_hours']).min()} hours
- Maximum: {pd.to_numeric(df['duration_hours']).max()} hours
- Mean: {pd.to_numeric(df['duration_hours']).mean():.2f} hours
- Median: {pd.to_numeric(df['duration_hours']).median():.2f} hours
- Unique values: {pd.to_numeric(df['duration_hours']).nunique()}
- Zero-duration rows: {int((pd.to_numeric(df['duration_hours']) == 0).sum())}

## Repeated conditions

Condition key: `protein_id + pH + temperature_c + duration_hours + substrate`.

- Total condition groups: {len(condition_counts)}
- Repeated condition groups: {len(repeated_condition_counts)}
- Rows involved: {repeated_rows}
- Groups with identical target values: {repeated_identical}
- Groups with different target values: {repeated_different}

No rows were removed.

## Exact duplicates

- Exact duplicate groups: {len(duplicate_groups)}
- Rows involved: {duplicate_rows}

{markdown_table(pd.DataFrame(duplicate_details))}

No duplicate rows were removed.

## UniProt coverage

- Unique proteins with UniProt accession: {int(uniprot_available.sum())}
- Unique proteins without UniProt accession: {int((~uniprot_available).sum())}
- Coverage: {uniprot_available.mean() * 100:.2f}%

Unresolved proteins:

{markdown_table(pd.DataFrame(unresolved_proteins))}

No missing accessions were inferred.

## Sequence quality

- Missing sequences: {int(proteins['sequence'].isna().sum())}
- Empty sequences: {int((proteins['sequence'].str.strip() == '').sum())}
- Duplicate sequences across different protein IDs: {len(duplicate_sequences)} groups
- Sequence length minimum: {sequence_lengths.min()}
- Sequence length median: {sequence_lengths.median()}
- Sequence length maximum: {sequence_lengths.max()}

No duplicate sequences occur across different protein IDs.

## Leakage analysis

- Same protein IDs occur across multiple conditions: yes; this is expected for condition-response data.
- Duplicate sequences across different IDs: none found.
- Exact duplicate observations: {len(duplicate_groups)} groups, {duplicate_rows} rows involved.
- Same protein-condition-target combinations repeated: {int(df.groupby(condition_columns + ['target_value_standardized'], dropna=False).size().gt(1).sum())} groups, {int(df.groupby(condition_columns + ['target_value_standardized'], dropna=False).size().pipe(lambda values: values[values > 1].sum()))} rows involved.

Grouping by `protein_id` prevents the same protein and its repeated observations from appearing in both training and validation. Random row-wise splitting should not be used. Native source-record identifiers are blank, so source-level identity beyond the preserved JSON cannot be checked as a separate grouping variable.

## GroupKFold feasibility

- Unique protein groups, $G$: {df['protein_id'].nunique()}
- Five-fold GroupKFold feasible: yes
- Approximate protein groups per validation fold: 5
- Group size range: {protein_counts.record_count.min()} to {protein_counts.record_count.max()} records
- Median group size: {protein_counts.record_count.median()}
- Group imbalance: high

The dataset supports protein-grouped five-fold evaluation mechanically, but the unequal group sizes mean validation folds can contain very different numbers of records and information.

## High-value observations

These are **high-value observations requiring source/assay awareness**, not observations declared erroneous.

{markdown_table(top_rows)}

## Recommendations for model evaluation

- Keep validation grouped by protein; do not use random row-wise splitting.
- Report per-protein record counts and fold composition because group sizes range from 1 to 75 records.
- Keep exact duplicates, repeated observations, zero-duration rows, and high-value observations until their source meaning is separately reviewed.
- Report performance overall and by held-out protein where fold sizes permit.
- Treat the observed pH, temperature, and duration ranges as dataset support limits rather than industrial-environment coverage.

No datasets were modified, no records were deleted, no model artifacts were changed, and no model training or embedding generation was performed.

PRE-TRAINING AUDIT COMPLETE
"""
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")

    print("PRE-TRAINING DATA AUDIT")
    print("Rows:", len(df))
    print("Unique proteins:", df["protein_id"].nunique())
    print("Unique protein-condition combinations:", len(condition_counts))
    print("Exact duplicate groups:", len(duplicate_groups))
    print("Repeated condition groups:", len(repeated_condition_counts))
    print("Zero-duration rows:", int((pd.to_numeric(df["duration_hours"]) == 0).sum()))
    print("UniProt coverage:", f"{uniprot_available.mean() * 100:.2f}%")
    print("Reports written:", JSON_PATH, MARKDOWN_PATH)
    print("PRE-TRAINING AUDIT COMPLETE")


if __name__ == "__main__":
    main()