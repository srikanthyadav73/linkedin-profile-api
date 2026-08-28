"""
Custom application exceptions.

Why custom exceptions instead of raising generic ones (like ValueError)?
Because the route layer needs to know *what kind* of failure happened in
order to choose the correct HTTP status code. A generic exception can't
carry that meaning. Each class below maps to exactly one HTTP outcome,
which keeps that mapping explicit and easy to test.
"""


class LinkedInAPIError(Exception):
    """Base class for all errors raised by this application's domain logic."""


class InvalidURLError(LinkedInAPIError):
    """Raised when the supplied URL is not a valid LinkedIn profile URL. -> HTTP 400"""


class ProfileNotFoundError(LinkedInAPIError):
    """Raised when the profile does not exist or is not accessible. -> HTTP 404"""


class RateLimitError(LinkedInAPIError):
    """Raised when the upstream source is rate-limiting us. -> HTTP 429"""


class UpstreamUnavailableError(LinkedInAPIError):
    """Raised when the upstream data source is temporarily unreachable. -> HTTP 503"""
