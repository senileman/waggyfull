"""
shop.py — Shop blueprint for Waggy.

Routes:
    GET  /shop                    — Browseable product grid (all / by category)
    GET  /shop/product/<id>       — Individual product detail page
    GET  /shop/change-listing     — Admin: list all products
    GET/POST /shop/change-listing/add        — Admin: add a product
    GET/POST /shop/change-listing/edit/<id>  — Admin: edit a product
    POST     /shop/change-listing/delete/<id>— Admin: delete a product
"""

import os
import uuid
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Product, PRODUCT_CATEGORIES

shop_bp = Blueprint("shop", __name__, url_prefix="/shop")

# ── Allowed image extensions ──────────────────────────────────────────────────
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save_image(file_obj) -> str | None:
    """Save an uploaded image; return the stored filename or None."""
    if not file_obj or file_obj.filename == "":
        return None
    if not _allowed_file(file_obj.filename):
        return None
    ext = file_obj.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, "static", "images", "products")
    os.makedirs(upload_dir, exist_ok=True)
    file_obj.save(os.path.join(upload_dir, unique_name))
    return unique_name


# ── Admin-only decorator ──────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Public routes ─────────────────────────────────────────────────────────────

@shop_bp.route("/")
def index():
    """Main shop page — all active products, filterable by category."""
    category = request.args.get("category", "all")
    q = Product.query.filter_by(is_active=True)
    if category and category != "all":
        q = q.filter_by(category=category)
    products = q.order_by(Product.created_at.desc()).all()

    return render_template(
        "shop/index.html",
        products=products,
        categories=PRODUCT_CATEGORIES,
        active_category=category,
    )


@shop_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    """Individual product page."""
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    related = (
        Product.query
        .filter_by(category=product.category, is_active=True)
        .filter(Product.id != product.id)
        .limit(4)
        .all()
    )
    return render_template(
        "shop/product.html",
        product=product,
        related=related,
        categories=PRODUCT_CATEGORIES,
    )


# ── Admin routes ──────────────────────────────────────────────────────────────

@shop_bp.route("/change-listing")
@admin_required
def change_listing():
    """Admin dashboard — list all products."""
    category = request.args.get("category", "all")
    q = Product.query
    if category and category != "all":
        q = q.filter_by(category=category)
    products = q.order_by(Product.created_at.desc()).all()

    return render_template(
        "shop/change_listing.html",
        products=products,
        categories=PRODUCT_CATEGORIES,
        active_category=category,
        total=Product.query.count(),
        active_count=Product.query.filter_by(is_active=True).count(),
    )


@shop_bp.route("/change-listing/add", methods=["GET", "POST"])
@admin_required
def add_product():
    """Admin: add a new product."""
    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        category    = request.form.get("category", "misc")
        description = request.form.get("description", "").strip()
        price_raw   = request.form.get("price", "0")
        is_active   = bool(request.form.get("is_active"))
        image_file  = request.files.get("image")
        stock_raw   = request.form.get("stock", "0")

        # Validate
        errors = []
        if not name:
            errors.append("Product name is required.")
        if category not in PRODUCT_CATEGORIES:
            errors.append("Please select a valid category.")
        try:
            price = round(float(price_raw), 2)
            if price < 0:
                raise ValueError
        except ValueError:
            errors.append("Price must be a positive number.")
            price = 0.0
        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            errors.append("Stock must be a whole number of 0 or more.")
            stock = 0

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "shop/add_product.html",
                categories=PRODUCT_CATEGORIES,
                form=request.form,
            )

        image_filename = _save_image(image_file)

        product = Product(
            name=name,
            category=category,
            description=description,
            image_filename=image_filename,
            price=price,
            is_active=is_active,
            stock=stock,
        )
        db.session.add(product)
        db.session.commit()

        flash(f"Product \"{name}\" added successfully.", "success")
        return redirect(url_for("shop.change_listing"))

    return render_template(
        "shop/add_product.html",
        categories=PRODUCT_CATEGORIES,
        form={},
    )


@shop_bp.route("/change-listing/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    """Admin: edit an existing product."""
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        name        = request.form.get("name", "").strip()
        category    = request.form.get("category", "misc")
        description = request.form.get("description", "").strip()
        price_raw   = request.form.get("price", "0")
        is_active   = bool(request.form.get("is_active"))
        image_file  = request.files.get("image")
        clear_image = bool(request.form.get("clear_image"))
        stock_raw   = request.form.get("stock", "0")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if category not in PRODUCT_CATEGORIES:
            errors.append("Please select a valid category.")
        try:
            price = round(float(price_raw), 2)
            if price < 0:
                raise ValueError
        except ValueError:
            errors.append("Price must be a positive number.")
            price = product.price
        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            errors.append("Stock must be a whole number of 0 or more.")
            stock = product.stock

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "shop/edit_product.html",
                product=product,
                categories=PRODUCT_CATEGORIES,
            )

        # Handle image update
        new_image = _save_image(image_file)
        if new_image:
            product.image_filename = new_image
        elif clear_image:
            product.image_filename = None

        product.name        = name
        product.category    = category
        product.description = description
        product.price       = price
        product.is_active   = is_active
        product.stock       = stock
        db.session.commit()

        flash(f"Product \"{name}\" updated.", "success")
        return redirect(url_for("shop.change_listing"))

    return render_template(
        "shop/edit_product.html",
        product=product,
        categories=PRODUCT_CATEGORIES,
    )


@shop_bp.route("/change-listing/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    """Admin: permanently delete a product."""
    product = Product.query.get_or_404(product_id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f"Product \"{name}\" deleted.", "info")
    return redirect(url_for("shop.change_listing"))


@shop_bp.route("/change-listing/toggle/<int:product_id>", methods=["POST"])
@admin_required
def toggle_product(product_id):
    """Admin: toggle a product's active/hidden status."""
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    state = "visible" if product.is_active else "hidden"
    flash(f"\"{product.name}\" is now {state}.", "success")
    return redirect(url_for("shop.change_listing"))
