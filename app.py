from dotenv import load_dotenv
load_dotenv()

import os
from flask import Flask, render_template
from flask_login import LoginManager, login_required, current_user

from models import db, User, PRODUCT_CATEGORIES
from auth import auth_bp
from shop import shop_bp, seed_missing_slugs
from cart import cart_bp, get_cart_count
from orders import orders_bp
from users import users_bp


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "waggy-dev-key-REPLACE-this-before-deploying",
    )
    app.config["SQLALCHEMY_DATABASE_URI"]        = "sqlite:///waggy.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"]             = 8 * 1024 * 1024

    app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"]        = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
        "MAIL_DEFAULT_SENDER", ("Waggy", "noreply@waggy.com")
    )

    try:
        from flask_mail import Mail
        if app.config["MAIL_USERNAME"]:
            Mail(app)
            print("[Waggy] Flask-Mail configured — receipt emails are active.")
        else:
            print("[Waggy] MAIL_USERNAME not set — receipt emails disabled.")
    except ImportError:
        print("[Waggy] flask-mail not installed — receipt emails disabled.")

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
    app.register_blueprint(orders_bp)
    app.register_blueprint(users_bp)

    @app.context_processor
    def inject_globals():
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
    existing = User.query.filter_by(email=admin_email).first()

    if existing:
        # Backfill the flag if the account already existed before this feature
        if not existing.is_seeded_admin:
            existing.is_seeded_admin = True
            db.session.commit()
        return

    admin = User(
        username="admin",
        email=admin_email,
        role="admin",
        is_active=True,
        is_seeded_admin=True,
    )
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
