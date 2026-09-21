# ENZAIme Training Report

* Date: 2026-09-18 | device `cpu` | kaggle=False
* ESM model: `facebook/esm2_t12_35M_UR50D` (embed_dim 480)
* Scenarios: 6900 rows, 69 unique enzymes
* Split: GroupShuffleSplit on enzyme_id (0.2 holdout; GroupKFold for CV); train enzymes=55, test enzymes=14

## Model comparison (test set, disagreement only)

| model                   |    mae |   rmse |       r2 |   spearman |   top3_consistent |
|:------------------------|-------:|-------:|---------:|-----------:|------------------:|
| ridge                   | 0.0097 | 0.0334 |   0.374  |     0.2815 |            0      |
| random_forest           | 0.0079 | 0.0347 |   0.3236 |     0.6262 |            0.3333 |
| gradient_boosting       | 0.008  | 0.0347 |   0.3235 |     0.2794 |            0      |
| mlp                     | 0.0132 | 0.0336 |   0.3648 |     0.2804 |            0      |
| derived_label_reference | 0      | 0      |   1      |     1      |            1      |
| pollutant_evidence_only | 0.2042 | 0.2072 | -23.1272 |   nan      |            0      |

**Important:** metrics measure agreement with the **derived compatibility label**. They are not experimental degradation measurements.

## Best model: ridge

### Permutation importance (environment features, random-forest based)

```
{
  "pollutant_PA": -0.090316,
  "pollutant_PET": -0.086456,
  "pollutant_PUR": 0.0,
  "scenario_ph_norm": -0.009671,
  "scenario_temp_norm": 0.027115,
  "scenario_sal_norm": -0.000676,
  "pollutant_evidence_score": 0.0,
  "ph_metadata_available": 0.081753,
  "temperature_metadata_available": 0.051211,
  "salinity_metadata_available": 0.0,
  "has_sequence": 0.0,
  "has_accession": 0.0,
  "metadata_completeness": 0.057555,
  "unknown_feature_count": 0.044989
}
```

## Backend-compatible artifacts: written (SuitabilityNet, val_mse=0.00090)