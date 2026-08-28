"""
Fallback Scraper & Education Enricher.

When the primary API provider (Captapi) omits the education section due to
guest privacy filters or scraper limitations, this module acts as a smart
fallback. It attempts:
1. Direct LinkedIn public HTML scrape for JSON-LD and embedded metadata.
2. Direct candidate portfolio / website scrape (extracted from the 'about' bio).
3. Structured degree extraction.
"""

import json
import logging
import re
from urllib.parse import urlparse

import httpx

from app.models.response import Education, ProfileResponse

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_DEGREE_PATTERNS = [
    r"\b(?:Bachelor(?:\s+of\s+[A-Za-z]+)?|B\.Tech|BTech|B\.E\.|B\.Sc|BSc|BCA)\b",
    r"\b(?:Master(?:\s+of\s+[A-Za-z]+)?|M\.Tech|MTech|MCA|M\.Sc|MSc|MBA)\b",
    r"\b(?:Ph\.D|Doctor of Philosophy|Diploma in [A-Za-z\s]+)\b",
]

_ACADEMIC_INSTITUTION_PATTERN = re.compile(
    r"\b(?:University|College|Institute\s+of\s+Technology|Polytechnic|School\s+of\s+[A-Za-z]+|Academy)\b",
    re.IGNORECASE,
)


async def enrich_profile(profile: ProfileResponse, raw: dict) -> ProfileResponse:
    """
    Enrich profile with education and other details if missing.
    Ensures the main function and existing flow are never disrupted (fails gracefully).
    """
    if profile.education and len(profile.education) > 0:
        return profile

    logger.info("Education is empty in primary response — initiating fallback enrichment for %s", profile.profile_url)

    # 1. Try Direct LinkedIn Public HTML Scrape
    try:
        edu_items = await _scrape_linkedin_public_education(profile.profile_url)
        if edu_items:
            logger.info("Found %d education item(s) from direct LinkedIn HTML scrape", len(edu_items))
            profile.education = edu_items
            return profile
    except Exception as exc:
        logger.debug("Direct LinkedIn scrape fallback error: %s", exc)

    # 2. Try Candidate Portfolio Website (found in bio / about)
    try:
        portfolio_url = _extract_portfolio_url(raw.get("about") or "")
        if portfolio_url:
            logger.info("Found portfolio link in bio: %s. Fetching education details...", portfolio_url)
            edu_items = await _scrape_portfolio_education(portfolio_url)
            if edu_items:
                logger.info("Found %d education item(s) from candidate portfolio", len(edu_items))
                profile.education = edu_items
                return profile
    except Exception as exc:
        logger.debug("Portfolio scrape fallback error: %s", exc)

    return profile


async def _scrape_linkedin_public_education(url: str) -> list[Education]:
    """Attempt to parse public schema.org JSON-LD or HTML from LinkedIn."""
    async with httpx.AsyncClient(headers=_BROWSER_HEADERS, timeout=8.0, follow_redirects=True) as client:
        res = await client.get(url)
        if res.status_code != 200:
            return []

        html = res.text
        education_list: list[Education] = []

        # Check for JSON-LD schema
        json_ld_matches = re.findall(r'<script type="application/ld\+json">([^<]+)</script>', html)
        for block in json_ld_matches:
            try:
                data = json.loads(block.strip())
                if isinstance(data, dict):
                    # Check alumniOf
                    alumni = data.get("alumniOf") or []
                    if isinstance(alumni, dict):
                        alumni = [alumni]
                    for item in alumni:
                        name = item.get("name") if isinstance(item, dict) else str(item)
                        if name:
                            education_list.append(
                                Education(
                                    institution=name,
                                    degree=None,
                                    field_of_study=None,
                                    start_date=None,
                                    end_date=None,
                                    description=None,
                                )
                            )
            except Exception:
                continue

        # Check for Pegasus code tags or profile education containers
        edu_section_match = re.search(r'class="[^"]*education[^"]*"[^>]*>(.*?)</section>', html, re.DOTALL | re.IGNORECASE)
        if edu_section_match:
            sec_text = edu_section_match.group(1)
            titles = re.findall(r'<h3[^>]*>([^<]+)</h3>', sec_text)
            subs = re.findall(r'<h4[^>]*>([^<]+)</h4>', sec_text)
            for i, school in enumerate(titles):
                deg = subs[i].strip() if i < len(subs) else None
                education_list.append(
                    Education(
                        institution=school.strip(),
                        degree=deg,
                        field_of_study=None,
                        start_date=None,
                        end_date=None,
                        description=None,
                    )
                )

        return education_list


def _extract_portfolio_url(text: str) -> str | None:
    """Find portfolio or personal site URL in text."""
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    for u in urls:
        parsed = urlparse(u)
        host = parsed.netloc.lower()
        if "linkedin.com" not in host and "twitter.com" not in host:
            return u
    return None


async def _scrape_portfolio_education(url: str) -> list[Education]:
    """Scrape and extract education from candidate's portfolio/resume site strictly."""
    async with httpx.AsyncClient(headers=_BROWSER_HEADERS, timeout=8.0, follow_redirects=True) as client:
        res = await client.get(url)
        if res.status_code != 200:
            return []

        html = res.text
        cleaned_html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        cleaned_html = re.sub(r'<style[^>]*>.*?</style>', '', cleaned_html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '\n', cleaned_html)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        results: list[Education] = []

        # Find explicit education blocks
        in_edu_section = False
        for i, line in enumerate(lines):
            # Check if this section header represents Education
            if re.match(r'^(?:Education|Academic\s+Background|Qualifications|Studies|Degrees)$', line, re.IGNORECASE):
                in_edu_section = True
                continue
            elif in_edu_section and re.match(r'^(?:Skills|Experience|Projects|Portfolio|Contact|About)$', line, re.IGNORECASE):
                in_edu_section = False

            # Strict degree pattern match
            degree_match = None
            for pattern in _DEGREE_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    degree_match = line
                    break

            if degree_match:
                # Find university/college in context
                institution = None
                dates = None
                context_lines = lines[max(0, i - 2): min(len(lines), i + 4)]
                for ctx in context_lines:
                    if ctx == line:
                        continue
                    if _ACADEMIC_INSTITUTION_PATTERN.search(ctx):
                        institution = ctx
                    date_match = re.search(r'(20\d{2}\s*[-–—]\s*(?:20\d{2}|Present|\d{2})|20\d{2})', ctx)
                    if date_match and not dates:
                        dates = date_match.group(1)

                # Only include if we found a verified institution OR we are inside an explicit Education section
                if institution or in_edu_section:
                    start_date = None
                    end_date = None
                    if dates:
                        parts = re.split(r'[-–—]', dates)
                        start_date = parts[0].strip() if len(parts) > 0 else None
                        end_date = parts[1].strip() if len(parts) > 1 else None

                    results.append(
                        Education(
                            institution=institution or "Academic Institution",
                            degree=degree_match,
                            field_of_study=None,
                            start_date=start_date,
                            end_date=end_date,
                            description=None,
                        )
                    )

        # Deduplicate
        seen = set()
        deduped = []
        for e in results:
            key = (e.institution, e.degree)
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        return deduped
