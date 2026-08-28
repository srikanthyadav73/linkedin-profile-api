"""
Application entrypoint.

This file's ONLY job is to build the FastAPI app object: create it,
register routers, configure logging, and add app-wide exception
handling. It intentionally contains no business logic — that lives in
app/services and app/routes.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.logging_config import configure_logging
from app.routes.profile import router as profile_router
from app.utils.exceptions import (
    InvalidURLError,
    LinkedInAPIError,
    ProfileNotFoundError,
    RateLimitError,
    UpstreamUnavailableError,
)

_STATIC_DIR = Path(__file__).parent.parent / "static"

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Accepts a LinkedIn profile URL and returns structured profile data as JSON.",
    version="0.1.0",
)

app.include_router(profile_router)

# Serve the dashboard at /
# Mount static files for any future assets (CSS, JS, images).
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    """Serve the frontend dashboard."""
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple liveness check used by the hosting provider and for manual testing."""
    return {"status": "ok"}


# --- Global exception handlers -------------------------------------------
# These translate our internal domain exceptions (app/utils/exceptions.py)
# into the correct HTTP status codes, in one place, so individual routes
# don't need repetitive try/except blocks.

@app.exception_handler(InvalidURLError)
async def handle_invalid_url(request: Request, exc: InvalidURLError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ProfileNotFoundError)
async def handle_not_found(request: Request, exc: ProfileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(RateLimitError)
async def handle_rate_limit(request: Request, exc: RateLimitError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(UpstreamUnavailableError)
async def handle_upstream_unavailable(
    request: Request, exc: UpstreamUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(LinkedInAPIError)
async def handle_generic_domain_error(request: Request, exc: LinkedInAPIError) -> JSONResponse:
    # Catch-all for any domain exception we haven't special-cased above.
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})
