from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.cross_validation import (
    router as cross_validation_router,
)


app = FastAPI(
    title="EnzAIme ML API",
    description="Environment-aware enzyme activity prediction API",
    version="1.0.0",
)


# Allow the React frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Prediction and recommendation routes
app.include_router(router, prefix="/api")

# ML evaluation route
app.include_router(evaluation_router, prefix="/api")
app.include_router(cross_validation_router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "EnzAIme ML API is running",
        "docs": "/docs",
    }