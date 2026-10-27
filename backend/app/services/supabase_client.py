"""
app/services/supabase_client.py — Singleton Supabase Client

Why a singleton?
  Creating a new Supabase client on every request is wasteful.
  We create it once at module load time and reuse it everywhere.

Why service_role key?
  The service_role key bypasses Row Level Security (RLS), which is
  what we want here because our Flask backend is trusted server-side code.
  The anon key is meant for direct browser/client usage.

Usage (in any route file):
    from app.services.supabase_client import supabase
    result = supabase.table("tasks").select("*").execute()
"""

import os
from supabase import create_client, Client
from flask import current_app


def get_supabase_client() -> Client:
    """
    Returns a Supabase client initialised with the project URL
    and the service_role key from Flask's config.
    """
    url: str = current_app.config["SUPABASE_URL"]
    key: str = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment."
        )

    return create_client(url, key)
