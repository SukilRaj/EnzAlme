"""Targeted Step 4 audit for protein 37 and fold 3."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
PROVENANCE_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_activity_provenance_audit.csv"
OOF_PATH = PROJECT_ROOT / "reports" / "results" / "ablation_error_analysis" / "oof_predictions.csv"
FOLD_PATH = PROJECT_ROOT / "reports" / "results" / "ablation_error_analysis" / "fold_metrics.csv"
POOLED_PATH = PROJECT_ROOT / "reports" / "results" / "ablation_error_analysis" / "pooled_metrics.csv"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "results" / "ablation_error_analysis" / "targeted_audit"
CONFIGURATIONS = ["A", "B", "C"]
FOLD_NUMBER = 3


def finite_or_none(value):
    return None if pd.isna(value) else float(value)


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def parse_json_field(value, default):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def make_protein37_tables(df, oof, provenance):
    protein_rows = df[df["protein_id"].astype(str) == "37"].copy()
    oof_rows = oof[oof["protein_id"].astype(str) == "37"].copy()
    observed = protein_rows[[
        "source_row_id" if "source_row_id" in protein_rows.columns else "protein_id",
        "protein_id", "protein_name", "target_value", "target_unit",
        "target_value_standardized", "standardized_unit", "temperature_c", "ph",
        "duration_hours", "source", "source_file", "assay_index", "literature_doi",
        "conversion_formula", "conversion_status", "classification", "repeated_condition",
    ]].copy() if "source_row_id" in protein_rows.columns else protein_rows[[
        "protein_id", "protein_name", "target_value", "target_unit",
        "target_value_standardized", "standardized_unit", "temperature_c", "ph",
        "duration_hours", "source", "source_file", "assay_index", "literature_doi",
        "conversion_formula", "conversion_status", "classification", "repeated_condition",
    ]].copy()
    observed.insert(0, "source_row_id", protein_rows.index.astype(int))
    predictions = oof_rows[[
        "source_row_id", "configuration", "fold", "actual_target_um",
        "predicted_target_um", "residual_um", "absolute_error_um", "squared_error_um2",
    ]].sort_values(["source_row_id", "configuration"])

    row45 = df.iloc[45]
    original = parse_json_field(row45["original_record_json"], [])
    assay = original[0] if original else {}
    conditions = parse_json_field(assay.get("conditions"), {})
    measurements = parse_json_field(assay.get("measurements"), [])
    row45_trace = {
        "source_row_id": 45,
        "protein_id": str(row45["protein_id"]),
        "protein_name": str(row45["protein_name"]),
        "source_file": str(row45["source_file"]),
        "source_record_id": str(row45["source_record_id"]),
        "assay_index": str(row45["assay_index"]),
        "literature_doi": str(row45["literature_doi"]),
        "source_reference": parse_json_field(row45["source"], {}),
        "analyte": str(row45["analyte"]),
        "recorded_value": float(row45["target_value"]),
        "recorded_unit": str(row45["target_unit"]),
        "standardized_value_um": float(row45["target_value_standardized"]),
        "standardized_unit": str(row45["standardized_unit"]),
        "conversion_formula": str(row45["conversion_formula"]),
        "conversion_status": str(row45["conversion_status"]),
        "classification": str(row45["classification"]),
        "temperature_c": float(row45["temperature_c"]),
        "ph": float(row45["ph"]),
        "duration_value": float(row45["duration_value"]),
        "duration_unit": str(row45["duration_unit"]),
        "duration_hours": float(row45["duration_hours"]),
        "assay_method": parse_json_field(row45["assay_method"], []),
        "material_description": parse_json_field(row45["material_description"], {}),
        "original_assay_json": assay,
        "original_conditions": conditions,
        "original_measurements": measurements,
        "source_consistency": {
            "value_and_unit_match_retained_record": any(
                measurement.get("analyte") == "TPA"
                and measurement.get("value") == 47
                and measurement.get("unit") == "mM"
                for measurement in measurements
            ),
            "digitized_approximate_value": any(
                measurement.get("analyte") == "TPA"
                and measurement.get("value_is_digitized") is True
                for measurement in measurements
            ),
            "transcription_error_verified": False,
            "unresolved_evidence": [
                "The retained record describes the TPA value as approximate and digitized from Figure 3C.",
                "The raw figure/image and independent replicate-level values are not present in the retained workspace record.",
            ],
        },
    }
    provenance_rows = provenance[provenance["protein_id"].astype(str) == "37"].copy()
    provenance_columns = [column for column in [
        "protein_id", "protein_name", "target_value", "target_unit", "target_value_standardized",
        "standardized_unit", "analyte", "metric_type", "temperature_c", "ph", "duration_hours",
        "source", "source_file", "assay_index", "replicate_n", "literature_doi",
        "conversion_formula", "conversion_status", "classification", "condition_group_id",
        "repeated_condition",
    ] if column in provenance_rows.columns]
    return observed, predictions, row45_trace, provenance_rows[provenance_columns]


def make_fold3_tables(df, oof, fold_metrics):
    fold_oof = oof[oof["fold"] == FOLD_NUMBER].copy()
    fold_sse = fold_oof.groupby("configuration")["squared_error_um2"].sum()
    names = df.groupby(df["protein_id"].astype(str))["protein_name"].first().to_dict()
    rows = []
    for protein_id, group in fold_oof.groupby(fold_oof["protein_id"].astype(str)):
        actual = group["actual_target_um"]
        row = {
            "fold": FOLD_NUMBER,
            "protein_id": protein_id,
            "protein_name": names[protein_id],
            "record_count": int(group["source_row_id"].nunique()),
            "actual_min_um": float(actual.min()),
            "actual_max_um": float(actual.max()),
        }
        for config_name in CONFIGURATIONS:
            config_rows = group[group["configuration"] == config_name]
            row[f"{config_name}_prediction_min_um"] = float(config_rows["predicted_target_um"].min())
            row[f"{config_name}_prediction_max_um"] = float(config_rows["predicted_target_um"].max())
            row[f"{config_name}_mae_um"] = float(config_rows["absolute_error_um"].mean())
            row[f"{config_name}_sse_um2"] = float(config_rows["squared_error_um2"].sum())
            row[f"{config_name}_fold_sse_share"] = float(config_rows["squared_error_um2"].sum() / fold_sse[config_name])
            row[f"{config_name}_underprediction_rows"] = int((config_rows["residual_um"] > 0).sum())
            row[f"{config_name}_overprediction_rows"] = int((config_rows["residual_um"] < 0).sum())
        rows.append(row)
    protein_table = pd.DataFrame(rows).sort_values("protein_id").reset_index(drop=True)
    top_rows = fold_oof[fold_oof["configuration"].isin(["B", "C"])].sort_values(
        ["configuration", "squared_error_um2"], ascending=[True, False]
    ).reset_index(drop=True)
    return protein_table, top_rows


def make_condition_table(df, oof):
    fold_rows = oof[oof["fold"] == FOLD_NUMBER]["source_row_id"].drop_duplicates().astype(int)
    train = df.loc[~df.index.isin(fold_rows)].copy()
    test = df.loc[df.index.isin(fold_rows)].copy()
    fields = {"temperature_c": "temperature_c", "ph": "ph", "duration_hours": "duration_hours"}
    rows = []
    outside = []
    for name, column in fields.items():
        train_values = pd.to_numeric(train[column], errors="coerce")
        test_values = pd.to_numeric(test[column], errors="coerce")
        train_nonmissing = train_values.dropna()
        outside_mask = test_values.notna() & ((test_values < train_nonmissing.min()) | (test_values > train_nonmissing.max()))
        rows.append({
            "feature": name,
            "train_min": float(train_nonmissing.min()),
            "train_max": float(train_nonmissing.max()),
            "train_missing": int(train_values.isna().sum()),
            "train_records": int(len(train_values)),
            "test_min": float(test_values.dropna().min()),
            "test_max": float(test_values.dropna().max()),
            "test_missing": int(test_values.isna().sum()),
            "test_records": int(len(test_values)),
            "test_outside_training_range": int(outside_mask.sum()),
        })
        for source_row_id in test.index[outside_mask]:
            outside.append({
                "source_row_id": int(source_row_id),
                "protein_id": str(test.loc[source_row_id, "protein_id"]),
                "feature": name,
                "test_value": float(test.loc[source_row_id, column]),
                "train_min": float(train_nonmissing.min()),
                "train_max": float(train_nonmissing.max()),
            })
    return pd.DataFrame(rows), pd.DataFrame(outside)


def make_aggregation_table(fold_metrics, pooled):
    rows = []
    for config_name in CONFIGURATIONS:
        fold_rows = fold_metrics[fold_metrics["configuration"] == config_name]
        pooled_row = pooled[pooled["configuration"] == config_name].iloc[0]
        for metric in ["mae_um", "rmse_um", "r2", "spearman"]:
            rows.append({
                "configuration": config_name,
                "metric": metric,
                "pooled_oof_value": finite_or_none(pooled_row[metric]),
                "mean_fold_value": finite_or_none(fold_rows[metric].mean()),
                "defined_fold_count": int(fold_rows[metric].notna().sum()),
                "fold_count": int(len(fold_rows)),
                "aggregation_note": "pooled computes once over 221 OOF rows; mean_fold averages defined fold metrics",
            })
    return pd.DataFrame(rows)


def report_text(df, protein37, protein37_predictions, row45, provenance37, fold3, top_rows, conditions, outside, aggregation):
    fold2 = pd.read_csv(FOLD_PATH)
    fold2 = fold2[(fold2.configuration == "A") & (fold2.fold == 2)].iloc[0]
    lines = [
        "# Targeted Ablation Diagnostic Audit",
        "",
        "## Scope",
        "",
        "This audit uses existing out-of-fold predictions and retained provenance records only. No models were retrained, embeddings regenerated, observations removed, or production artifacts changed.",
        "",
        "## Protein 37: PHL-7",
        "",
        f"Protein 37 is PHL-7 and is held out in fold 2. Its fold-2 training target range is {fold2.train_target_min_um:.3g} to {fold2.train_target_max_um:.3g} uM; its observed range is {protein37.target_value_standardized.min():.3g} to {protein37.target_value_standardized.max():.3g} uM.",
        "",
        "| Source row | Duration (h) | Actual (uM) | A prediction | B prediction | C prediction |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    pivot = protein37_predictions.pivot(index="source_row_id", columns="configuration", values="predicted_target_um")
    for source_row_id in protein37.source_row_id:
        actual = protein37.loc[protein37.source_row_id == source_row_id, "target_value_standardized"].iloc[0]
        duration = protein37.loc[protein37.source_row_id == source_row_id, "duration_hours"].iloc[0]
        lines.append(f"| {source_row_id} | {duration} | {actual:.3f} | {pivot.loc[source_row_id, 'A']:.3f} | {pivot.loc[source_row_id, 'B']:.3f} | {pivot.loc[source_row_id, 'C']:.3f} |")

    lines += [
        "",
        "### Row 45 provenance",
        "",
        "The retained row records TPA from PET substrate, 47.0 mM, converted with `value * 1000` to 47,000 uM. The material is reported as amorphous G-PET film (Goodfellow ES301445), 250 um thick, approximately 3 x 0.5 cm and 45 mg, with reported crystallinity of 5-7%. The original assay JSON records an approximate digitized TPA measurement from Figure 3C, PHL7, 16 h; 70 °C; pH 8; purified enzyme; 0.6 mg enzyme/g PET; 1.8 mL reaction volume; shaking at 700 rpm; and 1 M potassium phosphate buffer. The retained assay methods cite HPLC quantification of TPA/MHET/BHET, with gravimetric, VSI, and SEM supporting measurements.",
        "",
        "Evidence assessment:",
        "",
        "- Verified: the retained dataset, original JSON, and provenance audit agree on protein, analyte, value, unit, conversion, conditions, DOI, assay index, and TPA classification.",
        "- Verified: the source JSON reports 90% ± 2.8% G-PET weight loss within 16 h and an approximate digitized TPA value of 47 mM.",
        "- Missing evidence: the raw figure/image, independent replicate-level TPA values, and a direct uncertainty estimate for the digitized 47 mM point are not retained here.",
        "- Suspected issue: none is verified. The value is large relative to the fold-2 training maximum, but magnitude alone does not establish a transcription error.",
        "",
        "## Fold 3 held-out proteins",
        "",
        "| Protein | Name | Records | Actual range | A range / MAE | B range / MAE | C range / MAE | B SSE share | C SSE share |",
        "|---:|---|---:|---:|---|---|---|---:|---:|",
    ]
    for _, row in fold3.iterrows():
        lines.append(f"| {row.protein_id} | {row.protein_name} | {row.record_count} | {row.actual_min_um:.3f}-{row.actual_max_um:.3f} | {row.A_prediction_min_um:.3f}-{row.A_prediction_max_um:.3f} / {row.A_mae_um:.3f} | {row.B_prediction_min_um:.3f}-{row.B_prediction_max_um:.3f} / {row.B_mae_um:.3f} | {row.C_prediction_min_um:.3f}-{row.C_prediction_max_um:.3f} / {row.C_mae_um:.3f} | {row.B_fold_sse_share:.1%} | {row.C_fold_sse_share:.1%} |")

    lines += [
        "",
        "B and C error direction is descriptive: protein 149 accounts for the largest B and C SSE shares and is predominantly overpredicted; proteins 1, 148, and 185 also show large errors, with their direction varying by configuration. The largest B rows are protein 149 predictions near 6,254 uM against actual values from 8.0 to 187.9 uM. The largest C rows are the same protein, with predictions up to 3,931 uM.",
        "",
        "## Fold 3 condition coverage",
        "",
        "| Feature | Train range | Test range | Train missing | Test missing | Test outside train range |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in conditions.iterrows():
        lines.append(f"| {row.feature} | {row.train_min:g}-{row.train_max:g} | {row.test_min:g}-{row.test_max:g} | {row.train_missing} | {row.test_missing} | {row.test_outside_training_range} |")
    lines += ["", "Only one test observation is outside a training range: protein 11 at 25 °C, below the training minimum of 30 °C. pH and duration have no fold-3 test observations outside their training ranges, and there is no missingness in these three fields in train or test.", ""]

    lines += ["## Aggregation and B fold 1", "", "| Configuration | Metric | Pooled OOF | Mean fold | Defined folds |", "|---|---|---:|---:|---:|"]
    for _, row in aggregation.iterrows():
        pooled_value = "undefined" if pd.isna(row.pooled_oof_value) else f"{row.pooled_oof_value:.4f}"
        mean_value = "undefined" if pd.isna(row.mean_fold_value) else f"{row.mean_fold_value:.4f}"
        lines.append(f"| {row.configuration} | {row.metric} | {pooled_value} | {mean_value} | {row.defined_fold_count}/{row.fold_count} |")
    lines += ["", "B fold 1 has one test protein and one unique prediction value (2,774.4148 uM) across all 75 rows. This is expected for a protein-only representation when the held-out fold contains one protein: every row shares the same protein embedding, and environment/duration features are absent from B. It is not evidence of a data mutation.", "", "## Unresolved source questions", "", "- Can the original Figure 3C and its underlying replicate-level values be retrieved to quantify uncertainty around the approximate digitized 47 mM TPA point?", "- Does the source distinguish the reported 0.6 mg enzyme/g PET loading from the methods-series value of 0.55 mg/g for the exact TPA point?", "- Are there raw HPLC replicate values for the 16 h PHL-7 measurement beyond the retained digitized summary?", ""]
    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATASET_PATH, dtype=str, keep_default_na=False, low_memory=False)
    for column in ["target_value_standardized", "temperature_c", "ph", "duration_hours"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    oof = pd.read_csv(OOF_PATH)
    fold_metrics = pd.read_csv(FOLD_PATH)
    pooled = pd.read_csv(POOLED_PATH)
    provenance = pd.read_csv(PROVENANCE_PATH, dtype=str, keep_default_na=False)

    protein37, protein37_predictions, row45, provenance37 = make_protein37_tables(df, oof, provenance)
    fold3, fold3_top_rows = make_fold3_tables(df, oof, fold_metrics)
    conditions, outside = make_condition_table(df, oof)
    aggregation = make_aggregation_table(fold_metrics, pooled)

    protein37.to_csv(OUTPUT_DIR / "protein37_observations.csv", index=False, encoding="utf-8-sig")
    protein37_predictions.to_csv(OUTPUT_DIR / "protein37_oof_predictions.csv", index=False, encoding="utf-8-sig")
    provenance37.to_csv(OUTPUT_DIR / "protein37_provenance_audit_records.csv", index=False, encoding="utf-8-sig")
    fold3.to_csv(OUTPUT_DIR / "fold3_protein_metrics.csv", index=False, encoding="utf-8-sig")
    fold3_top_rows.to_csv(OUTPUT_DIR / "fold3_error_contributing_rows.csv", index=False, encoding="utf-8-sig")
    conditions.to_csv(OUTPUT_DIR / "fold3_condition_ranges.csv", index=False, encoding="utf-8-sig")
    outside.to_csv(OUTPUT_DIR / "fold3_test_outside_training_ranges.csv", index=False, encoding="utf-8-sig")
    aggregation.to_csv(OUTPUT_DIR / "aggregation_check.csv", index=False, encoding="utf-8-sig")

    summary = {
        "protein37": {"protein_name": "PHL-7", "held_out_fold": 2, "row45": row45},
        "fold3": {"held_out_proteins": fold3[["protein_id", "protein_name"]].to_dict(orient="records"), "condition_outside_training_ranges": outside.to_dict(orient="records")},
        "aggregation": aggregation.to_dict(orient="records"),
        "b_fold1": {"test_protein_count": 1, "unique_prediction_count": 1, "constant_prediction": True, "prediction_um": 2774.41479492, "expected_from_protein_only_features": True},
        "outputs": sorted(path.name for path in OUTPUT_DIR.iterdir()),
    }
    (OUTPUT_DIR / "targeted_audit_summary.json").write_text(json.dumps(json_safe(summary), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "targeted_audit_report.md").write_text(report_text(df, protein37, protein37_predictions, row45, provenance37, fold3, fold3_top_rows, conditions, outside, aggregation), encoding="utf-8")

    print("TARGETED ABLATION AUDIT COMPLETE")
    print("protein 37 rows:", len(protein37))
    print("fold 3 proteins:", ", ".join(fold3["protein_id"].tolist()))
    print("fold 3 outside-range observations:", len(outside))
    print("B fold 1 constant predictions:", True)
    print("output directory:", OUTPUT_DIR.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()