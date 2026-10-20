"""Mutation/structure endpoints deliberately independent of model loading."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.mutation import protein_catalog, preview_mutations, mutation_evidence
from backend.app.services.structure import inspect_structure

router = APIRouter()


class MutationRequest(BaseModel):
    protein_id: str = Field(min_length=1, max_length=30)
    substitutions: str = Field(min_length=1, max_length=500)


class StructureRequest(BaseModel):
    protein_id: str = Field(min_length=1, max_length=30)
    pdb_text: str = Field(min_length=1, max_length=2_000_000)
    chain_id: str | None = Field(default=None, max_length=1)
    position: int | None = Field(default=None, ge=1, le=100_000, strict=True)


def checked_call(function, *args):
    try:
        return function(*args)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=503, detail="Local evidence files are unavailable.") from error


@router.get("/mutation-proteins")
def proteins():
    return {"proteins": checked_call(lambda: list(protein_catalog().values()))}


@router.get("/mutations/{protein_id}/evidence")
def evidence(protein_id: str):
    return checked_call(mutation_evidence, protein_id)


@router.post("/mutations/preview")
def preview(request: MutationRequest):
    return checked_call(preview_mutations, request.protein_id, request.substitutions)


@router.post("/structures/inspect")
def structure(request: StructureRequest):
    return checked_call(inspect_structure, request.protein_id, request.pdb_text, request.chain_id, request.position)
