import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"
CSV_PATH = RESULTS_DIR / "repeated_condition_variability.csv"
JSON_PATH = RESULTS_DIR / "repeated_condition_variability.json"
MARKDOWN_PATH = RESULTS_DIR / "repeated_condition_variability.md"

CONDITION_COLUMNS = [
    "protein_id",
    "temperature_c",
    "ph",
    "duration_hours",
]
SOURCE_FIELDS = [
    "assay_index",
    "literature_doi",
    "source_file",
    "analyte",
    "metric_type",
    "target_unit",
    "replicate_n",
]
SOURCE_RECORD_FIELDS = [
    "material",
    "detection_methods",
    "evidence",
]
CONDITION_METADATA_FIELDS = [
    "additional_conditions",
    "agitation_mode",
    "agitation_speed_rpm",
    "buffer",
    "enzyme_amount_unit",
    "enzyme_amount_value",
    "enzyme_concentration_unit",
    "enzyme_concentration_value",
    "enzyme_features",
    "enzyme_preparation",
    "reaction_volume_unit",
    "reaction_volume_value",
    "substrate_amount_unit",
    "substrate_amount_value",
    "substrate_concentration_unit",
    "substrate_concentration_value",
    "temperature_reported",
]


def parse_json(value, default):
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def canonical(value):
    if value is None or value == "":
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def unique_values(values):
    result = []
    for value in values:
        value = canonical(value)
        if value and value not in result:
            result.append(value)
    return sorted(result)


def extract_source_records(row):
    records = parse_json(row["original_record_json"], [])
    return records if isinstance(records, list) else []


def metadata_for_group(group):
    metadata = {field: [] for field in SOURCE_FIELDS + SOURCE_RECORD_FIELDS}
    metadata.update({field: [] for field in CONDITION_METADATA_FIELDS})

    for _, row in group.iterrows():
        for field in SOURCE_FIELDS:
            metadata[field].append(row.get(field, ""))
        records = extract_source_records(row)
        for record in records:
            for field in SOURCE_RECORD_FIELDS:
                metadata[field].append(record.get(field, ""))
            conditions = parse_json(record.get("conditions", ""), {})
            if isinstance(conditions, dict):
                for field in CONDITION_METADATA_FIELDS:
                    metadata[field].append(conditions.get(field, ""))

    normalized = {
        field: unique_values(values)
        for field, values in metadata.items()
    }
    difference_fields = [
        field for field, values in normalized.items() if len(values) > 1
    ]
    unavailable_fields = [
        field for field, values in normalized.items() if not values
    ]
    return {
        "values": normalized,
        "difference_fields": difference_fields,
        "unavailable_fields": unavailable_fields,
    }


def numeric_stats(values):
    values = pd.to_numeric(values, errors="coerce")
    mean = float(values.mean())
    std = float(values.std(ddof=1))
    return {
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "mean": mean,
        "median": float(values.median()),
        "standard_deviation": std,
        "coefficient_of_variation": None if mean <= 0 else std / mean,
        "range": float(values.max() - values.min()),
    }


def summarize_group(key, group):
    target = pd.to_numeric(group["target_value_standardized"], errors="coerce")
    log_target = np.log1p(target)
    metadata = metadata_for_group(group)
    target_stats = numeric_stats(target)
    log_stats = numeric_stats(log_target)
    target_values = [float(value) for value in sorted(target.tolist())]
    return {
        "protein_id": key[0],
        "protein_name": group["protein_name"].iloc[0],
        "temperature_c": float(key[1]),
        "ph": float(key[2]),
        "duration_hours": float(key[3]),
        "record_count": len(group),
        "target_min_uM": target_stats["minimum"],
        "target_max_uM": target_stats["maximum"],
        "target_mean_uM": target_stats["mean"],
        "target_median_uM": target_stats["median"],
        "target_std_uM": target_stats["standard_deviation"],
        "target_cv": target_stats["coefficient_of_variation"],
        "target_range_uM": target_stats["range"],
        "log1p_min": log_stats["minimum"],
        "log1p_max": log_stats["maximum"],
        "log1p_median": log_stats["median"],
        "log1p_mean": log_stats["mean"],
        "log1p_std": log_stats["standard_deviation"],
        "log1p_range": log_stats["range"],
        "target_values": "; ".join(str(value) for value in target_values),
        "source_metadata_summary": json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        ),
        "metadata_difference_fields": "; ".join(metadata["difference_fields"]),
        "metadata_difference_count": len(metadata["difference_fields"]),
        "metadata_explanation_status": (
            "metadata differences recorded"
            if metadata["difference_fields"]
            else "no obvious recorded metadata explanation"
        ),
        "target_values_identical": target.nunique() == 1,
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
    grouped = df.groupby(CONDITION_COLUMNS, dropna=False, sort=False)
    repeated_groups = [(key, group) for key, group in grouped if len(group) > 1]
    summaries = [summarize_group(key, group) for key, group in repeated_groups]
    variability = pd.DataFrame(summaries).sort_values(
        ["target_range_uM", "protein_id"],
        ascending=[False, True],
    )

    identical = variability[variability["target_values_identical"]]
    different = variability[~variability["target_values_identical"]]
    metadata_difference_groups = variability[
        variability["metadata_difference_count"] > 0
    ]
    unexplained_groups = different[
        different["metadata_difference_count"] == 0
    ]
    high_variation = different.sort_values(
        ["target_range_uM", "target_cv"],
        ascending=[False, False],
    ).head(10)

    summary_statistics = {
        "record_count_distribution": {
            "minimum": float(variability["record_count"].min()),
            "maximum": float(variability["record_count"].max()),
            "mean": float(variability["record_count"].mean()),
            "median": float(variability["record_count"].median()),
        },
        "target_range_distribution_uM": {
            "minimum": float(variability["target_range_uM"].min()),
            "maximum": float(variability["target_range_uM"].max()),
            "mean": float(variability["target_range_uM"].mean()),
            "median": float(variability["target_range_uM"].median()),
        },
        "target_cv_distribution": {
            "minimum": float(variability["target_cv"].min()),
            "maximum": float(variability["target_cv"].max()),
            "mean": float(variability["target_cv"].mean()),
            "median": float(variability["target_cv"].median()),
        },
    }
    report = {
        "total_confirmed_records": len(df),
        "total_proteins": int(df["protein_id"].nunique()),
        "total_repeated_condition_groups": len(variability),
        "repeated_groups_with_identical_targets": len(identical),
        "repeated_groups_with_different_targets": len(different),
        "groups_with_metadata_differences": len(metadata_difference_groups),
        "groups_without_obvious_recorded_explanation": len(unexplained_groups),
        "summary_statistics": summary_statistics,
        "high_variation_group_count_reported": len(high_variation),
        "high_variation_groups": high_variation.to_dict("records"),
        "analysis_columns": CONDITION_COLUMNS,
        "metadata_fields_inspected": SOURCE_FIELDS
        + SOURCE_RECORD_FIELDS
        + CONDITION_METADATA_FIELDS,
        "interpretation": (
            "Different target values are reported descriptively. Metadata differences are "
            "evidence of recorded experimental differences, not proof of causation. Groups "
            "without such differences remain unresolved and are not assumed to be noise or replicates."
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    variability.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    JSON_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    important_columns = [
        "protein_id",
        "protein_name",
        "record_count",
        "target_min_uM",
        "target_max_uM",
        "target_range_uM",
        "target_cv",
        "metadata_difference_fields",
        "metadata_explanation_status",
    ]
    markdown = f"""# Repeated Condition Target Variability Analysis

## Objective

Investigate target variability among repeated protein-condition groups in the confirmed PET/TPA dataset without deleting records, treating values as noise, or assuming that repeated observations are biological replicates.

## Methodology

- Source: `data/processed/tpa_pet_ml_confirmed.csv`
- Condition key: `protein_id + temperature_c + ph + duration_hours`
- Confirmed records: {len(df)}
- Proteins: {df['protein_id'].nunique()}
- Repeated groups analyzed: {len(variability)}
- Source provenance: preserved `original_record_json` was parsed where available.
- Metadata inspected: assay index, DOI, source file, material, detection methods, evidence, analyte, metric type, target unit, replicate count, and other recorded condition metadata.

## Dataset scope

The confirmed dataset contains 221 records from 25 proteins. There are 123 unique protein-condition groups in total, of which {len(variability)} contain multiple observations. This analysis reports all {len(variability)} repeated groups, including the {len(identical)} group with identical targets and the {len(different)} groups with different targets.

## Findings

- Repeated groups with identical target values: {len(identical)}
- Repeated groups with different target values: {len(different)}
- Groups with recorded metadata differences: {len(metadata_difference_groups)}
- Groups without an obvious recorded metadata explanation: {len(unexplained_groups)}
- Largest target range: {different['target_range_uM'].max():.3f} µM
- Largest coefficient of variation: {different['target_cv'].max():.3f}

The complete group-level analysis is in `repeated_condition_variability.csv`. Its `source_metadata_summary` field preserves the available source metadata values as JSON for each group.

### Highest target-range groups

{markdown_table(high_variation[important_columns])}

## Possible explanations

Recorded metadata differences may indicate that repeated condition keys combine observations from different experimental contexts. The inspected fields include:

- Different assay indices or literature records.
- Different material descriptions or pretreatment details.
- Different detection methods.
- Different analytes, metrics, or original units.
- Different replicate counts.
- Different buffers, enzyme preparations, enzyme concentrations, substrate amounts, agitation, or other nested condition metadata.

A metadata difference does not prove why the target changed. It only shows that the reduced protein-condition key does not capture all recorded experimental context.

## Unresolved issues

There are {len(unexplained_groups)} different-target groups without an obvious recorded metadata difference in the preserved fields. These values cannot be safely labeled as biological noise, technical replicates, or errors from the available data. Some source-record identifiers are unavailable, so source-level identity may remain unresolved even when the nested source JSON is present.

No observations were removed.

## Implications for ML modeling

Repeated condition groups with different targets mean that a single protein-condition key can map to multiple target values. This can represent distinct assays, material contexts, measurement choices, or unresolved source variation. Protein-grouped validation prevents the same protein from crossing folds, but it does not make the target values interchangeable within a protein.

The target variability should therefore be considered when interpreting fold metrics. The current analysis does not establish that any group is invalid and does not select a modeling treatment.

## Recommendation for next data-cleaning/modeling step

Preserve the current records and add explicit source-record and measurement-level identifiers before retraining. Review groups with large ranges first, using the recorded assay, material, method, analyte, and citation fields. Decide whether distinct assay contexts should remain separate, be modeled with additional features, or be excluded only after source review. Do not collapse repeated groups or remove observations solely because their target values differ.

## Summary table

{markdown_table(variability[important_columns])}

No model was trained and no dataset, embedding, backend, frontend, or model artifact was modified.

REPEATED CONDITION ANALYSIS COMPLETE
"""
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")

    print("confirmed records:", len(df))
    print("repeated-condition groups:", len(variability))
    print("identical-target groups:", len(identical))
    print("different-target groups:", len(different))
    print("groups with metadata differences:", len(metadata_difference_groups))
    print("groups with no obvious explanation:", len(unexplained_groups))
    print("REPEATED CONDITION ANALYSIS COMPLETE")


if __name__ == "__main__":
    main()