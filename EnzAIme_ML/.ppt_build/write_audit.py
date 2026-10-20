import json,hashlib,zipfile
from pathlib import Path
from lxml import etree as E
root=Path.cwd(); manifest=json.loads(Path('.ppt_build/slide_manifest.json').read_text()); evidence=json.loads(Path('.ppt_build/evidence.json').read_text())
text='''# EnzAIme final-review presentation content audit

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
'''
for k,v in evidence['metrics'].items(): text+=f"| {k} | {v['mae_um']:.2f} | {v['rmse_um']:.2f} | {v['r2']:.2f} | {v['spearman']:.3f} |\n"
text+='''
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

'''
for x in manifest:text+=f"### {x['slide']}. {x['title']}\n\nSources: {x['source']}\n\n"+(f"Note: {x['note']}\n\n" if x['note'] else '')
Path('reports/results/ppt_content_audit.md').write_text(text,encoding='utf-8')
print('Content audit written')
