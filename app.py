"""
app.py — Waggy Flask application.

Run with:
    python app.py              (development)
    flask --app app run        (Flask CLI)

Environment variables (optional, but set before deploying):
    SECRET_KEY  — Random secret string for session signing.
                  Defaults to a hard-coded dev value — CHANGE THIS in production.
"""

import os
from datetime import datetime

from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user

from models import db, User
from auth import auth_bp


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__)

    # ── Configuration ─────────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "waggy-dev-key-REPLACE-this-before-deploying"
    )
    # The SQLite database is stored in the auto-created  instance/  folder.
    app.config["SQLALCHEMY_DATABASE_URI"]        = "sqlite:///waggy.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view         = "auth.login"          # redirect target when @login_required fails
    login_manager.login_message      = "Please log in to continue."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp)

    # ── Main blueprint (inline for simplicity) ────────────────────────────────
    from flask import Blueprint
    main_bp = Blueprint("main", __name__)

    @main_bp.route("/")
    def index():
        return render_template("index.html")

    @main_bp.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    app.register_blueprint(main_bp)

    # ── Database init + seed ──────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


# ── Admin seeding ─────────────────────────────────────────────────────────────

def _seed_admin() -> None:
    """
    Create the default admin account on first run.

    Credentials (change the password after first login!):
        Email:    admin@waggy.com
        Password: Admin@waggy1
    """
    admin_email = "admin@waggy.com"

    if User.query.filter_by(email=admin_email).first():
        return   # already seeded

    admin = User(
        username  = "admin",
        email     = admin_email,
        role      = "admin",
        is_active = True,
    )
    admin.set_password("Admin@waggy1")
    db.session.add(admin)
    db.session.commit()
    print(
        "\n[Waggy] ✅ Default admin account created.\n"
        "        Email:    admin@waggy.com\n"
        "        Password: Admin@waggy1\n"
        "        ⚠️  Change this password after your first login!\n"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True)
