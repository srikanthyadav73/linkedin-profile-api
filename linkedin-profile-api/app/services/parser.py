"""
Captapi response parser.

Maps the raw ``data`` dict returned by Captapi's GET /v1/linkedin/profile
endpoint into our internal ProfileResponse model.

Confirmed Captapi response shape (from live logs + August 2026 changelog):
{
  "platform": "linkedin",
  "type": "person",
  "url": str,
  "username": str,
  "name": str | None,
  "headline": str | None,
  "location": str | None,
  "about": str | None,
  "followers": int | None,
  "connections": int | None,          -- null on guest scrape (LinkedIn limit)
  "profileImage": str | None,
  "currentCompany": str | None,
  "experience": [
    {
      "title": str | None,
      "company": str | None,
      "location": str | None,
      "description": str | None,
      "startDate": str | None,        -- stringified dict "{'year': 2024, 'month': 'May'}"
      "endDate": str | None,          -- same format, or None for current roles
      "isCurrent": bool,
    }
  ],
  "education": [                      -- present when Apify enrichment fires
    {
      "school": str | None,           -- institution name
      "degree": str | None,
      "fieldOfStudy": str | None,
      "startDate": str | None,        -- same stringified-dict format
      "endDate": str | None,
      "description": str | None,
    }
  ],
  "projects": [ { "name": str, "description": str } ],
  "certifications": [
    {
      "name": str | None,
      "authority": str | None,        -- NOT issuingOrganization
    }
  ],
  "languages": [                      -- present when Apify enrichment fires
    {
      "name": str | None,
      "proficiency": str | None,
    }
  ],
  "timings": {...},
  "fetchedAt": str,
}

NOTE: "skills" is NOT in Captapi's response — confirmed from changelog which
lists every additive section (experience, education, similarProfiles, projects,
publications, articles, activity, recommendations, certifications, languages)
and does not include skills. skills always returns [].
"""

import ast
import logging
import re

from app.models.response import (
    Certification,
    Education,
    Experience,
    Language,
    ProfileImages,
    ProfileResponse,
)

logger = logging.getLogger(__name__)

# Standard technical & industry skills taxonomy for keyword extraction
_COMMON_SKILLS_KEYWORDS = [
    # Languages & Core
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Golang", "Rust", "PHP", "Ruby", "SQL", "HTML", "CSS", "R", "Kotlin", "Swift",
    # Frameworks & Backend
    "Django", "Django REST Framework", "FastAPI", "Flask", "Node.js", "Express", "Spring Boot", "Next.js", "React", "Vue", "Angular", "Tailwind CSS",
    # Databases & Caching
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "DynamoDB", "Cassandra", "Elasticsearch", "pgvector",
    # Cloud & DevOps
    "AWS", "AWS EC2", "AWS S3", "AWS Lambda", "CloudWatch", "Docker", "Kubernetes", "Heroku", "GCP", "Azure", "CI/CD", "Git", "GitHub", "Linux",
    # Architecture & Tools
    "REST API", "RESTful APIs", "GraphQL", "WebSockets", "Celery", "RabbitMQ", "Kafka", "Microservices", "OAuth2", "JWT",
    # AI / ML / Data
    "RAG", "LLMs", "AI Agents", "Vector Search", "Embeddings", "Machine Learning", "Deep Learning", "Data Science", "Data Analytics", "NLP", "PyTorch", "TensorFlow", "Pandas", "NumPy",
    # Testing & Methods
    "Pytest", "Postman", "Unit Testing", "API Testing", "Agile", "Scrum"
]


def parse_profile(raw: dict, linkedin_url: str) -> ProfileResponse:
    """
    Convert a raw Captapi ``data`` dict into a ProfileResponse.

    Parameters
    ----------
    raw:
        The ``data`` object from Captapi's response body.
    linkedin_url:
        The original request URL — used as profile_url in the response.
    """
    keys = list(raw.keys())
    logger.info(
        "Parsing Captapi response — keys: %s | raw education: %s | raw languages: %s",
        keys,
        len(raw.get("education") or []),
        len(raw.get("languages") or []),
    )

    profile_images = ProfileImages(
        profile=raw.get("profileImage") or raw.get("profilePicture"),
        background=raw.get("backgroundImage") or raw.get("coverImage"),
    )

    experience = [
        _parse_experience(exp)
        for exp in (raw.get("experience") or raw.get("experiences") or [])
        if isinstance(exp, dict)
    ]

    education = _parse_education_list(raw)
    skills = _parse_skills(raw, experience)
    certifications = [
        _parse_certification(cert)
        for cert in (raw.get("certifications") or [])
        if isinstance(cert, dict)
    ]
    languages = _parse_languages_list(raw)

    return ProfileResponse(
        profile_url=linkedin_url,
        name=raw.get("name"),
        headline=raw.get("headline"),
        location=raw.get("location"),
        about=_clean_about(raw.get("about")),
        profile_images=profile_images,
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean_about(text: str | None) -> str | None:
    """Strip HTML tags from the about field (Captapi returns <br> tags)."""
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip() or None


def _parse_date(raw_date) -> str | None:
    """
    Captapi returns dates as stringified Python dicts:
        "{'year': 2024, 'month': 'May'}"
    or as plain dicts, or None.
    Returns a clean "Month YYYY" string.
    """
    if not raw_date:
        return None
    if isinstance(raw_date, dict):
        d = raw_date
    elif isinstance(raw_date, str):
        try:
            d = ast.literal_eval(raw_date)
        except (ValueError, SyntaxError):
            return raw_date.strip()  # already a clean string
    else:
        return str(raw_date)

    year = d.get("year", "")
    month = d.get("month", "")
    if month and year:
        return f"{month} {year}"
    return str(year) if year else None


def _parse_experience(exp: dict) -> Experience:
    return Experience(
        title=exp.get("title") or exp.get("role"),
        company=exp.get("company") or exp.get("companyName"),
        location=exp.get("location"),
        start_date=_parse_date(exp.get("startDate") or exp.get("start_date")),
        end_date=_parse_date(exp.get("endDate") or exp.get("end_date")),
        description=exp.get("description"),
    )


def _parse_education_list(raw: dict) -> list[Education]:
    """Parse education from raw payload or infer from profile text."""
    raw_edu = (
        raw.get("education")
        or raw.get("educations")
        or raw.get("schools")
        or raw.get("studies")
        or []
    )
    if raw_edu and isinstance(raw_edu, list):
        parsed = []
        for edu in raw_edu:
            if isinstance(edu, dict):
                parsed.append(_parse_education_entry(edu))
        if parsed:
            return parsed

    # Fallback: Check if education or degree info is mentioned in about or headline
    about_text = raw.get("about") or ""
    headline_text = raw.get("headline") or ""
    combined_text = f"{headline_text}\n{about_text}"

    edu_matches = re.findall(
        r"(?:Bachelor|Master|B\.Tech|B\.E\.|B\.Sc|M\.Tech|M\.Sc|BCA|MCA|MBA|Ph\.D|Diploma)\s+(?:of|in)?\s*[^,\n\.]+(?:at|from)?\s*[^,\n\.]*",
        combined_text,
        re.IGNORECASE,
    )
    if edu_matches:
        results = []
        for match in edu_matches[:2]:
            clean_match = match.strip()
            if clean_match:
                results.append(
                    Education(
                        institution="Mentioned in Profile",
                        degree=clean_match,
                        field_of_study=None,
                        start_date=None,
                        end_date=None,
                        description=None,
                    )
                )
        if results:
            return results

    return []


def _parse_education_entry(edu: dict) -> Education:
    return Education(
        institution=(
            edu.get("school")
            or edu.get("institution")
            or edu.get("schoolName")
            or edu.get("collegeName")
            or edu.get("university")
        ),
        degree=edu.get("degree") or edu.get("degreeName"),
        field_of_study=edu.get("fieldOfStudy") or edu.get("field_of_study") or edu.get("major"),
        start_date=_parse_date(edu.get("startDate") or edu.get("start_date")),
        end_date=_parse_date(edu.get("endDate") or edu.get("end_date")),
        description=edu.get("description"),
    )


def _parse_skills(raw: dict, experiences: list[Experience]) -> list[str]:
    """
    Extract skills from raw payload (if present) or intelligently extract
    technical skills from experience descriptions, projects, about, and certifications.
    """
    raw_skills = raw.get("skills") or []
    if raw_skills and isinstance(raw_skills, list):
        extracted_skills = []
        for s in raw_skills:
            if isinstance(s, str) and s.strip():
                extracted_skills.append(s.strip())
            elif isinstance(s, dict) and s.get("name"):
                extracted_skills.append(s["name"].strip())
        if extracted_skills:
            return list(dict.fromkeys(extracted_skills))

    # Smart extraction from text:
    skills_found: list[str] = []
    text_blocks = []

    if raw.get("about"):
        text_blocks.append(raw["about"])
    if raw.get("headline"):
        text_blocks.append(raw["headline"])

    for exp in experiences:
        if exp.description:
            text_blocks.append(exp.description)
        if exp.title:
            text_blocks.append(exp.title)

    for proj in raw.get("projects") or []:
        if isinstance(proj, dict):
            if proj.get("name"):
                text_blocks.append(proj["name"])
            if proj.get("description"):
                text_blocks.append(proj["description"])

    for cert in raw.get("certifications") or []:
        if isinstance(cert, dict) and cert.get("name"):
            text_blocks.append(cert["name"])

    full_text = "\n".join(text_blocks)

    # 1. Extract explicit "Key Skills: a, b, c" or "✔️ Skill" patterns
    explicit_matches = re.findall(
        r"(?:Key\s*Skills|Expertise|Tech\s*Stack|Technologies)\s*:\s*([^\n\r]+)",
        full_text,
        re.IGNORECASE,
    )
    for match in explicit_matches:
        parts = re.split(r"[,|•·/]\s*", match)
        for p in parts:
            p_clean = re.sub(r"^[\s\-✔️•*]+", "", p).strip()
            if p_clean and len(p_clean) < 40:
                skills_found.append(p_clean)

    # 2. Extract bulleted "✔️ Skill Name" patterns
    bullet_matches = re.findall(r"[✔️•\-\*]\s*([A-Za-z0-9+#\.\s/\(\)&-]{3,35})", full_text)
    for b in bullet_matches:
        b_clean = b.strip()
        if (
            b_clean
            and not b_clean.lower().startswith(("reach me", "developed", "built", "managed", "designed"))
            and len(b_clean) < 35
        ):
            skills_found.append(b_clean)

    # 3. Match against known keyword taxonomy
    for keyword in _COMMON_SKILLS_KEYWORDS:
        # Match as whole word / token
        pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
        if re.search(pattern, full_text, re.IGNORECASE):
            skills_found.append(keyword)

    # Clean, normalize and deduplicate preserving case & order
    seen = set()
    cleaned_skills = []
    for s in skills_found:
        s_stripped = s.strip()
        norm = s_stripped.lower()
        if norm and norm not in seen and len(s_stripped) > 1:
            seen.add(norm)
            cleaned_skills.append(s_stripped)

    return cleaned_skills


def _parse_certification(cert: dict) -> Certification:
    """Captapi uses 'authority', not 'issuingOrganization'."""
    return Certification(
        name=cert.get("name") or cert.get("title"),
        issuer=cert.get("authority") or cert.get("issuer") or cert.get("issuingOrganization"),
        issue_date=_parse_date(cert.get("issueDate") or cert.get("issue_date")),
        expiration_date=_parse_date(cert.get("expirationDate") or cert.get("expiration_date")),
        credential_id=cert.get("credentialId") or cert.get("credential_id") or cert.get("id"),
        credential_url=cert.get("credentialUrl") or cert.get("credential_url") or cert.get("url"),
    )


def _parse_languages_list(raw: dict) -> list[Language]:
    """Parse languages array from raw data or fallback from about."""
    raw_langs = raw.get("languages") or raw.get("language") or []
    parsed_langs = []
    if isinstance(raw_langs, list):
        for lang in raw_langs:
            if isinstance(lang, dict):
                parsed_langs.append(
                    Language(
                        name=lang.get("name") or lang.get("language"),
                        proficiency=lang.get("proficiency") or lang.get("level"),
                    )
                )
            elif isinstance(lang, str) and lang.strip():
                parsed_langs.append(Language(name=lang.strip(), proficiency=None))

    if parsed_langs:
        return parsed_langs

    # Fallback: check about text for "Languages: English, Hindi, Telugu"
    about = raw.get("about") or ""
    lang_match = re.search(r"Languages?\s*:\s*([^\n\r\.]+)", about, re.IGNORECASE)
    if lang_match:
        items = re.split(r"[,|/•]\s*", lang_match.group(1))
        for item in items:
            cleaned = item.strip()
            if cleaned and len(cleaned) < 25:
                parsed_langs.append(Language(name=cleaned, proficiency=None))

    return parsed_langs
