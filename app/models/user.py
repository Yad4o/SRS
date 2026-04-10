"""
app/models/user.py

Purpose:
Defines the User database model.

Responsibilities:
- Represent application users in the database
- Store authentication-related fields
- Support role-based access control

DO NOT:
- Hash passwords here
- Implement authentication logic
- Write database queries here
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.session import Base
from app.constants import UserRole


class User(Base):
    """
    User ORM model.

    This table stores all users of the system, including:
    - Regular users (customers)
    - Support agents
    - Admins
    """

    __tablename__ = "users"

    def __init__(self, **kwargs):
        """Initialize User with default role if not provided."""
        if 'role' not in kwargs:
            kwargs['role'] = UserRole.USER.value
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    # -------------------------------------------------
    # Columns
    # -------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        doc="Primary key identifier for the user",
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
        doc="User email address (used for login)",
    )

    hashed_password = Column(
        String,
        nullable=False,
        doc="Hashed password (never store plain text)",
    )

    role = Column(
        String,
        default=UserRole.USER.value,
        nullable=False,
        doc="User role: user | agent | admin",
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether the user account is active",
    )

    # Password reset fields
    reset_otp = Column(
        String(6),
        nullable=True,
        doc="6-digit OTP for password reset",
    )

    reset_otp_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="OTP expiration timestamp",
    )

    reset_otp_attempts = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Number of OTP verification attempts",
    )

    # -------------------------------------------------
    # Timestamps
    # -------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the user was created",
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp when the record was last updated",
    )

