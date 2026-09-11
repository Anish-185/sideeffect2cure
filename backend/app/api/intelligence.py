"""Standalone Level 2 / Level 3 lookup endpoints: a disease or drug profile on
its own, independent of any pipeline run.

Thin routing only — every response is exactly the ``DiseaseProfile`` /
``DrugProfile`` that ``app.services.disease`` / ``app.services.drug`` already
build (Level 2 / Level 3, both pre-existing). Nothing is computed here.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.disease import DiseaseProfile, ResolutionStatus
from app.models.drug import DrugProfile, DrugResolutionStatus
from app.services import disease as disease_service
from app.services import drug as drug_service

from .schemas import (
    AmbiguousDiseaseResponse,
    AmbiguousDrugResponse,
    UnsupportedDiseaseResponse,
    UnsupportedDrugResponse,
)

router = APIRouter()


@router.get("/disease/profile", response_model=DiseaseProfile, tags=["intelligence"])
def disease_profile(
    query: str = Query(..., min_length=0, description="disease name, alias, or internal/ontology id"),
) -> DiseaseProfile:
    """Level 2 alone: resolve + full ``DiseaseProfile`` (genes, pathways,
    provenance), with no candidate generation or scoring attached."""
    try:
        return disease_service.build_disease_profile(query)
    except disease_service.DiseaseResolutionError as exc:
        result = exc.result
        if result.status is ResolutionStatus.EMPTY_QUERY:
            raise HTTPException(
                status_code=400, detail={"status": "empty_query", "message": "Enter a disease name, alias, or id."}
            ) from exc
        if result.status is ResolutionStatus.AMBIGUOUS:
            body = AmbiguousDiseaseResponse(
                query=result.query,
                candidates=result.candidates,
                message=result.message or "Multiple diseases match this query — pick one.",
            )
            raise HTTPException(status_code=409, detail=body.model_dump(mode="json")) from exc
        body = UnsupportedDiseaseResponse(
            query=result.query,
            suggestions=result.suggestions,
            message=result.message or f"{result.query!r} is not a supported disease.",
        )
        raise HTTPException(status_code=404, detail=body.model_dump(mode="json")) from exc


@router.get("/drug/profile", response_model=DrugProfile, tags=["intelligence"])
def drug_profile(
    query: str = Query(..., min_length=0, description="drug name, or internal/ChEMBL/PubChem id"),
) -> DrugProfile:
    """Level 3 alone: resolve + full ``DrugProfile`` (side effects, targets,
    mechanisms, optional pathway context), independent of any disease."""
    try:
        return drug_service.build_drug_profile(query)
    except drug_service.DrugResolutionError as exc:
        result = exc.result
        if result.status is DrugResolutionStatus.EMPTY_QUERY:
            raise HTTPException(
                status_code=400, detail={"status": "empty_query", "message": "Enter a drug name or id."}
            ) from exc
        if result.status is DrugResolutionStatus.AMBIGUOUS:
            body = AmbiguousDrugResponse(
                query=result.query,
                candidates=result.candidates,
                message=result.message or "Multiple drugs match this query — pick one.",
            )
            raise HTTPException(status_code=409, detail=body.model_dump(mode="json")) from exc
        body = UnsupportedDrugResponse(
            query=result.query,
            suggestions=result.suggestions,
            message=result.message or f"{result.query!r} is not a supported drug.",
        )
        raise HTTPException(status_code=404, detail=body.model_dump(mode="json")) from exc
