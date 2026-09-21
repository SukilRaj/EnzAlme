"""
backend/app/schemas.py
=========================
Pydantic request/response models. Input validation here is the first line
of defense described in Section 53 (reject NaN/Infinity/negative
salinity/absurd pH/absurd temperature/unknown pollutants with HTTP 400).
"""
from __future__ import annotations

import math
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from enzaime_core import config as core_config


# --------------------------------------------------------------------------
# /recommend
# --------------------------------------------------------------------------
class RecommendRequest(BaseModel):
    pollutant: str = Field(..., description="One of: " + ", ".join(core_config.SUPPORTED_POLLUTANTS))
    ph: float = Field(..., description="Environmental pH")
    temperature: float = Field(..., description="Environmental temperature in Celsius")
    salinity: float = Field(..., description="Environmental salinity (project-defined unit, e.g. % w/v)")

    @field_validator("pollutant")
    @classmethod
    def validate_pollutant(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("pollutant must be a non-empty string")
        if v.strip().upper() not in core_config.SUPPORTED_POLLUTANTS:
            raise ValueError(
                f"Unsupported pollutant '{v}'. Supported: {core_config.SUPPORTED_POLLUTANTS}"
            )
        return v.strip().upper()

    @field_validator("ph")
    @classmethod
    def validate_ph(cls, v: float) -> float:
        _reject_nan_inf(v, "ph")
        if not (core_config.PH_MIN_ALLOWED <= v <= core_config.PH_MAX_ALLOWED):
            raise ValueError(
                f"pH must be between {core_config.PH_MIN_ALLOWED} and {core_config.PH_MAX_ALLOWED}"
            )
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        _reject_nan_inf(v, "temperature")
        if not (core_config.TEMP_MIN_ALLOWED <= v <= core_config.TEMP_MAX_ALLOWED):
            raise ValueError(
                f"temperature must be between {core_config.TEMP_MIN_ALLOWED} and "
                f"{core_config.TEMP_MAX_ALLOWED} Celsius"
            )
        return v

    @field_validator("salinity")
    @classmethod
    def validate_salinity(cls, v: float) -> float:
        _reject_nan_inf(v, "salinity")
        if v < 0:
            raise ValueError("salinity cannot be negative")
        if v > core_config.SALINITY_MAX_ALLOWED:
            raise ValueError(f"salinity must be <= {core_config.SALINITY_MAX_ALLOWED}")
        return v


def _reject_nan_inf(v: float, field_name: str) -> None:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        raise ValueError(f"{field_name} must be a finite number (NaN/Infinity are not allowed)")


class CompatibilityBreakdownOut(BaseModel):
    pollutant: float
    ph: float
    temperature: float
    salinity: float


class RecommendationItem(BaseModel):
    rank: int
    enzyme_id: str
    enzyme_name: str
    accession: Optional[str] = None
    pollutant: str
    suitability_score: float
    score_percent: float
    breakdown: CompatibilityBreakdownOut
    evidence: Optional[str] = None
    salinity_status: str
    explanation: dict
    scoring_mode: str  # "demo_compatibility_engine" | "ai_model"


class RecommendResponse(BaseModel):
    query: RecommendRequest
    scoring_mode: str
    demo_mode: bool
    recommendations: List[RecommendationItem]
    n_candidates_evaluated: int
    n_candidates_with_pollutant_evidence: int
    disclaimer: str


# --------------------------------------------------------------------------
# /enzymes , /enzyme/{id}
# --------------------------------------------------------------------------
class EnzymeSummary(BaseModel):
    enzyme_id: str
    enzyme_name: str
    accession: Optional[str] = None
    ec_number: Optional[str] = None
    pollutant: Optional[str] = None
    evidence_type: Optional[str] = None
    has_sequence: bool
    demo_assumption: Optional[bool] = None


class EnzymeDetail(BaseModel):
    enzyme_id: str
    enzyme_name: str
    accession: Optional[str] = None
    ec_number: Optional[str] = None
    pollutant: Optional[str] = None
    sequence: Optional[str] = None
    seq_length: Optional[int] = None
    source: Optional[str] = None
    evidence_type: Optional[str] = None
    pH_opt: Optional[float] = None
    pH_min: Optional[float] = None
    pH_max: Optional[float] = None
    T_opt: Optional[float] = None
    T_min: Optional[float] = None
    T_max: Optional[float] = None
    salinity_evidence: Optional[bool] = None
    salinity_min: Optional[float] = None
    salinity_max: Optional[float] = None
    notes: Optional[str] = None
    demo_assumption: Optional[bool] = None
    has_sequence: bool
    mutation_analysis_available: bool


# --------------------------------------------------------------------------
# /mutations
# --------------------------------------------------------------------------
class MutationRequest(BaseModel):
    enzyme_id: str
    max_mutations: Optional[int] = Field(default=None, ge=1, le=core_config.MAX_MUTATIONS)
    top_n: Optional[int] = Field(default=None, ge=1, le=1000, description="Number of ranked results to return")

    @field_validator("enzyme_id")
    @classmethod
    def validate_enzyme_id(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("enzyme_id must be a non-empty string")
        return v.strip()


class MutationCandidateOut(BaseModel):
    rank: int
    mutation: str
    position: int
    original_residue: str
    new_residue: str
    predicted_stability_score: float
    predicted_fitness_proxy: float
    mutation_score: float


class MutationResponse(BaseModel):
    enzyme_id: str
    enzyme_name: str
    sequence_length: int
    provider: str
    n_candidates_generated: int
    n_candidates_returned: int
    mutations: List[MutationCandidateOut]
    disclaimer: str = (
        "Computational prediction — experimental validation required. "
        "Structural/docking validation is future work (not part of this MVP)."
    )


# --------------------------------------------------------------------------
# /metadata , /health
# --------------------------------------------------------------------------
class MetadataResponse(BaseModel):
    app_name: str
    app_version: str
    demo_mode: bool
    scoring_mode: str
    model_name: str
    device: str
    supported_pollutants: List[str]
    weights: dict
    n_enzymes_loaded: int
    data_source: str


class HealthResponse(BaseModel):
    status: str
    demo_mode: bool
    model_loaded: bool
    n_enzymes_loaded: int


# --------------------------------------------------------------------------
# /simulate  — Environmental Sensitivity Simulator
# /simulate/sweep
# --------------------------------------------------------------------------
class _EnvQueryMixin(BaseModel):
    pollutant: str = Field(..., description="One of: " + ", ".join(core_config.SUPPORTED_POLLUTANTS))
    ph: float = Field(..., description="Environmental pH")
    temperature: float = Field(..., description="Environmental temperature in Celsius")
    salinity: float = Field(..., description="Environmental salinity (project-defined unit, e.g. % w/v)")

    @field_validator("pollutant")
    @classmethod
    def validate_pollutant(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("pollutant must be a non-empty string")
        if v.strip().upper() not in core_config.SUPPORTED_POLLUTANTS:
            raise ValueError(
                f"Unsupported pollutant '{v}'. Supported: {core_config.SUPPORTED_POLLUTANTS}"
            )
        return v.strip().upper()

    @field_validator("ph")
    @classmethod
    def validate_ph(cls, v: float) -> float:
        _reject_nan_inf(v, "ph")
        if not (core_config.PH_MIN_ALLOWED <= v <= core_config.PH_MAX_ALLOWED):
            raise ValueError(
                f"pH must be between {core_config.PH_MIN_ALLOWED} and {core_config.PH_MAX_ALLOWED}"
            )
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        _reject_nan_inf(v, "temperature")
        if not (core_config.TEMP_MIN_ALLOWED <= v <= core_config.TEMP_MAX_ALLOWED):
            raise ValueError(
                f"temperature must be between {core_config.TEMP_MIN_ALLOWED} and "
                f"{core_config.TEMP_MAX_ALLOWED} Celsius"
            )
        return v

    @field_validator("salinity")
    @classmethod
    def validate_salinity(cls, v: float) -> float:
        _reject_nan_inf(v, "salinity")
        if v < 0:
            raise ValueError("salinity cannot be negative")
        if v > core_config.SALINITY_MAX_ALLOWED:
            raise ValueError(f"salinity must be <= {core_config.SALINITY_MAX_ALLOWED}")
        return v


class SimulateRequest(_EnvQueryMixin):
    """Score a single enzyme at a specific environmental point."""
    enzyme_id: str = Field(..., description="Enzyme ID to score (e.g. ENZ001)")

    @field_validator("enzyme_id")
    @classmethod
    def validate_enzyme_id(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("enzyme_id must be a non-empty string")
        return v.strip()


_SWEEP_VARS = {"ph", "temperature", "salinity"}
_MAX_STEPS = 200


class SimulateSweepRequest(BaseModel):
    """Vary one variable, score the same enzyme across a sweep."""
    enzyme_id: str = Field(..., description="Enzyme ID to score (e.g. ENZ001)")
    pollutant: str = Field(..., description="One of: " + ", ".join(core_config.SUPPORTED_POLLUTANTS))
    sweep_variable: str = Field(..., description="Which variable to sweep: ph, temperature, salinity")
    sweep_min: float = Field(..., description="Starting value of the sweep")
    sweep_max: float = Field(..., description="Ending value of the sweep")
    steps: int = Field(default=40, ge=1, le=_MAX_STEPS, description="Number of points in the sweep, max 200")
    fixed_ph: float = Field(..., description="Fixed pH when not sweeping pH")
    fixed_temperature: float = Field(..., description="Fixed temperature when not sweeping it")
    fixed_salinity: float = Field(..., description="Fixed salinity when not sweeping it")

    @field_validator("enzyme_id")
    @classmethod
    def validate_enzyme_id(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("enzyme_id must be a non-empty string")
        return v.strip()

    @field_validator("pollutant")
    @classmethod
    def validate_pollutant(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip() == "":
            raise ValueError("pollutant must be a non-empty string")
        if v.strip().upper() not in core_config.SUPPORTED_POLLUTANTS:
            raise ValueError(
                f"Unsupported pollutant '{v}'. Supported: {core_config.SUPPORTED_POLLUTANTS}"
            )
        return v.strip().upper()

    @field_validator("sweep_variable")
    @classmethod
    def validate_sweep_variable(cls, v: str) -> str:
        if not isinstance(v, str) or v.strip().lower() not in _SWEEP_VARS:
            raise ValueError(
                f"sweep_variable must be one of: {sorted(_SWEEP_VARS)}"
            )
        return v.strip().lower()

    @field_validator("sweep_min", "sweep_max")
    @classmethod
    def validate_sweep_bounds(cls, v: float) -> float:
        _reject_nan_inf(v, "sweep bound")
        return v

    @field_validator("fixed_ph")
    @classmethod
    def validate_fixed_ph(cls, v: float) -> float:
        _reject_nan_inf(v, "fixed_ph")
        if not (core_config.PH_MIN_ALLOWED <= v <= core_config.PH_MAX_ALLOWED):
            raise ValueError(
                f"fixed_ph must be between {core_config.PH_MIN_ALLOWED} and {core_config.PH_MAX_ALLOWED}"
            )
        return v

    @field_validator("fixed_temperature")
    @classmethod
    def validate_fixed_temperature(cls, v: float) -> float:
        _reject_nan_inf(v, "fixed_temperature")
        if not (core_config.TEMP_MIN_ALLOWED <= v <= core_config.TEMP_MAX_ALLOWED):
            raise ValueError(
                f"fixed_temperature must be between {core_config.TEMP_MIN_ALLOWED} and "
                f"{core_config.TEMP_MAX_ALLOWED} Celsius"
            )
        return v

    @field_validator("fixed_salinity")
    @classmethod
    def validate_fixed_salinity(cls, v: float) -> float:
        _reject_nan_inf(v, "fixed_salinity")
        if v < 0:
            raise ValueError("fixed_salinity cannot be negative")
        if v > core_config.SALINITY_MAX_ALLOWED:
            raise ValueError(f"fixed_salinity must be <= {core_config.SALINITY_MAX_ALLOWED}")
        return v


class SimulateSweepPoint(BaseModel):
    value: float
    suitability_score: float
    score: Optional[float] = None
    score_percent: float
    breakdown: CompatibilityBreakdownOut


class SimulateResponse(BaseModel):
    """Single-point simulation — same shape as one RecommendationItem, no rank."""
    enzyme_id: str
    enzyme_name: str
    accession: Optional[str] = None
    pollutant: str
    suitability_score: float
    score: Optional[float] = None
    score_percent: float
    breakdown: CompatibilityBreakdownOut
    evidence: Optional[str] = None
    salinity_status: str
    explanation: dict
    scoring_mode: str
    query: Optional[SimulateRequest] = None


class SimulateSweepResponse(BaseModel):
    enzyme_id: str
    enzyme_name: str
    pollutant: str
    sweep_variable: str
    points: list[SimulateSweepPoint]
    scoring_mode: str
