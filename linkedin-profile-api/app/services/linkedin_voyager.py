"""
LinkedIn Voyager / Dash API reverse-engineered client.

Uses LinkedIn's internal REST API endpoints authenticated via a valid `li_at`
session cookie — no browser automation (no Selenium, no Playwright, no Chrome).

Endpoint strategy (tries in order):
  1. /voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity={username}
     (newer Dash endpoint — returns full profile including education/skills/languages)
  2. /voyager/api/identity/profiles/{username}/profileView  (deprecated, 410 on most accounts)
"""

import json
import logging
import re
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.models.response import (
    Certification,
    Education,
    Experience,
    Language,
    ProfileImages,
    ProfileResponse,
)
from app.utils.exceptions import ProfileNotFoundError, RateLimitError, UpstreamUnavailableError

logger = logging.getLogger(__name__)

_VOYAGER_BASE = "https://www.linkedin.com/voyager/api"

# Headers that mirror what LinkedIn's own SPA sends on every Voyager request
_VOYAGER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.linkedin.normalized+json+2.1",
    "Accept-Language": "en-US,en;q=0.9",
    "x-restli-protocol-version": "2.0.0",
    "x-li-lang": "en_US",
    "x-li-track": '{"clientVersion":"1.13.9840"}',
    "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base;1234567890",
}


def extract_username(linkedin_url: str) -> str:
    """Extract vanity username or profile slug from a LinkedIn URL."""
    path = urlparse(linkedin_url.strip()).path.strip("/")
    parts = path.split("/")
    if "in" in parts:
        idx = parts.index("in")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return parts[-1]


async def fetch_voyager_profile(linkedin_url: str) -> ProfileResponse:
    """
    Fetch a complete LinkedIn profile using reverse-engineered Voyager/Dash API.
    Requires LINKEDIN_LI_AT_COOKIE in environment settings.
    """
    settings = get_settings()
    li_at = settings.linkedin_li_at_cookie
    if not li_at:
        raise ValueError("LINKEDIN_LI_AT_COOKIE is not configured.")

    username = extract_username(linkedin_url)
    logger.info("Fetching profile via LinkedIn Voyager/Dash API for slug: %s", username)

    jsessionid = "ajax:9876543210123"
    cookies = {
        "li_at": li_at.strip(),
        "JSESSIONID": f'"{jsessionid}"',
    }
    headers = {
        **_VOYAGER_HEADERS,
        "csrf-token": jsessionid,
        "referer": f"https://www.linkedin.com/in/{username}/",
    }

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers=headers,
        cookies=cookies,
    ) as client:
        # Strategy 1: New Dash endpoint (memberIdentity query)
        dash_url = (
            f"{_VOYAGER_BASE}/identity/dash/profiles"
            f"?q=memberIdentity&memberIdentity={username}"
            f"&decorationId=com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-86"
        )
        logger.info("Trying Dash endpoint: %s", dash_url)
        payload, status = await _safe_get(client, dash_url)
        logger.info("Dash endpoint status: %d", status)

        if status == 200 and payload:
            return _parse_dash_payload(payload, linkedin_url, username)

        # Strategy 2: Older profileView endpoint (410 on most accounts, but try)
        view_url = f"{_VOYAGER_BASE}/identity/profiles/{username}/profileView"
        logger.info("Dash endpoint returned %d, trying profileView: %s", status, view_url)
        payload, status = await _safe_get(client, view_url)
        logger.info("profileView endpoint status: %d", status)

        if status == 200 and payload:
            return _parse_voyager_payload(payload, linkedin_url)

        # Strategy 3: Simpler profile endpoint
        profile_url = f"{_VOYAGER_BASE}/identity/profiles/{username}"
        logger.info("profileView returned %d, trying basic profile endpoint: %s", status, profile_url)
        payload, status = await _safe_get(client, profile_url)
        logger.info("Basic profile endpoint status: %d", status)

        if status == 200 and payload:
            return _parse_basic_profile(payload, linkedin_url, username, client, headers, cookies)

    # Map error codes to proper exceptions
    if status == 404:
        raise ProfileNotFoundError(f"Profile '{username}' not found on LinkedIn.")
    if status == 429:
        raise RateLimitError("LinkedIn API rate limit reached.")
    if status in (401, 403, 999):
        raise UpstreamUnavailableError(f"LinkedIn session expired or access denied (HTTP {status}).")
    raise UpstreamUnavailableError(f"LinkedIn Voyager API returned HTTP {status}")


async def _safe_get(client: httpx.AsyncClient, url: str) -> tuple[dict | None, int]:
    """Make a GET request, return (parsed_json, status_code). Returns None if not JSON or error."""
    try:
        res = await client.get(url)
        if res.status_code == 200:
            try:
                return res.json(), 200
            except Exception:
                return None, 200
        return None, res.status_code
    except httpx.TimeoutException:
        logger.warning("Timeout reaching: %s", url)
        return None, 408
    except httpx.RequestError as exc:
        logger.warning("Network error reaching %s: %s", url, exc)
        return None, 503


async def _parse_basic_profile(
    payload: dict,
    linkedin_url: str,
    username: str,
    client: httpx.AsyncClient,
    headers: dict,
    cookies: dict,
) -> ProfileResponse:
    """
    Parse the simple /identity/profiles/{username} response and fetch sections separately.
    """
    # Fetch additional sections in parallel
    edu_url = f"{_VOYAGER_BASE}/identity/profiles/{username}/educations"
    skills_url = f"{_VOYAGER_BASE}/identity/profiles/{username}/skills"
    positions_url = f"{_VOYAGER_BASE}/identity/profiles/{username}/positions"

    edu_payload, _ = await _safe_get(client, edu_url)
    skills_payload, _ = await _safe_get(client, skills_url)
    positions_payload, _ = await _safe_get(client, positions_url)

    # Build Education
    education: list[Education] = []
    if edu_payload:
        for edu in edu_payload.get("elements", []):
            tp = edu.get("timePeriod", {})
            education.append(Education(
                institution=edu.get("schoolName") or edu.get("school"),
                degree=edu.get("degreeName"),
                field_of_study=edu.get("fieldOfStudy"),
                start_date=_format_date(tp.get("startDate")),
                end_date=_format_date(tp.get("endDate")),
                description=edu.get("description"),
            ))

    # Build Skills
    skills: list[str] = []
    if skills_payload:
        for s in skills_payload.get("elements", []):
            name = s.get("name") or (s.get("skill") or {}).get("name")
            if name and name not in skills:
                skills.append(name)

    # Build Experience
    experiences: list[Experience] = []
    if positions_payload:
        for pos in positions_payload.get("elements", []):
            tp = pos.get("timePeriod", {})
            experiences.append(Experience(
                title=pos.get("title"),
                company=pos.get("companyName"),
                location=pos.get("locationName"),
                start_date=_format_date(tp.get("startDate")),
                end_date=_format_date(tp.get("endDate")),
                description=pos.get("description"),
            ))

    first_name = payload.get("firstName", "")
    last_name = payload.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip()

    return ProfileResponse(
        profile_url=linkedin_url,
        name=full_name or None,
        headline=payload.get("headline"),
        location=payload.get("locationName") or payload.get("geoLocationName"),
        about=payload.get("summary"),
        profile_images=ProfileImages(profile=None, background=None),
        experience=experiences,
        education=education,
        skills=skills,
        certifications=[],
        languages=[],
    )


def _parse_dash_payload(payload: dict, linkedin_url: str, username: str) -> ProfileResponse:
    """
    Parse the new LinkedIn Dash API response format.
    Data is in 'included' array; each entity has a $type field.
    Education uses 'dateRange' (not 'timePeriod').
    """
    included = payload.get("included", [])

    # Index included entities by type
    entities_by_type: dict[str, list[dict]] = {}
    for item in included:
        t = item.get("$type", "")
        entities_by_type.setdefault(t, []).append(item)

    # Get main Profile entity
    profile_data = {}
    for key in ["com.linkedin.voyager.dash.identity.profile.Profile",
                "com.linkedin.voyager.identity.profile.Profile"]:
        if key in entities_by_type:
            # Find the one matching our username
            for p in entities_by_type[key]:
                if p.get("publicIdentifier") == username:
                    profile_data = p
                    break
            if not profile_data and entities_by_type[key]:
                profile_data = entities_by_type[key][0]
            break

    first_name = profile_data.get("firstName", "")
    last_name = profile_data.get("lastName", "")
    full_name = f"{first_name} {last_name}".strip()
    headline = profile_data.get("headline")
    location = profile_data.get("locationName") or profile_data.get("geoLocationName")
    about = profile_data.get("summary")

    photo_url = _extract_photo(profile_data)

    # Experience — Dash uses 'dateRange' key
    experiences: list[Experience] = []
    raw_positions = _find_by_type(entities_by_type, ["Position"])
    for pos in raw_positions:
        dr = pos.get("dateRange") or pos.get("timePeriod") or {}
        start = dr.get("start") or {}
        end = dr.get("end") or {}
        experiences.append(Experience(
            title=pos.get("title"),
            company=pos.get("companyName"),
            location=pos.get("locationName"),
            start_date=_format_date(start),
            end_date=_format_date(end),
            description=pos.get("description"),
        ))

    # Education — Dash uses 'dateRange' key
    education: list[Education] = []
    raw_edu = _find_by_type(entities_by_type, ["Education"])
    for edu in raw_edu:
        dr = edu.get("dateRange") or edu.get("timePeriod") or {}
        start = dr.get("start") or {}
        end = dr.get("end") or {}
        school = edu.get("schoolName")
        degree = edu.get("degreeName")
        field = edu.get("fieldOfStudy")
        if school or degree or field:
            education.append(Education(
                institution=school,
                degree=degree,
                field_of_study=field,
                start_date=_format_date(start),
                end_date=_format_date(end),
                description=edu.get("description"),
            ))

    # Skills
    skills: list[str] = []
    raw_skills = _find_by_type(entities_by_type, ["Skill"])
    for s in raw_skills:
        name = s.get("name") or (s.get("skill") or {}).get("name")
        if name and name not in skills:
            skills.append(name)

    # Certifications — Dash uses 'dateRange'
    certifications: list[Certification] = []
    raw_certs = _find_by_type(entities_by_type, ["Certification"])
    for c in raw_certs:
        dr = c.get("dateRange") or c.get("timePeriod") or {}
        certifications.append(Certification(
            name=c.get("name"),
            issuer=c.get("authority"),
            issue_date=_format_date(dr.get("start") or {}),
            expiration_date=_format_date(dr.get("end") or {}),
            credential_id=c.get("licenseNumber"),
            credential_url=c.get("url"),
        ))

    # Languages
    languages: list[Language] = []
    raw_langs = _find_by_type(entities_by_type, ["Language"])
    for lang in raw_langs:
        languages.append(Language(
            name=lang.get("name"),
            proficiency=lang.get("proficiency"),
        ))

    return ProfileResponse(
        profile_url=linkedin_url,
        name=full_name or None,
        headline=headline,
        location=location,
        about=about,
        profile_images=ProfileImages(profile=photo_url, background=None),
        experience=experiences,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
    )




def _parse_voyager_payload(payload: dict, linkedin_url: str) -> ProfileResponse:
    """Parse normalized Voyager JSON (older profileView format) into ProfileResponse model."""
    profile_data = payload.get("profile") or {}

    included = payload.get("included") or []
    entities_by_type: dict[str, list[dict]] = {}
    for item in included:
        entity_type = item.get("$type", "")
        entities_by_type.setdefault(entity_type, []).append(item)

    first_name = profile_data.get("firstName") or ""
    last_name = profile_data.get("lastName") or ""
    full_name = f"{first_name} {last_name}".strip() or profile_data.get("localizedFirstName") or None
    headline = profile_data.get("headline")
    location = profile_data.get("locationName") or profile_data.get("geoLocationName")
    about = profile_data.get("summary")

    photo_url = _extract_photo(profile_data)

    experiences: list[Experience] = []
    raw_positions = (
        _get_from_view(payload, "positionView")
        or _find_by_type(entities_by_type, ["Position"])
    )
    for pos in raw_positions:
        tp = pos.get("timePeriod") or {}
        experiences.append(Experience(
            title=pos.get("title"),
            company=pos.get("companyName"),
            location=pos.get("locationName"),
            start_date=_format_date(tp.get("startDate")),
            end_date=_format_date(tp.get("endDate")),
            description=pos.get("description"),
        ))

    education: list[Education] = []
    raw_edu = (
        _get_from_view(payload, "educationView")
        or _find_by_type(entities_by_type, ["Education"])
    )
    for edu in raw_edu:
        tp = edu.get("timePeriod") or {}
        school = edu.get("schoolName") or edu.get("school")
        degree = edu.get("degreeName")
        field = edu.get("fieldOfStudy")
        if school or degree or field:
            education.append(Education(
                institution=school,
                degree=degree,
                field_of_study=field,
                start_date=_format_date(tp.get("startDate")),
                end_date=_format_date(tp.get("endDate")),
                description=edu.get("description"),
            ))

    skills: list[str] = []
    raw_skills = (
        _get_from_view(payload, "skillView")
        or _find_by_type(entities_by_type, ["Skill"])
    )
    for s in raw_skills:
        name = s.get("name") or (s.get("skill") or {}).get("name")
        if name and name not in skills:
            skills.append(name)

    certifications: list[Certification] = []
    raw_certs = _find_by_type(entities_by_type, ["Certification"])
    for c in raw_certs:
        tp = c.get("timePeriod") or {}
        certifications.append(Certification(
            name=c.get("name"),
            issuer=c.get("authority"),
            issue_date=_format_date(tp.get("startDate")),
            expiration_date=_format_date(tp.get("endDate")),
            credential_id=c.get("licenseNumber"),
            credential_url=c.get("url"),
        ))

    languages: list[Language] = []
    raw_langs = _find_by_type(entities_by_type, ["Language"])
    for lang in raw_langs:
        languages.append(Language(
            name=lang.get("name"),
            proficiency=lang.get("proficiency"),
        ))

    return ProfileResponse(
        profile_url=linkedin_url,
        name=full_name,
        headline=headline,
        location=location,
        about=about,
        profile_images=ProfileImages(profile=photo_url, background=None),
        experience=experiences,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
    )


# ────────────────────────────────────────────────────────────────
# Helper utilities
# ────────────────────────────────────────────────────────────────

def _get_from_view(data: dict, view_key: str) -> list[dict]:
    """Extract elements from a *View sub-object."""
    return data.get(view_key, {}).get("elements") or []


def _find_by_type(entities_by_type: dict[str, list[dict]], type_keywords: list[str]) -> list[dict]:
    """
    Find all entities matching any of the given type keywords (case-sensitive substring match).
    Searches both voyager and dash namespaces.
    """
    results = []
    for key, items in entities_by_type.items():
        if any(kw in key for kw in type_keywords):
            results.extend(items)
    return results


def _extract_photo(profile_data: dict) -> str | None:
    """Extract profile photo URL from profilePicture object."""
    picture_obj = profile_data.get("profilePicture", {})
    if not picture_obj:
        return None
    vector = picture_obj.get("displayImageReference", {}).get("vectorImage", {})
    root_url = vector.get("rootUrl", "")
    artifacts = vector.get("artifacts", [])
    if root_url and artifacts:
        return root_url + artifacts[-1].get("fileIdentifyingUrlPathSegment", "")
    return None


def _format_date(date_dict: dict | None) -> str | None:
    """Format Voyager date dict {'year': 2020, 'month': 6} into human-readable string."""
    if not date_dict:
        return None
    year = date_dict.get("year")
    month = date_dict.get("month")
    if year and month:
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        try:
            month_str = month_names[int(month) - 1]
            return f"{month_str} {year}"
        except (IndexError, ValueError):
            return str(year)
    return str(year) if year else None
