"""
app/__init__.py — Application Factory Pattern

Why the factory pattern?
  Using create_app() instead of a global `app` object lets us:
  1. Create multiple app instances (e.g., one for testing, one for production)
  2. Avoid circular imports — routes import `app`, but `app` is only created here
  3. Keep configuration flexible — different configs per environment
"""

from flask import Flask
from flask_cors import CORS
from .config import Config


def create_app():
    """
    Create and configure the Flask application.
    Returns the configured app instance.
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Cross-Origin Resource Sharing: allows our Next.js frontend (running on a
    # different port/domain) to make requests to this Flask API.
    # supports_credentials=True is needed because we send JWT in cookies/headers.
    CORS(app, origins=[app.config["FRONTEND_URL"]], supports_credentials=True)

    # ── Register Blueprints (Route Groups) ────────────────────────────────────
    # Blueprints let us split routes into separate files without circular imports.
    from .routes.auth import auth_bp
    from .routes.tasks import tasks_bp
    from .routes.users import users_bp

    app.register_blueprint(auth_bp,  url_prefix="/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health")
    def health():
        """Simple liveness probe used by Railway/Render to check the app is up."""
        return {"status": "ok"}, 200

    return app
