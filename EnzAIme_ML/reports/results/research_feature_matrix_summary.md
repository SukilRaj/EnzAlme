# Research Feature Matrix

## 1. Objective

Construct controlled, read-only feature matrices for a research ablation study on the confirmed 221-record TPA activity dataset. The objective is to separate protein embeddings, environmental conditions, and context variables without leaking target, assay identity, or source metadata into the training matrix.

## 2. Dataset

- Confirmed records: 221
- Unique proteins: 25
- Embedding dimension: 1280
- Target: log1p(target_value_standardized) in uM, computed after splitting in the next modeling step.
- Source: data/processed/tpa_pet_ml_confirmed.csv
- Existing embeddings: data/embeddings/index.json plus the corresponding .npy files

## 3. Configuration A — Environment Only

- Features: temperature_c, ph, duration_hours
- Dimension: 3
- Records: 221
- Proteins: 25
- Approved: yes

## 4. Configuration B — ESM-2 Only

- Features: ESM-2 embedding
- Dimension: 1280
- Records: 221
- Proteins: 25
- Approved: yes

## 5. Configuration C — ESM-2 + Environment

- Features: ESM-2 embedding, temperature_c, ph, duration_hours
- Dimension: 1283
- Records: 221
- Proteins: 25
- Approved: yes

## 6. Configuration D — Context-Aware

- Features: 
- Dimension: 0
- Records: 221
- Proteins: 25
- Approved: no
- Reason: material_description is highly heterogeneous and source-specific, with 33 unique values and rich preparation metadata; this can encode source/protocol context rather than stable prediction-time substrate features. substrate is constant (PET) across the confirmed dataset, so it contributes no discriminative signal. The context block is therefore rejected for the next research matrix.

## 7. Material Analysis

- Unique values: 33
- Missing count: 0
- Interpretation: material_description is highly heterogeneous and source-specific, with rich preparation and product metadata.
- Decision: not approved for predictive encoding in the next research matrix.

## 8. Substrate Analysis

- Unique values: 1
- Missing count: 0
- Distribution: {'PET': 221}
- Interpretation: the confirmed activity dataset is essentially all PET, so the substrate variable is constant and provides no discriminative signal.
- Decision: not included in the context-aware configuration.

## 9. Missingness

Temperature, pH, and duration are complete in the confirmed dataset. Material and substrate are present, but material is not stable enough and substrate is constant. Missingness remains zero for the approved feature blocks.

## 10. Protein Coverage

- Unique proteins in the confirmed data: 25
- Proteins with embedding files: 25
- Missing embeddings: []
- Embedding verification: verified

## 11. Leakage Controls

- No protein identifiers or source IDs were used as predictive features.
- No target-derived or outcome fields were included.
- Sequence remains in the metadata table for traceability only.
- The ESM-2 embedding is used as a fixed protein representation and is not regenerated.
- Preprocessing such as scaling and categorical encoding will be learned only within training folds later.

## 12. Final Feature Configurations

Approved research matrices: A, B, and C. D is rejected based on material/source-specific heterogeneity and the constant PET substrate.

## 13. Limitations

The confirmed dataset is small and protein-imbalanced. The material context is highly specific and may encode source, vendor, or preparation details rather than predictive biology. The next modeling step should keep protein-grouped cross-validation and avoid global categorical fitting before fold-local preprocessing.
