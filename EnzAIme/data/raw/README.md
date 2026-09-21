# data/raw/

This directory holds **unmodified, original source files** as identified in the
project data-collection phase. Nothing in this folder is ever overwritten by
the pipeline (Section 19).

## Expected files (per project inventory)

| File | Source | Status in this MVP package |
|---|---|---|
| `pazy_proteins.fasta` | PAZy (Plastics-Active enZymes) | See `data/raw/pazy/` — MVP includes a curated subset derived from verified PAZy-listed, literature-characterized plastic-active enzymes (see `data/processed/enzymes.csv` `source` column). |
| `new_release_structure_sequence.tsv` | PDB structure/sequence release | Placeholder — drop the real TSV here; `scripts/01_inspect_data.py` will read it if present. |
| `rcsb_pdb_7CWQ.fasta` | RCSB PDB | Placeholder — drop real PDB FASTA exports here; used only after biological annotation/filtering per Section 5. |
| `uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz` | UniProt | **Explicitly excluded from the enzyme recommendation dataset.** This file's ~12 sequences are tRNA dimethylallyltransferases and are NOT plastic-degrading enzymes (Section 5). Kept here for provenance only; the pipeline never reads it into `enzymes.csv`. |

## Why this MVP does not ship your original files

This packaged MVP was assembled without direct access to your uploaded
lab/project files (no `uploaded_files` were attached in the conversation that
produced this package). To keep the system **honest and fully functional**,
the shipped dataset (`data/demo/enzymes_demo.csv`, promoted to
`data/processed/enzymes.csv` by `scripts/03_build_master_dataset.py`) was
built instead from independently verified, citable public records
(UniProt accessions, EC numbers, primary literature) for well-characterized
plastic-active enzymes — see `data/demo/SOURCES.md` for full citations.

**To use your real files:** copy them into this directory using the exact
names above, then run the pipeline from `scripts/01_inspect_data.py` onward.
The abstraction layer (`common/enzaime_core/data_loader.py`) and each script
were written so that dropping in real PAZy/BRENDA/UniProt/FireProtDB/
wastewater files requires **no code changes** — only re-running the scripts.
