"""
backend/app/main.py
======================
ENZAIme FastAPI application.

Endpoints (Section 23-24):
  GET  /health
  GET  /enzymes
  POST /recommend
  GET  /enzyme/{enzyme_id}
  POST /mutations
  GET  /metadata
  POST /reload-model

Run locally:
  uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Make the shared core package importable when running via
# `uvicorn backend.app.main:app` from the repo root, and also add the repo
# root itself so `import app.xxx` (used inside backend/app/*) resolves.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "common"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from enzaime_core import config as core_config
from enzaime_core import data_loader

from app import schemas
from app.config import APP_NAME, APP_VERSION, APP_DESCRIPTION
from app.services import recommendation_service, mutation_service, simulation_service
from app.services.model_service import get_model_service
from app.utils.logging_config import setup_logging

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.time()
    try:
        df = data_loader.load_enzyme_table()
        logger.info("Startup: loaded %d enzyme records from %s", len(df), data_loader.get_data_source())
    except Exception as e:
        logger.error("Startup: FAILED to load enzyme dataset: %s", e)

    ms = get_model_service()
    logger.info("Startup: model service ready in scoring_mode=%s (%.3fs total)",
                ms.scoring_mode, time.time() - t0)
    yield
    logger.info("Shutdown: ENZAIme API stopping.")


app = FastAPI(title=APP_NAME, version=APP_VERSION, description=APP_DESCRIPTION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=core_config.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean_validation_errors(errors):
    import math

    def _sanitize(v):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return str(v)  # "nan" / "inf" / "-inf" -> safe, JSON-compliant string
        if isinstance(v, dict):
            return {k: _sanitize(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_sanitize(x) for x in v]
        return v

    def _clean(err):
        e = dict(err)
        e.pop("ctx", None)  # ctx can hold non-JSON-serializable exception objects
        return _sanitize(e)

    return [_clean(e) for e in errors]


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": _clean_validation_errors(exc.errors())})


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": _clean_validation_errors(exc.errors())})


# --------------------------------------------------------------------------
# GET /health
# --------------------------------------------------------------------------
@app.get("/health", response_model=schemas.HealthResponse)
def health():
    ms = get_model_service()
    try:
        df = data_loader.load_enzyme_table()
        n = len(df)
        status = "ok"
    except Exception as e:
        logger.error("Health check: dataset load failed: %s", e)
        n = 0
        status = "degraded"
    return schemas.HealthResponse(
        status=status, demo_mode=(ms.scoring_mode != "ai_model"),
        model_loaded=ms.model is not None, n_enzymes_loaded=n,
    )


# --------------------------------------------------------------------------
# GET /enzymes
# --------------------------------------------------------------------------
@app.get("/enzymes", response_model=list[schemas.EnzymeSummary])
def list_enzymes(pollutant: str | None = None):
    df = data_loader.load_enzyme_table()
    if pollutant:
        pollutant = pollutant.strip().upper()
        if pollutant not in core_config.SUPPORTED_POLLUTANTS:
            raise HTTPException(status_code=400, detail=f"Unsupported pollutant '{pollutant}'.")
        df = df[df["pollutant"].astype(str).str.upper() == pollutant]

    out = []
    for _, row in df.iterrows():
        seq = _none_if_nan(row.get("sequence"))
        out.append(schemas.EnzymeSummary(
            enzyme_id=str(row["enzyme_id"]), enzyme_name=str(row["enzyme_name"]),
            accession=_none_if_nan(row.get("accession")), ec_number=_none_if_nan(row.get("ec_number")),
            pollutant=_none_if_nan(row.get("pollutant")), evidence_type=_none_if_nan(row.get("evidence_type")),
            has_sequence=isinstance(seq, str) and len(seq) > 0,
            demo_assumption=_parse_bool(row.get("demo_assumption")),
        ))
    return out


# --------------------------------------------------------------------------
# GET /enzyme/{enzyme_id}
# --------------------------------------------------------------------------
@app.get("/enzyme/{enzyme_id}", response_model=schemas.EnzymeDetail)
def get_enzyme(enzyme_id: str):
    row = data_loader.get_enzyme_by_id(enzyme_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No enzyme found with enzyme_id='{enzyme_id}'.")

    seq = _none_if_nan(row.get("sequence"))
    has_seq = isinstance(seq, str) and len(seq) > 0
    seq_len = _none_if_nan(row.get("seq_length"))
    if seq_len is not None:
        try:
            seq_len = int(seq_len)
        except (ValueError, TypeError):
            seq_len = None

    return schemas.EnzymeDetail(
        enzyme_id=str(row["enzyme_id"]),
        enzyme_name=str(row["enzyme_name"]),
        accession=_none_if_nan(row.get("accession")),
        ec_number=_none_if_nan(row.get("ec_number")),
        pollutant=_none_if_nan(row.get("pollutant")),
        sequence=seq if has_seq else None,
        seq_length=seq_len,
        source=_none_if_nan(row.get("source")),
        evidence_type=_none_if_nan(row.get("evidence_type")),
        pH_opt=_none_if_nan(row.get("pH_opt")),
        pH_min=_none_if_nan(row.get("pH_min")),
        pH_max=_none_if_nan(row.get("pH_max")),
        T_opt=_none_if_nan(row.get("T_opt")),
        T_min=_none_if_nan(row.get("T_min")),
        T_max=_none_if_nan(row.get("T_max")),
        salinity_evidence=_parse_bool(row.get("salinity_evidence")),
        salinity_min=_none_if_nan(row.get("salinity_min")),
        salinity_max=_none_if_nan(row.get("salinity_max")),
        notes=_none_if_nan(row.get("notes")),
        demo_assumption=_parse_bool(row.get("demo_assumption")),
        has_sequence=has_seq,
        mutation_analysis_available=has_seq,
    )


# --------------------------------------------------------------------------
# POST /recommend
# --------------------------------------------------------------------------
@app.post("/recommend", response_model=schemas.RecommendResponse)
def recommend(payload: schemas.RecommendRequest):
    ms = get_model_service()
    try:
        result = recommendation_service.get_recommendations(
            pollutant=payload.pollutant, ph=payload.ph, temperature=payload.temperature,
            salinity=payload.salinity, model_service=ms,
        )
    except Exception as e:
        logger.exception("recommend: unexpected error")
        raise HTTPException(status_code=500, detail=f"Internal error while generating recommendations: {e}")

    return schemas.RecommendResponse(
        query=payload,
        scoring_mode=result["scoring_mode"],
        demo_mode=(result["scoring_mode"] != "ai_model"),
        recommendations=result["recommendations"],
        n_candidates_evaluated=result["n_candidates_evaluated"],
        n_candidates_with_pollutant_evidence=result["n_candidates_with_pollutant_evidence"],
        disclaimer=recommendation_service.DISCLAIMER,
    )


# --------------------------------------------------------------------------
# POST /mutations
# --------------------------------------------------------------------------
@app.post("/mutations", response_model=schemas.MutationResponse)
def mutations(payload: schemas.MutationRequest):
    try:
        result = mutation_service.analyze_mutations(
            enzyme_id=payload.enzyme_id, max_mutations=payload.max_mutations, top_n=payload.top_n
        )
    except mutation_service.EnzymeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except mutation_service.SequenceUnavailableError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("mutations: unexpected error")
        raise HTTPException(status_code=500, detail=f"Internal error while analyzing mutations: {e}")

    return schemas.MutationResponse(**result)


# --------------------------------------------------------------------------
# GET /metadata
# --------------------------------------------------------------------------
@app.get("/metadata", response_model=schemas.MetadataResponse)
def metadata():
    ms = get_model_service()
    try:
        df = data_loader.load_enzyme_table()
        n = len(df)
        source = data_loader.get_data_source()
    except Exception:
        n, source = 0, "unavailable"

    return schemas.MetadataResponse(
        app_name=APP_NAME, app_version=APP_VERSION,
        demo_mode=(ms.scoring_mode != "ai_model"), scoring_mode=ms.scoring_mode,
        model_name=core_config.MODEL_NAME, device=ms.device,
        supported_pollutants=core_config.SUPPORTED_POLLUTANTS, weights=core_config.WEIGHTS,
        n_enzymes_loaded=n, data_source=source,
    )


# --------------------------------------------------------------------------
# POST /reload-model
# --------------------------------------------------------------------------
@app.post("/reload-model")
def reload_model():
    ms = get_model_service()
    status = ms.reload()
    data_loader.load_enzyme_table(force_reload=True)
    logger.info("Model/data reloaded via /reload-model: %s", status)
    return {"reloaded": True, **status}


# --------------------------------------------------------------------------
# POST /simulate
# --------------------------------------------------------------------------
@app.post("/simulate", response_model=schemas.SimulateResponse)
def simulate(payload: schemas.SimulateRequest):
    ms = get_model_service()
    try:
        result = simulation_service.simulate_enzyme(
            enzyme_id=payload.enzyme_id,
            pollutant=payload.pollutant,
            ph=payload.ph,
            temperature=payload.temperature,
            salinity=payload.salinity,
            model_service=ms,
        )
    except simulation_service.EnzymeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("simulate: unexpected error")
        raise HTTPException(status_code=500, detail=f"Internal error during simulation: {e}")

    return schemas.SimulateResponse(**result)


# --------------------------------------------------------------------------
# POST /simulate/sweep
# --------------------------------------------------------------------------
@app.post("/simulate/sweep", response_model=list[schemas.SimulateSweepPoint])
def simulate_sweep(payload: schemas.SimulateSweepRequest):
    ms = get_model_service()
    try:
        points = simulation_service.simulate_sweep(
            enzyme_id=payload.enzyme_id,
            pollutant=payload.pollutant,
            sweep_variable=payload.sweep_variable,
            sweep_min=payload.sweep_min,
            sweep_max=payload.sweep_max,
            steps=payload.steps,
            fixed_ph=payload.fixed_ph,
            fixed_temperature=payload.fixed_temperature,
            fixed_salinity=payload.fixed_salinity,
            model_service=ms,
        )
    except simulation_service.EnzymeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("simulate/sweep: unexpected error")
        raise HTTPException(status_code=500, detail=f"Internal error during sweep simulation: {e}")

    return points


def _none_if_nan(v):
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except Exception:
        pass
    try:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, str) and v.strip().lower() in {"nan", "none", "null", ""}:
        return None
    return v


def _parse_bool(v):
    if v is None:
        return None
    try:
        import pandas as pd
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no", "nan", "none", "null", ""}:
        return False
    return None
