
from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for, flash, current_app,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from models import db, Product, CartItem

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")

_MAX_QTY = 99



def _session_cart() -> dict:
    return session.get("cart", {})


def _save_session_cart(cart: dict) -> None:
    session["cart"] = cart
    session.modified = True


def _clean_session_cart() -> dict:
    cart = _session_cart()
    if not cart:
        return cart

    pids = [int(k) for k in cart.keys()]
    active_ids = {
        row.id
        for row in Product.query
        .filter(Product.id.in_(pids), Product.is_active.is_(True))
        .with_entities(Product.id)
        .all()
    }

    cleaned = {k: v for k, v in cart.items() if int(k) in active_ids}
    if len(cleaned) != len(cart):
        _save_session_cart(cleaned)
    return cleaned


def get_cart_count() -> int:
    if current_user.is_authenticated:
        result = (
            db.session.query(func.sum(CartItem.quantity))
            .join(CartItem.product)
            .filter(
                CartItem.user_id == current_user.id,
                Product.is_active.is_(True),
            )
            .scalar()
        )
        return int(result or 0)
    cart = _clean_session_cart()
    return sum(cart.values())


def get_cart_items() -> list[dict]:
    if current_user.is_authenticated:
        rows = (
            CartItem.query
            .filter_by(user_id=current_user.id)
            .join(CartItem.product)
            .filter(Product.is_active.is_(True))
            .all()
        )
        stale = (
            CartItem.query
            .filter_by(user_id=current_user.id)
            .join(CartItem.product)
            .filter(Product.is_active.is_(False))
            .all()
        )
        if stale:
            for item in stale:
                db.session.delete(item)
            db.session.commit()
        return [{"product": r.product, "quantity": r.quantity} for r in rows]

    cart = _clean_session_cart()
    result = []
    for pid_str, qty in cart.items():
        p = Product.query.filter_by(id=int(pid_str), is_active=True).first()
        if p:
            result.append({"product": p, "quantity": qty})
    return result


def _cart_total(items: list[dict]) -> float:
    return round(sum(i["product"].price * i["quantity"] for i in items), 2)




def _send_receipt_email(order) -> None:
    """Send a plain-text receipt email. Silent if Flask-Mail is not configured."""
    try:
        mail = current_app.extensions.get("mail")
        if not mail:
            return

        from flask_mail import Message

        items_lines = []
        for item in order.items:
            items_lines.append(
                f"  • {item.product_name}\n"
                f"    {item.quantity} × ${item.unit_price:.2f}"
                f" = ${item.line_total:.2f}"
            )
        items_text = "\n".join(items_lines)

        receipt_url = url_for(
            "orders.receipt",
            receipt_id=order.receipt_id,
            _external=True,
        )

        body = (
            f"Hi {order.user.username},\n\n"
            f"Thank you for shopping with Waggy! 🐾 "
            f"Your order has been received and confirmed.\n\n"
            f"{'━' * 40}\n"
            f"Receipt  : {order.receipt_id}\n"
            f"Date     : {order.created_at.strftime('%d %B %Y at %H:%M')} UTC\n"
            f"Status   : {order.status_label}\n"
            f"{'━' * 40}\n\n"
            f"ITEMS ORDERED:\n{items_text}\n\n"
            f"ORDER TOTAL: ${order.total:.2f}\n\n"
            f"SHIPPING ADDRESS:\n{order.address}\n\n"
            f"CONTACT PHONE: {order.phone}\n\n"
            f"{'━' * 40}\n"
            f"View your full receipt online:\n{receipt_url}\n"
            f"{'━' * 40}\n\n"
            f"We'll notify you when your order ships.\n\n"
            f"Thank you,\nThe Waggy Team 🐾\n"
        )

        msg = Message(
            subject=f"Order Confirmed — Waggy Receipt #{order.receipt_id}",
            recipients=[order.user.email],
            body=body,
        )
        mail.send(msg)

    except Exception as exc:
        current_app.logger.warning(f"[Waggy] Receipt email failed: {exc}")




def merge_session_cart(user) -> None:
    cart = session.pop("cart", {})
    if not cart:
        return
    for pid_str, qty in cart.items():
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        product = Product.query.filter_by(id=pid, is_active=True).first()
        if not product:
            continue
        existing = CartItem.query.filter_by(user_id=user.id, product_id=pid).first()
        if existing:
            existing.quantity = min(existing.quantity + qty, _MAX_QTY)
        else:
            db.session.add(CartItem(user_id=user.id, product_id=pid, quantity=qty))
    db.session.commit()
    session.modified = True




@cart_bp.route("/")
def view_cart():
    items = get_cart_items()
    total = _cart_total(items)
    return render_template("cart/cart.html", items=items, total=total)


@cart_bp.route("/add", methods=["POST"])
def add_to_cart():
    pid      = request.form.get("product_id", type=int)
    quantity = max(1, min(request.form.get("quantity", 1, type=int), _MAX_QTY))

    if not pid:
        return jsonify({"success": False, "message": "No product specified."}), 400

    product = Product.query.filter_by(id=pid, is_active=True).first()
    if not product:
        return jsonify({"success": False, "message": "Product not found."}), 404
    if product.stock == 0:
        return jsonify({"success": False, "message": "This product is out of stock."}), 400

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
        if item:
            item.quantity = min(item.quantity + quantity, _MAX_QTY)
        else:
            item = CartItem(user_id=current_user.id, product_id=pid, quantity=quantity)
            db.session.add(item)
        db.session.commit()
    else:
        cart = _clean_session_cart()
        pid_str = str(pid)
        cart[pid_str] = min(cart.get(pid_str, 0) + quantity, _MAX_QTY)
        _save_session_cart(cart)

    return jsonify({
        "success": True,
        "message": f'"{product.name}" added to cart.',
        "count":   get_cart_count(),
    })


@cart_bp.route("/update", methods=["POST"])
def update_cart():
    pid      = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=int)

    if pid is None or quantity is None:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    quantity = max(0, min(quantity, _MAX_QTY))

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
        if item:
            if quantity == 0:
                db.session.delete(item)
            else:
                item.quantity = quantity
            db.session.commit()
    else:
        cart = _clean_session_cart()
        pid_str = str(pid)
        if quantity == 0:
            cart.pop(pid_str, None)
        elif pid_str in cart:
            cart[pid_str] = quantity
        _save_session_cart(cart)

    items = get_cart_items()
    total = _cart_total(items)
    return jsonify({"success": True, "count": get_cart_count(), "total": f"{total:.2f}"})


@cart_bp.route("/remove", methods=["POST"])
def remove_from_cart():
    pid = request.form.get("product_id", type=int)

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
        if item:
            db.session.delete(item)
            db.session.commit()
    else:
        cart = _clean_session_cart()
        cart.pop(str(pid), None)
        _save_session_cart(cart)

    items = get_cart_items()
    total = _cart_total(items)
    return jsonify({"success": True, "count": get_cart_count(), "total": f"{total:.2f}"})


@cart_bp.route("/count")
def cart_count():
    return jsonify({"count": get_cart_count()})


@cart_bp.route("/mini")
def mini_cart():
    items = get_cart_items()
    total = _cart_total(items)
    return render_template("cart/_mini_cart.html", items=items, total=total)


@cart_bp.route("/checkout", methods=["POST"])
@login_required
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view_cart"))

    phone   = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()

    if not phone:
        flash("Please provide a phone number.", "danger")
        return redirect(url_for("cart.view_cart"))
    if not address:
        flash("Please provide a shipping address.", "danger")
        return redirect(url_for("cart.view_cart"))

    from models import Order, OrderItem, _gen_receipt_id

    total = _cart_total(items)


    receipt_id = _gen_receipt_id()
    for _ in range(10):
        if not Order.query.filter_by(receipt_id=receipt_id).first():
            break
        receipt_id = _gen_receipt_id()

    order = Order(
        receipt_id=receipt_id,
        user_id=current_user.id,
        phone=phone,
        address=address,
        total=total,
        status="confirmed",
    )
    db.session.add(order)
    db.session.flush()

    for item in items:
        db.session.add(OrderItem(
            order_id=order.id,
            product_id=item["product"].id,
            product_name=item["product"].name,
            product_category=item["product"].category,
            quantity=item["quantity"],
            unit_price=item["product"].price,
        ))

    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    _send_receipt_email(order)

    flash(
        f"Order placed successfully! Your receipt ID is "
        f"<strong>{order.receipt_id}</strong>.",
        "success",
    )
    return redirect(url_for("orders.receipt", receipt_id=order.receipt_id))
