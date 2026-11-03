"""Google OAuth and JWT authentication routes."""

from flask import Blueprint, redirect, request, jsonify, current_app, session
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
import datetime
from typing import cast

from app.services.supabase_client import get_supabase_client

auth_bp = Blueprint("auth", __name__)


def _build_flow() -> Flow:
    """Build the Google OAuth flow from application settings."""
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [current_app.config["GOOGLE_REDIRECT_URI"]],
            }
        },
        scopes=current_app.config["GOOGLE_SCOPES"],
        redirect_uri=current_app.config["GOOGLE_REDIRECT_URI"],
    )


def _create_jwt(user: dict) -> str:
    """Create a signed JWT containing the user's profile."""
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=current_app.config["JWT_EXPIRY_HOURS"]
    )
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user.get("name", ""),
        "avatar_url": user.get("avatar_url", ""),
        "exp": expiry,
    }
    token = jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return token


# Start Google OAuth.
@auth_bp.get("/google")
def google_login():
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",   # request refresh_token
        include_granted_scopes="true",
        prompt="select_account",  # always show account picker
    )
    session["oauth_state"] = state
    session["oauth_code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


# Handle Google's OAuth callback.
@auth_bp.get("/callback")
def google_callback():
    flow = _build_flow()
    flow.code_verifier = session.pop("oauth_code_verifier", None)
    session.pop("oauth_state", None)
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    oauth_id_token = getattr(credentials, "id_token", None)
    if not oauth_id_token:
        raise ValueError("Google OAuth response did not include an ID token")

    id_info = id_token.verify_oauth2_token(
        oauth_id_token,
        google_requests.Request(),
        current_app.config["GOOGLE_CLIENT_ID"],
    )

    google_id = id_info["sub"]          # Google's unique user ID
    email = id_info["email"]
    name = id_info.get("name", "")
    avatar_url = id_info.get("picture", "")

    supabase = get_supabase_client()
    result = (
        supabase.table("users")
        .upsert(
            {
                "google_id": google_id,
                "email": email,
                "name": name,
                "avatar_url": avatar_url,
            },
            on_conflict="google_id",   # update if google_id already exists
        )
        .execute()
    )

    user = cast(dict, result.data[0])

    token = _create_jwt(user)

    frontend_url = current_app.config["FRONTEND_URL"]
    return redirect(f"{frontend_url}/auth/callback?token={token}")


# Return the current authenticated user.
@auth_bp.get("/me")
def get_me():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired. Please log in again."}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    return jsonify(payload), 200
