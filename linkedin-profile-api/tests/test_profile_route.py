"""
Integration tests for POST /api/profile — Phase 2 (Captapi provider).

We mock app.services.captapi.fetch_profile so no real HTTP calls are
made. This lets us test the full request→route→service→parser→response
pipeline, including error handling, without needing an API key or network.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.utils.exceptions import (
    ProfileNotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
)

client = TestClient(app)

VALID_URL = "https://www.linkedin.com/in/williamhgates/"

# Representative Captapi data object (the `data` field from the envelope).
_MOCK_RAW = {
    "platform": "linkedin",
    "type": "person",
    "name": "William Gates",
    "headline": "Co-chair at Bill & Melinda Gates Foundation",
    "location": "Seattle, WA, US",
    "about": "Co-chair of the Bill &amp; Melinda Gates Foundation.",
    "profileImage": "https://example.com/photo.jpg",
    "currentCompany": "Bill & Melinda Gates Foundation",
    "experience": [
        {
            "title": "Co-chair",
            "company": "Bill & Melinda Gates Foundation",
            "location": "Seattle, WA",
            "startDate": "{'year': 2000, 'month': 'Jan'}",
            "endDate": None,
            "isCurrent": True,
            "description": "Philanthropy work.",
        }
    ],
    "certifications": [
        {"name": "Example Cert", "authority": "Example Org"},
    ],
}


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_valid_request_returns_200_with_real_data() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        return_value=_MOCK_RAW,
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    assert response.status_code == 200
    body = response.json()
    assert body["profile_url"] == VALID_URL
    assert body["name"] == "William Gates"
    assert body["headline"] == "Co-chair at Bill & Melinda Gates Foundation"
    assert body["location"] == "Seattle, WA, US"
    assert body["profile_images"]["profile"] == "https://example.com/photo.jpg"
    assert len(body["experience"]) == 1
    assert body["experience"][0]["title"] == "Co-chair"
    assert body["experience"][0]["company"] == "Bill & Melinda Gates Foundation"
    assert body["experience"][0]["start_date"] == "Jan 2000"
    # education/skills/languages not from Captapi — always empty
    assert body["education"] == []
    assert body["skills"] == []
    assert body["languages"] == []
    assert len(body["certifications"]) == 1
    assert body["certifications"][0]["issuer"] == "Example Org"


def test_response_contains_all_required_schema_keys() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        return_value=_MOCK_RAW,
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    body = response.json()
    for key in (
        "profile_url", "name", "headline", "location", "about",
        "profile_images", "experience", "education",
        "skills", "certifications", "languages",
    ):
        assert key in body, f"Missing key in response: {key}"


def test_background_image_mapped() -> None:
    # Captapi doesn't return background image — always None
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        return_value=_MOCK_RAW,
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    assert response.json()["profile_images"]["background"] is None


# ---------------------------------------------------------------------------
# Error paths — service exceptions map to correct HTTP codes
# ---------------------------------------------------------------------------

def test_profile_not_found_returns_404() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        side_effect=ProfileNotFoundError("Profile not found."),
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    assert response.status_code == 404
    assert "detail" in response.json()


def test_rate_limit_returns_429() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        side_effect=RateLimitError("Rate limited."),
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    assert response.status_code == 429
    assert "detail" in response.json()


def test_upstream_unavailable_returns_503() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        side_effect=UpstreamUnavailableError("Service down."),
    ):
        response = client.post("/api/profile", json={"linkedin_url": VALID_URL})

    assert response.status_code == 503
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Input validation (Pydantic layer — no service call needed)
# ---------------------------------------------------------------------------

def test_invalid_url_returns_422_no_service_call() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
    ) as mock_fetch:
        response = client.post(
            "/api/profile", json={"linkedin_url": "https://google.com"}
        )
        mock_fetch.assert_not_called()

    assert response.status_code == 422


def test_missing_body_returns_422() -> None:
    response = client.post("/api/profile", json={})
    assert response.status_code == 422


def test_non_https_linkedin_url_returns_422() -> None:
    response = client.post(
        "/api/profile",
        json={"linkedin_url": "http://www.linkedin.com/in/example/"},
    )
    assert response.status_code == 422
