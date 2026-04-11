"""
cart.py — Shopping cart blueprint for Waggy.

Routes (all prefixed with /cart):
    GET  /cart/              — Full cart page
    POST /cart/add           — Add item (AJAX → JSON)
    POST /cart/update        — Update quantity (AJAX → JSON)
    POST /cart/remove        — Remove item (AJAX → JSON)
    GET  /cart/mini          — Mini-cart HTML for offcanvas (AJAX → HTML)
    GET  /cart/count         — Cart item count (AJAX → JSON)
    POST /cart/checkout      — Placeholder checkout
"""

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for, flash,
)
from flask_login import current_user
from sqlalchemy import func

from models import db, Product, CartItem

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")

_MAX_QTY = 99


# ── Internal helpers ──────────────────────────────────────────────────────────

def _session_cart() -> dict:
    """Return the guest cart dict from the session (str keys → int quantities)."""
    return session.get("cart", {})


def _save_session_cart(cart: dict) -> None:
    session["cart"] = cart
    session.modified = True


def get_cart_count() -> int:
    """Total number of units across all cart lines. Safe to call from templates."""
    if current_user.is_authenticated:
        result = (
            db.session.query(func.sum(CartItem.quantity))
            .filter_by(user_id=current_user.id)
            .scalar()
        )
        return int(result or 0)
    cart = _session_cart()
    return sum(cart.values())


def get_cart_items() -> list[dict]:
    """
    Return a list of dicts: {product: Product, quantity: int}
    Skips any product that is no longer active.
    """
    if current_user.is_authenticated:
        rows = (
            CartItem.query
            .filter_by(user_id=current_user.id)
            .join(CartItem.product)
            .filter(Product.is_active.is_(True))
            .all()
        )
        return [{"product": r.product, "quantity": r.quantity} for r in rows]

    cart = _session_cart()
    result = []
    for pid_str, qty in cart.items():
        p = Product.query.filter_by(id=int(pid_str), is_active=True).first()
        if p:
            result.append({"product": p, "quantity": qty})
    return result


def _cart_total(items: list[dict]) -> float:
    return sum(i["product"].price * i["quantity"] for i in items)


# ── Public route helpers ──────────────────────────────────────────────────────

def merge_session_cart(user) -> None:
    """
    Called after a guest logs in.  Merges the session cart into the DB cart
    and clears the session cart.
    """
    cart = session.pop("cart", {})
    if not cart:
        return
    for pid_str, qty in cart.items():
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        existing = CartItem.query.filter_by(
            user_id=user.id, product_id=pid
        ).first()
        if existing:
            existing.quantity = min(existing.quantity + qty, _MAX_QTY)
        else:
            db.session.add(CartItem(user_id=user.id, product_id=pid, quantity=qty))
    db.session.commit()
    session.modified = True


# ── Routes ────────────────────────────────────────────────────────────────────

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
        item = CartItem.query.filter_by(
            user_id=current_user.id, product_id=pid
        ).first()
        if item:
            item.quantity = min(item.quantity + quantity, _MAX_QTY)
        else:
            item = CartItem(user_id=current_user.id, product_id=pid, quantity=quantity)
            db.session.add(item)
        db.session.commit()
    else:
        cart = _session_cart()
        pid_str = str(pid)
        cart[pid_str] = min(cart.get(pid_str, 0) + quantity, _MAX_QTY)
        _save_session_cart(cart)

    return jsonify({
        "success": True,
        "message": f'"{product.name}" added to cart.',
        "count": get_cart_count(),
    })


@cart_bp.route("/update", methods=["POST"])
def update_cart():
    pid      = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=int)

    if pid is None or quantity is None:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    quantity = max(0, min(quantity, _MAX_QTY))

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(
            user_id=current_user.id, product_id=pid
        ).first()
        if item:
            if quantity == 0:
                db.session.delete(item)
            else:
                item.quantity = quantity
            db.session.commit()
    else:
        cart = _session_cart()
        pid_str = str(pid)
        if quantity == 0:
            cart.pop(pid_str, None)
        elif pid_str in cart:
            cart[pid_str] = quantity
        _save_session_cart(cart)

    items = get_cart_items()
    total = _cart_total(items)
    return jsonify({
        "success": True,
        "count":   get_cart_count(),
        "total":   f"{total:.2f}",
    })


@cart_bp.route("/remove", methods=["POST"])
def remove_from_cart():
    pid = request.form.get("product_id", type=int)

    if current_user.is_authenticated:
        item = CartItem.query.filter_by(
            user_id=current_user.id, product_id=pid
        ).first()
        if item:
            db.session.delete(item)
            db.session.commit()
    else:
        cart = _session_cart()
        cart.pop(str(pid), None)
        _save_session_cart(cart)

    items = get_cart_items()
    total = _cart_total(items)
    return jsonify({
        "success": True,
        "count":   get_cart_count(),
        "total":   f"{total:.2f}",
    })


@cart_bp.route("/count")
def cart_count():
    return jsonify({"count": get_cart_count()})


@cart_bp.route("/mini")
def mini_cart():
    items = get_cart_items()
    total = _cart_total(items)
    return render_template("cart/_mini_cart.html", items=items, total=total)


@cart_bp.route("/checkout", methods=["POST"])
def checkout():
    items = get_cart_items()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart.view_cart"))
    flash("Checkout is coming soon — thanks for shopping with Waggy! 🐾", "info")
    return redirect(url_for("cart.view_cart"))
