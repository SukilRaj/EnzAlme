# Repeated Condition Target Variability Analysis

## Objective

Investigate target variability among repeated protein-condition groups in the confirmed PET/TPA dataset without deleting records, treating values as noise, or assuming that repeated observations are biological replicates.

## Methodology

- Source: `data/processed/tpa_pet_ml_confirmed.csv`
- Condition key: `protein_id + temperature_c + ph + duration_hours`
- Confirmed records: 221
- Proteins: 25
- Repeated groups analyzed: 48
- Source provenance: preserved `original_record_json` was parsed where available.
- Metadata inspected: assay index, DOI, source file, material, detection methods, evidence, analyte, metric type, target unit, replicate count, and other recorded condition metadata.

## Dataset scope

The confirmed dataset contains 221 records from 25 proteins. There are 123 unique protein-condition groups in total, of which 48 contain multiple observations. This analysis reports all 48 repeated groups, including the 1 group with identical targets and the 47 groups with different targets.

## Findings

- Repeated groups with identical target values: 1
- Repeated groups with different target values: 47
- Groups with recorded metadata differences: 48
- Groups without an obvious recorded metadata explanation: 0
- Largest target range: 30700.000 µM
- Largest coefficient of variation: 1.345

The complete group-level analysis is in `repeated_condition_variability.csv`. Its `source_metadata_summary` field preserves the available source metadata values as JSON for each group.

### Highest target-range groups

|   protein_id | protein_name   |   record_count |   target_min_uM |   target_max_uM |   target_range_uM |   target_cv | metadata_difference_fields                                                                                              | metadata_explanation_status   |
|-------------:|:---------------|---------------:|----------------:|----------------:|------------------:|------------:|:------------------------------------------------------------------------------------------------------------------------|:------------------------------|
|           37 | PHL-7          |              3 |         13800   |         44500   |           30700   |    0.618971 | assay_index; material; evidence                                                                                         | metadata differences recorded |
|           44 | HiC            |             12 |          1694.8 |          5981.9 |            4287.1 |    0.360575 | assay_index; evidence; additional_conditions; enzyme_concentration_value; substrate_concentration_value                 | metadata differences recorded |
|           44 | HiC            |              4 |          1788.3 |          4613   |            2824.7 |    0.367807 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              4 |           938.6 |          3349.6 |            2411   |    0.432126 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              8 |           670   |          2490.6 |            1820.6 |    0.304388 | assay_index; material; evidence; additional_conditions; agitation_mode; agitation_speed_rpm; enzyme_concentration_value | metadata differences recorded |
|           44 | HiC            |              4 |           400   |          2193.1 |            1793.1 |    0.624026 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|          483 | DIEGO          |              2 |            35.1 |          1390   |            1354.9 |    1.34455  | assay_index; target_unit; replicate_n; material; detection_methods; evidence; additional_conditions                     | metadata differences recorded |
|           44 | HiC            |              4 |           711.7 |          2010.7 |            1299   |    0.376884 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              4 |           300   |          1365.7 |            1065.7 |    0.504418 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|          483 | DIEGO          |              2 |            27.3 |           828   |             800.7 |    1.32393  | assay_index; target_unit; replicate_n; material; detection_methods; evidence; additional_conditions                     | metadata differences recorded |

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

There are 0 different-target groups without an obvious recorded metadata difference in the preserved fields. These values cannot be safely labeled as biological noise, technical replicates, or errors from the available data. Some source-record identifiers are unavailable, so source-level identity may remain unresolved even when the nested source JSON is present.

No observations were removed.

## Implications for ML modeling

Repeated condition groups with different targets mean that a single protein-condition key can map to multiple target values. This can represent distinct assays, material contexts, measurement choices, or unresolved source variation. Protein-grouped validation prevents the same protein from crossing folds, but it does not make the target values interchangeable within a protein.

The target variability should therefore be considered when interpreting fold metrics. The current analysis does not establish that any group is invalid and does not select a modeling treatment.

## Recommendation for next data-cleaning/modeling step

Preserve the current records and add explicit source-record and measurement-level identifiers before retraining. Review groups with large ranges first, using the recorded assay, material, method, analyte, and citation fields. Decide whether distinct assay contexts should remain separate, be modeled with additional features, or be excluded only after source review. Do not collapse repeated groups or remove observations solely because their target values differ.

## Summary table

|   protein_id | protein_name   |   record_count |   target_min_uM |   target_max_uM |   target_range_uM |   target_cv | metadata_difference_fields                                                                                              | metadata_explanation_status   |
|-------------:|:---------------|---------------:|----------------:|----------------:|------------------:|------------:|:------------------------------------------------------------------------------------------------------------------------|:------------------------------|
|           37 | PHL-7          |              3 |       13800     |       44500     |         30700     |    0.618971 | assay_index; material; evidence                                                                                         | metadata differences recorded |
|           44 | HiC            |             12 |        1694.8   |        5981.9   |          4287.1   |    0.360575 | assay_index; evidence; additional_conditions; enzyme_concentration_value; substrate_concentration_value                 | metadata differences recorded |
|           44 | HiC            |              4 |        1788.3   |        4613     |          2824.7   |    0.367807 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              4 |         938.6   |        3349.6   |          2411     |    0.432126 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              8 |         670     |        2490.6   |          1820.6   |    0.304388 | assay_index; material; evidence; additional_conditions; agitation_mode; agitation_speed_rpm; enzyme_concentration_value | metadata differences recorded |
|           44 | HiC            |              4 |         400     |        2193.1   |          1793.1   |    0.624026 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|          483 | DIEGO          |              2 |          35.1   |        1390     |          1354.9   |    1.34455  | assay_index; target_unit; replicate_n; material; detection_methods; evidence; additional_conditions                     | metadata differences recorded |
|           44 | HiC            |              4 |         711.7   |        2010.7   |          1299     |    0.376884 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           44 | HiC            |              4 |         300     |        1365.7   |          1065.7   |    0.504418 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|          483 | DIEGO          |              2 |          27.3   |         828     |           800.7   |    1.32393  | assay_index; target_unit; replicate_n; material; detection_methods; evidence; additional_conditions                     | metadata differences recorded |
|            1 | IsPETase       |              7 |           4     |         682     |           678     |    0.641883 | assay_index; material; evidence; additional_conditions; enzyme_concentration_value                                      | metadata differences recorded |
|          177 | Sub1           |              3 |         394.27  |         970.926 |           576.657 |    0.421603 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              4 |         120     |         564.9   |           444.9   |    0.57355  | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|          177 | Sub1           |              3 |         266.057 |         699.452 |           433.396 |    0.44444  | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              3 |         886     |        1313     |           427     |    0.218597 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           13 | MG8            |              6 |          43     |         420     |           377     |    0.591058 | assay_index; replicate_n; evidence; additional_conditions; buffer; substrate_amount_value                               | metadata differences recorded |
|           44 | HiC            |              3 |         576.5   |         806.1   |           229.6   |    0.166035 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              2 |         294.6   |         493.1   |           198.5   |    0.356381 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|          483 | DIEGO          |              2 |          20.2   |         203     |           182.8   |    1.15824  | assay_index; target_unit; replicate_n; material; detection_methods; evidence; additional_conditions                     | metadata differences recorded |
|           44 | HiC            |              2 |         619.5   |         799.5   |           180     |    0.179393 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              2 |         816     |         956     |           140     |    0.111732 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              2 |         527.5   |         658.7   |           131.2   |    0.15642  | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|          195 | BurPL          |              2 |          89.3   |         194.8   |           105.5   |    0.525166 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           44 | HiC            |              2 |         280.2   |         377.1   |            96.9   |    0.208485 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           15 | RgPETase       |              2 |          21     |         106.2   |            85.2   |    0.947256 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|          195 | BurPL          |              2 |          31.6   |         108.2   |            76.6   |    0.774884 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           15 | RgPETase       |              2 |           7     |          76.9   |            69.9   |    1.17823  | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           44 | HiC            |              3 |         347.1   |         415.2   |            68.1   |    0.106321 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           15 | RgPETase       |              2 |           5.5   |          66     |            60.5   |    1.19664  | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|          149 | 606            |              5 |          23.4   |          82.9   |            59.5   |    0.500589 | assay_index; evidence; additional_conditions; enzyme_concentration_value                                                | metadata differences recorded |
|           42 | CalB           |              2 |          13     |          61.8   |            48.8   |    0.922642 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           44 | HiC            |              3 |         129.4   |         170.1   |            40.7   |    0.164361 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|          195 | BurPL          |              2 |          22.2   |          55.7   |            33.5   |    0.608166 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           15 | RgPETase       |              2 |          10.5   |          40.8   |            30.3   |    0.835296 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           44 | HiC            |              2 |          22.7   |          46.7   |            24     |    0.489065 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           13 | MG8            |              5 |          25     |          49     |            24     |    0.247165 | assay_index; evidence; additional_conditions                                                                            | metadata differences recorded |
|           42 | CalB           |              2 |          17.9   |          41.9   |            24     |    0.567577 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|           42 | CalB           |              2 |           3.4   |          17.9   |            14.5   |    0.962728 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|          496 | PET94          |              2 |          37.3   |          51.39  |            14.09  |    0.224673 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|          195 | BurPL          |              2 |           7.5   |          19     |            11.5   |    0.613715 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|          495 | PET93          |              2 |          26.63  |          37.06  |            10.43  |    0.231594 | assay_index; material; evidence; additional_conditions                                                                  | metadata differences recorded |
|           42 | CalB           |              2 |           3.4   |          13     |             9.6   |    0.827832 | assay_index; material; additional_conditions                                                                            | metadata differences recorded |
|          148 | CtPl           |              2 |           1.18  |           8.283 |             7.103 |    1.06152  | assay_index; material; evidence; substrate_amount_value                                                                 | metadata differences recorded |
|          185 | SM14est        |              2 |           1.5   |           5.6   |             4.1   |    0.816659 | assay_index; additional_conditions                                                                                      | metadata differences recorded |
|          185 | SM14est        |              2 |           0.8   |           3.3   |             2.5   |    0.862325 | assay_index; additional_conditions                                                                                      | metadata differences recorded |
|            4 | PET12          |              2 |           0.983 |           2.85  |             1.867 |    0.688843 | assay_index; material; evidence; substrate_amount_value                                                                 | metadata differences recorded |
|          185 | SM14est        |              2 |           0.3   |           1.4   |             1.1   |    0.915079 | assay_index; additional_conditions                                                                                      | metadata differences recorded |
|           42 | CalB           |              2 |          13     |          13     |             0     |    0        | material; additional_conditions                                                                                         | metadata differences recorded |

No model was trained and no dataset, embedding, backend, frontend, or model artifact was modified.

REPEATED CONDITION ANALYSIS COMPLETE
