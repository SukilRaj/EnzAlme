# Mutation and structure modules

Implemented 2026-10-12. Open **Mutation & structure** in the frontend navigation.

## Workflow

1. Choose one of the 25 proteins in the confirmed TPA/PET dataset.
2. Enter single or combined substitutions using one-based positions in the displayed reference sequence (for example, CalB `V235I, A306E`). Preview validates the wild-type letter, bounds, replacement and uniqueness of each position. Download the resulting FASTA if needed.
3. Inspect the local FireProtDB evidence. The current extract has ten CalB records, eight with substitutions. Combined variants remain combined; a measured effect is never attributed to each constituent substitution.
4. Upload a PDB coordinate file, choose a chain if there are several, and optionally enter a reference sequence position. Rotate the C-alpha trace and inspect the mapped residue and nearby C-alpha positions.

No model is trained or replaced. Sequence edits do not receive an invented activity/stability score. Uploaded PDB contents are processed in memory and are not saved by these endpoints. Original datasets and evidence files are read only.

## Evidence interpretation

Protein sequences come from `data/processed/tpa_pet_ml_confirmed.csv`; UniProt accessions and PDB links come from `master_dataset.csv`. Evidence is joined by UniProt accession to `data/fireprotdb/model_protein_mutations.csv`, not by protein name alone. Accession matching and residue-letter checks do not establish source sequence identity. The extract lacks the source sequences, measurement unit fields and sign definitions, so the interface retains raw measurement strings and points to source DOIs without interpreting their direction. No DDG values are present in the current ten-record extract.

Missing evidence is distinct from an unavailable extract. The absence of a local record does not establish absence from the published literature.

## Structure mapping contract

The parser follows the [wwPDB coordinate-column specification](https://www.wwpdb.org/documentation/file-format-content/format33/sect9.html) for the fields used here. It reads ATOM C-alpha coordinates in the first model, preserving chain ID, residue number and insertion code. Alternate locations use the greatest occupancy, with ties resolved by blank then lexical alternate-location ID. Non-finite coordinates and alternate residue identities are rejected. HETATM records are excluded; this is a protein backbone context viewer, not a ligand/docking tool.

Mapping requires a **unique exact contiguous match of at least ten observed residues** within the reference sequence. This supports a resolved mature chain with omitted termini without confusing PDB numbering and full-sequence numbering. Internal missing residues, sequence substitutions, nonstandard residues, and ambiguous repeated fragments can result in unresolved mapping. The trace remains viewable, but no reference position is assigned in that case. Gapped alignment, mmCIF, energy calculations, docking and mutation-effect prediction are not implemented.

Coverage is the mapped observed C-alpha residue count divided by reference length, not confidence. B-factors remain uninterpreted raw fields. Neighborhood distances are C-alpha distances within 8 angstroms, including sequential neighbors; they are not atom contacts. The viewer leaves consecutive C-alpha pairs more than 4.5 angstroms apart disconnected. The response includes a SHA-256 digest of the UTF-8 PDB text received by the API.

Limits: 2,000,000 characters per API PDB input (browser file limit: 2,000,000 bytes), 5,000 observed C-alpha residues, and 20 substitutions per preview.

## API

| Method | Endpoint | Input / output |
|---|---|---|
| GET | `/api/mutation-proteins` | Confirmed protein catalog and source metadata |
| GET | `/api/mutations/{protein_id}/evidence` | Raw accession-matched records and evidence limitations |
| POST | `/api/mutations/preview` | `protein_id`, `substitutions`; validated edits and mutant sequence |
| POST | `/api/structures/inspect` | `protein_id`, `pdb_text`, optional `chain_id`, optional integer `position` |

An omitted chain on a multichain PDB returns `select_chain`. A blank chain identifier is represented by the empty string, separately from an omitted (`null`) chain. Unknown proteins return 404; invalid inputs return 422; inaccessible local evidence files return 503. An absent FireProtDB extract produces an explicit `unavailable` evidence state.

Start the existing environment from the project root:

```powershell
.\.venv\Scripts\python.exe -B -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

The full application still loads its existing ESM encoder and legacy model on startup. The new router itself has no model-loading dependency. On this host the documented `.venv` requires execution outside the tool sandbox; `.venv-1` is not a substitute and lacks FastAPI.

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Nine new tests cover real catalog/evidence, combined variants, invalid edits, first-model selection, alternate locations, insertion codes, ambiguous/short/mismatched mapping, unobserved sites, malformed coordinates, API limits and errors. Synthetic coordinate fixtures are used only for edge cases; they are not experimental data.

Real browser verification used [RCSB PDB 1TCA](https://www.rcsb.org/structure/1TCA), downloaded to a temporary file from `https://files.rcsb.org/download/1TCA.pdb`. Chain A has 317 observed residues, mapped to CalB reference positions 26–342 (92.7% coverage). Reference V235 maps to PDB V210. Text SHA-256: `8950b5f7a08c6e8be8506de6af728ec7c28583aa28362cb7886726f757d70d56`. Browser checks also verified the incorrect `A235I` error and successful `V235I, A306E` preview.

Existing scikit-learn artifact/runtime compatibility warnings remain visible. These modules do not resolve legacy model lineage or establish scientifically validated mutation effects.

Final checks: all 13 tests passed (nine new, four existing preservation/integration checks); frontend lint and production build passed; `git diff --check` passed. The downloaded 342-residue FASTA matched the validated double variant. Browser rotation and narrow-screen layout were checked, with no horizontal overflow or browser console errors observed.

## Viewer refinement, 2026-10-12

The default display is now a smooth, depth-colored backbone tube drawn on a high-resolution canvas. Sequence coloring runs from blue at the observed N terminus toward gold at the observed C terminus. Drag or arrow keys rotate; zoom, selected-site focus, reset, raw C-alpha trace mode and PNG export are available. Hover reveals coordinate and reference residue labels.

Catmull–Rom interpolation is used only for drawing connected C-alpha segments. Original coordinates and distances are unchanged, and gaps greater than 4.5 angstroms are not interpolated across. This view does not assign helices/sheets, generate mutant structures, or relax atomic coordinates. `node tests/test_structure_geometry.mjs` verifies interpolation endpoints, gap preservation and unchanged source coordinates.

The separate model-selection study is documented in [the nested evaluation report](../reports/results/nested_improvement_20261012T152329Z/README.md). Smoothing the drawing is independent of prediction error. No model was promoted to the live predictor.
