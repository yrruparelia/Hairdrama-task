"""
app/routes/users.py — User Listing Route

Why do we need this?
  When creating/editing a task, the UI needs to show a list of all
  registered users so the task can be assigned to someone.
  This route returns all users (excluding sensitive fields).
"""

from flask import Blueprint, jsonify, request
from app.services.supabase_client import get_supabase_client
from app.routes.tasks import _decode_jwt   # shared JWT decode helper

users_bp = Blueprint("users", __name__)


@users_bp.get("/")
def list_users():
    """
    GET /api/users
    Returns all registered users (id, email, name, avatar_url).
    Requires a valid JWT in the Authorization header.
    """
    # We only want to expose this to authenticated users
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):   # error response tuple
        return payload

    supabase = get_supabase_client()
    result = (
        supabase.table("users")
        .select("id, email, name, avatar_url, created_at")  # never expose google_id
        .order("name")
        .execute()
    )

    return jsonify(result.data), 200
