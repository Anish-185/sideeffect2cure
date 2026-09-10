"""Typed errors for Level 5 feature engineering."""

from __future__ import annotations


class FeatureEngineeringError(Exception):
    """Base class for feature-engineering failures."""


class InvalidFeatureInputError(FeatureEngineeringError):
    """A candidate / disease profile / drug profile input is missing or the wrong type,
    or the three inputs do not refer to the same (disease, drug) pair."""
