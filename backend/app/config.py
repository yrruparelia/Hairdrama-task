"""
app/config.py — Centralised Configuration

All environment variables are read once here.
Flask's app.config.from_object(Config) loads every CLASS-LEVEL attribute
that is ALL_CAPS into the Flask config dict.

Why read from env?
  Hard-coding secrets is a security risk. Environment variables keep
  secrets out of source code and out of Git history.
"""

import os
from dotenv import load_dotenv

# Load .env file in development. In production (Railway/Render),
# env vars are set directly in the platform dashboard.
load_dotenv()

# OAuthlib rejects plain HTTP by default. Allow it only for the local
# development callback; deployed environments must use HTTPS.
if (
    os.getenv("FLASK_ENV", "development") == "development"
    and os.getenv("GOOGLE_REDIRECT_URI", "").startswith(
        ("http://localhost:", "http://127.0.0.1:")
    )
):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


class Config:
    # ── Flask core ─────────────────────────────────────────────────────────
    # SECRET_KEY is used by Flask to sign session cookies.
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"

    # ── Supabase ───────────────────────────────────────────────────────────
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    # ── Google OAuth ───────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    # Scopes we request from Google:
    #   openid        → lets us verify the user's identity
    #   email         → get the user's email address
    #   profile       → get name and avatar picture
    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    # ── Frontend ───────────────────────────────────────────────────────────
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # ── Gmail / Email ──────────────────────────────────────────────────────
    GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
