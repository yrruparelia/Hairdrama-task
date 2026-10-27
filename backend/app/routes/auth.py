"""
app/routes/auth.py — Google OAuth 2.0 Routes

This module handles the complete OAuth 2.0 Authorization Code Flow:

  Step 1: /auth/google
    User's browser visits this URL.
    We build a Google authorization URL (with our client_id, scopes, redirect_uri).
    We redirect the user to Google's login/consent page.

  Step 2: Google → /auth/callback
    After the user approves, Google redirects back with ?code=...&state=...
    We exchange the `code` for an access_token + id_token.
    We decode the id_token to get the user's profile (email, name, avatar).
    We upsert the user into Supabase (create if new, update if returning).
    We issue our own JWT and redirect to the frontend with it.

  Step 3: /auth/me
    Frontend calls this with the JWT to get the logged-in user's profile.

Why JWT instead of Flask sessions?
  Our frontend (Next.js on Vercel) and backend (Flask on Railway) are on
  different domains. Cookie-based sessions break across domains. JWTs are
  sent in the Authorization header, which works across origins.
"""

from flask import Blueprint, redirect, request, jsonify, current_app
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import jwt
import datetime

from app.services.supabase_client import get_supabase_client

auth_bp = Blueprint("auth", __name__)


def _build_flow() -> Flow:
    """
    Build a google_auth_oauthlib Flow object from our app config.
    The Flow object handles building the auth URL and exchanging the code.
    """
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
    """
    Issue a signed JWT for a user.

    Payload includes:
      sub  — Supabase user UUID (used to identify the user in API calls)
      email — for display / convenience
      name  — display name
      exp   — expiry timestamp (default 24h)
    """
    expiry = datetime.datetime.utcnow() + datetime.timedelta(
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


# ── Step 1: Initiate OAuth ────────────────────────────────────────────────────
@auth_bp.get("/google")
def google_login():
    """
    Redirect the user to Google's OAuth consent screen.
    `authorization_url` is built by the Flow object using our client_id,
    scopes, and redirect_uri.
    `state` is a CSRF token to verify the callback is genuine.
    """
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",   # request refresh_token
        include_granted_scopes="true",
        prompt="select_account",  # always show account picker
    )
    # NOTE: In production, store `state` in a secure cookie to verify in callback.
    return redirect(authorization_url)


# ── Step 2: Handle Google's Callback ─────────────────────────────────────────
@auth_bp.get("/callback")
def google_callback():
    """
    Google redirects here with ?code=... after user approves.
    We exchange the code for tokens, verify the id_token, and log the user in.
    """
    # Exchange authorization code for tokens
    flow = _build_flow()
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # Verify the ID token (ensures it was issued by Google for OUR client_id)
    id_info = id_token.verify_oauth2_token(
        credentials.id_token,
        google_requests.Request(),
        current_app.config["GOOGLE_CLIENT_ID"],
    )

    # Extract user profile from the verified token payload
    google_id = id_info["sub"]          # Google's unique user ID
    email = id_info["email"]
    name = id_info.get("name", "")
    avatar_url = id_info.get("picture", "")

    # Upsert user into Supabase
    # "Upsert" = INSERT ... ON CONFLICT DO UPDATE
    # This handles both new signups and returning users in one query.
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

    user = result.data[0]

    # Issue our own JWT
    token = _create_jwt(user)

    # Redirect the user back to the frontend, passing the JWT as a URL param.
    # The frontend reads it, stores it (e.g. localStorage), and uses it for API calls.
    frontend_url = current_app.config["FRONTEND_URL"]
    return redirect(f"{frontend_url}/auth/callback?token={token}")


# ── Step 3: Get Current User ──────────────────────────────────────────────────
@auth_bp.get("/me")
def get_me():
    """
    Returns the logged-in user's profile.
    Expects: Authorization: Bearer <jwt>
    """
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
