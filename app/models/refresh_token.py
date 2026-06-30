"""
app/models/refresh_token.py

Purpose:
Defines the RefreshToken database model.

Responsibilities:
- Persist long-lived refresh tokens (hashed, never plaintext) so a client
  can obtain a new access token without re-authenticating.
- Support revocation (logout, rotation-on-refresh) — something a
  stateless JWT access token cannot do before it naturally expires.

DO NOT:
- Store the raw refresh token (only its HMAC-SHA256 hash — see
  app/core/security.py: hash_refresh_token / verify_refresh_token_hash)
- Implement auth business logic here (that belongs in app/api/auth.py)
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.session import Base


class RefreshToken(Base):
    """
    RefreshToken ORM model.

    Each row represents one issued refresh token. Tokens are rotated on
    every use (POST /auth/refresh): the old row is marked revoked and a
    new row is inserted, so a stolen-and-replayed old token is detectable
    and rejected.
    """

    __tablename__ = "refresh_tokens"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="Primary key identifier for the refresh token row",
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        doc="ID of the user this refresh token belongs to",
    )

    # HMAC-SHA256 digest of the raw token, keyed on SECRET_KEY (same
    # approach as OTP hashing in app/core/otp.py). Deterministic, so it
    # can be looked up directly with an equality query, unlike a
    # randomly-salted bcrypt hash.
    token_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        doc="HMAC-SHA256 hex digest of the raw refresh token",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Expiration timestamp for this refresh token",
    )

    revoked = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="True once this token has been used (rotated) or explicitly revoked via logout",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when this refresh token was issued",
    )

    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"
