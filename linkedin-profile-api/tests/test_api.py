"""
Core API smoke tests.

We use FastAPI's TestClient, which runs the app in-process (no real
network calls, no real server needed) — fast and deterministic.

Phase 2 note: POST /api/profile now calls the Captapi service, so we
mock fetch_profile to avoid needing a real API key in CI. Detailed
route + service tests live in test_profile_route.py.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_MOCK_RAW = {
    "platform": "linkedin",
    "type": "person",
    "name": "Jane Doe",
    "headline": "Software Engineer at Example Corp",
    "location": "Hyderabad, India",
    "about": "Placeholder bio.",
    "profileImage": None,
    "experience": [
        {
            "title": "Software Engineer",
            "company": "Example Corp",
            "location": "Hyderabad, India",
            "startDate": "{'year': 2022, 'month': 'Jan'}",
            "endDate": None,
            "isCurrent": True,
            "description": None,
        }
    ],
    "certifications": [],
}


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_valid_profile_request_returns_200() -> None:
    with patch(
        "app.services.captapi.fetch_profile",
        new_callable=AsyncMock,
        return_value=_MOCK_RAW,
    ):
        response = client.post(
            "/api/profile",
            json={"linkedin_url": "https://www.linkedin.com/in/example/"},
        )

    assert response.status_code == 200

    body = response.json()
    assert body["profile_url"] == "https://www.linkedin.com/in/example/"
    for key in (
        "name", "headline", "location", "about",
        "profile_images", "experience", "education",
        "skills", "certifications", "languages",
    ):
        assert key in body


def test_invalid_domain_returns_422() -> None:
    response = client.post("/api/profile", json={"linkedin_url": "https://google.com"})
    assert response.status_code == 422


def test_missing_field_returns_422() -> None:
    response = client.post("/api/profile", json={})
    assert response.status_code == 422


def test_malformed_url_returns_422() -> None:
    response = client.post("/api/profile", json={"linkedin_url": "not-a-url"})
    assert response.status_code == 422
