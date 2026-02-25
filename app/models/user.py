"""
app/models/user.py

Purpose:
--------
Defines the User database model.

Owner:
------
Om (Backend / Data Modeling)

Responsibilities:
-----------------
- Represent application users in the database
- Store authentication-related fields
- Support role-based access control

DO NOT:
-------
- Hash passwords here
- Implement authentication logic
- Write database queries here
"""

from sqlalchemy import Column, Integer, String
from app.db.session import Base


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
            kwargs['role'] = 'user'
        super().__init__(**kwargs)

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
        default="user",
        nullable=False,
        doc="User role: user | agent | admin",
    )

    # -------------------------------------------------
    # TODO (Future Enhancements)
    # -------------------------------------------------
    # - created_at timestamp
    # - updated_at timestamp
    # - is_active flag
