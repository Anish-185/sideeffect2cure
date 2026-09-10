"""Top-level API router.

Level 0 exposes only infrastructure endpoints (health / metadata). Pipeline
endpoints are added in later levels.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import DISCLAIMER, get_settings

router = APIRouter()


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", tags=["meta"])
def meta() -> dict[str, str]:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "disclaimer": DISCLAIMER,
    }
