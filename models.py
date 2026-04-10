from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    Represents a registered user in the Waggy store.

    Roles:
        'admin'    — Full site management access.
        'customer' — Standard shopper account (default).
    """

    __tablename__ = "users"

    id            = db.Column(db.Integer,     primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="customer")
    is_active     = db.Column(db.Boolean,     nullable=False, default=True)
    created_at    = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime,    nullable=True)

    # ── Password helpers ─────────────────────────────────────────────────────

    def set_password(self, plain_text: str) -> None:
        """Hash and store the password (PBKDF2-SHA256 via Werkzeug)."""
        self.password_hash = generate_password_hash(plain_text)

    def check_password(self, plain_text: str) -> bool:
        """Return True if plain_text matches the stored hash."""
        return check_password_hash(self.password_hash, plain_text)

    # ── Convenience properties ───────────────────────────────────────────────

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"
