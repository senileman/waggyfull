from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from models import db, User
from . import auth_bp


# ------------------------------------------------------------------ #
# Register
# ------------------------------------------------------------------ #
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # ----- basic validation -----
        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."
        elif User.query.filter_by(username=username).first():
            error = "That username is already taken."

        if error:
            flash(error, "danger")
            return render_template(
                "auth/register.html",
                username=username,
                email=email,
            )

        # ----- create user -----
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", username="", email="")


# ------------------------------------------------------------------ #
# Login
# ------------------------------------------------------------------ #
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", email=email)

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.username}!", "success")

        # Redirect to the page the user originally wanted (safe redirect)
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", email="")


# ------------------------------------------------------------------ #
# Logout
# ------------------------------------------------------------------ #
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))
