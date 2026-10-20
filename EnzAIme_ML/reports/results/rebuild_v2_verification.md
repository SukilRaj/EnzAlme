# Reconstruction verification — 14 October 2026

- Backend: 20 unittest checks passed across `test_rebuild_v2`, `test_neural_pipeline`, and `test_mutation_structure`.
- The extended stability test additionally trained three synthetic checkpoints and exercised the complete v2 artifact review, encoder compatibility and joint-ranking inference. Passed. Synthetic targets verify software contracts only.
- Frontend: production build and ESLint passed.
- Kaggle delivery: all Python code cells compile; ZIP CRC checks passed (29 entries). Dependency-install cell uses notebook `%pip` syntax.
- Browser: real activity checkpoint ranked the protein catalog; local Llama returned grounded evidence with correct candidate and units; real residue gradients rendered successfully.
- Browser: cached IsPETase AlphaFold coordinates mapped at full sequence coverage; its structural distance image and interactive backbone view rendered.
- Startup: `Start-EnzAIme.ps1` started the unified API and local Ollama, returning the application URL on port 8001.

The installed first activity checkpoint remains a weak research baseline (held-out R² approximately -2.30). The new Tm and image-fusion checkpoints have not been trained on the collected datasets. No biological performance or mutation-improvement claim follows from these software tests. The next user action is the T4×2 Kaggle notebook described in `docs/rebuild_v2.md`.
