
import re
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")



_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
_EMAIL_RE    = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_username(value: str) -> str | None:
    if not value:
        return "Username is required."
    if not _USERNAME_RE.match(value):
        return "Username must be 3–30 characters (letters, numbers, underscores only)."
    return None


def _validate_email(value: str) -> str | None:
    if not value:
        return "Email is required."
    if not _EMAIL_RE.match(value):
        return "Please enter a valid email address."
    return None


def _validate_password(value: str) -> str | None:
    if not value:
        return "Password is required."
    if len(value) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in value):
        return "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in value):
        return "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in value):
        return "Password must contain at least one number."
    return None



@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password   = request.form.get("password", "")
        remember   = bool(request.form.get("remember"))

        if not identifier or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("auth/login.html", identifier=identifier)

        user = (
            User.query.filter_by(email=identifier.lower()).first()
            or User.query.filter_by(username=identifier).first()
        )

        if user is None or not user.check_password(password):
            flash("Incorrect email / username or password.", "danger")
            return render_template("auth/login.html", identifier=identifier)

        if not user.is_active:
            flash("Your account has been suspended. Please contact support.", "warning")
            return render_template("auth/login.html")

        user.last_login_at = datetime.utcnow()
        db.session.commit()

        login_user(user, remember=remember)

        from cart import merge_session_cart
        merge_session_cart(user)

        flash(f"Welcome back, {user.username}! 🐾", "success")

        next_page = request.args.get("next")
        return redirect(next_page or url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        errors = []

        err = _validate_username(username)
        if err:
            errors.append(err)

        err = _validate_email(email)
        if err:
            errors.append(err)

        err = _validate_password(password)
        if err:
            errors.append(err)

        if password and confirm and password != confirm:
            errors.append("Passwords do not match.")

        if not errors:
            if User.query.filter_by(username=username).first():
                errors.append("That username is already taken.")
            if User.query.filter_by(email=email).first():
                errors.append("An account with that email already exists.")

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return render_template(
                "auth/register.html",
                username=username,
                email=email,
            )

        new_user = User(username=username, email=email, role="customer")
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out. See you soon! 🐾", "info")
    return redirect(url_for("main.index"))
