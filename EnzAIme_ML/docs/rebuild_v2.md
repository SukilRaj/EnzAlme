# EnzAIme v2 reconstruction — 14 October 2026

## Run the application

From PowerShell in the project folder, run `./Start-EnzAIme.ps1`. Open http://127.0.0.1:8001. The script starts the local Ollama service and the unified API, which serves the built frontend. Logs are in `outputs/runtime`. After code changes, rebuild with `npm run build` in `frontend` and run `./Start-EnzAIme.ps1 -Restart`. Restart checks the listening process belongs to this project before stopping it. It does not register any system startup task.

For frontend development, use `npm run dev` in `frontend`; Vite proxies `/api` to port 8001. Both `backend.app.main:app` and the previous `backend.app.neural_main:app` launch the same backend. Legacy Ridge services no longer load during app startup. Before-rebuild application files were preserved in `outputs/rebuild_archive`.

## Implemented workflow

- One interface for neural ranking, sequence/structure inspection, held-out evaluation, data provenance and service health.
- Checkpoint-backed ESM-2 Attention1D activity ranking; pending capabilities are explicit.
- Separate local LLM health and explanation requests. Rankings remain visible if Ollama is slow or unavailable.
- Llama 3.2 1B selects evidence IDs using a constrained JSON schema; the server renders verified statements, units and scores. This design follows observed wrong-candidate and wrong-unit errors in unrestricted model output. It is LLM-assisted evidence selection, not unrestricted scientific reasoning or causal explanation.
- Gradient × input residue attribution on ESM representations and condition derivatives, alongside attention and image-removal sensitivity. Attribution explains model sensitivity, not biological causality.
- Optional Tm checkpoint loading and Pareto-front filtering for joint activity/Tm recommendations. Requires a trained, compatible stability model; absent weights never produce stability scores.
- Local PDB inspection and mutation preview are retained. The bounded ESM search module remains a research utility; no validated mutation-improvement endpoint is exposed because the current activity training data does not establish variant effects.

## Data collected directly

FireProtDB's documented API was used to retrieve sequence entries with Tm measurements, excluding mutant entries. Responses are cached under `data/stability/raw`. The initial curated result contains 5,622 measurements, 660 unique amino-acid sequences and 207 excluded records. The acquisition exhausted its search, rather than silently stopping at the page limit. The manifest records retrieval time and scope.

Filtering requires standard residues, length at most 1,022, agreement with reported sequence length, valid measured Tm in (0,150) interpreted in degrees C, and unique measurement IDs. Source publication, method, pH and database identifiers are retained. These checks establish data consistency, not independent recuration of every original paper. The API's sequence entries are treated as reference/wild-type records; underlying constructs still need study review. Database protein identity groups do not establish sequence-family independence.

Sources: https://loschmidt.chemi.muni.cz/fireprotdb/api-docs/ and https://loschmidt.chemi.muni.cz/fireprotdb/help/ .

AlphaFold DB structures were retrieved for project UniProt mappings. Thirteen proteins passed both full sequence-string and observed C-alpha chain identity checks. The remaining twelve were excluded with reasons in `data/structure_images/manifest.json`. Deterministic C-alpha distance maps use a 20 Angstrom cutoff. No experimental labels or publication text are drawn into the images. These are predicted structures, not experimental structural measurements. No wild-type structure is silently assigned to a mutant.

Source: https://alphafold.ebi.ac.uk/ . Image fusion is an extension to the base paper, which used sequences rather than image inputs.

## Training still required

The running activity model is the first Kaggle checkpoint (held-out R² -2.30). It has no trained image branch and cannot support claims of accurate activity optimization.

The new `notebooks/EnzAIme_v2_Kaggle.ipynb` and `outputs/enzaime_v2_training.zip` provide the next experiment using the collected data. Attach the ZIP as a private Kaggle dataset, import the notebook, enable Internet and T4 x2, then run all cells in order. The notebook handles intact ZIPs and extracted Kaggle inputs.

GPU 0 prepares sequence/image features and trains matched sequence-only and image-fusion activity models. GPU 1 prepares frozen ESM-2 features for the 660 stability sequences and trains an Attention1D Tm model. Training-only normalization, validation early stopping and independent held-out records are saved. Tm groups join exact-sequence and database-protein identity; family/study leakage remains possible. pH and its missingness are inputs; assay methods and buffers are not modeled. The Tm model is not a mutation-effect model.

Return `enzaime_v2_results.zip` for checkpoint review. Checkpoints and features are separated by experiment, and no unreviewed model automatically replaces the served model. Dataset and feature consistency must be checked during import. Multimodal superiority and joint predictive reliability remain unproven until the new experiments are evaluated. Images exist for only 13 of 25 activity proteins, so modality availability can confound results; add shuffled-image and matched-subset controls before claims of image benefit.

Review a returned archive with `python -m scripts.import_v2_results PATH_TO_ZIP`. The importer checks archive paths, safe tensor loading, dataset digests, split separation, finite predictions and compatible encoders, then performs a joint-ranking smoke test. It reports validation loss separately from test metrics. Select the activity model using validation evidence, preserving the test set for final reporting. Explicit activation uses `--activate sequence` or `--activate images`; complete model/feature pairs are backed up before copying. Restart the app after activation. These integrity checks do not establish predictive validity.

The Sequence & structure page can load any of the 13 cached, sequence-verified structures without downloading a PDB manually. Expand its structural-image panel to see the exact distance representation prepared for training.

## Remaining scientific work

1. Audit assay/construct consistency and condition omissions in the small activity dataset.
2. Evaluate family/study splits and matched simple baselines before model selection.
3. Add experimentally measured PET variants with mapped mutant sequences before optimizing mutation effects.
4. Calibrate uncertainty; uncertainty cannot be inferred from attention or an LLM's wording.
5. Evaluate directed evolution with independent held-out evidence, then laboratory assays if feasible.

The software rebuild is distinct from demonstrating an experimentally validated enzyme-design system. Current scores and proposed experiments must retain that distinction.
