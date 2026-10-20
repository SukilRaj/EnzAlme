# EnzAIme evaluation and error plots

Saved-result gallery: no models were fitted and no predictions were invented. MAE/RMSE are in µM (lower is better); R² and Spearman are dimensionless (higher is better). Negative R² means performance below the corresponding test-target mean baseline. There is no classification accuracy percentage. Fold means and pooled metrics are different summaries. Bars show saved means or individual values; consult source reports for fold standard deviations. Legacy results remain separate because exact row membership is unresolved.

- [Controlled feature ablation · confirmed 221 rows](01_ablation.svg) — Unweighted mean of five protein-group folds. B Spearman is defined in 4/5 folds. Bars are means, not confidence intervals.
- [Ablation · individual held-out fold results](02_ablation_folds.svg) — Same fixed protein-group folds across A/B/C; undefined correlation is retained.
- [Pooled out-of-fold evaluation · 221 predictions per configuration](03_pooled.svg) — Metrics recomputed over all held-out rows in the saved analysis; these differ from the mean of fold metrics.
- [Model comparison · all 58 saved configurations](04_all_model_configurations.svg) — Confirmed 221 rows; mean across protein-group folds (finite values only). Separate experiment from controlled A/B/C.
- [Protein-balance sensitivity](05_balance.svg) — Fold means. The 82-row subset changes the test distribution; differences do not establish improved production performance.
- [Legacy served model · separately reported evaluation](06_legacy.svg) — 227 reported records. Exact training/evaluation row membership unresolved. NOT a confirmed 221-row comparison.
- [Observed variability · identical modeled conditions](07_repeated_conditions.svg) — All saved repeated-condition groups; other assay metadata can differ. These are observations, not prediction error bars.
- [Actual versus predicted · A/B/C](../ablation_error_analysis/actual_vs_predicted.png) — Existing project plot; preserved without alteration.
- [Squared error contribution by protein](../ablation_error_analysis/per_protein_squared_error.png) — Existing project plot; preserved without alteration.

Source hashes are recorded in `source_manifest.json`. Rebuild with `python build_gallery.py` (standard library only). Existing datasets, reports and models are read-only inputs.
