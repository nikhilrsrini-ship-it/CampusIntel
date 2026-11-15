from functools import lru_cache
from pathlib import Path

import joblib

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _load_model(path: str, modified: float):
    return joblib.load(path)


@lru_cache(maxsize=1)
def _load_encoder(path: str, modified: float):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(path, device="cpu", local_files_only=True)


def classify(text: str) -> dict:
    settings = get_settings()
    if settings.embedding_model_path:
        semantic_path = Path(settings.semantic_model_path)
        embedding_path = Path(settings.embedding_model_path)
        if semantic_path.is_file() and embedding_path.is_dir():
            try:
                semantic = _load_model(str(semantic_path.resolve()), semantic_path.stat().st_mtime)
                encoder = _load_encoder(str(embedding_path.resolve()), embedding_path.stat().st_mtime)
                vector = encoder.encode([text], normalize_embeddings=True, convert_to_numpy=True)
                probabilities = semantic["classifier"].predict_proba(vector)[0]
                predicted = str(semantic["classifier"].classes_[probabilities.argmax()])
                return {
                    "available": True,
                    "predicted_category": predicted,
                    "confidence": float(probabilities.max()),
                    "department": semantic.get("category_departments", {}).get(predicted),
                    "model_name": "sentence-transformer-logistic-regression",
                    "model_version": semantic.get("model_version", "unknown"),
                    "dataset_type": semantic.get("dataset_type", "unknown"),
                    "explanation": {"note": "Semantic model suggestion only; no automatic workflow decision is made."},
                }
            except (ImportError, OSError, ValueError, RuntimeError):
                pass
    path = Path(settings.classification_model_path)
    if not path.is_file():
        return {"available": False, "predicted_category": None, "confidence": None, "department": None, "explanation": "No trained classifier is installed. Select an approximate category or train a local model."}
    try:
        model = _load_model(str(path.resolve()), path.stat().st_mtime)
        pipeline = model["pipeline"]
        predicted = str(pipeline.predict([text])[0])
        probabilities = pipeline.predict_proba([text])[0]
        confidence = float(max(probabilities))
        explanation = model.get("explanations", {}).get(predicted, [])
        return {
            "available": True,
            "predicted_category": predicted,
            "confidence": confidence,
            "department": model.get("category_departments", {}).get(predicted),
            "model_name": model.get("model_name", "tfidf-logistic-regression"),
            "model_version": model.get("model_version", "unknown"),
            "dataset_type": model.get("dataset_type", "unknown"),
            "explanation": {"learned_terms": explanation[:5], "note": "Model suggestion only; it does not change the selected category or request outcome."},
        }
    except Exception as exc:
        return {"available": False, "predicted_category": None, "confidence": None, "department": None, "explanation": f"Local model could not be loaded: {type(exc).__name__}."}
