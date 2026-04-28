from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required, current_user

from models import db, User, CartItem

users_bp = Blueprint("users", __name__, url_prefix="/dashboard/users")



def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated



def _is_protected(user: User) -> bool:

    return bool(getattr(user, "is_seeded_admin", False))


def _self_action_blocked(target: User) -> bool:

    return target.id == current_user.id



@users_bp.route("/")
@admin_required
def users_list():
    search   = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "all")
    status_filter = request.args.get("status", "all")

    q = User.query

    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                User.username.ilike(like),
                User.email.ilike(like),
            )
        )

    if role_filter == "admin":
        q = q.filter_by(role="admin")
    elif role_filter == "customer":
        q = q.filter_by(role="customer")

    if status_filter == "active":
        q = q.filter_by(is_active=True)
    elif status_filter == "banned":
        q = q.filter_by(is_active=False)

    users = q.order_by(User.created_at.desc()).all()

    # Aggregate counts for the stat bar
    total       = User.query.count()
    admin_count = User.query.filter_by(role="admin").count()
    banned_count = User.query.filter_by(is_active=False).count()

    return render_template(
        "admin/users.html",
        users=users,
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
        total=total,
        admin_count=admin_count,
        banned_count=banned_count,
    )


@users_bp.route("/<int:user_id>/promote", methods=["POST"])
@admin_required
def promote(user_id):
    target = User.query.get_or_404(user_id)

    if _is_protected(target):
        flash("The original admin account cannot be modified.", "warning")
        return redirect(url_for("users.users_list"))

    if _self_action_blocked(target):
        flash("You cannot change your own role.", "warning")
        return redirect(url_for("users.users_list"))

    if not target.is_active:
        flash(
            f'"{target.username}" is banned. Unban the account before promoting.',
            "warning",
        )
        return redirect(url_for("users.users_list"))

    if target.role == "customer":
        target.role = "admin"
        db.session.commit()
        flash(
            f'"{target.username}" has been promoted to Admin.',
            "success",
        )
    else:
        target.role = "customer"
        db.session.commit()
        flash(
            f'"{target.username}" has been demoted to Customer.',
            "info",
        )

    return redirect(url_for("users.users_list"))


@users_bp.route("/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban(user_id):
    target = User.query.get_or_404(user_id)

    if _is_protected(target):
        flash("The original admin account cannot be banned.", "warning")
        return redirect(url_for("users.users_list"))

    if _self_action_blocked(target):
        flash("You cannot ban your own account.", "warning")
        return redirect(url_for("users.users_list"))

    if not target.is_active:
        flash(f'"{target.username}" is already banned.', "info")
        return redirect(url_for("users.users_list"))

    role_revoked = target.role == "admin"
    target.is_active = False
    target.role = "customer"

    CartItem.query.filter_by(user_id=target.id).delete()

    db.session.commit()

    msg = f'"{target.username}" has been banned.'
    if role_revoked:
        msg += " Their Admin role has been revoked."
    flash(msg, "danger")
    return redirect(url_for("users.users_list"))


@users_bp.route("/<int:user_id>/unban", methods=["POST"])
@admin_required
def unban(user_id):
    target = User.query.get_or_404(user_id)

    if _is_protected(target):
        flash("The original admin account cannot be modified.", "warning")
        return redirect(url_for("users.users_list"))

    if target.is_active:
        flash(f'"{target.username}" is not banned.', "info")
        return redirect(url_for("users.users_list"))

    target.is_active = True
    db.session.commit()
    flash(f'"{target.username}" has been unbanned.', "success")
    return redirect(url_for("users.users_list"))
