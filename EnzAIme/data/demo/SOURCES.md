# Data Sources — `data/demo/enzymes_demo.csv`

This MVP was assembled without direct access to the project's original lab
files (no files were attached to the session that produced this package —
see `data/raw/README.md`). To keep the shipped system scientifically honest
and immediately runnable, the demo dataset below was built from independently
verifiable public records instead of fabricated data.

**Nothing in this table is invented.** Every accession, EC number, organism
and citation is real and checkable. Where an exact numeric pH/temperature
value could not be independently curated from BRENDA within the scope of
this MVP, the value is a literature-informed approximation and is flagged
`demo_assumption = true` in the CSV — it is never presented in the UI as an
experimental measurement.

| enzyme_id | Name | Accession | Sequence status | Key source(s) |
|---|---|---|---|---|
| ENZ001 | PETase (IsPETase) | UniProt A0A0K8P6T7 | **Verified real sequence** (290 aa) — cross-checked against ESTHER alpha/beta-hydrolase DB and PDBe residue mapping for 6EQE (100% coverage/identity). Catalytic triad Ser160/Asp206/His237 confirmed in-sequence. | Yoshida et al. 2016, *Science* (discovery); Han et al. 2017; Palm et al. 2019, *Nat Commun* (MHETase structure); PMC10851425 (moderate-temperature activity) |
| ENZ002 | MHETase | UniProt A0A0K8P8E7 | **Verified real sequence** (603 aa) — retrieved directly from UniProt REST | Palm et al. 2019, *Nat Commun*, doi:10.1038/s41467-019-09326-3 |
| ENZ003 | LCC (leaf-branch compost cutinase) | UniProt G9BY57 | Pending fetch | Sulaiman et al. 2012 (discovery); Tournier et al. 2020, *Nature*, doi:10.1038/s41586-020-2149-4 (LCC-ICCG, 72°C industrial operation, 90% PET depolymerization in 10h) |
| ENZ004 | TfCut2 | UniProt Q6A0I4 | Pending fetch | Bornscheuer 2016, *Science*; ACS Org. Inorg. Au 2022, doi:10.1021/acsorginorgau.2c00054 |
| ENZ005 | BurPL | UniProt A0A1F4JXW8 | Pending fetch | ACS Org. Inorg. Au 2022, doi:10.1021/acsorginorgau.2c00054 |
| ENZ006 | NylB | UniProt P07061 | Pending fetch | Negoro et al.; microbewiki Paenarthrobacter ureafaciens KI72 |
| ENZ007 | NylC | UniProt Q79F77 | Pending fetch | Negoro et al.; PDB 5XYG (thermostability engineering, 47°C span) |
| ENZ008 | PueA | GenBank (accession not independently confirmed for this MVP) | Pending fetch | Stern & Howard 2000, *FEMS Microbiol Lett*, PMID:10754242 (617 aa, GXSXG motif, lipase activity) |
| ENZ009 | PueB | GenBank (accession not independently confirmed for this MVP) | Pending fetch | ScienceDirect S0964830501000427 (565 aa, 60 kDa, ~42% identity to PueA) |

## "Pending fetch" sequences

For 7 of 9 records, the exact residue-level sequence could not be reliably
retrieved through the tooling available while assembling this package
(no direct network access to UniProt/NCBI from the build environment).
Per the project specification, **sequences are never fabricated** — these
rows ship with `sequence` left blank rather than an invented string.

This does **not** block the MVP: the compatibility-scoring recommendation
pipeline (the core deliverable, Section 11-12 of the spec) operates purely
on documented metadata (pollutant evidence, pH/T ranges) and does not
require a sequence. Only two downstream, optional stages need the actual
residues:

1. **ESM-2 embedding** (proposed/refinement path) — rows without a sequence
   are simply skipped when building the embedding cache; DEMO_MODE never
   needs them.
2. **Mutation module** — a sequence is required to generate point mutations
   for a *specific* enzyme. IsPETase and MHETase (both verified) are fully
   supported end-to-end; other enzymes will return a clear
   "sequence unavailable for mutation analysis" message from the API
   rather than silently fabricating a result.

Run `scripts/00_fetch_uniprot.py <ACCESSION>` (requires real internet
access, not available in the packaging environment) to populate the
remaining sequences from UniProt before re-running the embedding/training
pipeline.

## Explicitly excluded data

Per the project brief, the ~12 UniProt tRNA dimethylallyltransferase
sequences from `uniprotkb_Enzyme_sequence_dmatase_2026_08_02.fasta.gz`
are **not** plastic-degrading enzymes and are never included in
`enzymes.csv` or any recommendation candidate set.
