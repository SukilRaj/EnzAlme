from pathlib import Path
import json
import joblib
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "models"


class Predictor:
    def __init__(self):
        self.pca = joblib.load(MODEL_DIR / "pca.pkl")
        self.scaler = joblib.load(MODEL_DIR / "scaler.pkl")
        self.model = joblib.load(MODEL_DIR / "ridge_model.pkl")

        with open(MODEL_DIR / "model_config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def predict(
        self,
        embedding: np.ndarray,
        temperature: float,
        ph: float,
        duration_hours: float,
    ) -> float:

        embedding = np.asarray(embedding, dtype=np.float32).reshape(1, -1)

        # Reduce ESM-2 embedding from 1280 dimensions to PCA dimensions
        embedding_pca = self.pca.transform(embedding)

        # Add environmental features
        environment = np.array(
            [[temperature, ph, duration_hours]],
            dtype=np.float32,
        )

        features = np.concatenate(
            [embedding_pca, environment],
            axis=1,
        )

        # Apply the same scaler used during training
        features_scaled = self.scaler.transform(features)

        # Predict log1p(TPA concentration)
        prediction_log = self.model.predict(features_scaled)[0]

        # Convert back to µM
        prediction_um = np.expm1(prediction_log)

        # Avoid tiny negative floating-point values
        return max(0.0, float(prediction_um))