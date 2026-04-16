"""
orders.py — Orders blueprint for Waggy.

Routes:
    GET  /orders/receipt/<receipt_id>          — View receipt (owner or admin)
    GET  /my/orders                            — Customer: their own order history
    GET  /dashboard/orders                     — Admin: all orders
    GET  /dashboard/orders/<id>                — Admin: order detail
    POST /dashboard/orders/<id>/status         — Admin: update order status
"""

from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort,
)
from flask_login import login_required, current_user

from models import db, Order, ORDER_STATUSES, ORDER_STATUS_STYLES

orders_bp = Blueprint("orders", __name__)


# ── Decorators ────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Customer routes ───────────────────────────────────────────────────────────

@orders_bp.route("/orders/receipt/<receipt_id>")
@login_required
def receipt(receipt_id):
    order = Order.query.filter_by(receipt_id=receipt_id).first_or_404()
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template(
        "orders/receipt.html",
        order=order,
        statuses=ORDER_STATUSES,
        status_styles=ORDER_STATUS_STYLES,
    )


@orders_bp.route("/my/orders")
@login_required
def my_orders():
    orders = (
        Order.query
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template(
        "orders/my_orders.html",
        orders=orders,
        statuses=ORDER_STATUSES,
        status_styles=ORDER_STATUS_STYLES,
    )


# ── Admin routes ──────────────────────────────────────────────────────────────

@orders_bp.route("/dashboard/orders")
@admin_required
def orders_list():
    status_filter = request.args.get("status", "all")

    q = Order.query
    if status_filter != "all":
        q = q.filter_by(status=status_filter)
    orders = q.order_by(Order.created_at.desc()).all()

    # Aggregate counts per status for the stat bar
    counts = {s: Order.query.filter_by(status=s).count() for s in ORDER_STATUSES}
    counts["all"] = Order.query.count()

    return render_template(
        "orders/orders_list.html",
        orders=orders,
        statuses=ORDER_STATUSES,
        status_styles=ORDER_STATUS_STYLES,
        active_status=status_filter,
        counts=counts,
    )


@orders_bp.route("/dashboard/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template(
        "orders/order_detail.html",
        order=order,
        statuses=ORDER_STATUSES,
        status_styles=ORDER_STATUS_STYLES,
    )


@orders_bp.route("/dashboard/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status", "").strip()

    if new_status not in ORDER_STATUSES:
        flash("Invalid status value.", "danger")
        return redirect(url_for("orders.order_detail", order_id=order_id))

    old_label = order.status_label
    order.status = new_status
    db.session.commit()

    flash(
        f'Order <strong>{order.receipt_id}</strong> status changed from '
        f'<em>{old_label}</em> → <strong>{ORDER_STATUSES[new_status]}</strong>.',
        "success",
    )
    return redirect(url_for("orders.order_detail", order_id=order_id))
