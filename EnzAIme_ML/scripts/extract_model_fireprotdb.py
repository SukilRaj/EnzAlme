import pandas as pd
from pathlib import Path

MASTER = Path("master_dataset.csv")
ML = Path("data/tpa_pet_ml_dataset.csv")
FIREPROT = Path("fireprotdb_20251015-164116.csv")
OUT = Path("data/fireprotdb/model_protein_mutations.csv")

OUT.parent.mkdir(parents=True, exist_ok=True)

# Load the 25 proteins used by the ML model
ml = pd.read_csv(
    ML,
    usecols=["protein_id", "protein_name"]
).drop_duplicates()

# Load UniProt mapping
master = pd.read_csv(
    MASTER,
    usecols=["protein_id", "protein_name", "uniprot_accessions"]
)

proteins = (
    ml.merge(
        master,
        on=["protein_id", "protein_name"],
        how="left"
    )
    .drop_duplicates()
)

# Build UniProt -> model protein mapping
accession_to_protein = {}

for _, row in proteins.iterrows():
    value = row["uniprot_accessions"]

    if pd.isna(value):
        continue

    for acc in str(value).split(";"):
        acc = acc.strip()

        if acc:
            accession_to_protein[acc] = row["protein_name"]

print("Model proteins:", len(proteins))
print("Unique UniProt accessions:", len(accession_to_protein))
print()
print("Searching FireProtDB...")
print()

matches = []

# Read the 5.46-million-row FireProtDB in chunks
for chunk_number, chunk in enumerate(
    pd.read_csv(
        FIREPROT,
        chunksize=100000,
        low_memory=False
    ),
    start=1
):

    values = chunk["UNIPROTKB"].astype("string").str.strip()

    hit = chunk[
        values.isin(accession_to_protein)
    ]

    if not hit.empty:

        hit = hit.copy()

        hit["model_protein_name"] = (
            hit["UNIPROTKB"].map(accession_to_protein)
        )

        matches.append(hit)

        print(
            "Chunk",
            chunk_number,
            "-> matched rows:",
            len(hit)
        )

# Combine matches
if matches:
    result = pd.concat(
        matches,
        ignore_index=True
    )
else:
    result = pd.DataFrame()

# Save extracted mutations
result.to_csv(
    OUT,
    index=False
)

print()
print("===================================")
print("FireProtDB extraction completed")
print("===================================")
print("Total matching rows:", len(result))
print("Saved to:", OUT)

if not result.empty:
    print()
    print("Matches by model protein:")
    print(
        result["model_protein_name"]
        .value_counts()
        .to_string()
    )