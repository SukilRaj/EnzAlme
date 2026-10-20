# EnzAIme final-review presentation content audit

## Deliverable and preservation

- Source: `C:/Users/Welcome/Downloads/ProjectReview_EnzymeDE_Updated.pptx` (59 slides).
- Updated deck: `outputs/ProjectReview_EnzAIme_Final_Review.pptx` (45 slides).
- The original file was not modified. Models, embeddings, research datasets and application source were not changed or regenerated.
- The original 4:3 size (9144000 × 6858000 EMU), college background artwork, watermark, column motif and MEPCO footer were retained. The date was updated to October 1, 2026.
- The template background remains fixed. Text, tables, chart and diagrams are editable. No transitions, animations or timed advances were added.
- The supplied pasted document was treated as the requested content brief, subject to verification against the project files. Its stale implementation statements were corrected rather than executed as independent instructions.

## Restructuring

The 59-slide source was consolidated into 45 slides. This is a content restructuring, so slide numbers are not a one-to-one edit mapping.

- Original cover, motivation, aim and objectives (1–9) became final slides 1–4 with a narrower confirmed PET/TPA research scope.
- Literature and references (10, 58) became final slides 5–7 and 44.
- Proposed encoding, masking, neural oracle and directed-evolution slides (11–23) were consolidated into current-model slides 15–20 and clearly future slides 39–40. Repetitive equation/pseudocode continuation slides were removed.
- Data integration/preprocessing and modules (24–28) were replaced by verified source-role, dataset, audit, validation and output slides.
- Old implementation, score, mutation, code and tests (29–41) were revised in final slides 28–30 and 34–38. Outdated code screenshots, the 9-enzyme dataset, 54-test assertion and clean-install claim were removed.
- Three genuine source screenshots were retained: original 42 → final 31, original 44 → final 32, original 47 → final 33. Redundant source screenshots 43, 45, 46, 48 and 49 were omitted.
- Deliverables, complexity, SWOT, cost, impact and future-work material (50–57) was consolidated into status, limitations, future roadmap and output/feasibility slides. Unverified cost/hardware claims were removed.
- Closing slide (59) became final slide 45.

## New evidence added

- Dataset construction and exact source counts, dataset profile, provenance and ambiguity handling.
- Protein imbalance, repeated-condition variability, feature eligibility audit, A/B/C and rejected D configurations.
- Current ESM-2/Ridge baseline, accurate pooling implementation, equations, grouped CV and controlled results.
- Completed diagnostics, targeted error analysis, follow-up experiments and legacy serving lineage.
- Actual saved API result with an explicit legacy-model caption.

## Scientific corrections

1. Confirmed ML scope is PET assays with TPA concentration targets, not validated activity prediction across all industrial pollutants.
2. Master CSV has 462 rows and 7,195 embedded assay records, directly recounted from `activity_records_json`.
3. Confirmed research data has 221 rows and 25 unique proteins. Legacy data has 227 rows, with six ambiguous source records excluded from confirmed research.
4. Zero-duration count is exactly 8 in the confirmed dataset. No guessed count was used.
5. The dataset has 48 repeated protein-condition groups. Repeated metadata patterns are not automatically biological replicates or data errors. There are four exact duplicate groups involving nine rows.
6. Target is standardized TPA concentration in µM, not a percentage accuracy, universal fitness score or degradation rate.
7. Environmental/wastewater data is scenario context, not the source of experimental activity labels. PAZy records support the confirmed target provenance.
8. ESM-2 is frozen. Current controlled estimator is Ridge α=10, with 10 PCA components in B/C. No trained multimodal neural oracle is claimed.
9. The actual encoder pools attention-mask tokens including special tokens. The simplified residue-only equation in the brief was corrected accordingly.
10. Configuration C scales ESM features, fits PCA, concatenates the three condition features and applies final scaling within each training fold. Raw dimensions are 1,283; post-PCA model inputs are 13.
11. Protein IDs are split/group keys. Scalers and PCA are fitted on training folds. No same-protein train/test overlap is permitted within a fold.
12. Negative R² is shown openly and interpreted against the held-out mean predictor. The deck makes no production-model selection claim.
13. B Spearman averages only four defined folds. B fold 1 is undefined due to constant predictions. Mean fold metrics are not pooled OOF metrics.
14. The original weighted compatibility score is historical and rule based. The mutation proxy is an unvalidated computational hypothesis.
15. Fold analysis, targeted audit, model comparison and balance sensitivity already exist; the brief's blanket future/in-progress labels for these were updated.
16. The served PCA/scaler has strong legacy 227-row lineage evidence. Exact final Ridge and saved CV row membership remains unresolved. The confirmed A/B/C results are not asserted to validate those artifacts.
17. The saved API prediction 23.14270943023124 µM is labeled as a legacy-system output, not an experimental measurement or fresh inference.
18. The historical UI images are explicitly archived prototype screenshots. They are not portrayed as the current interface or confirmed-model predictions.
19. No wet-lab validation, validated mutation predictor or industrial deployment is claimed.

## Controlled results used

Source: `reports/results/controlled_ablation_results.csv`. Values recomputed by configuration. Table shows two decimals for errors/R² and three for Spearman. Chart uses the same two-decimal errors, with rounded whole-number display labels.

| Configuration | MAE (µM) | RMSE (µM) | Mean fold R² | Mean fold Spearman |
|---|---:|---:|---:|---:|
| A | 1423.11 | 3200.77 | -0.29 | 0.313 |
| B | 1918.29 | 3943.42 | -86.87 | -0.227 |
| C | 1592.12 | 3452.48 | -23.22 | 0.239 |

## Screenshots and figures

- Three genuine archived screenshots extracted from the source deck, without invented UI content.
- One existing research figure: `reports/results/ablation_error_analysis/actual_vs_predicted.png`.
- One new editable grouped bar chart from actual controlled-ablation data.
- One editable table transcribing the actual saved API output. It is deliberately not described as a screenshot.

## Future work separation

Slides 39–41 identify proposed multimodal fusion/oracle, masking, generation, beam search, mutation prioritization, structural analysis and wet-lab validation as future work. Current outputs and future outputs are compared on slide 42. Limitations are explicit on slide 38.

## Unverified or unresolved information

- The exact producing run, row membership and artifact-to-evaluation linkage of the served legacy Ridge model remain unresolved in the saved audit.
- Original encoder/checkpoint provenance for every cached vector is not fully recorded. Existing vectors were only checked for coverage, dimensions and finiteness.
- BRENDA and environmental-dataset integration roles are described as intended/context roles, without claiming all fields are complete in the confirmed cohort.
- The source deck's historical screenshots were not recaptured or independently linked to their original code execution. Captions accurately describe them as archived evidence supplied with the deck.
- The targeted-audit narrative has a conflicting B fold-1 constant prediction. The conflicting constant was omitted. CSV-derived metrics were used.
- For PHL-7's 47 mM digitized measurement, original figure/replicate uncertainty remains unresolved. Magnitude alone was not treated as an error.
- Hong et al.'s title was checked against IEEE's entry, but full text was not available for detailed independent method review. Original author/year details were retained with a narrow contribution description.
- Project-wide 54-test, hardware-cost, clean-install and industrial-deployment claims were not re-established and were removed.

## Slide inventory and traceability

### 1. EnzAIme

Sources: Original title slide and project brief

Note: Final review. Preserve team and guide identities from the supplied deck.

### 2. Motivation and current scope

Sources: Original slides 2–7; data/processed/tpa_pet_ml_confirmed.csv

### 3. Aim and research objectives

Sources: data/processed/tpa_pet_ml_confirmed.csv; scripts/

### 4. Current work and long-term proposal

Sources: reports/results/served_model_audit/README.md; reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 5. Literature survey: evolution and structure

Sources: https://github.com/HySonLab/Directed_Evolution; https://ieeexplore.ieee.org/document/10443319/

Note: Hong title corrected to Artificial Intelligence. Bibliographic details retained from the source deck; full paper access was limited.

### 6. Literature survey: protein representations

Sources: https://doi.org/10.1126/science.ade2574; https://doi.org/10.1073/pnas.2016239118

### 7. Research gap and question

Sources: Project brief; reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 8. Dataset sources and intended roles

Sources: master_dataset.csv; reports/results/tpa_provenance_audit_summary.json; reports/results/fireprotdb_analysis.json

### 9. Dataset construction and provenance

Sources: master_dataset.csv; data/processed/tpa_pet_ml_confirmed.csv; reports/results/tpa_provenance_audit_summary.json

### 10. Confirmed dataset profile

Sources: data/processed/tpa_pet_ml_confirmed.csv; reports/results/tpa_confirmed_dataset_summary.json

### 11. Activity provenance audit

Sources: reports/results/tpa_confirmed_dataset_summary.json; reports/results/tpa_ambiguous_review.md

### 12. Protein imbalance and assay variability

Sources: reports/results/repeated_condition_variability.json; data/processed/tpa_pet_ml_confirmed.csv

### 13. Feature eligibility and leakage audit

Sources: reports/results/feature_eligibility_audit.csv

### 14. Controlled feature configurations

Sources: reports/results/research_feature_matrix_summary.json

### 15. What model are we using?

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py; backend/app/services/esm_encoder.py

### 16. Frozen ESM-2 feature extraction

Sources: backend/app/services/esm_encoder.py; data/embeddings/index.json; reports/results/research_feature_matrix_summary.json

Note: Current implementation pools all attention-mask tokens, including special tokens; it truncates at 1024 tokens. Existing vectors reused, no regeneration.

### 17. Current research prediction pipeline

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 18. Representation and feature equations

Sources: backend/app/services/esm_encoder.py; reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

Note: m_i is 1 for attended tokens. This corrects the brief’s residue-only pooling description to match the implementation.

### 19. Ridge training and prediction

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

Note: Ridge fits an intercept by default. The objective uses transformed training targets. log1p itself has no fitted parameters, but is applied within the fold training flow.

### 20. Evaluation metrics

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 21. Protein-grouped cross-validation

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 22. Controlled ablation results

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

Note: Arithmetic means of fold metrics. B Spearman excludes undefined fold 1 and uses four defined folds; all other displayed means use five folds. These are not pooled OOF metrics.

### 23. Ablation: absolute prediction error

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

Note: Editable chart generated from actual CSV fold means. No synthetic metric values.

### 24. What the current results tell us

Sources: reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py

### 25. Completed fold-level error analysis

Sources: reports/results/ablation_error_analysis/actual_vs_predicted.png; reports/results/ablation_error_analysis/ablation_error_analysis_report.md

### 26. Error analysis: two major findings

Sources: reports/results/ablation_error_analysis/targeted_audit/targeted_audit_report.md

Note: The targeted report contains a conflicting B fold-1 constant value. That constant is omitted. Controlled metrics are taken directly from the CSV.

### 27. Additional research already completed

Sources: reports/results/model_comparison_results.json; reports/results/protein_balance_sensitivity.md; reports/results/repeated_condition_variability.json

Note: These follow-up experiments differ from the fixed A/B/C ablation. No production model selection or deployment follows from them.

### 28. Software architecture

Sources: backend/app/api/routes.py; backend/app/services/; frontend/src/App.jsx; reports/results/served_model_audit/README.md

### 29. Served model: lineage and reproducibility

Sources: reports/results/served_model_audit/README.md; models/model_config.json

### 30. Actual saved API output

Sources: reports/results/served_model_audit/live_api_prediction.json; reports/results/served_model_audit/prediction_comparison.json

Note: Saved API output from the 2026-09-28 audit, not a newly run inference or screenshot.

### 31. Prototype interface: home

Sources: Original PPT embedded screenshot, preserved without fabrication

Note: These images document the older prototype and do not represent the current React interface or confirmed-model inference.

### 32. Prototype interface: recommendation

Sources: Original PPT embedded screenshot, preserved without fabrication

Note: These images document the older prototype and do not represent the current React interface or confirmed-model inference.

### 33. Prototype interface: enzyme details

Sources: Original PPT embedded screenshot, preserved without fabrication

Note: These images document the older prototype and do not represent the current React interface or confirmed-model inference.

### 34. Initial rule-based baseline

Sources: Original slide 31

Note: Historical prototype documentation. The formula is preserved for context, not claimed as the current learned predictor.

### 35. Preliminary mutation prioritization

Sources: Original slide 32; reports/results/fireprotdb_analysis.json

Note: Current EnzAIme_ML routes do not expose a mutation endpoint. Historical implementation claims are not carried into the present ML application.

### 36. Current implementation status

Sources: data/processed/tpa_pet_ml_confirmed.csv; reports/results/; backend/app/; frontend/src/

### 37. Codebase and verification evidence

Sources: backend/app/; frontend/src/; scripts/; tests/test_legacy_evidence_integration.py; reports/results/served_model_audit/README.md

Note: No existing application tests were rerun for this presentation-only edit. The old 54-test assertion and clean-install claim are not supported for this repository.

### 38. Current limitations

Sources: data/processed/tpa_pet_ml_confirmed.csv; reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py; reports/results/served_model_audit/README.md

### 39. Long-term EnzAIme architecture

Sources: Original proposed architecture and user brief

Note: PROPOSED / FUTURE ARCHITECTURE. This diagram is a roadmap, not a claim that its modules are trained.

### 40. Future masking and evolution strategy

Sources: Original slides 14–22; https://github.com/HySonLab/Directed_Evolution

Note: Proposal adapted from literature. No current EnzAIme condition-aware neural oracle has been established as trained.

### 41. Future work in research order

Sources: Project brief updated against existing reports

### 42. Outputs, feasibility and intended impact

Sources: Project brief; repository artifacts

### 43. Conclusion

Sources: data/processed/tpa_pet_ml_confirmed.csv; reports/results/controlled_ablation_results.csv; scripts/run_controlled_ablation.py; reports/results/ablation_error_analysis/

### 44. References and research evidence

Sources: Bibliographic references and local project evidence

### 45. Thank you

Sources: Original closing slide


## Final validation

- Final deck: 45 slides in the source 4:3 format. All slides have source notes.
- All 45 slides rendered successfully in installed Microsoft PowerPoint. Visual inspection covered the complete deck and changed slides, including equations, tables, diagrams, source screenshots and result charts.
- PowerPoint text-bound check reported zero overflow findings after repairs.
- Package integrity passed with zero findings. First-party Artifact Tool import passed for all 45 slides.
- Layout checks passed with zero findings. One heuristic warning estimated possible table overflow on slide 8; direct PowerPoint rendering showed the full table and separated caption, so no actual collision was observed.
- There are 18 editable tables and one editable grouped chart. Chart category/value caches match the embedded data workbook.
- Dataset counts and embedding coverage were independently read from project data. Displayed A/B/C results were recalculated from the actual result CSV and verified in slide XML.
- No slide contains animation timing or transitions. No fabricated metric values or screenshots were inserted.
- Final SHA-256: 9689e68a4569336418ab841b3c67059ac8dba2749f169b94599734a2b5f4a92f.
- Private validation receipt: `.ppt_build/validation_delivery.json`. Its staging destination was moved unchanged to the canonical output filename after validation.
- Original source, research data, models, cached embeddings and application source remain unchanged by this task.

