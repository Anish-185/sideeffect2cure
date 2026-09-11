"""``DeepSeekFeatherlessProvider`` — DeepSeek V4 Flash via Featherless's
OpenAI-compatible chat-completions API.

Isolated behind the ``ExplanationProvider`` interface (``provider.py``) so it
can be swapped for a different provider later without touching the rest of
the pipeline. Reads its API key from the environment
(``FEATHERLESS_API_KEY``, via ``app.core.config.Settings``) — never
hardcoded, never logged, never included in an exception message.
"""

from __future__ import annotations

import json

import httpx

from app.core.config import get_settings
from app.models.explanation import CandidateExplanation, ExplanationContext
from app.models.ranking import RankedCandidate
from app.services.explanation.errors import (
    ExplanationHTTPError,
    ExplanationNetworkError,
    ExplanationTimeoutError,
    MalformedResponseError,
    MissingAPIKeyError,
)
from app.services.explanation.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.explanation.validate import validate_llm_payload

_CHAT_COMPLETIONS_PATH = "/chat/completions"


class DeepSeekFeatherlessProvider:
    """``ExplanationProvider`` backed by DeepSeek V4 Flash on Featherless."""

    name = "deepseek_featherless"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.featherless_api_key
        self.base_url = (base_url or settings.featherless_base_url).rstrip("/")
        self.model = model or settings.featherless_model
        self.timeout = timeout if timeout is not None else settings.featherless_timeout_seconds

    def explain(
        self, candidate: RankedCandidate, context: ExplanationContext
    ) -> CandidateExplanation:
        if not self.api_key:
            raise MissingAPIKeyError(
                "FEATHERLESS_API_KEY is not configured; set it in the environment to enable "
                "the DeepSeek explanation provider."
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_payload(context)},
            ],
            "temperature": 0.2,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }

        try:
            resp = httpx.post(
                f"{self.base_url}{_CHAT_COMPLETIONS_PATH}",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ExplanationTimeoutError("Featherless request timed out") from exc
        except httpx.RequestError as exc:
            raise ExplanationNetworkError(f"Featherless request failed: {type(exc).__name__}") from exc

        if resp.is_error:
            # status code + reason phrase only — never the response body, which
            # could echo the request (and thus never anything key-bearing).
            raise ExplanationHTTPError(resp.status_code, resp.reason_phrase or "request failed")

        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            raw = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise MalformedResponseError(
                f"could not parse Featherless response: {type(exc).__name__}"
            ) from exc

        # ExplanationValidationError is allowed to propagate — the caller
        # (service.explain_candidate) falls back to the deterministic provider.
        return validate_llm_payload(
            raw, candidate, context, provider_name=self.name, model_name=self.model
        )
