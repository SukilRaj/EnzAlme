from functools import lru_cache
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from backend.app.services.neural_recommender import NeuralRecommender, explain_with_ollama

router = APIRouter(prefix="/neural", tags=["Neural research"])


class NeuralRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    temperature: float
    ph: float = Field(ge=0, le=14)
    duration: float = Field(gt=0)
    top_n: int = Field(default=5, ge=1, le=10)
    explain: bool = False
    objective: Literal['activity', 'joint'] = 'activity'


class AttributionRequest(NeuralRequest):
    protein_id: str = Field(min_length=1, max_length=30)


@lru_cache(maxsize=1)
def service():
    return NeuralRecommender()


@router.get("/status")
def status():
    try:
        model = service()
        return {"status": "research_checkpoint_loaded", "image_trained": model.meta["image_trained"],
                "thermostability_ready": model.stability is not None, "test_metrics": model.meta["test_metrics"]}
    except (FileNotFoundError, ValueError, KeyError, RuntimeError, OSError) as error:
        return {"status": "training_required", "detail": str(error), "thermostability_ready": False}


@router.post("/recommend")
def recommend(request: NeuralRequest):
    try:
        result = service().recommend(request.temperature, request.ph, request.duration, request.top_n, request.objective)
    except FileNotFoundError as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, KeyError, RuntimeError, OSError) as error:
        raise HTTPException(422, str(error)) from error
    if request.explain:
        try:
            result["llm_explanation"] = explain_with_ollama(result)
        except (OSError, ValueError, KeyError, RuntimeError) as error:
            result["llm_explanation"] = {"status": "unavailable", "detail": str(error)}
    return result


@router.get("/llm/status")
def llm_status():
    from backend.app.services.local_llm import health
    return health()


@router.post('/attribution')
def attribution(request: AttributionRequest):
    try:
        return service().attribution(request.protein_id, request.temperature, request.ph, request.duration)
    except FileNotFoundError as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, KeyError, RuntimeError, OSError) as error:
        raise HTTPException(422, str(error)) from error


@router.post("/explain")
def explain(request: NeuralRequest):
    # Recompute trusted evidence: client-provided prose never becomes the source of scores.
    try:
        evidence = service().recommend(request.temperature, request.ph, request.duration, request.top_n, request.objective)
        return explain_with_ollama(evidence)
    except (FileNotFoundError, RuntimeError, OSError) as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, KeyError) as error:
        raise HTTPException(422, str(error)) from error
