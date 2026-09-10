"""Typed errors for Level 4 candidate generation."""

from __future__ import annotations


class CandidateGenerationError(Exception):
    """Base class for candidate-generation failures."""


class InvalidDiseaseProfileError(CandidateGenerationError):
    """The object passed to generate_candidates is not a usable DiseaseProfile."""
