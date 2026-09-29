from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
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

    top_n: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of candidates to return",
    )


class RecommendationConditions(BaseModel):
    ph: float
    temperature: float
    duration: float


class RecommendationEvidence(BaseModel):
    sequence_available: bool
    esm2_embedding_available: bool
    experimental_activity_records: int
    experimental_activity_available: bool
    source: str


class RecommendationItem(BaseModel):
    rank: int
    protein_id: str
    protein_name: str
    predicted_activity_um: float

    evidence: RecommendationEvidence

    prediction_status: str
    validation_note: str


class RecommendationResponse(BaseModel):
    target: str
    substrate: str
    conditions: RecommendationConditions
    recommendations: list[RecommendationItem]