# Feature Eligibility and Leakage Audit

## 1. Objective

Assess which variables in the 221-record confirmed TPA activity dataset can be used as prediction-time inputs without obvious target, source-record, or split leakage. This audit is read-only and does not train a model or modify source data.

## 2. Dataset Scope

- Confirmed records: **221**
- Unique proteins: **25**
- Candidate features audited: **48**
- Primary source: `data/processed/tpa_pet_ml_confirmed.csv`.
- Provenance context: `master_dataset.csv`, `data/embeddings/index.json`, and the existing repeated-condition JSON report.

## 3. Feature Inventory

| feature                   | feature_group        |   non_missing_count |   non_missing_percentage | role                        | eligibility       |
|:--------------------------|:---------------------|--------------------:|-------------------------:|:----------------------------|:------------------|
| protein_id                | Protein              |                 221 |                   100    | GROUPING/SPLIT VARIABLE     | LEAKAGE_RISK      |
| protein_name              | Protein              |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | NOT_RECOMMENDED   |
| sequence                  | Protein              |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE              |
| sequence_length           | Protein              |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| ESM-2 embedding           | Protein              |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| UniProt accession         | Protein              |                 168 |                    76.02 | EVIDENCE/TRACEABILITY FIELD | NOT_RECOMMENDED   |
| UniProt entry             | Protein              |                 168 |                    76.02 | EVIDENCE/TRACEABILITY FIELD | NOT_RECOMMENDED   |
| EC number                 | Protein              |                   0 |                     0    | FUTURE FEATURE              | FUTURE_FEATURE    |
| organism                  | Protein              |                 209 |                    94.57 | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| substrate                 | Protein              |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| PDB IDs                   | Protein              |                 153 |                    69.23 | FUTURE FEATURE              | NOT_RECOMMENDED   |
| temperature_c             | Environmental        |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| ph                        | Environmental        |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| duration_hours            | Environmental        |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| salinity                  | Environmental        |                   0 |                     0    | FUTURE FEATURE              | FUTURE_FEATURE    |
| COD                       | Environmental        |                   0 |                     0    | FUTURE FEATURE              | FUTURE_FEATURE    |
| BOD                       | Environmental        |                   0 |                     0    | FUTURE FEATURE              | FUTURE_FEATURE    |
| pollutant type            | Environmental        |                   0 |                     0    | FUTURE FEATURE              | FUTURE_FEATURE    |
| material                  | Experimental context |                 221 |                   100    | CURRENT MODEL FEATURE       | SAFE_WITH_CAUTION |
| analyte                   | Experimental/assay   |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| metric_type               | Experimental/assay   |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| target_value              | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| target_unit               | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| target_value_standardized | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| standardized_unit         | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| conversion_formula        | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| molecular_weight_used     | Target-related       |                  12 |                     5.43 | EXCLUDED FIELD              | LEAKAGE_RISK      |
| conversion_status         | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| detection_methods         | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| evidence                  | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| assay_index               | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| literature_doi            | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| source_file               | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| source_record_id          | Experimental/assay   |                   0 |                     0    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| measurement_index         | Experimental/assay   |                   0 |                     0    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| replicate_n               | Experimental/assay   |                 185 |                    83.71 | EXCLUDED FIELD              | LEAKAGE_RISK      |
| additional_conditions     | Experimental context |                 233 |                   105.43 | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| buffer                    | Experimental context |                 221 |                   100    | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| concentrations            | Experimental context |                 146 |                    66.06 | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| enzyme loading            | Experimental context |                  18 |                     8.14 | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| reaction volume           | Experimental context |                 184 |                    83.26 | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| agitation                 | Experimental context |                 113 |                    51.13 | FUTURE FEATURE              | SAFE_WITH_CAUTION |
| original_record_json      | Experimental/assay   |                 221 |                   100    | EVIDENCE/TRACEABILITY FIELD | LEAKAGE_RISK      |
| condition_group_id        | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| repeated_condition        | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| possible_duplicate        | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| zero_duration_flag        | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |
| classification            | Target-related       |                 221 |                   100    | EXCLUDED FIELD              | LEAKAGE_RISK      |

## 4. Protein Features

Sequence is complete in the confirmed dataset. The ESM-2 index covers all 25 proteins. UniProt identifiers are only partially populated and should remain lookup/evidence fields. EC number is empty in all confirmed records. No exact duplicate sequences were found; near-identical screening used a conservative 0.90 `difflib.SequenceMatcher` ratio threshold.

## 5. Environmental Features

Temperature, pH, and duration are complete and recorded before measurement, so they are candidates with caution around confounding and extrapolation. Salinity, COD, BOD, and pollutant type are absent from the confirmed activity records and remain future scenario features; they must not be merged into the current training table without valid same-record labels.

## 6. Experimental Context Features

`material` is available through `material_description` for all confirmed rows and can represent substrate/context. It should be normalized and compared against the existing `substrate` field. Buffer, concentrations, enzyme loading, reaction volume, agitation, and additional conditions require field-level parsing and coverage checks before use. Raw assay/source metadata is retained for traceability, not prediction.

## 7. Leakage Analysis

- Split by `protein_id` (or unique sequence) so repeated rows from one protein cannot cross train/test folds.
- Keep exact duplicate records in the audit, but ensure duplicates never cross folds; do not treat them as independent biological evidence.
- Repeated conditions are common: 48 groups, 47 with different target values, and all 48 have recorded metadata differences.
- Exclude source identifiers, assay identifiers, DOI, target fields, and raw original JSON from model inputs.
- Fit scaling, imputation, categorical vocabularies, and any sequence/embedding transformations within training folds where they learn parameters.

## 8. Features Safe for the Next Model

`sequence`

## 9. Features Requiring Caution

`sequence_length`, `ESM-2 embedding`, `organism`, `substrate`, `temperature_c`, `ph`, `duration_hours`, `material`, `additional_conditions`, `buffer`, `concentrations`, `enzyme loading`, `reaction volume`, `agitation`

## 10. Features Excluded from Prediction

`analyte`, `metric_type`, `target_value`, `target_unit`, `target_value_standardized`, `standardized_unit`, `conversion_formula`, `molecular_weight_used`, `conversion_status`, `replicate_n`, `condition_group_id`, `repeated_condition`, `possible_duplicate`, `zero_duration_flag`, `classification`.

## 11. Future Features

`EC number`, `salinity`, `COD`, `BOD`, `pollutant type`.

## 12. Recommended Next Feature Set

Use ESM-2 embedding, sequence, temperature_c, ph, duration_hours, and normalized material/substrate context. Treat sequence/embedding as protein-level features and validate with protein-grouped splits. Keep sequence_length and organism as secondary ablation candidates under the same grouped validation; they are not required for the minimal next set.

## 13. Implications for Experimental Design

Record stable protein identifiers and sequences, pre-assay condition values, material/substrate vocabulary, units, enzyme loading, reaction volume, buffer, and replicate structure in a structured schema. Assign source-record and measurement identifiers for traceability, but never expose them as predictive inputs. Balance proteins and conditions so the model is not dominated by HiC or other high-count proteins.

## 14. Limitations

The dataset is small, protein-imbalanced, and observational across source protocols. Near-identity detection is a screening heuristic rather than a biological multiple-sequence alignment. Availability of nested metadata is counted from non-empty JSON values, not proof that units or semantics are harmonized. No causal or predictive performance claim is made.

## 15. Conclusion

The current defensible feature set is protein sequence/ESM-2 plus pre-assay temperature, pH, duration, and carefully normalized material/substrate context. The dominant risks are protein identity memorization, repeated-condition/replicate leakage, exact duplicates, source/publication identifiers, and target-derived fields. Eligibility counts are recorded in `feature_eligibility_audit.csv` and the full structured result in `feature_eligibility_audit.json`.
