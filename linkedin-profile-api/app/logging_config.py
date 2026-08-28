"""
Logging configuration.

Centralizing logging setup here (instead of calling logging.basicConfig
scattered around the codebase) means every module gets consistent
formatting, and we have one place to enforce the rule: never log secrets,
tokens, or full request/response bodies that might contain personal data.
"""

import logging

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
