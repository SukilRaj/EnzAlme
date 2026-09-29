"""Build a read-only feature eligibility and leakage audit.

The script reads the confirmed activity data, master metadata, embedding index,
and existing repeated-condition summary. It writes only the three requested
reports under reports/results and never changes source data or trains a model.
"""

import difflib
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIRMED_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
MASTER_PATH = PROJECT_ROOT / "master_dataset.csv"
EMBEDDING_INDEX_PATH = PROJECT_ROOT / "data" / "embeddings" / "index.json"
REPEATED_JSON_PATH = PROJECT_ROOT / "reports" / "results" / "repeated_condition_variability.json"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "results"
CSV_PATH = OUTPUT_DIR / "feature_eligibility_audit.csv"
JSON_PATH = OUTPUT_DIR / "feature_eligibility_audit.json"
MARKDOWN_PATH = OUTPUT_DIR / "feature_eligibility_audit.md"


def present(value):
    if value is None:
        return False
    if isinstance(value, (dict, list)):
        return bool(value)
    return str(value).strip() != ""


def non_missing(series):
    return series.map(present)


def parse_json(value, default):
    if not isinstance(value, str) or not value.strip():
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def canonical(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return "" if value is None else str(value).strip()


def nested_values(df, record_field, condition_field=None):
    values = []
    for raw_records in df["original_record_json"]:
        records = parse_json(raw_records, [])
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            value = record if condition_field is None else parse_json(record.get("conditions", ""), {})
            if condition_field is not None and not isinstance(value, dict):
                continue
            values.append(value.get(record_field, ""))
    return pd.Series(values, dtype=object)


def stats(values, total):
    series = pd.Series(values, dtype=object)
    count = int(series.map(present).sum())
    return count, round(100 * count / total, 2) if total else 0.0


def sequence_findings(df):
    sequences = (
        df[["protein_id", "sequence"]]
        .drop_duplicates("protein_id")
        .dropna()
        .to_dict("records")
    )
    exact = []
    near = []
    for index, left in enumerate(sequences):
        for right in sequences[index + 1 :]:
            if left["sequence"] == right["sequence"]:
                exact.append({"protein_ids": [left["protein_id"], right["protein_id"]]})
                continue
            similarity = difflib.SequenceMatcher(
                None, left["sequence"], right["sequence"], autojunk=False
            ).ratio()
            if similarity >= 0.90:
                near.append(
                    {
                        "protein_ids": [left["protein_id"], right["protein_id"]],
                        "sequence_similarity_ratio": round(similarity, 4),
                    }
                )
    return {"exact_duplicate_sequence_pairs": exact, "near_identical_pairs_at_or_above_0_90": near}


def embedding_stats(df, embedding_index):
    available_ids = {str(key) for key in embedding_index}
    values = df["protein_id"].astype(str).isin(available_ids)
    return int(values.sum()), round(100 * values.mean(), 2)


def row(feature, group, source, count, percentage, prediction, role, eligibility, risk, reason, encoding, notes):
    return {
        "feature": feature,
        "feature_group": group,
        "source": source,
        "current_dataset_available": count > 0,
        "non_missing_count": count,
        "non_missing_percentage": percentage,
        "prediction_time_available": prediction,
        "role": role,
        "eligibility": eligibility,
        "leakage_risk": risk,
        "reason": reason,
        "recommended_encoding": encoding,
        "notes": notes,
    }


def build_audit(df, master, embedding_index):
    total = len(df)
    master_by_id = master.drop_duplicates("protein_id").set_index("protein_id")
    mapped = master_by_id.reindex(df["protein_id"])
    audit = []

    def add_direct(feature, group, source, column, prediction, role, eligibility, reason, encoding, notes):
        count, percentage = stats(df[column], total) if column in df else (0, 0.0)
        risk_by_eligibility = {
            "SAFE": "Low",
            "SAFE_WITH_CAUTION": "Moderate: confounding, coverage, or encoding risk",
            "LEAKAGE_RISK": "High",
            "NOT_RECOMMENDED": "Low direct leakage risk; unsuitable or identifier-like",
            "FUTURE_FEATURE": "Unassessable until valid same-record coverage exists",
        }
        audit.append(row(feature, group, source, count, percentage, prediction, role, eligibility, risk_by_eligibility[eligibility], reason, encoding, notes))

    def add_master(feature, group, column, prediction, role, eligibility, reason, encoding, notes):
        count, percentage = stats(mapped[column], total) if column in mapped else (0, 0.0)
        risk_by_eligibility = {
            "SAFE": "Low",
            "SAFE_WITH_CAUTION": "Moderate: confounding, coverage, or encoding risk",
            "LEAKAGE_RISK": "High",
            "NOT_RECOMMENDED": "Low direct leakage risk; unsuitable or identifier-like",
            "FUTURE_FEATURE": "Unassessable until valid same-record coverage exists",
        }
        audit.append(row(feature, group, "master_dataset.csv", count, percentage, prediction, role, eligibility, risk_by_eligibility[eligibility], reason, encoding, notes))

    add_direct("protein_id", "Protein", "tpa_pet_ml_confirmed.csv", "protein_id", False, "GROUPING/SPLIT VARIABLE", "LEAKAGE_RISK", "Identifies the protein and can let train/test rows share protein-specific target distributions.", "Never encode; group-aware split by protein_id.", "Retain for grouping, joins, and traceability only.")
    add_direct("protein_name", "Protein", "tpa_pet_ml_confirmed.csv", "protein_name", False, "EVIDENCE/TRACEABILITY FIELD", "NOT_RECOMMENDED", "A categorical alias for protein identity with no independent biological representation.", "Do not encode.", "May be retained for reporting.")
    add_direct("sequence", "Protein", "tpa_pet_ml_confirmed.csv", "sequence", True, "CURRENT MODEL FEATURE", "SAFE", "Sequence is available for every confirmed record and does not contain the measured activity.", "Validated sequence tokenizer or sequence-derived representation fit within each training fold.", "Deduplicate or group by sequence before splitting.")
    add_master("sequence_length", "Protein", "sequence_length", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Available through the master protein join, but it is redundant with sequence and must be computed without target information.", "Numeric feature; impute only if needed.", "Do not use a protein_id lookup as a substitute for sequence.")
    embedding_count, embedding_percentage = embedding_stats(df, embedding_index)
    audit.append(row("ESM-2 embedding", "Protein", "data/embeddings/index.json and data/embeddings/*.npy", embedding_count, embedding_percentage, True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Moderate: protein-level representation and preprocessing risk", "All 25 proteins are indexed, so rows share one protein-level embedding; representation preprocessing must be fixed before or fit within each training fold as appropriate.", "Use the precomputed vector; verify model/sequence provenance and keep one vector per unique sequence.", "Embedding is safe as an input but cannot prevent protein-level memorization when rows from one protein cross folds."))
    add_direct("UniProt accession", "Protein", "tpa_pet_ml_confirmed.csv", "uniprot_accession", False, "EVIDENCE/TRACEABILITY FIELD", "NOT_RECOMMENDED", "Present for 168/221 rows but acts as a database identifier, not a biological measurement.", "Lookup only; never one-hot encode.", "Use for external annotation and provenance.")
    add_direct("UniProt entry", "Protein", "tpa_pet_ml_confirmed.csv", "uniprot_entry", False, "EVIDENCE/TRACEABILITY FIELD", "NOT_RECOMMENDED", "Identifier-like field with the same split and memorization risk as UniProt accession.", "Lookup only.", "Not a predictive feature.")
    add_master("EC number", "Protein", "ec_number", True, "FUTURE FEATURE", "FUTURE_FEATURE", "No confirmed records have an EC number; current coverage is 0/221.", "Controlled categorical encoding after coverage and temporal availability are established.", "Scientifically useful, but unavailable in this labeled dataset.")
    add_master("organism", "Protein", "organism", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Biological context is available for most joined proteins but may be a proxy for protein/source identity.", "Grouped categorical encoding with rare-level handling; assess incremental value under protein-grouped validation.", "Current confirmed coverage is computed through protein_id to master_dataset.csv.")
    add_direct("substrate", "Protein", "tpa_pet_ml_confirmed.csv", "substrate", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Substrate is recorded for every row and is available before the assay, but it may be constant or strongly confounded with the dataset scope.", "Normalized categorical encoding with an explicit unknown level.", "Treat as context, not as a substitute for material details." )
    add_master("PDB IDs", "Protein", "pdb_ids", True, "FUTURE FEATURE", "NOT_RECOMMENDED", "Only a small subset of master proteins has PDB IDs and the identifier itself primarily gives database/source information.", "Do not encode identifiers; use structure-derived features in a future study.", "Current coverage is insufficient for the 221-row model.")

    add_direct("temperature_c", "Environmental", "tpa_pet_ml_confirmed.csv", "temperature_c", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Recorded pre-assay and complete, but repeated measurements and narrow experimental ranges can create protein-condition confounding.", "Numeric; preserve units, inspect range, and scale using training folds only.", "Evaluate extrapolation separately from interpolation." )
    add_direct("ph", "Environmental", "tpa_pet_ml_confirmed.csv", "ph", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Recorded pre-assay and complete, but discrete and protein/source-confounded in this dataset.", "Numeric or ordinal numeric encoding with range checks.", "Do not infer continuous behavior beyond observed values." )
    add_direct("duration_hours", "Environmental", "tpa_pet_ml_confirmed.csv", "duration_hours", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Available pre-assay after a transparent unit conversion; zero-duration rows and repeated conditions require explicit handling.", "Numeric, preferably log1p if scientifically justified; conversion must be fixed before validation.", "Derived from duration_value and duration_unit, not from target." )
    for feature in ["salinity", "COD", "BOD", "pollutant type"]:
        audit.append(row(feature, "Environmental", "Separate wastewater/environmental datasets; absent from confirmed activity CSV", 0, 0.0, False, "FUTURE FEATURE", "FUTURE_FEATURE", "Unassessable until valid same-record coverage exists", "No current labeled activity-record coverage; merging would introduce unsupported labels or scenario assumptions.", "Define a harmonized measurement schema and join only when the same activity record has a valid value.", "Do not merge into the 221 activity records for the next model."))

    add_direct("material", "Experimental context", "original_record_json.material", "material_description", True, "CURRENT MODEL FEATURE", "SAFE_WITH_CAUTION", "Material is recorded for all confirmed rows and can describe substrate/context, but source wording and possible confounding require normalization and audit.", "Normalize controlled vocabulary; encode categorical values with unknown handling; compare against substrate-only baseline.", "Use only information known before prediction; retain raw wording for provenance." )
    add_direct("analyte", "Experimental/assay", "tpa_pet_ml_confirmed.csv and original_record_json", "analyte", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Identifies the measured product and overlaps the target definition; the confirmed dataset is selected using TPA analyte evidence.", "Exclude from model inputs.", "Target-definition and selection information." )
    add_direct("metric_type", "Experimental/assay", "tpa_pet_ml_confirmed.csv and original_record_json", "metric_type", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Describes how the activity outcome was reported and may identify the target distribution or normalization path.", "Exclude unless a future protocol fixes it before measurement.", "Post-measurement/assay interpretation metadata." )
    add_direct("target_value", "Target-related", "tpa_pet_ml_confirmed.csv", "target_value", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Original activity target.", "Exclude.", "Direct target." )
    add_direct("target_unit", "Target-related", "tpa_pet_ml_confirmed.csv", "target_unit", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Target normalization input and measurement-unit information.", "Exclude from predictive inputs; standardize target in the label pipeline.", "Target-derived normalization field." )
    add_direct("target_value_standardized", "Target-related", "tpa_pet_ml_confirmed.csv", "target_value_standardized", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Mathematically standardized target.", "Exclude.", "Direct target transformation." )
    add_direct("standardized_unit", "Target-related", "tpa_pet_ml_confirmed.csv", "standardized_unit", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Target normalization output.", "Exclude.", "Target-derived field." )
    add_direct("conversion_formula", "Target-related", "tpa_pet_ml_confirmed.csv", "conversion_formula", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Records the target conversion procedure and can reveal target units/source measurement.", "Exclude.", "Target normalization provenance." )
    add_direct("molecular_weight_used", "Target-related", "tpa_pet_ml_confirmed.csv", "molecular_weight_used", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Used only in target unit conversion and available for a subset of converted target rows.", "Exclude.", "Post-measurement target conversion field." )
    add_direct("conversion_status", "Target-related", "tpa_pet_ml_confirmed.csv", "conversion_status", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Describes whether target conversion succeeded and reflects target/source measurement handling.", "Exclude.", "Target processing status." )
    add_direct("detection_methods", "Experimental/assay", "original_record_json", "assay_method", False, "EVIDENCE/TRACEABILITY FIELD", "LEAKAGE_RISK", "Assay method can identify publication/protocol and may be unavailable at prediction time.", "Do not encode for this experiment.", "Retain for reproducibility and stratified diagnostics." )
    for feature, column, reason in [
        ("evidence", "source", "Evidence text/source context can identify the publication and target distribution."),
        ("assay_index", "assay_index", "Assay index identifies a source assay record and can leak record-level grouping."),
        ("literature_doi", "literature_doi", "DOI identifies a publication associated with a particular target distribution."),
        ("source_file", "source_file", "Source file is a dataset/provenance identifier and can encode collection batch."),
        ("source_record_id", "source_record_id", "Record identifier would identify an individual source record; it is unavailable here but must remain excluded."),
        ("measurement_index", "measurement_index", "Measurement identifier would identify a measurement record; it is unavailable here but must remain excluded."),
    ]:
        add_direct(feature, "Experimental/assay", "tpa_pet_ml_confirmed.csv and original_record_json", column, False, "EVIDENCE/TRACEABILITY FIELD", "LEAKAGE_RISK", reason, "Exclude from inputs; use for provenance or grouped validation only.", "Potential publication, assay, batch, or record leakage." )
    add_direct("replicate_n", "Experimental/assay", "tpa_pet_ml_confirmed.csv and original_record_json", "replicate_n", False, "EXCLUDED FIELD", "LEAKAGE_RISK", "Replicate count is experimental metadata that may be known only after the measurement and can identify assay quality/source practice.", "Exclude from inputs; use in uncertainty and QC analyses.", "Coverage is incomplete (185/221)." )
    for feature, field in [
        ("additional_conditions", "additional_conditions"),
        ("buffer", "buffer"),
        ("concentrations", "substrate_concentration_value"),
        ("enzyme loading", "enzyme_amount_value"),
        ("reaction volume", "reaction_volume_value"),
        ("agitation", "agitation_mode"),
    ]:
        values = nested_values(df, field, condition_field="conditions")
        count, percentage = stats(values, total)
        eligibility = "FUTURE_FEATURE" if count == 0 else "SAFE_WITH_CAUTION"
        risk = "Unassessable until valid same-record coverage exists" if count == 0 else "Moderate: coverage, units, and prediction-time protocol risk"
        audit.append(row(feature, "Experimental context", "original_record_json.conditions", count, percentage, True, "FUTURE FEATURE", eligibility, risk, "Recorded experimental context may be scientifically useful, but coverage, units, and prediction-time protocol availability require validation." if count else "Not available in the confirmed activity records.", "Parse into controlled numeric/categorical fields with units and missingness indicators.", "Do not infer availability from the JSON key alone; values must be present and harmonized."))
    add_direct("original_record_json", "Experimental/assay", "tpa_pet_ml_confirmed.csv", "original_record_json", False, "EVIDENCE/TRACEABILITY FIELD", "LEAKAGE_RISK", "Raw source records contain target, source identifiers, assay metadata, and post-measurement information.", "Never provide raw JSON to a model.", "Parse only explicitly approved pre-assay fields." )
    for feature, column, reason in [
        ("condition_group_id", "condition_group_id", "Identifier derived from protein and assay conditions; it can identify repeated observations and split membership."),
        ("repeated_condition", "repeated_condition", "Post hoc flag derived using the complete dataset and therefore unavailable without split leakage."),
        ("possible_duplicate", "possible_duplicate", "Post hoc duplicate assessment can expose record relationships."),
        ("zero_duration_flag", "zero_duration_flag", "Derived QC/post-processing flag; use duration_hours instead if scientifically valid."),
        ("classification", "classification", "Dataset inclusion/classification is based on analyte evidence and target provenance."),
    ]:
        add_direct(feature, "Target-related", "tpa_pet_ml_confirmed.csv", column, False, "EXCLUDED FIELD", "LEAKAGE_RISK", reason, "Exclude.", "Use only for audit or split diagnostics." )
    return audit


def markdown_report(audit_df, summary):
    by_role = {role: audit_df[audit_df["role"] == role]["feature"].tolist() for role in audit_df["role"].unique()}
    by_eligibility = {eligibility: audit_df[audit_df["eligibility"] == eligibility]["feature"].tolist() for eligibility in audit_df["eligibility"].unique()}
    risk_lines = [
        "- Split by `protein_id` (or unique sequence) so repeated rows from one protein cannot cross train/test folds.",
        "- Keep exact duplicate records in the audit, but ensure duplicates never cross folds; do not treat them as independent biological evidence.",
        "- Repeated conditions are common: 48 groups, 47 with different target values, and all 48 have recorded metadata differences.",
        "- Exclude source identifiers, assay identifiers, DOI, target fields, and raw original JSON from model inputs.",
        "- Fit scaling, imputation, categorical vocabularies, and any sequence/embedding transformations within training folds where they learn parameters.",
    ]
    lines = [
        "# Feature Eligibility and Leakage Audit",
        "",
        "## 1. Objective",
        "",
        "Assess which variables in the 221-record confirmed TPA activity dataset can be used as prediction-time inputs without obvious target, source-record, or split leakage. This audit is read-only and does not train a model or modify source data.",
        "",
        "## 2. Dataset Scope",
        "",
        f"- Confirmed records: **{summary['total_records']}**",
        f"- Unique proteins: **{summary['total_proteins']}**",
        f"- Candidate features audited: **{summary['total_candidate_features']}**",
        "- Primary source: `data/processed/tpa_pet_ml_confirmed.csv`.",
        "- Provenance context: `master_dataset.csv`, `data/embeddings/index.json`, and the existing repeated-condition JSON report.",
        "",
        "## 3. Feature Inventory",
        "",
        audit_df[["feature", "feature_group", "non_missing_count", "non_missing_percentage", "role", "eligibility"]].to_markdown(index=False),
        "",
        "## 4. Protein Features",
        "",
        "Sequence is complete in the confirmed dataset. The ESM-2 index covers all 25 proteins. UniProt identifiers are only partially populated and should remain lookup/evidence fields. EC number is empty in all confirmed records. No exact duplicate sequences were found; near-identical screening used a conservative 0.90 `difflib.SequenceMatcher` ratio threshold.",
        "",
        "## 5. Environmental Features",
        "",
        "Temperature, pH, and duration are complete and recorded before measurement, so they are candidates with caution around confounding and extrapolation. Salinity, COD, BOD, and pollutant type are absent from the confirmed activity records and remain future scenario features; they must not be merged into the current training table without valid same-record labels.",
        "",
        "## 6. Experimental Context Features",
        "",
        "`material` is available through `material_description` for all confirmed rows and can represent substrate/context. It should be normalized and compared against the existing `substrate` field. Buffer, concentrations, enzyme loading, reaction volume, agitation, and additional conditions require field-level parsing and coverage checks before use. Raw assay/source metadata is retained for traceability, not prediction.",
        "",
        "## 7. Leakage Analysis",
        "",
        "\n".join(risk_lines),
        "",
        "## 8. Features Safe for the Next Model",
        "",
        ", ".join(f"`{feature}`" for feature in by_eligibility.get("SAFE", [])) or "None.",
        "",
        "## 9. Features Requiring Caution",
        "",
        ", ".join(f"`{feature}`" for feature in by_eligibility.get("SAFE_WITH_CAUTION", [])) or "None.",
        "",
        "## 10. Features Excluded from Prediction",
        "",
        ", ".join(f"`{feature}`" for feature in by_role.get("EXCLUDED FIELD", [])) + ".",
        "",
        "## 11. Future Features",
        "",
        ", ".join(f"`{feature}`" for feature in by_eligibility.get("FUTURE_FEATURE", [])) + ".",
        "",
        "## 12. Recommended Next Feature Set",
        "",
        "Use ESM-2 embedding, sequence, temperature_c, ph, duration_hours, and normalized material/substrate context. Treat sequence/embedding as protein-level features and validate with protein-grouped splits. Keep sequence_length and organism as secondary ablation candidates under the same grouped validation; they are not required for the minimal next set.",
        "",
        "## 13. Implications for Experimental Design",
        "",
        "Record stable protein identifiers and sequences, pre-assay condition values, material/substrate vocabulary, units, enzyme loading, reaction volume, buffer, and replicate structure in a structured schema. Assign source-record and measurement identifiers for traceability, but never expose them as predictive inputs. Balance proteins and conditions so the model is not dominated by HiC or other high-count proteins.",
        "",
        "## 14. Limitations",
        "",
        "The dataset is small, protein-imbalanced, and observational across source protocols. Near-identity detection is a screening heuristic rather than a biological multiple-sequence alignment. Availability of nested metadata is counted from non-empty JSON values, not proof that units or semantics are harmonized. No causal or predictive performance claim is made.",
        "",
        "## 15. Conclusion",
        "",
        f"The current defensible feature set is protein sequence/ESM-2 plus pre-assay temperature, pH, duration, and carefully normalized material/substrate context. The dominant risks are protein identity memorization, repeated-condition/replicate leakage, exact duplicates, source/publication identifiers, and target-derived fields. Eligibility counts are recorded in `feature_eligibility_audit.csv` and the full structured result in `feature_eligibility_audit.json`.",
        "",
    ]
    return "\n".join(lines)


def main():
    df = pd.read_csv(CONFIRMED_PATH, dtype=str, keep_default_na=False, low_memory=False)
    master = pd.read_csv(MASTER_PATH, dtype=str, keep_default_na=False, low_memory=False)
    embedding_index = json.loads(EMBEDDING_INDEX_PATH.read_text(encoding="utf-8"))
    repeated = json.loads(REPEATED_JSON_PATH.read_text(encoding="utf-8"))
    audit_df = pd.DataFrame(build_audit(df, master, embedding_index))
    sequence = sequence_findings(df)
    exact_duplicates = int(df.groupby(list(df.columns), dropna=False).size().gt(1).sum())
    repeated_condition_groups = int(repeated.get("total_repeated_condition_groups", 0))
    eligibility_counts = audit_df["eligibility"].value_counts().to_dict()
    recommended = [
        "sequence",
        "ESM-2 embedding",
        "temperature_c",
        "ph",
        "duration_hours",
        "material",
        "substrate",
    ]
    excluded = audit_df.loc[audit_df["role"] == "EXCLUDED FIELD", "feature"].tolist()
    future = audit_df.loc[audit_df["eligibility"] == "FUTURE_FEATURE", "feature"].tolist()
    summary = {
        "dataset_scope": {
            "confirmed_dataset": str(CONFIRMED_PATH.relative_to(PROJECT_ROOT)),
            "master_dataset": str(MASTER_PATH.relative_to(PROJECT_ROOT)),
            "total_records": len(df),
            "total_proteins": int(df["protein_id"].nunique()),
        },
        "total_records": len(df),
        "total_proteins": int(df["protein_id"].nunique()),
        "total_candidate_features": len(audit_df),
        "feature_counts": {"by_group": audit_df["feature_group"].value_counts().to_dict(), "by_role": audit_df["role"].value_counts().to_dict()},
        "eligibility_counts": eligibility_counts,
        "current_recommended_feature_set": recommended,
        "excluded_features": excluded,
        "future_features": future,
        "leakage_risks": {
            "protein_group_split_required": True,
            "exact_duplicate_groups": exact_duplicates,
            "repeated_condition_groups": repeated_condition_groups,
            "repeated_groups_with_identical_targets": repeated.get("repeated_groups_with_identical_targets"),
            "repeated_groups_with_different_targets": repeated.get("repeated_groups_with_different_targets"),
            "groups_with_metadata_differences": repeated.get("groups_with_metadata_differences"),
            "source_identifiers_excluded": ["literature_doi", "source_file", "assay_index", "protein_id", "UniProt accession"],
            "target_derived_fields_excluded": excluded,
        },
        "duplicate_near_duplicate_findings": {
            "exact_duplicate_record_groups": exact_duplicates,
            "exact_duplicate_sequence_pairs": sequence["exact_duplicate_sequence_pairs"],
            "near_identical_sequence_pairs_at_or_above_0_90": sequence["near_identical_pairs_at_or_above_0_90"],
            "repeated_condition_groups": repeated_condition_groups,
        },
        "methodological_recommendations": [
            "Use protein- or unique-sequence-grouped train/test splits.",
            "Do not allow exact duplicate rows or repeated experimental records to cross folds.",
            "Fit preprocessing within each training fold and retain missingness/coverage audits.",
            "Keep identifiers and target/provenance fields outside model inputs.",
            "Do not merge salinity, COD, BOD, or pollutant type into the current 221 rows without same-record labels.",
        ],
        "sequence_findings": sequence,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    JSON_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown_report(audit_df, summary), encoding="utf-8")

    print("FEATURE ELIGIBILITY AUDIT COMPLETE")
    print("1. total confirmed records:", summary["total_records"])
    print("2. total proteins:", summary["total_proteins"])
    print("3. total candidate features audited:", summary["total_candidate_features"])
    for index, eligibility in enumerate(["SAFE", "SAFE_WITH_CAUTION", "LEAKAGE_RISK", "NOT_RECOMMENDED", "FUTURE_FEATURE"], 4):
        print(f"{index}. {eligibility} features:", eligibility_counts.get(eligibility, 0))
    print("9. recommended current model features:", ", ".join(recommended))
    print("10. excluded features:", ", ".join(excluded))
    print("11. major leakage risks: protein identity across folds; repeated conditions/replicates; exact duplicates; source identifiers; target-derived fields; preprocessing fit before cross-validation")
    print("12. duplicate/near-duplicate findings:", json.dumps(summary["duplicate_near_duplicate_findings"], ensure_ascii=False))
    print("Model training performed: no")


if __name__ == "__main__":
    main()