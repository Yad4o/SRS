"""
app/api/dependencies.py

Purpose:
--------
Shared API dependencies for authentication, authorization, and RBAC.

Owner:
------
Backend Team

Responsibilities:
-----------------
- Reusable FastAPI dependencies for protected routes
- RBAC middleware (require_agent_or_admin, etc.)

DO NOT:
-------
- Implement business logic here
- Access database directly (use get_db from app.db.session)
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.user import User


def require_agent_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure current user has agent or admin role.
    
    Args:
        current_user: Current authenticated user from JWT token
        
    Returns:
        Current user if agent or admin
        
    Raises:
        HTTPException: 403 if user is not agent or admin
    """
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Agent or admin role required."
        )
    return current_user
