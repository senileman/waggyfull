import random
import string
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ── User ──────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer,     primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="customer")
    is_active     = db.Column(db.Boolean,     nullable=False, default=True)
    created_at    = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime,    nullable=True)

    def set_password(self, plain_text: str) -> None:
        self.password_hash = generate_password_hash(plain_text)

    def check_password(self, plain_text: str) -> bool:
        return check_password_hash(self.password_hash, plain_text)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"


# ── Product ───────────────────────────────────────────────────────────────────

PRODUCT_CATEGORIES = {
    "food":        "Pet Foods",
    "clothing":    "Pet Clothing",
    "accessories": "Pet Accessories",
    "comforts":    "Pet Comforts",
    "misc":        "Pet Misc",
}


class Product(db.Model):
    __tablename__ = "products"

    id                   = db.Column(db.Integer,     primary_key=True)
    name                 = db.Column(db.String(120), nullable=False)
    slug                 = db.Column(db.String(160), unique=True, nullable=True, index=True)
    category             = db.Column(db.String(30),  nullable=False, default="misc")
    description          = db.Column(db.Text,        nullable=False, default="")
    extended_description = db.Column(db.Text,        nullable=False, default="")
    image_filename       = db.Column(db.String(256), nullable=True)
    price                = db.Column(db.Float,       nullable=False, default=0.0)
    is_active            = db.Column(db.Boolean,     nullable=False, default=True)
    stock                = db.Column(db.Integer,     nullable=False, default=0)
    created_at           = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow,
                                     onupdate=datetime.utcnow)

    cart_items = db.relationship(
        "CartItem",
        backref=db.backref("product", lazy="joined"),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def category_label(self) -> str:
        return PRODUCT_CATEGORIES.get(self.category, self.category.capitalize())

    @property
    def image_url(self) -> str:
        if self.image_filename:
            return f"images/products/{self.image_filename}"
        return "images/item1.jpg"

    def __repr__(self) -> str:
        return f"<Product {self.name!r} [{self.category}] ${self.price:.2f}>"


# ── Cart ──────────────────────────────────────────────────────────────────────

class CartItem(db.Model):
    __tablename__ = "cart_items"

    id         = db.Column(db.Integer,  primary_key=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey("users.id"),    nullable=False)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity   = db.Column(db.Integer,  nullable=False, default=1)
    added_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("cart_items", lazy=True))

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
    )

    def __repr__(self) -> str:
        return f"<CartItem user={self.user_id} product={self.product_id} qty={self.quantity}>"


# ── Orders ────────────────────────────────────────────────────────────────────

ORDER_STATUSES = {
    "confirmed": "Confirmed",
    "shipping":  "Shipping",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# Status badge colours for templates
ORDER_STATUS_STYLES = {
    "confirmed": {"bg": "rgba(105,149,177,0.12)", "color": "#1d5a7a", "dot": "#6995B1"},
    "shipping":  {"bg": "rgba(255,152,0,0.12)",   "color": "#a06000", "dot": "#ff9800"},
    "completed": {"bg": "rgba(90,171,90,0.12)",   "color": "#2d7a2d", "dot": "#5aab5a"},
    "cancelled": {"bg": "rgba(192,57,43,0.10)",   "color": "#a02020", "dot": "#c0392b"},
}


def _gen_receipt_id() -> str:
    """Generate a unique-enough receipt ID like WGY-20250412-A3B7C2."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"WGY-{date_part}-{rand_part}"


class Order(db.Model):
    __tablename__ = "orders"

    id         = db.Column(db.Integer,  primary_key=True)
    receipt_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id    = db.Column(db.Integer,  db.ForeignKey("users.id"), nullable=False)
    status     = db.Column(db.String(20), nullable=False, default="confirmed")
    phone      = db.Column(db.String(40), nullable=False)
    address    = db.Column(db.Text,       nullable=False)
    total      = db.Column(db.Float,      nullable=False)
    notes      = db.Column(db.Text,       nullable=True)
    created_at = db.Column(db.DateTime,   nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,   nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user  = db.relationship("User", backref=db.backref("orders", lazy=True))
    items = db.relationship("OrderItem", backref="order",
                            cascade="all, delete-orphan", lazy=True)

    @property
    def status_label(self) -> str:
        return ORDER_STATUSES.get(self.status, self.status.capitalize())

    @property
    def status_style(self) -> dict:
        return ORDER_STATUS_STYLES.get(
            self.status,
            {"bg": "#f5f5f5", "color": "#908F8D", "dot": "#CACACA"},
        )

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)

    def __repr__(self) -> str:
        return f"<Order {self.receipt_id} user={self.user_id} {self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id               = db.Column(db.Integer,     primary_key=True)
    order_id         = db.Column(db.Integer,     db.ForeignKey("orders.id"), nullable=False)
    # product_id kept as reference; nullable because products can be deleted later
    product_id       = db.Column(db.Integer,     nullable=True)
    product_name     = db.Column(db.String(120), nullable=False)
    product_category = db.Column(db.String(30),  nullable=False, default="misc")
    quantity         = db.Column(db.Integer,     nullable=False)
    unit_price       = db.Column(db.Float,       nullable=False)

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_name!r} x{self.quantity} @ ${self.unit_price}>"
