"""
Request models.

Pydantic models define the *shape* of incoming JSON and validate it
automatically. If a client sends malformed JSON or is missing a required
field, FastAPI + Pydantic return a 422 error before our route code ever
runs — we don't have to write that validation by hand.
"""

from pydantic import BaseModel, Field, field_validator

from app.utils.validator import is_valid_linkedin_profile_url


class ProfileRequest(BaseModel):
    """Request body for POST /api/profile."""

    linkedin_url: str = Field(
        ...,
        description="A full LinkedIn profile URL, e.g. https://www.linkedin.com/in/example/",
        examples=["https://www.linkedin.com/in/example/"],
    )

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, value: str) -> str:
        """
        Reject obviously-invalid URLs at the model level.

        Doing this in the Pydantic model (rather than only in the route)
        means FastAPI automatically returns a 422 with a clear error
        message for bad input, and this validation is reused anywhere
        else this model is used (e.g. in tests).
        """
        if not is_valid_linkedin_profile_url(value):
            raise ValueError(
                "linkedin_url must be a valid LinkedIn profile URL, "
                "e.g. https://www.linkedin.com/in/example/"
            )
        return value
