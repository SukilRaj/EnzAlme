from pydantic import BaseModel, Field
from backend.app.config import LEGACY_MODEL_NAME, LEGACY_MODEL_LINEAGE


class PredictionRequest(BaseModel):
    sequence: str = Field(
        ...,
        min_length=1,
        description="Protein amino-acid sequence",
    )

    ph: float = Field(
        ...,
        ge=0,
        le=14,
        description="pH value",
    )

    temperature: float = Field(
        ...,
        description="Temperature in Celsius",
    )

    duration: float = Field(
        ...,
        gt=0,
        description="Reaction duration in hours",
    )


class PredictionResponse(BaseModel):
    model: str = LEGACY_MODEL_NAME
    lineage_note: str = LEGACY_MODEL_LINEAGE
    predicted_activity_um: float
    target: str
    substrate: str
    conditions: dict
