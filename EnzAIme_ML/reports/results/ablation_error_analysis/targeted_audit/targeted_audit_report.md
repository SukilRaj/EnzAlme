# Targeted Ablation Diagnostic Audit

## Scope

This audit uses existing out-of-fold predictions and retained provenance records only. No models were retrained, embeddings regenerated, observations removed, or production artifacts changed.

## Protein 37: PHL-7

Protein 37 is PHL-7 and is held out in fold 2. Its fold-2 training target range is 0.3 to 6.86e+03 uM; its observed range is 1.1e+03 to 4.7e+04 uM.

| Source row | Duration (h) | Actual (uM) | A prediction | B prediction | C prediction |
|---:|---:|---:|---:|---:|---:|
| 41 | 1.0 | 1100.000 | 325.272 | 58.437 | 103.678 |
| 42 | 2.0 | 2700.000 | 328.172 | 58.437 | 104.283 |
| 43 | 4.0 | 8800.000 | 334.049 | 58.437 | 105.503 |
| 44 | 8.0 | 24000.000 | 346.119 | 58.437 | 107.988 |
| 45 | 16.0 | 47000.000 | 371.580 | 58.437 | 113.131 |
| 46 | 24.0 | 44500.000 | 465.491 | 58.437 | 132.976 |
| 47 | 24.0 | 13800.000 | 465.491 | 58.437 | 132.976 |
| 48 | 24.0 | 20200.000 | 465.491 | 58.437 | 132.976 |

### Row 45 provenance

The retained row records TPA from PET substrate, 47.0 mM, converted with `value * 1000` to 47,000 uM. The material is reported as amorphous G-PET film (Goodfellow ES301445), 250 um thick, approximately 3 x 0.5 cm and 45 mg, with reported crystallinity of 5-7%. The original assay JSON records an approximate digitized TPA measurement from Figure 3C, PHL7, 16 h; 70 °C; pH 8; purified enzyme; 0.6 mg enzyme/g PET; 1.8 mL reaction volume; shaking at 700 rpm; and 1 M potassium phosphate buffer. The retained assay methods cite HPLC quantification of TPA/MHET/BHET, with gravimetric, VSI, and SEM supporting measurements.

Evidence assessment:

- Verified: the retained dataset, original JSON, and provenance audit agree on protein, analyte, value, unit, conversion, conditions, DOI, assay index, and TPA classification.
- Verified: the source JSON reports 90% ± 2.8% G-PET weight loss within 16 h and an approximate digitized TPA value of 47 mM.
- Missing evidence: the raw figure/image, independent replicate-level TPA values, and a direct uncertainty estimate for the digitized 47 mM point are not retained here.
- Suspected issue: none is verified. The value is large relative to the fold-2 training maximum, but magnitude alone does not establish a transcription error.

## Fold 3 held-out proteins

| Protein | Name | Records | Actual range | A range / MAE | B range / MAE | C range / MAE | B SSE share | C SSE share |
|---:|---|---:|---:|---|---|---|---:|---:|
| 1 | IsPETase | 12 | 1.300-682.000 | 7.997-106.357 / 240.530 | 25.018-25.018 / 227.655 | 2.417-43.481 / 233.782 | 0.3% | 1.0% |
| 11 | Mors1 | 1 | 102.000-102.000 | 9.391-9.391 / 92.609 | 47.217-47.217 / 54.783 | 22.889-22.889 / 79.111 | 0.0% | 0.0% |
| 148 | CtPl | 2 | 1.180-8.283 | 559.326-559.326 / 554.594 | 186.429-186.429 / 181.698 | 658.317-658.317 / 653.586 | 0.0% | 0.6% |
| 149 | 606 | 13 | 8.000-187.900 | 55.816-96.375 / 38.733 | 6254.299-6254.299 / 6187.253 | 2545.376-3931.400 / 3172.311 | 99.3% | 98.0% |
| 185 | SM14est | 7 | 0.300-9.400 | 63.542-65.752 / 61.299 | 520.756-520.756 / 517.570 | 255.732-262.801 / 255.564 | 0.4% | 0.3% |
| 496 | PET94 | 2 | 37.300-51.390 | 30.618-30.618 / 13.727 | 35.784-35.784 / 8.561 | 19.339-19.339 / 25.006 | 0.0% | 0.0% |

B and C error direction is descriptive: protein 149 accounts for the largest B and C SSE shares and is predominantly overpredicted; proteins 1, 148, and 185 also show large errors, with their direction varying by configuration. The largest B rows are protein 149 predictions near 6,254 uM against actual values from 8.0 to 187.9 uM. The largest C rows are the same protein, with predictions up to 3,931 uM.

## Fold 3 condition coverage

| Feature | Train range | Test range | Train missing | Test missing | Test outside train range |
|---|---:|---:|---:|---:|---:|
| temperature_c | 30-80 | 25-60 | 0 | 0 | 1 |
| ph | 7-9 | 7-9 | 0 | 0 | 0 |
| duration_hours | 0-672 | 1-120 | 0 | 0 | 0 |

Only one test observation is outside a training range: protein 11 at 25 °C, below the training minimum of 30 °C. pH and duration have no fold-3 test observations outside their training ranges, and there is no missingness in these three fields in train or test.

## Aggregation and B fold 1

| Configuration | Metric | Pooled OOF | Mean fold | Defined folds |
|---|---|---:|---:|---:|
| A | mae_um | 1420.7127 | 1423.1084 | 5/5 |
| A | rmse_um | 5085.6992 | 3200.7687 | 5/5 |
| A | r2 | -0.0490 | -0.2917 | 5/5 |
| A | spearman | 0.4409 | 0.3132 | 5/5 |
| B | mae_um | 1888.3306 | 1918.2932 | 5/5 |
| B | rmse_um | 5346.7490 | 3943.4204 | 5/5 |
| B | r2 | -0.1594 | -86.8720 | 5/5 |
| B | spearman | 0.2737 | -0.2268 | 4/5 |
| C | mae_um | 1515.8998 | 1592.1209 | 5/5 |
| C | rmse_um | 5116.6227 | 3452.4825 | 5/5 |
| C | r2 | -0.0618 | -23.2216 | 5/5 |
| C | spearman | 0.3920 | 0.2394 | 5/5 |

B fold 1 has one test protein and one unique prediction value (2,774.4148 uM) across all 75 rows. This is expected for a protein-only representation when the held-out fold contains one protein: every row shares the same protein embedding, and environment/duration features are absent from B. It is not evidence of a data mutation.

## Unresolved source questions

- Can the original Figure 3C and its underlying replicate-level values be retrieved to quantify uncertainty around the approximate digitized 47 mM TPA point?
- Does the source distinguish the reported 0.6 mg enzyme/g PET loading from the methods-series value of 0.55 mg/g for the exact TPA point?
- Are there raw HPLC replicate values for the 16 h PHL-7 measurement beyond the retained digitized summary?
