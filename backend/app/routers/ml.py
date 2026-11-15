from datetime import timezone
from uuid import UUID
from pathlib import Path

import joblib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.database.session import get_db
from app.core.config import get_settings
from app.ml.classification import classify
from app.models import DepartmentStaff, ResolutionPrediction, ServiceRequest, User
from app.models.core import utcnow
from app.routers.requests import _scoped_request

router = APIRouter(prefix="/ml", tags=["machine learning"])


class ClassifyInput(BaseModel):
    subject: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=10000)


@router.post("/classify")
def predict_category(payload: ClassifyInput, _: User = Depends(get_current_user)):
    return classify(f"{payload.subject}\n{payload.description}")


@router.get("/requests/{request_id}/duplicates")
def duplicate_candidates(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = _scoped_request(db, user, request_id)
    query = select(ServiceRequest).where(ServiceRequest.id != target.id)
    if user.role == "STUDENT":
        query = query.where(ServiceRequest.student_id == user.id)
    elif user.role == "STAFF":
        department_ids = select(DepartmentStaff.department_id).where(DepartmentStaff.staff_id == user.id)
        query = query.where((ServiceRequest.assigned_staff_id == user.id) | ServiceRequest.assigned_department_id.in_(department_ids))
    rows = db.scalars(query.order_by(ServiceRequest.created_at.desc()).limit(300)).all()
    if not rows:
        return {"available": True, "method": "tfidf_cosine_similarity", "candidates": [], "note": "No other requests exist."}
    texts = [f"{target.subject} {target.description}"] + [f"{row.subject} {row.description}" for row in rows]
    method = "tfidf_cosine_similarity"
    settings = get_settings()
    try:
        if settings.embedding_model_path:
            import faiss
            from sentence_transformers import SentenceTransformer
            from pathlib import Path
            model_path = Path(settings.embedding_model_path)
            if model_path.is_dir():
                encoder = SentenceTransformer(str(model_path.resolve()), device="cpu", local_files_only=True)
                vectors = encoder.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
                index = faiss.IndexFlatIP(vectors.shape[1])
                index.add(vectors[1:].astype("float32"))
                values, indexes = index.search(vectors[:1].astype("float32"), min(5, len(rows)))
                ranked = [(rows[int(index)], float(score)) for index, score in zip(indexes[0], values[0]) if index >= 0]
                method = "sentence_transformer_faiss_cosine_similarity"
            else:
                raise ImportError("Local embedding model unavailable")
        else:
            raise ImportError("Local embedding model not configured")
    except (ImportError, OSError, ValueError, RuntimeError):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform(texts)
        except ValueError:
            return {"available": True, "method": "tfidf_cosine_similarity", "candidates": [], "note": "No usable word features were available for similarity comparison."}
        scores = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
        ranked = sorted(zip(rows, scores), key=lambda item: float(item[1]), reverse=True)[:5]
    return {"available": True, "method": method, "candidates": [{"request_id": str(row.id), "ticket_number": row.ticket_number, "subject": row.subject, "status": row.current_status, "similarity": round(float(score), 4)} for row, score in ranked if score >= 0.1], "note": "Candidates require human review; requests are never merged automatically."}


@router.get("/requests/{request_id}/resolution-estimate")
def resolution_estimate(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    completed = db.scalars(select(ServiceRequest).where(ServiceRequest.resolved_at.is_not(None), ServiceRequest.category_id == row.category_id)).all() if row.category_id else []
    artifact_path = Path(get_settings().resolution_model_path)
    if artifact_path.is_file() and len(completed) >= 20:
        artifact = joblib.load(artifact_path)
        prediction = float(artifact["model"].predict([{"category": row.category_id or "unknown", "department": row.assigned_department_id or "unknown", "priority": row.priority}])[0])
        db.add(ResolutionPrediction(request_id=row.id, model_version=artifact["model_version"], predicted_resolution_hours=max(0.0, prediction), prediction_confidence=None))
        db.commit()
        return {"available": True, "estimate_hours": round(max(0.0, prediction), 2), "sample_size": artifact["training_rows"], "model_version": artifact["model_version"], "note": "Random forest estimate from historical completed requests; an estimate, not a deadline or verified fact."}
    if len(completed) < 10:
        return {"available": False, "estimate_hours": None, "sample_size": len(completed), "model_version": "category-median-v1", "note": "At least 10 resolved requests in this category are required; no estimate was generated."}
    durations = sorted(max(0, ((item.resolved_at.replace(tzinfo=timezone.utc) if item.resolved_at.tzinfo is None else item.resolved_at) - (item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at)).total_seconds() / 3600) for item in completed)
    median = durations[len(durations) // 2] if len(durations) % 2 else (durations[len(durations) // 2 - 1] + durations[len(durations) // 2]) / 2
    prediction = ResolutionPrediction(request_id=row.id, model_version="category-median-v1", predicted_resolution_hours=median, prediction_confidence=None)
    db.add(prediction)
    db.commit()
    return {"available": True, "estimate_hours": round(median, 2), "sample_size": len(completed), "model_version": "category-median-v1", "note": "Historical median baseline; an estimate, not a deadline or verified fact."}
