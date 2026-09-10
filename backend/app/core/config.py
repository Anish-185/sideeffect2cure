"""Application configuration.

Values are read from the environment with sensible local-development defaults so
the prototype runs with zero setup.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository layout anchors.
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

# Shown by the API and dashboard on every response that ranks drugs.
DISCLAIMER = (
    "SideEffect2Cure AI is a research prototype for drug repurposing discovery. "
    "It does not diagnose, treat, or cure any disease and is not a clinical "
    "decision-support tool. All output is hypothesis-generating only."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SE2C_", env_file=".env", extra="ignore")

    app_name: str = "SideEffect2Cure AI"
    version: str = "0.0.0"
    environment: str = "development"

    data_dir: Path = DATA_DIR
    raw_dir: Path = DATA_DIR / "raw"
    processed_dir: Path = DATA_DIR / "processed"
    features_dir: Path = DATA_DIR / "features"
    mappings_dir: Path = DATA_DIR / "mappings"

    # Network etiquette for the ingestion layer (see app.data.sources).
    http_timeout_seconds: float = 60.0
    http_retries: int = 3
    http_user_agent: str = "SideEffect2Cure-AI/prototype (research; contact via repo)"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
