"""Typed errors for Phase 9 AI-powered candidate explanation.

Every failure mode is explicit so ``app.services.explanation.service`` can
catch precisely ``ExplanationProviderError`` / ``ExplanationValidationError``
and fall back to the deterministic provider — never a silent success, never a
crash of the surrounding pipeline.
"""

from __future__ import annotations


class ExplanationError(Exception):
    """Base class for all Phase 9 failures."""


class ExplanationProviderError(ExplanationError):
    """The provider could not produce a response at all."""


class MissingAPIKeyError(ExplanationProviderError):
    """``FEATHERLESS_API_KEY`` is not configured."""


class ExplanationTimeoutError(ExplanationProviderError):
    """The request to Featherless timed out."""


class ExplanationNetworkError(ExplanationProviderError):
    """The request to Featherless failed at the network layer."""


class ExplanationHTTPError(ExplanationProviderError):
    """Featherless returned a non-2xx HTTP response (auth, rate limit, 5xx, ...).

    The message is built only from the status code and reason phrase — never
    from response headers/body, so the API key can never leak into it.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Featherless API returned HTTP {status_code}: {message}")
        self.status_code = status_code


class MalformedResponseError(ExplanationProviderError):
    """The HTTP call succeeded but the response body could not be parsed."""


class ExplanationValidationError(ExplanationError):
    """The provider responded, but the response failed grounding validation
    (mismatched ids/rank/score, a fabricated identifier, or disallowed
    clinical-claim language). The response is discarded, never partially
    accepted."""
