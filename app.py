"""
app.py — Waggy Flask application.
"""

import os
from flask import Flask, render_template
from flask_login import LoginManager, login_required, current_user

from models import db, User, PRODUCT_CATEGORIES
from auth import auth_bp
from shop import shop_bp, seed_missing_slugs
from cart import cart_bp, get_cart_count


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "waggy-dev-key-REPLACE-this-before-deploying"
    )
    app.config["SQLALCHEMY_DATABASE_URI"]        = "sqlite:///waggy.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"]             = 8 * 1024 * 1024

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view             = "auth.login"
    login_manager.login_message          = "Please log in to continue."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(cart_bp)

    @app.context_processor
    def inject_globals():
        # get_cart_count() handles both cases correctly:
        #   - authenticated users: joins Product and filters is_active=True
        #   - guests: calls _clean_session_cart() which drops any
        #     hidden/deleted product IDs before summing quantities
        return {
            "cart_count": get_cart_count(),
            "categories": PRODUCT_CATEGORIES,
        }

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

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    with app.app_context():
        db.create_all()
        _seed_admin()
        seed_missing_slugs()

    return app


def _seed_admin() -> None:
    admin_email = "admin@waggy.com"
    if User.query.filter_by(email=admin_email).first():
        return
    admin = User(username="admin", email=admin_email, role="admin", is_active=True)
    admin.set_password("Admin@waggy1")
    db.session.add(admin)
    db.session.commit()
    print(
        "\n[Waggy] Default admin created.\n"
        "        Email: admin@waggy.com  Password: Admin@waggy1\n"
    )


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(debug=True)
