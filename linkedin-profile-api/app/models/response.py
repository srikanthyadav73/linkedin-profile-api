"""
Response models.

These define the exact JSON shape returned by POST /api/profile. Every
field that may legitimately be absent from a profile is Optional — we
never fabricate data to fill a field; missing data is represented as
`null` (single values) or `[]` (lists).
"""

from pydantic import BaseModel, Field


class ProfileImages(BaseModel):
    profile: str | None = Field(None, description="URL of the profile photo")
    background: str | None = Field(None, description="URL of the background/cover image")


class Experience(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Education(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Certification(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issue_date: str | None = None
    expiration_date: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None


class Language(BaseModel):
    name: str | None = None
    proficiency: str | None = None


class ProfileResponse(BaseModel):
    """Full structured representation of a LinkedIn profile."""

    profile_url: str
    name: str | None = None
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    profile_images: ProfileImages = Field(default_factory=ProfileImages)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
