"""
Validation for LinkedIn profile URLs.

A valid LinkedIn *profile* URL (as opposed to a company page, job posting,
etc.) looks like:

    https://www.linkedin.com/in/some-slug/
    https://linkedin.com/in/some-slug
    https://www.linkedin.com/in/some-slug-123abc/

We validate the full structure with a regex rather than a loose substring
check like `"linkedin.com" in url`, because a substring check can be
trivially fooled, e.g.:

    https://evil.com/?next=linkedin.com   <- contains "linkedin.com" but
                                              is not a LinkedIn URL at all
"""

import re
from urllib.parse import urlparse

# Matches https://[www.|in.|uk.]linkedin.com/in/<slug> with an optional trailing slash
_PROFILE_PATH_PATTERN = re.compile(r"^/in/[a-zA-Z0-9\-_%À-ÿ]{2,100}/?$")


def is_valid_linkedin_profile_url(url: str) -> bool:
    """
    Return True if `url` is a syntactically valid LinkedIn profile URL.
    Supports global and regional country domains (e.g. in.linkedin.com, uk.linkedin.com).
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False

    if parsed.scheme != "https":
        return False

    netloc = parsed.netloc.lower()
    # Matches linkedin.com, www.linkedin.com, in.linkedin.com, uk.linkedin.com, etc.
    if netloc != "linkedin.com" and not netloc.endswith(".linkedin.com"):
        return False

    if not _PROFILE_PATH_PATTERN.match(parsed.path):
        return False

    return True
