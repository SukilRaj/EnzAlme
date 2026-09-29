from fastapi import APIRouter, HTTPException

from backend.app.schemas.prediction import (
    PredictionRequest,
    PredictionResponse,
)
from backend.app.schemas.recommendation import (
    RecommendationRequest,
    RecommendationResponse,
)
from backend.app.services.esm_encoder import ESMEncoder
from backend.app.services.predictor import Predictor
from backend.app.services.recommender import Recommender


router = APIRouter()

# Load models once when the API starts
esm_encoder = ESMEncoder()
predictor = Predictor()
recommender = Recommender(predictor=predictor)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "EnzAIme ML API",
    }


@router.post(
    "/predict",
    response_model=PredictionResponse,
)
def predict(request: PredictionRequest):

    try:
        # 1. Protein sequence → ESM-2 embedding
        embedding = esm_encoder.encode(request.sequence)

        # 2. Embedding + environment → prediction
        predicted_activity = predictor.predict(
            embedding=embedding,
            temperature=request.temperature,
            ph=request.ph,
            duration_hours=request.duration,
        )

        return PredictionResponse(
            predicted_activity_um=predicted_activity,
            target="TPA",
            substrate="PET",
            conditions={
                "ph": request.ph,
                "temperature": request.temperature,
                "duration": request.duration,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post(
    "/recommend",
    response_model=RecommendationResponse,
)
def recommend(request: RecommendationRequest):
    try:
        recommendations = recommender.recommend(
            ph=request.ph,
            temperature=request.temperature,
            duration_hours=request.duration,
            top_n=request.top_n,
        )

        return RecommendationResponse(
            target="TPA",
            substrate="PET",
            conditions={
                "ph": request.ph,
                "temperature": request.temperature,
                "duration": request.duration,
            },
            recommendations=recommendations,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )