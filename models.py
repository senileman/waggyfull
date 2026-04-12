from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


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


# ── Product categories ────────────────────────────────────────────────────────

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

    # Cascade: deleting a Product automatically deletes its CartItem rows.
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
