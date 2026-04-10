"""
app/api/dependencies.py

Purpose:
Shared FastAPI dependency functions for RBAC (role-based access control).

Keeping role-enforcement logic here — separate from app/api/auth.py — prevents
circular imports and ensures auth.py remains responsible only for token
issuance/validation, not downstream permission checks.
"""

from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.constants import UserRole
from app.models.user import User


def require_agent_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency that restricts access to users with 'agent' or 'admin' role.

    Args:
        current_user: Authenticated user resolved by get_current_user.

    Returns:
        The current user if their role is permitted.

    Raises:
        HTTPException: 403 Forbidden if the user's role is neither 'agent' nor 'admin'.
    """
    if current_user.role not in (UserRole.AGENT.value, UserRole.ADMIN.value):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Agent or admin role required.",
        )
    return current_user

