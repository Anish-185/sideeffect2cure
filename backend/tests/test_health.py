"""Smoke tests for the Level 0 infrastructure endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_exposes_disclaimer() -> None:
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert "disclaimer" in body
    assert "not a clinical" in body["disclaimer"].lower()
