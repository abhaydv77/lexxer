"""API configuration: CORS origins and general settings.

Keep CORS configuration here so it is easy to modify when the frontend
origin changes. Origins can also be overridden at runtime via the
``LEXXER_CORS_ORIGINS`` environment variable (comma-separated).
"""

from __future__ import annotations

import os

# Default local development origins for the Lovable-built frontend.
DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    """Return the CORS allow-list, honouring ``LEXXER_CORS_ORIGINS``.

    The environment variable overrides the defaults entirely; it is a
    comma-separated list of origins, e.g.
    ``LEXXER_CORS_ORIGINS=http://localhost:5173,http://localhost:3000``.
    """
    override = os.environ.get("LEXXER_CORS_ORIGINS")
    if override:
        origins = [origin.strip() for origin in override.split(",") if origin.strip()]
        if origins:
            return origins
    return list(DEFAULT_CORS_ORIGINS)
