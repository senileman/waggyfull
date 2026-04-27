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
    flash, request, abort, current_app,
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


# ── Email helper ──────────────────────────────────────────────────────────────

# Emoji / icon per status — makes the email a little friendlier
_STATUS_ICONS = {
    "confirmed": "✅",
    "shipping":  "🚚",
    "completed": "🎉",
    "cancelled": "❌",
}

# Short blurb included beneath the status line
_STATUS_MESSAGES = {
    "confirmed": (
        "Your order has been confirmed and is being prepared. "
        "We'll let you know as soon as it ships."
    ),
    "shipping": (
        "Great news — your order is on its way! "
        "Keep an eye on your door; your furry friend's goodies are coming. 🐾"
    ),
    "completed": (
        "Your order has been marked as delivered. "
        "We hope your pet loves their new items! "
        "Feel free to browse the shop for more."
    ),
    "cancelled": (
        "Your order has been cancelled. "
        "If you believe this is a mistake or have any questions, "
        "please contact our support team."
    ),
}


def _send_status_email(order, old_status: str, new_status: str) -> None:
    """
    Email the customer informing them their order status has changed.
    Silently skipped if Flask-Mail is not installed or not configured.
    """
    try:
        mail = current_app.extensions.get("mail")
        if not mail:
            return

        from flask_mail import Message

        old_label = ORDER_STATUSES.get(old_status, old_status.capitalize())
        new_label = ORDER_STATUSES.get(new_status, new_status.capitalize())
        icon      = _STATUS_ICONS.get(new_status, "📦")
        blurb     = _STATUS_MESSAGES.get(new_status, "Your order has been updated.")

        receipt_url = url_for(
            "orders.receipt",
            receipt_id=order.receipt_id,
            _external=True,
        )

        # Build a summary of the ordered items
        items_lines = []
        for item in order.items:
            items_lines.append(
                f"  • {item.product_name}  "
                f"({item.quantity} × ${item.unit_price:.2f}"
                f" = ${item.line_total:.2f})"
            )
        items_text = "\n".join(items_lines) if items_lines else "  (no items)"

        body = (
            f"Hi {order.user.username},\n\n"
            f"{icon}  Your Waggy order status has been updated.\n\n"
            f"{'━' * 44}\n"
            f"Receipt  : {order.receipt_id}\n"
            f"Status   : {old_label}  →  {new_label}\n"
            f"Date     : {order.updated_at.strftime('%d %B %Y at %H:%M')} UTC\n"
            f"{'━' * 44}\n\n"
            f"{blurb}\n\n"
            f"ORDER SUMMARY:\n{items_text}\n\n"
            f"ORDER TOTAL : ${order.total:.2f}\n\n"
            f"SHIPPING TO :\n{order.address}\n\n"
            f"CONTACT     : {order.phone}\n\n"
            f"{'━' * 44}\n"
            f"View your full receipt online:\n{receipt_url}\n"
            f"{'━' * 44}\n\n"
            f"Thank you for shopping with Waggy! 🐾\n"
            f"The Waggy Team\n"
        )

        subject = (
            f"{icon} Waggy Order Update — "
            f"{order.receipt_id} is now {new_label}"
        )

        msg = Message(
            subject=subject,
            recipients=[order.user.email],
            body=body,
        )
        mail.send(msg)
        current_app.logger.info(
            f"[Waggy] Status-change email sent to {order.user.email} "
            f"for order {order.receipt_id} ({old_label} → {new_label})."
        )

    except Exception as exc:
        # Never let a mail failure break the admin action
        current_app.logger.warning(
            f"[Waggy] Status-change email failed for order "
            f"{order.receipt_id}: {exc}"
        )


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

    # Nothing to do if the status hasn't actually changed
    if order.status == new_status:
        flash("Order status is already set to that value.", "info")
        return redirect(url_for("orders.order_detail", order_id=order_id))

    old_status = order.status
    old_label  = order.status_label

    order.status = new_status
    db.session.commit()

    # Notify the customer by email (non-blocking)
    _send_status_email(order, old_status, new_status)

    flash(
        f'Order <strong>{order.receipt_id}</strong> status changed from '
        f'<em>{old_label}</em> → <strong>{ORDER_STATUSES[new_status]}</strong>. '
        f'A notification email has been sent to {order.user.email}.',
        "success",
    )
    return redirect(url_for("orders.order_detail", order_id=order_id))
