"""
run.py — Entry point for the Flask development server.

Usage:
    python run.py

In production (Railway/Render), gunicorn is used instead:
    gunicorn run:app --bind 0.0.0.0:$PORT
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True enables hot-reload and detailed error pages in dev.
    # NEVER set debug=True in production.
    app.run(debug=True, port=5000)
