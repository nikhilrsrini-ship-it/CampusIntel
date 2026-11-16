import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.database.session import engine
from app.routers import admin, analytics, attachments, auth, catalog, ml, notifications, requests

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    root_path="/api" if os.getenv("VERCEL") == "1" else "",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(requests.router)
app.include_router(attachments.router)
app.include_router(notifications.router)
app.include_router(analytics.router)
app.include_router(ml.router)
app.include_router(admin.router)


@app.get("/healthz", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
def readiness() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
