"""Flask application factory and route registration."""

from flask import Flask
from flask_cors import CORS
from .config import Config


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Allow requests from the configured frontend.
    CORS(app, origins=[app.config["FRONTEND_URL"]], supports_credentials=True)

    # Register route groups.
    from .routes.auth import auth_bp
    from .routes.tasks import tasks_bp
    from .routes.users import users_bp

    app.register_blueprint(auth_bp,  url_prefix="/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    @app.get("/health")
    def health():
        """Simple liveness probe used by Railway/Render to check the app is up."""
        return {"status": "ok"}, 200

    return app
