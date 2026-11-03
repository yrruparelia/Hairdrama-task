"""User listing routes."""

from flask import Blueprint, jsonify, request
from app.services.supabase_client import get_supabase_client
from app.routes.tasks import _decode_jwt   # shared JWT decode helper

users_bp = Blueprint("users", __name__)


@users_bp.get("/")
def list_users():
    """Return users available for task assignment."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()
    result = (
        supabase.table("users")
        .select("id, email, name, avatar_url, created_at")
        .order("name")
        .execute()
    )

    return jsonify(result.data), 200
