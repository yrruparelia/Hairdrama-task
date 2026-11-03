"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

# Load local development settings.
load_dotenv()

# Allow HTTP only for local OAuth callbacks.
if (
    os.getenv("FLASK_ENV", "development") == "development"
    and os.getenv("GOOGLE_REDIRECT_URI", "").startswith(
        ("http://localhost:", "http://127.0.0.1:")
    )
):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


class Config:
    # Flask and session settings.
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.getenv("FLASK_ENV", "development") == "development"

    # Supabase settings.
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    # JWT settings.
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-me")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    # Google OAuth settings.
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    GOOGLE_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    # Frontend settings.
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Gmail settings.
    GMAIL_SENDER_ADDRESS = os.getenv("GMAIL_SENDER_ADDRESS")
    GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
    GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", GOOGLE_CLIENT_ID)
    GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
