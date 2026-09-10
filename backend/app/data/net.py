"""Small HTTP helpers for the ingestion layer.

Thin wrapper over ``httpx`` (already a dependency via FastAPI's test client)
with retry/backoff, a project User-Agent, and streaming downloads so large
files never sit fully in memory.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from app.core.config import get_settings


class DownloadError(RuntimeError):
    pass


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(
        timeout=s.http_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": s.http_user_agent},
    )


def _retries() -> int:
    return max(1, get_settings().http_retries)


def _content_length(url: str) -> int | None:
    try:
        with _client() as client:
            resp = client.head(url)
            resp.raise_for_status()
            cl = resp.headers.get("content-length")
            return int(cl) if cl is not None else None
    except (httpx.HTTPError, ValueError):
        return None


def download_file(url: str, dest: Path, *, force: bool = False, max_attempts: int = 8) -> Path:
    """Download ``url`` to ``dest``, resuming a partial ``.part`` on each attempt.

    Robust to the slow / flaky EBI FTP-over-HTTPS endpoints: it discovers the
    expected size up front and keeps issuing ranged requests (appending to
    ``.part``) until the file is complete, rather than trusting a stream that
    ended early. Raises :class:`DownloadError` if it still cannot complete.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    if force:
        tmp.unlink(missing_ok=True)

    total = _content_length(url)
    last_err: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        have = tmp.stat().st_size if tmp.exists() else 0
        if total is not None and have >= total:
            break
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with _client() as client, client.stream("GET", url, headers=headers) as resp:
                if resp.status_code == 416:  # requested range past EOF -> already done
                    break
                resp.raise_for_status()
                append = have > 0 and resp.status_code == 206
                with tmp.open("ab" if append else "wb") as fh:
                    if not append:
                        fh.seek(0)
                        fh.truncate()
                    for chunk in resp.iter_bytes(chunk_size=1 << 16):
                        fh.write(chunk)
        except (httpx.HTTPError, OSError) as exc:
            last_err = exc
        # progress check
        now = tmp.stat().st_size if tmp.exists() else 0
        if total is not None and now >= total:
            break
        if total is None and last_err is None and now > 0:
            # no size to verify against and the stream ended cleanly
            break
        if attempt < max_attempts:
            time.sleep(min(2 * attempt, 15))
    else:
        raise DownloadError(
            f"failed to download {url}: got {tmp.stat().st_size if tmp.exists() else 0} bytes"
            f"{f' of {total}' if total else ''}; last error: {last_err}"
        )

    if total is not None and (not tmp.exists() or tmp.stat().st_size < total):
        raise DownloadError(
            f"incomplete download {url}: {tmp.stat().st_size if tmp.exists() else 0}/{total} bytes"
        )
    tmp.replace(dest)
    return dest


def get_json(
    url: str, *, params: dict | None = None, retries: int | None = None, timeout: float | None = None
) -> dict:
    n = retries if retries is not None else _retries()
    last_err: Exception | None = None
    for attempt in range(1, n + 1):
        try:
            with _client() as client:
                resp = client.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_err = exc
            if attempt < n:
                time.sleep(2 * attempt)
    raise DownloadError(f"GET {url} failed: {last_err}")


def post_form_json(
    url: str, data: dict, *, retries: int | None = None, timeout: float | None = None
) -> dict:
    """POST application/x-www-form-urlencoded (used for PubChem PUG-REST bulk cid lists)."""
    n = retries if retries is not None else _retries()
    last_err: Exception | None = None
    for attempt in range(1, n + 1):
        try:
            with _client() as client:
                resp = client.post(url, data=data, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_err = exc
            if attempt < n:
                time.sleep(2 * attempt)
    raise DownloadError(f"POST {url} failed: {last_err}")


def post_json(url: str, payload: dict) -> dict:
    last_err: Exception | None = None
    for attempt in range(1, _retries() + 1):
        try:
            with _client() as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_err = exc
            if attempt < _retries():
                time.sleep(2 * attempt)
    raise DownloadError(f"POST {url} failed: {last_err}")


def paginate_chembl(url: str, params: dict, list_key: str) -> Iterator[dict]:
    """Yield every record from a paginated ChEMBL REST collection endpoint."""
    from urllib.parse import urljoin

    next_params: dict | None = dict(params)
    next_url: str | None = url
    while next_url is not None:
        page = get_json(next_url, params=next_params)
        yield from page.get(list_key, [])
        nxt = page.get("page_meta", {}).get("next")
        next_params = None
        next_url = urljoin(url, nxt) if nxt else None
