"""
Captapi HTTP client (data-access layer).

This module is the ONLY place in the codebase that talks to Captapi
(https://api.captapi.com). Everything else works with our own domain models.

Captapi endpoint used:
    GET /v1/linkedin/profile
    Cost: 2 credits per successful request.
    Docs: https://captapi.com/docs  (LinkedIn section)

Input:
    The full LinkedIn profile URL is passed directly as the `url` query
    parameter — no slug extraction needed. Captapi accepts the URL as-is.

Auth:
    Authorization: Bearer capt_live_...

Response envelope from Captapi:
    {
      "success": true,
      "cached": false,
      "creditsUsed": 2,
      "requestId": "...",
      "fetchedAt": "...",
      "data": { ... profile fields ... }
    }

Error envelope:
    {
      "success": false,
      "error": { "code": "...", "message": "..." }
    }
"""

import json
import logging
import pathlib

import httpx

from app.config import get_settings
from app.utils.exceptions import (
    ProfileNotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
)

logger = logging.getLogger(__name__)

_CAPTAPI_BASE_URL = "https://api.captapi.com"
_LINKEDIN_PROFILE_PATH = "/v1/linkedin/profile"

# Captapi docs recommend a 100s read timeout for most endpoints.
_TIMEOUT = httpx.Timeout(connect=10.0, read=100.0, write=30.0, pool=10.0)


async def fetch_profile(linkedin_url: str) -> dict:
    """
    Fetch a LinkedIn person profile from the Captapi API.

    Parameters
    ----------
    linkedin_url:
        A validated LinkedIn profile URL (already passed through the
        Pydantic validator in ProfileRequest).

    Returns
    -------
    dict
        The ``data`` object from Captapi's response body.

    Raises
    ------
    ProfileNotFoundError   — 404 from Captapi (profile not found).
    RateLimitError         — 429 from Captapi (rate limited).
    UpstreamUnavailableError — 502 / timeout / network error.
    RuntimeError           — CAPTAPI_API_KEY not configured, or out of credits.
    """
    settings = get_settings()

    if not settings.captapi_api_key:
        raise RuntimeError(
            "CAPTAPI_API_KEY is not set. "
            "Create a free key at https://captapi.com/dashboard and add it to .env."
        )

    logger.info("Fetching Captapi LinkedIn profile for URL: %s", linkedin_url)

    headers = {"Authorization": f"Bearer {settings.captapi_api_key}"}
    # cache=false forces a live scrape, which triggers Captapi's Apify enrichment
    # fallback when the native LinkedIn HTML omits education/experience sections.
    # The August 2026 changelog confirms education[] is only populated on the
    # enriched path — a cached pre-enrichment response will be missing it.
    params = {"url": linkedin_url, "cache": "false"}

    async with httpx.AsyncClient(base_url=_CAPTAPI_BASE_URL, timeout=_TIMEOUT) as client:
        try:
            response = await client.get(
                _LINKEDIN_PROFILE_PATH,
                headers=headers,
                params=params,
            )
        except httpx.TimeoutException as exc:
            logger.warning("Captapi request timed out for %s: %s", linkedin_url, exc)
            raise UpstreamUnavailableError(
                "The profile data service timed out. Please try again."
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Captapi network error for %s: %s", linkedin_url, exc)
            raise UpstreamUnavailableError(
                "Could not reach the profile data service. Please try again."
            ) from exc

    _handle_error_status(response, linkedin_url)

    body: dict = response.json()

    # Captapi wraps data in a top-level envelope; return just the data object.
    if not body.get("success"):
        error = body.get("error", {})
        code = error.get("code", "unknown")
        msg = error.get("message", "Unknown error from Captapi.")
        logger.error("Captapi returned success=false (code=%s): %s", code, msg)
        raise UpstreamUnavailableError(f"Profile data service error: {msg}")

    data = body.get("data") or {}

    # ── TEMPORARY DEBUG DUMP ─────────────────────────────────────────────
    # Writes the complete raw Captapi response (full envelope + data) to a
    # local file so we can inspect exactly what is and isn't being returned.
    # Remove this block once the education/skills investigation is resolved.
    _debug_dir = pathlib.Path(__file__).parent.parent.parent / "debug_output"
    _debug_dir.mkdir(exist_ok=True)
    _dump_path = _debug_dir / "captapi_raw_response.json"
    with open(_dump_path, "w", encoding="utf-8") as _f:
        json.dump(body, _f, indent=2, ensure_ascii=False, default=str)
    logger.info("DEBUG: full Captapi response written to %s", _dump_path)
    # ── END TEMPORARY DEBUG DUMP ─────────────────────────────────────────

    logger.info(
        "Captapi profile fetched (credits used: %s, cached: %s, keys: %s)",
        body.get("creditsUsed"),
        body.get("cached"),
        list(data.keys()) if data else "EMPTY",
    )
    return data


def _handle_error_status(response: httpx.Response, linkedin_url: str) -> None:
    """
    Translate Captapi HTTP error codes into our domain exceptions.

    Captapi error codes (from docs):
        401  invalid_api_key
        402  insufficient_credits
        404  not_found
        429  rate_limited
        502  upstream_error  (temporary, safe to retry)
    """
    status = response.status_code

    if status == 200:
        return

    if status == 404:
        logger.info("Captapi: profile not found for %s", linkedin_url)
        raise ProfileNotFoundError(
            "No profile found for the given LinkedIn URL. "
            "The profile may be private, removed, or not yet indexed."
        )

    if status == 429:
        logger.warning("Captapi: rate limited (url=%s)", linkedin_url)
        raise RateLimitError(
            "The profile data service is rate-limiting requests. Please try again later."
        )

    if status == 502:
        logger.warning("Captapi: upstream error 502 (url=%s)", linkedin_url)
        raise UpstreamUnavailableError(
            "The profile data service encountered a temporary error. Please try again."
        )

    if status == 401:
        logger.error("Captapi: invalid API key (401)")
        raise RuntimeError(
            "Captapi API key is invalid. Check CAPTAPI_API_KEY in your .env file."
        )

    if status == 402:
        logger.error("Captapi: insufficient credits (402)")
        raise RuntimeError(
            "Captapi account has insufficient credits. "
            "Top up at https://captapi.com/dashboard."
        )

    logger.error(
        "Captapi: unexpected status %d for %s. Body: %s",
        status,
        linkedin_url,
        response.text[:200],
    )
    raise UpstreamUnavailableError(
        f"Unexpected response from the profile data service (HTTP {status})."
    )
