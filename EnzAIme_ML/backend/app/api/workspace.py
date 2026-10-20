"""Workspace health, data readiness and saved evaluation."""
import csv
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from backend.app.api.neural import status as model_status
from backend.app.services.local_llm import health as llm_health

ROOT = Path(__file__).resolve().parents[3]
router = APIRouter()


def read_manifest(relative):
    path = ROOT / relative
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


@router.get("/health")
def health():
    return {"status": "ok", "service": "EnzAIme research workspace", "version": "2.0.0"}


@router.get("/workspace/status")
def status():
    return {"activity": model_status(), "ollama": llm_health(),
            "stability_data": read_manifest("data/stability/manifest.json"),
            "stability_model": read_manifest("models/stability/manifest.json"),
            "structure_data": read_manifest("data/structure_images/manifest.json")}


@router.get("/workspace/evaluation")
def evaluation():
    return {"activity": read_manifest("models/neural/manifest.json"),
            "activity_review": model_status().get('test_metrics'),
            "held_out_predictions": read_manifest("models/neural/held_out_predictions.json") or [],
            "stability": read_manifest("models/stability/manifest.json")}


@router.get("/workspace/data")
def data():
    csv.field_size_limit(10_000_000)
    with (ROOT / "data/processed/tpa_pet_ml_confirmed.csv").open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    return {"activity": {"records": len(records), "proteins": len({r["protein_id"] for r in records}),
            "target": "Measured TPA concentration (µM)", "source": "Confirmed PAZy PET/TPA evidence"},
            "stability": read_manifest("data/stability/manifest.json"),
            "structures": read_manifest("data/structure_images/manifest.json")}


@router.get("/stability/evidence/{protein_id}")
def stability_evidence(protein_id: str):
    from backend.app.services.mutation import get_protein
    try:
        protein = get_protein(protein_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    records = read_manifest("data/stability/records.json") or []
    matches = [r for r in records if r["sequence"] == protein["sequence"]]
    return {"protein_id": protein_id, "matching": "exact amino-acid sequence",
            "records": [{k: v for k, v in r.items() if k != "sequence"} for r in matches],
            "note": "Measured Tm evidence, not a prediction. Assay conditions and constructs require review."}


def verified_structure(protein_id):
    from backend.app.services.structure import inspect_structure
    manifest = read_manifest('data/structure_images/manifest.json') or {}
    entry = next((r for r in manifest.get('matched', []) if r['protein_id'] == protein_id), None)
    if entry is None or not protein_id.isdecimal():
        raise HTTPException(404, 'No sequence-verified structure is available for this protein. You can inspect a PDB file instead.')
    text = (ROOT / f'data/structure_images/pdb/{protein_id}.pdb').read_text()
    checked = inspect_structure(protein_id, text)
    if checked['status'] != 'mapped' or checked.get('coverage') != 1:
        raise HTTPException(409, 'The cached structure no longer matches the full protein sequence.')
    return entry, text, checked


@router.get('/structures/catalog/{protein_id}')
def catalog_structure(protein_id: str):
    entry, text, checked = verified_structure(protein_id)
    return {'pdb_text':text,'provenance':entry,'inspection':checked,
            'image_url':f'/api/structures/catalog/{protein_id}/image'}


@router.get('/structures/catalog/{protein_id}/image')
def catalog_image(protein_id: str):
    verified_structure(protein_id)
    return FileResponse(ROOT/f'data/structure_images/views/{protein_id}_distance.png', media_type='image/png')
