"""
shop.py — Shop blueprint for Waggy.

Routes:
    GET  /shop                                  — Product grid
    GET  /shop/product/<slug>                   — Product detail (slug-based)
    GET  /shop/change-listing                   — Admin: list all products
    GET/POST /shop/change-listing/add           — Admin: add product
    GET/POST /shop/change-listing/edit/<id>     — Admin: edit product
    POST     /shop/change-listing/delete/<id>   — Admin: delete product
    POST     /shop/change-listing/toggle/<id>   — Admin: toggle visibility
"""

import os
import re
import uuid
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Product, PRODUCT_CATEGORIES

shop_bp = Blueprint("shop", __name__, url_prefix="/shop")

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


# ── Slug helpers ──────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "product"


def _unique_slug(name: str, exclude_id: int | None = None) -> str:
    base = _slugify(name)
    slug = base
    counter = 2
    while True:
        q = Product.query.filter_by(slug=slug)
        if exclude_id is not None:
            q = q.filter(Product.id != exclude_id)
        if not q.first():
            break
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def seed_missing_slugs() -> None:
    """Give existing products without slugs a slug. Called once on startup."""
    products = Product.query.filter(
        (Product.slug == None) | (Product.slug == "")
    ).all()
    for p in products:
        p.slug = _unique_slug(p.name, exclude_id=p.id)
    if products:
        db.session.commit()


# ── Image helpers ─────────────────────────────────────────────────────────────

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _save_image(file_obj) -> str | None:
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


@shop_bp.route("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
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
    if request.method == "POST":
        name                 = request.form.get("name", "").strip()
        category             = request.form.get("category", "misc")
        description          = request.form.get("description", "").strip()
        extended_description = request.form.get("extended_description", "").strip()
        price_raw            = request.form.get("price", "0")
        is_active            = bool(request.form.get("is_active"))
        image_file           = request.files.get("image")
        stock_raw            = request.form.get("stock", "0")

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
        slug = _unique_slug(name)

        product = Product(
            name=name,
            slug=slug,
            category=category,
            description=description,
            extended_description=extended_description,
            image_filename=image_filename,
            price=price,
            is_active=is_active,
            stock=stock,
        )
        db.session.add(product)
        db.session.commit()

        flash(f'Product "{name}" added successfully.', "success")
        return redirect(url_for("shop.change_listing"))

    return render_template(
        "shop/add_product.html",
        categories=PRODUCT_CATEGORIES,
        form={},
    )


@shop_bp.route("/change-listing/edit/<int:product_id>", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        name                 = request.form.get("name", "").strip()
        category             = request.form.get("category", "misc")
        description          = request.form.get("description", "").strip()
        extended_description = request.form.get("extended_description", "").strip()
        price_raw            = request.form.get("price", "0")
        is_active            = bool(request.form.get("is_active"))
        image_file           = request.files.get("image")
        clear_image          = bool(request.form.get("clear_image"))
        stock_raw            = request.form.get("stock", "0")

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

        # Regenerate slug only if name changed
        if name != product.name:
            product.slug = _unique_slug(name, exclude_id=product.id)

        new_image = _save_image(image_file)
        if new_image:
            product.image_filename = new_image
        elif clear_image:
            product.image_filename = None

        product.name                 = name
        product.category             = category
        product.description          = description
        product.extended_description = extended_description
        product.price                = price
        product.is_active            = is_active
        product.stock                = stock
        db.session.commit()

        flash(f'Product "{name}" updated.', "success")
        return redirect(url_for("shop.change_listing"))

    return render_template(
        "shop/edit_product.html",
        product=product,
        categories=PRODUCT_CATEGORIES,
    )


@shop_bp.route("/change-listing/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" deleted.', "info")
    return redirect(url_for("shop.change_listing"))


@shop_bp.route("/change-listing/toggle/<int:product_id>", methods=["POST"])
@admin_required
def toggle_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    state = "visible" if product.is_active else "hidden"
    flash(f'"{product.name}" is now {state}.', "success")
    return redirect(url_for("shop.change_listing"))
