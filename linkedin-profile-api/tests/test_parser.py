"""
Unit tests for app/services/parser.py — based on REAL Captapi response shape.

Field names confirmed from live API logs:
  - profileImage  (not profilePicture)
  - certifications[].authority  (not issuingOrganization)
  - startDate / endDate as stringified dicts "{'year': 2024, 'month': 'May'}"
  - NO education, skills, languages fields
"""

from app.services.parser import _parse_date, parse_profile

LINKEDIN_URL = "https://www.linkedin.com/in/madan-surthani-7a90571ba/"


# ---------------------------------------------------------------------------
# Fixtures — using REAL Captapi field names
# ---------------------------------------------------------------------------

def _full_raw() -> dict:
    return {
        "platform": "linkedin",
        "type": "person",
        "url": LINKEDIN_URL,
        "username": "madan-surthani-7a90571ba",
        "name": "Madan Surthani",
        "headline": "Associate Developer at Ealkay Consulting",
        "location": "Hyderabad, Telangana, India",
        "about": "Software developer with Python expertise.<br><br>Contact: test@example.com",
        "followers": 1769,
        "connections": 500,
        "profileImage": "https://static.licdn.com/photo.jpg",
        "currentCompany": "Ealkay Consulting",
        "experience": [
            {
                "title": "Associate Developer",
                "company": "Ealkay Consulting",
                "location": "Hyderabad, Telangana, India",
                "description": "Building scalable backend applications.",
                "startDate": "{'year': 2025, 'month': 'May'}",
                "isCurrent": True,
                "endDate": None,
            },
            {
                "title": "Software Developer",
                "company": "Nano Kernel Ltd",
                "location": "Bengaluru, Karnataka, India",
                "description": "Django therapy booking platform.",
                "startDate": "{'year': 2024, 'month': 'May'}",
                "isCurrent": False,
                "endDate": "{'year': 2024, 'month': 'Oct'}",
            },
        ],
        "projects": [],
        "certifications": [
            {"name": "Full stack data science", "authority": "Naresh i Technologies"},
            {"name": "Tata Data Visualisation", "authority": "Forage"},
        ],
        "timings": {"totalMs": 16765},
        "fetchedAt": "2026-08-27T12:24:36.675Z",
    }


def _minimal_raw() -> dict:
    return {
        "name": None,
        "headline": None,
        "location": None,
        "about": None,
        "profileImage": None,
        "experience": [],
        "certifications": [],
    }


def _empty_raw() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Tests: _parse_date helper
# ---------------------------------------------------------------------------

def test_parse_date_stringified_dict_with_month() -> None:
    assert _parse_date("{'year': 2024, 'month': 'May'}") == "May 2024"

def test_parse_date_stringified_dict_year_only() -> None:
    assert _parse_date("{'year': 2023, 'month': 'Oct'}") == "Oct 2023"

def test_parse_date_none() -> None:
    assert _parse_date(None) is None

def test_parse_date_real_dict() -> None:
    assert _parse_date({"year": 2022, "month": "Jan"}) == "Jan 2022"

def test_parse_date_plain_string_passthrough() -> None:
    assert _parse_date("2022-01") == "2022-01"

# ---------------------------------------------------------------------------
# Tests: basic field mapping
# ---------------------------------------------------------------------------

def test_profile_url_preserved() -> None:
    assert parse_profile(_full_raw(), LINKEDIN_URL).profile_url == LINKEDIN_URL

def test_name_mapped() -> None:
    assert parse_profile(_full_raw(), LINKEDIN_URL).name == "Madan Surthani"

def test_name_none_when_absent() -> None:
    assert parse_profile(_empty_raw(), LINKEDIN_URL).name is None

def test_headline_mapped() -> None:
    p = parse_profile(_full_raw(), LINKEDIN_URL)
    assert p.headline == "Associate Developer at Ealkay Consulting"

def test_location_mapped() -> None:
    p = parse_profile(_full_raw(), LINKEDIN_URL)
    assert p.location == "Hyderabad, Telangana, India"

def test_about_html_stripped() -> None:
    p = parse_profile(_full_raw(), LINKEDIN_URL)
    assert "<br>" not in p.about
    assert "Software developer" in p.about

def test_about_none_when_absent() -> None:
    assert parse_profile(_empty_raw(), LINKEDIN_URL).about is None

# ---------------------------------------------------------------------------
# Tests: profile image — uses profileImage not profilePicture
# ---------------------------------------------------------------------------

def test_profile_image_mapped_from_profileImage() -> None:
    p = parse_profile(_full_raw(), LINKEDIN_URL)
    assert p.profile_images.profile == "https://static.licdn.com/photo.jpg"

def test_profile_image_none_when_absent() -> None:
    assert parse_profile(_empty_raw(), LINKEDIN_URL).profile_images.profile is None

def test_background_always_none() -> None:
    assert parse_profile(_full_raw(), LINKEDIN_URL).profile_images.background is None

# ---------------------------------------------------------------------------
# Tests: experience
# ---------------------------------------------------------------------------

def test_experience_count() -> None:
    assert len(parse_profile(_full_raw(), LINKEDIN_URL).experience) == 2

def test_experience_fields() -> None:
    exp = parse_profile(_full_raw(), LINKEDIN_URL).experience[0]
    assert exp.title == "Associate Developer"
    assert exp.company == "Ealkay Consulting"
    assert exp.location == "Hyderabad, Telangana, India"
    assert exp.start_date == "May 2025"
    assert exp.end_date is None
    assert "backend" in exp.description

def test_experience_end_date_parsed() -> None:
    exp = parse_profile(_full_raw(), LINKEDIN_URL).experience[1]
    assert exp.start_date == "May 2024"
    assert exp.end_date == "Oct 2024"

def test_experience_empty_when_absent() -> None:
    assert parse_profile(_minimal_raw(), LINKEDIN_URL).experience == []

# ---------------------------------------------------------------------------
# Tests: certifications — uses 'authority' not 'issuingOrganization'
# ---------------------------------------------------------------------------

def test_certifications_count() -> None:
    assert len(parse_profile(_full_raw(), LINKEDIN_URL).certifications) == 2

def test_certification_fields() -> None:
    cert = parse_profile(_full_raw(), LINKEDIN_URL).certifications[0]
    assert cert.name == "Full stack data science"
    assert cert.issuer == "Naresh i Technologies"

def test_certifications_empty_when_absent() -> None:
    assert parse_profile(_minimal_raw(), LINKEDIN_URL).certifications == []

# ---------------------------------------------------------------------------
# Tests: education / skills / languages
# ---------------------------------------------------------------------------

def test_education_parsing_from_raw() -> None:
    raw = {
        "education": [
            {
                "school": "Stanford University",
                "degree": "Master of Science",
                "fieldOfStudy": "Computer Science",
                "startDate": "{'year': 2020, 'month': 'Sep'}",
                "endDate": "{'year': 2022, 'month': 'Jun'}",
            }
        ]
    }
    edu = parse_profile(raw, LINKEDIN_URL).education
    assert len(edu) == 1
    assert edu[0].institution == "Stanford University"
    assert edu[0].degree == "Master of Science"
    assert edu[0].field_of_study == "Computer Science"
    assert edu[0].start_date == "Sep 2020"
    assert edu[0].end_date == "Jun 2022"


def test_skills_extraction_from_text() -> None:
    profile = parse_profile(_full_raw(), LINKEDIN_URL)
    assert len(profile.skills) > 0
    assert "Python" in profile.skills
    assert "Django" in profile.skills


def test_skills_parsing_from_raw_array() -> None:
    raw = {"skills": ["FastAPI", "Docker", "PostgreSQL"]}
    profile = parse_profile(raw, LINKEDIN_URL)
    assert profile.skills == ["FastAPI", "Docker", "PostgreSQL"]


def test_languages_parsing_from_raw() -> None:
    raw = {
        "languages": [
            {"name": "English", "proficiency": "Full professional"},
            {"name": "Hindi", "proficiency": "Native"},
        ]
    }
    langs = parse_profile(raw, LINKEDIN_URL).languages
    assert len(langs) == 2
    assert langs[0].name == "English"
    assert langs[0].proficiency == "Full professional"
    assert langs[1].name == "Hindi"

