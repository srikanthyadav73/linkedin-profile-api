"""
HTTP route for POST /api/profile.

Accepts a LinkedIn profile URL, fetches real profile data via the
Captapi API (app/services/captapi.py), maps it to our response
schema (app/services/parser.py), and returns it as JSON.

Error handling is intentionally absent here — all domain exceptions
(ProfileNotFoundError, RateLimitError, etc.) bubble up to the global
handlers registered in app/main.py, which translate them to the correct
HTTP status codes. This keeps the route thin and easy to read.
"""

import logging

from fastapi import APIRouter

from app.config import get_settings
from app.models.request import ProfileRequest
from app.models.response import ProfileResponse
from app.services import captapi, enricher, linkedin_voyager, parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])


@router.post("/profile", response_model=ProfileResponse)
async def get_profile(request: ProfileRequest) -> ProfileResponse:
    """
    Accept a LinkedIn profile URL and return structured profile data.

    Data Access Strategy:
    1. If LINKEDIN_LI_AT_COOKIE is provided, calls LinkedIn's internal Voyager API
       as an authenticated client for 100% complete data (unmasked education, skills, etc.).
    2. Otherwise, fetches via Captapi and applies smart keyword & fallback enrichment.
    """
    logger.info("Received profile request for URL: %s", request.linkedin_url)
    settings = get_settings()

    # 1. Try authenticated Voyager API if session cookie is configured
    if settings.linkedin_li_at_cookie:
        try:
            logger.info("Attempting fetch via reverse-engineered LinkedIn Voyager API...")
            return await linkedin_voyager.fetch_voyager_profile(request.linkedin_url)
        except Exception as exc:
            logger.warning("Voyager API failed (%s); falling back to Captapi provider...", exc)

    # 2. Captapi primary / fallback data provider
    raw = await captapi.fetch_profile(request.linkedin_url)
    profile = parser.parse_profile(raw, request.linkedin_url)

    # Fallback enrichment if education is missing from upstream scrape
    profile = await enricher.enrich_profile(profile, raw)

    return profile

