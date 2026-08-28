"""
Unit tests for app/services/linkedin_voyager.py
"""

from app.services.linkedin_voyager import _parse_voyager_payload, extract_username


def test_extract_username() -> None:
    assert extract_username("https://www.linkedin.com/in/satyanadella/") == "satyanadella"
    assert extract_username("https://in.linkedin.com/in/madan-surthani-7a90571ba") == "madan-surthani-7a90571ba"
    assert extract_username("https://linkedin.com/in/williamhgates") == "williamhgates"


def test_parse_voyager_payload_structure() -> None:
    mock_payload = {
        "profile": {
            "firstName": "Satya",
            "lastName": "Nadella",
            "headline": "Chairman and CEO at Microsoft",
            "locationName": "Greater Seattle Area",
            "summary": "Satya Nadella is Chairman and CEO of Microsoft.",
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.identity.profile.Position",
                "title": "Chairman and CEO",
                "companyName": "Microsoft",
                "locationName": "Redmond, WA",
                "timePeriod": {"startDate": {"year": 2014, "month": 2}},
                "description": "Leading Microsoft.",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Education",
                "schoolName": "University of Chicago",
                "degreeName": "MBA",
                "fieldOfStudy": "Business",
                "timePeriod": {"startDate": {"year": 1995}, "endDate": {"year": 1997}},
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Skill",
                "name": "Cloud Computing",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Language",
                "name": "English",
                "proficiency": "NATIVE_OR_BILINGUAL",
            },
        ],
    }

    url = "https://www.linkedin.com/in/satyanadella/"
    profile = _parse_voyager_payload(mock_payload, url)

    assert profile.name == "Satya Nadella"
    assert profile.headline == "Chairman and CEO at Microsoft"
    assert len(profile.experience) == 1
    assert profile.experience[0].company == "Microsoft"
    assert len(profile.education) == 1
    assert profile.education[0].institution == "University of Chicago"
    assert profile.education[0].degree == "MBA"
    assert "Cloud Computing" in profile.skills
    assert len(profile.languages) == 1
    assert profile.languages[0].name == "English"
