# EnzAIme Pre-Training Data Audit

## Dataset size

- Total rows: 221
- Unique proteins: 25
- Unique protein-condition combinations: 123
- Exact duplicate rows: 5
- Exact duplicate groups: 4

## Protein distribution

Records per protein: mean 8.84, median 5.00, minimum 1, maximum 75, standard deviation 14.79.

|   protein_id | protein_name   |   record_count |
|-------------:|:---------------|---------------:|
|           44 | HiC            |             75 |
|           42 | CalB           |             20 |
|          149 | 606            |             13 |
|          483 | DIEGO          |             12 |
|            1 | IsPETase       |             12 |
|           13 | MG8            |             12 |
|          481 | Sis            |             12 |
|          177 | Sub1           |             12 |
|          195 | BurPL          |              8 |
|           37 | PHL-7          |              8 |
|           15 | RgPETase       |              8 |
|          185 | SM14est        |              7 |
|           17 | BhrPETase      |              5 |
|          148 | CtPl           |              2 |
|            4 | PET12          |              2 |
|           41 | PET46          |              2 |
|          495 | PET93          |              2 |
|          496 | PET94          |              2 |
|          240 | Dkca1          |              1 |
|          223 | HG-2           |              1 |
|          224 | HG-3           |              1 |
|          225 | HG-4           |              1 |
|          226 | HG-5           |              1 |
|           11 | Mors1          |              1 |
|           25 | TfCut2         |              1 |

## Target distribution

### `target_value_standardized`

|   minimum |   q1 |   median |    mean |   q3 |   maximum |   standard_deviation |   zero_values |   greater_than_1000_uM |   greater_than_5000_uM |   greater_than_10000_uM |
|----------:|-----:|---------:|--------:|-----:|----------:|---------------------:|--------------:|-----------------------:|-----------------------:|------------------------:|
|       0.3 | 25.1 |    194.8 | 1472.08 |  956 |     47000 |              4976.83 |             0 |                     53 |                     11 |                       5 |

Zero values: 0. Values above 1,000 µM: 53; above 5,000 µM: 11; above 10,000 µM: 5.

### `log1p(target_value_standardized)`

|   minimum |      q1 |   median |    mean |     q3 |   maximum |   standard_deviation |
|----------:|--------:|---------:|--------:|-------:|----------:|---------------------:|
|  0.262364 | 3.26194 |  5.27709 | 5.11904 | 6.8638 |   10.7579 |              2.31707 |

The log summary is analytical only; the dataset was not transformed.

## Environmental distribution

### pH

- Minimum: 7.0
- Maximum: 9.0
- Unique values: 5
- Counts: {'7.0': 71, '7.5': 24, '8.0': 75, '8.5': 13, '9.0': 38}

### Temperature

- Minimum: 25.0 °C
- Maximum: 80.0 °C
- Unique values: 12
- Counts: {'25.0': 1, '30.0': 22, '37.0': 40, '40.0': 26, '45.0': 7, '50.0': 36, '55.0': 11, '60.0': 27, '65.0': 1, '70.0': 46, '72.0': 3, '80.0': 1}

### Duration

- Minimum: 0.0 hours
- Maximum: 672.0 hours
- Mean: 119.75 hours
- Median: 72.00 hours
- Unique values: 31
- Zero-duration rows: 8

## Repeated conditions

Condition key: `protein_id + pH + temperature_c + duration_hours + substrate`.

- Total condition groups: 123
- Repeated condition groups: 48
- Rows involved: 146
- Groups with identical target values: 1
- Groups with different target values: 47

No rows were removed.

## Exact duplicates

- Exact duplicate groups: 4
- Rows involved: 9

|   protein_id | protein_name   |   target_value_standardized |   temperature_c |   ph |   duration_hours | substrate   |   rows |
|-------------:|:---------------|----------------------------:|----------------:|-----:|-----------------:|:------------|-------:|
|            1 | IsPETase       |                       521   |              30 |    9 |               18 | PET         |      3 |
|           42 | CalB           |                        13   |              37 |    7 |              168 | PET         |      2 |
|           44 | HiC            |                       129.4 |              50 |    7 |               72 | PET         |      2 |
|           44 | HiC            |                       347.1 |              50 |    7 |              168 | PET         |      2 |

No duplicate rows were removed.

## UniProt coverage

- Unique proteins with UniProt accession: 15
- Unique proteins without UniProt accession: 10
- Coverage: 60.00%

Unresolved proteins:

|   protein_id | protein_name   |
|-------------:|:---------------|
|           13 | MG8            |
|          148 | CtPl           |
|          224 | HG-3           |
|          226 | HG-5           |
|          240 | Dkca1          |
|           37 | PHL-7          |
|          481 | Sis            |
|          483 | DIEGO          |
|          495 | PET93          |
|          496 | PET94          |

No missing accessions were inferred.

## Sequence quality

- Missing sequences: 0
- Empty sequences: 0
- Duplicate sequences across different protein IDs: 0 groups
- Sequence length minimum: 186
- Sequence length median: 290.0
- Sequence length maximum: 462

No duplicate sequences occur across different protein IDs.

## Leakage analysis

- Same protein IDs occur across multiple conditions: yes; this is expected for condition-response data.
- Duplicate sequences across different IDs: none found.
- Exact duplicate observations: 4 groups, 9 rows involved.
- Same protein-condition-target combinations repeated: 4 groups, 9 rows involved.

Grouping by `protein_id` prevents the same protein and its repeated observations from appearing in both training and validation. Random row-wise splitting should not be used. Native source-record identifiers are blank, so source-level identity beyond the preserved JSON cannot be checked as a separate grouping variable.

## GroupKFold feasibility

- Unique protein groups, $G$: 25
- Five-fold GroupKFold feasible: yes
- Approximate protein groups per validation fold: 5
- Group size range: 1 to 75 records
- Median group size: 5.0
- Group imbalance: high

The dataset supports protein-grouped five-fold evaluation mechanically, but the unequal group sizes mean validation folds can contain very different numbers of records and information.

## High-value observations

These are **high-value observations requiring source/assay awareness**, not observations declared erroneous.

| protein_name   |   protein_id |   target |   temperature |   ph |   duration | source_file                 |   assay_index |
|:---------------|-------------:|---------:|--------------:|-----:|-----------:|:----------------------------|--------------:|
| PHL-7          |           37 |  47000   |            70 |  8   |         16 | pazy_polymer_assays.json.gz |            22 |
| PHL-7          |           37 |  44500   |            72 |  8   |         24 | pazy_polymer_assays.json.gz |            11 |
| PHL-7          |           37 |  24000   |            70 |  8   |          8 | pazy_polymer_assays.json.gz |            21 |
| PHL-7          |           37 |  20200   |            72 |  8   |         24 | pazy_polymer_assays.json.gz |            13 |
| PHL-7          |           37 |  13800   |            72 |  8   |         24 | pazy_polymer_assays.json.gz |            12 |
| PHL-7          |           37 |   8800   |            70 |  8   |          4 | pazy_polymer_assays.json.gz |            20 |
| DIEGO          |          483 |   6865   |            60 |  7.5 |        120 | pazy_polymer_assays.json.gz |            29 |
| DIEGO          |          483 |   6861   |            60 |  7.5 |         96 | pazy_polymer_assays.json.gz |            20 |
| HiC            |           44 |   5981.9 |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            10 |
| HiC            |           44 |   5442.7 |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            14 |
| HiC            |           44 |   5319.4 |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            15 |
| HiC            |           44 |   4718.1 |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            12 |
| HiC            |           44 |   4613   |            70 |  8   |        144 | pazy_polymer_assays.json.gz |            37 |
| HiC            |           44 |   4257.1 |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            38 |
| HiC            |           44 |   4163   |            70 |  8   |        168 | pazy_polymer_assays.json.gz |            13 |

## Recommendations for model evaluation

- Keep validation grouped by protein; do not use random row-wise splitting.
- Report per-protein record counts and fold composition because group sizes range from 1 to 75 records.
- Keep exact duplicates, repeated observations, zero-duration rows, and high-value observations until their source meaning is separately reviewed.
- Report performance overall and by held-out protein where fold sizes permit.
- Treat the observed pH, temperature, and duration ranges as dataset support limits rather than industrial-environment coverage.

No datasets were modified, no records were deleted, no model artifacts were changed, and no model training or embedding generation was performed.

PRE-TRAINING AUDIT COMPLETE
