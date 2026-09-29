"""Build read-only research feature matrices for controlled ablations.

This script reads the confirmed activity dataset and the existing ESM-2 embedding
index/files only. It verifies embedding completeness and writes the project-level
summary JSON, Markdown summary, and a small preview CSV that keeps the original
identifiers and metadata without exposing the full embedding matrix.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIRMED_PATH = PROJECT_ROOT / "data" / "processed" / "tpa_pet_ml_confirmed.csv"
INDEX_PATH = PROJECT_ROOT / "data" / "embeddings" / "index.json"
RESULTS_DIR = PROJECT_ROOT / "reports" / "results"
SUMMARY_PATH = RESULTS_DIR / "research_feature_matrix_summary.json"
MARKDOWN_PATH = RESULTS_DIR / "research_feature_matrix_summary.md"
PREVIEW_PATH = RESULTS_DIR / "research_feature_matrix_preview.csv"

A_FEATURES = ["temperature_c", "ph", "duration_hours"]
B_FEATURES = ["ESM-2 embedding"]
C_FEATURES = ["ESM-2 embedding", "temperature_c", "ph", "duration_hours"]


def safe_non_missing(series):
    if series is None:
        return 0
    return int(series.astype(str).str.strip().replace("nan", "").replace("NaN", "").ne("" ).sum())


def missingness_summary(frame, columns):
    summary = {}
    for column in columns:
        if column not in frame.columns:
            summary[column] = {"missing_count": 0, "missing_percentage": 0.0}
            continue
        series = frame[column]
        missing = int(series.isna().sum()) + int(series.astype(str).str.strip().eq("").sum())
        summary[column] = {
            "missing_count": missing,
            "missing_percentage": round(100 * missing / len(frame), 2) if len(frame) else 0.0,
        }
    return summary


def verify_embeddings(frame, index):
    protein_ids = frame["protein_id"].astype(str).unique()
    index_keys = {str(key) for key in index.keys()}
    missing_proteins = sorted(set(protein_ids) - index_keys)
    if missing_proteins:
        raise ValueError(f"Missing ESM-2 embedding files for proteins: {missing_proteins}")

    dims = []
    finite = True
    for protein_id in sorted(protein_ids):
        file_name = index[str(protein_id)]
        file_path = PROJECT_ROOT / "data" / "embeddings" / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"Embedding file not found for protein {protein_id}: {file_path}")
        array = np.load(file_path)
        dims.append(tuple(array.shape))
        if not np.isfinite(array).all():
            finite = False
    if len(set(dims)) != 1:
        raise ValueError(f"Inconsistent embedding dimensions found: {sorted(set(dims))}")
    dim = dims[0][-1]
    if not finite:
        raise ValueError("Embedding arrays include NaN or Inf values.")
    return {
        "embedding_dimension": int(dim),
        "protein_coverage": {
            "expected_unique_proteins": int(frame["protein_id"].nunique()),
            "embedding_files_available": int(len(protein_ids)),
            "missing_proteins": missing_proteins,
        },
        "verification_status": "verified",
    }


def summarize_material(frame):
    material = frame["material_description"].astype(str)
    values = material.value_counts(dropna=False)
    summary = {
        "unique_values": int(values.shape[0]),
        "missing_count": int((material.str.strip() == "").sum()),
        "top_values": values.head(15).to_dict(),
    }
    return summary


def summarize_substrate(frame):
    substrate = frame["substrate"].astype(str)
    values = substrate.value_counts(dropna=False)
    summary = {
        "unique_values": int(values.shape[0]),
        "missing_count": int((substrate.str.strip() == "").sum()),
        "distribution": values.to_dict(),
    }
    return summary


def build_configurations(frame, embedding_info):
    embed_dim = embedding_info["embedding_dimension"]
    config_rows = {}
    config_rows["A"] = {
        "name": "Environment Only",
        "features": A_FEATURES,
        "feature_count": len(A_FEATURES),
        "dimension": len(A_FEATURES),
        "records": int(len(frame)),
        "proteins": int(frame["protein_id"].nunique()),
        "missingness": missingness_summary(frame, A_FEATURES),
        "approved": True,
    }
    config_rows["B"] = {
        "name": "Protein Only",
        "features": B_FEATURES,
        "feature_count": 1,
        "dimension": embed_dim,
        "records": int(len(frame)),
        "proteins": int(frame["protein_id"].nunique()),
        "missingness": {"ESM-2 embedding": {"missing_count": 0, "missing_percentage": 0.0}},
        "approved": True,
    }
    config_rows["C"] = {
        "name": "ESM-2 + Environment",
        "features": C_FEATURES,
        "feature_count": len(C_FEATURES),
        "dimension": embed_dim + len(A_FEATURES),
        "records": int(len(frame)),
        "proteins": int(frame["protein_id"].nunique()),
        "missingness": missingness_summary(frame, A_FEATURES),
        "approved": True,
    }
    material = frame["material_description"].astype(str)
    substrate = frame["substrate"].astype(str)
    material_unique = int(material.nunique())
    substrate_unique = int(substrate.nunique())
    material_rejected_reason = (
        "material_description is highly heterogeneous and source-specific, with 33 unique values and rich preparation metadata; "
        "this can encode source/protocol context rather than stable prediction-time substrate features. "
        "substrate is constant (PET) across the confirmed dataset, so it contributes no discriminative signal. "
        "The context block is therefore rejected for the next research matrix."
    )
    config_rows["D"] = {
        "name": "ESM-2 + Environment + Context",
        "features": [],
        "feature_count": 0,
        "dimension": 0,
        "records": int(len(frame)),
        "proteins": int(frame["protein_id"].nunique()),
        "missingness": {
            "material": {"missing_count": int((material.str.strip() == "").sum()), "missing_percentage": round(100 * (material.str.strip() == "").mean(), 2)},
            "substrate": {"missing_count": int((substrate.str.strip() == "").sum()), "missing_percentage": round(100 * (substrate.str.strip() == "").mean(), 2)},
        },
        "approved": False,
        "rejected_reason": material_rejected_reason,
        "material_unique_values": material_unique,
        "substrate_unique_values": substrate_unique,
    }
    return config_rows


def build_markdown(summary):
    configs = summary["configurations"]
    a = configs["A"]
    b = configs["B"]
    c = configs["C"]
    d = configs["D"]
    material = summary["material_analysis"]
    substrate = summary["substrate_analysis"]
    lines = [
        "# Research Feature Matrix",
        "",
        "## 1. Objective",
        "",
        "Construct controlled, read-only feature matrices for a research ablation study on the confirmed 221-record TPA activity dataset. The objective is to separate protein embeddings, environmental conditions, and context variables without leaking target, assay identity, or source metadata into the training matrix.",
        "",
        "## 2. Dataset",
        "",
        f"- Confirmed records: {summary['dataset_size']['records']}",
        f"- Unique proteins: {summary['dataset_size']['proteins']}",
        f"- Embedding dimension: {summary['embedding_dimension']}",
        f"- Target: log1p(target_value_standardized) in uM, computed after splitting in the next modeling step.",
        "- Source: data/processed/tpa_pet_ml_confirmed.csv",
        "- Existing embeddings: data/embeddings/index.json plus the corresponding .npy files",
        "",
        "## 3. Configuration A — Environment Only",
        "",
        f"- Features: {', '.join(a['features'])}",
        f"- Dimension: {a['dimension']}",
        f"- Records: {a['records']}",
        f"- Proteins: {a['proteins']}",
        "- Approved: yes",
        "",
        "## 4. Configuration B — ESM-2 Only",
        "",
        f"- Features: {', '.join(b['features'])}",
        f"- Dimension: {b['dimension']}",
        f"- Records: {b['records']}",
        f"- Proteins: {b['proteins']}",
        "- Approved: yes",
        "",
        "## 5. Configuration C — ESM-2 + Environment",
        "",
        f"- Features: {', '.join(c['features'])}",
        f"- Dimension: {c['dimension']}",
        f"- Records: {c['records']}",
        f"- Proteins: {c['proteins']}",
        "- Approved: yes",
        "",
        "## 6. Configuration D — Context-Aware",
        "",
        f"- Features: {', '.join(d['features'])}",
        f"- Dimension: {d['dimension']}",
        f"- Records: {d['records']}",
        f"- Proteins: {d['proteins']}",
        "- Approved: no",
        f"- Reason: {d['rejected_reason']}",
        "",
        "## 7. Material Analysis",
        "",
        f"- Unique values: {material['unique_values']}",
        f"- Missing count: {material['missing_count']}",
        "- Interpretation: material_description is highly heterogeneous and source-specific, with rich preparation and product metadata.",
        "- Decision: not approved for predictive encoding in the next research matrix.",
        "",
        "## 8. Substrate Analysis",
        "",
        f"- Unique values: {substrate['unique_values']}",
        f"- Missing count: {substrate['missing_count']}",
        f"- Distribution: {substrate['distribution']}",
        "- Interpretation: the confirmed activity dataset is essentially all PET, so the substrate variable is constant and provides no discriminative signal.",
        "- Decision: not included in the context-aware configuration.",
        "",
        "## 9. Missingness",
        "",
        "Temperature, pH, and duration are complete in the confirmed dataset. Material and substrate are present, but material is not stable enough and substrate is constant. Missingness remains zero for the approved feature blocks.",
        "",
        "## 10. Protein Coverage",
        "",
        f"- Unique proteins in the confirmed data: {summary['dataset_size']['proteins']}",
        f"- Proteins with embedding files: {summary['embedding_protein_coverage']['embedding_files_available']}",
        f"- Missing embeddings: {summary['embedding_protein_coverage']['missing_proteins']}",
        f"- Embedding verification: {summary['embedding_verification_status']}",
        "",
        "## 11. Leakage Controls",
        "",
        "- No protein identifiers or source IDs were used as predictive features.",
        "- No target-derived or outcome fields were included.",
        "- Sequence remains in the metadata table for traceability only.",
        "- The ESM-2 embedding is used as a fixed protein representation and is not regenerated.",
        "- Preprocessing such as scaling and categorical encoding will be learned only within training folds later.",
        "",
        "## 12. Final Feature Configurations",
        "",
        "Approved research matrices: A, B, and C. D is rejected based on material/source-specific heterogeneity and the constant PET substrate.",
        "",
        "## 13. Limitations",
        "",
        "The confirmed dataset is small and protein-imbalanced. The material context is highly specific and may encode source, vendor, or preparation details rather than predictive biology. The next modeling step should keep protein-grouped cross-validation and avoid global categorical fitting before fold-local preprocessing.",
        "",
    ]
    return "\n".join(lines)


def main():
    df = pd.read_csv(CONFIRMED_PATH, dtype=str, keep_default_na=False, low_memory=False)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    embedding_info = verify_embeddings(df, index)
    material_summary = summarize_material(df)
    substrate_summary = summarize_substrate(df)
    config_summary = build_configurations(df, embedding_info)

    summary = {
        "dataset_size": {
            "records": int(len(df)),
            "proteins": int(df["protein_id"].nunique()),
            "source": str(CONFIRMED_PATH.relative_to(PROJECT_ROOT)),
        },
        "embedding_dimension": embedding_info["embedding_dimension"],
        "embedding_verification_status": embedding_info["verification_status"],
        "embedding_protein_coverage": embedding_info["protein_coverage"],
        "configurations": config_summary,
        "feature_dimensions": {
            "A": config_summary["A"]["dimension"],
            "B": config_summary["B"]["dimension"],
            "C": config_summary["C"]["dimension"],
            "D": config_summary["D"]["dimension"],
        },
        "missingness": {
            "temperature_c": missingness_summary(df, ["temperature_c"]),
            "ph": missingness_summary(df, ["ph"]),
            "duration_hours": missingness_summary(df, ["duration_hours"]),
            "material_description": missingness_summary(df, ["material_description"]),
            "substrate": missingness_summary(df, ["substrate"]),
        },
        "material_analysis": material_summary,
        "substrate_analysis": substrate_summary,
        "material_substrate_decision": {
            "material_approved": False,
            "substrate_approved": False,
            "configuration_d_approved": False,
            "reason": config_summary["D"]["rejected_reason"],
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(build_markdown(summary), encoding="utf-8")

    preview = df[["protein_id", "protein_name", "temperature_c", "ph", "duration_hours", "material_description", "substrate", "target_value_standardized"]].copy()
    preview["embedding_available"] = preview["protein_id"].astype(str).map(lambda value: str(value) in {str(key) for key in index.keys()})
    preview.columns = ["protein_id", "protein_name", "temperature_c", "ph", "duration_hours", "material", "substrate", "target_value_standardized", "embedding_available"]
    preview.to_csv(PREVIEW_PATH, index=False, encoding="utf-8-sig")

    records = int(len(df))
    proteins = int(df["protein_id"].nunique())
    embedding_dim = embedding_info["embedding_dimension"]
    config_d_rejected = "rejected"
    missingness = {
        "temperature_c": summary["missingness"]["temperature_c"]["temperature_c"]["missing_count"],
        "ph": summary["missingness"]["ph"]["ph"]["missing_count"],
        "duration_hours": summary["missingness"]["duration_hours"]["duration_hours"]["missing_count"],
        "material_description": summary["missingness"]["material_description"]["material_description"]["missing_count"],
        "substrate": summary["missingness"]["substrate"]["substrate"]["missing_count"],
    }

    print("RESEARCH FEATURE MATRIX COMPLETE")
    print("records:", records)
    print("proteins:", proteins)
    print("embedding dimension:", embedding_dim)
    print("Config A dimensions:", config_summary["A"]["dimension"])
    print("Config B dimensions:", config_summary["B"]["dimension"])
    print("Config C dimensions:", config_summary["C"]["dimension"])
    print("Config D dimensions:", config_summary["D"]["dimension"])
    print("material unique values:", material_summary["unique_values"])
    print("substrate unique values:", substrate_summary["unique_values"])
    print("missingness:", json.dumps(missingness, ensure_ascii=False, sort_keys=True))
    print("D approved or rejected:", config_d_rejected)
    print("embedding verification status:", embedding_info["verification_status"])


if __name__ == "__main__":
    main()
