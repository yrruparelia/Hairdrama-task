"""Supabase client factory."""

import os
from supabase import create_client, Client
from flask import current_app


def get_supabase_client() -> Client:
    """Return a Supabase client configured from Flask settings."""
    url: str = current_app.config["SUPABASE_URL"]
    key: str = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment."
        )

    return create_client(url, key)
