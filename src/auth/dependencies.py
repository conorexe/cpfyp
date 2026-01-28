"""
FastAPI dependencies for authentication.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import User, TokenData
from .service import auth_service

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """Extract token from Authorization header"""
    if credentials:
        return credentials.credentials
    return None


async def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract token from cookie (alternative to header)"""
    return request.cookies.get("access_token")


async def get_current_user(
    token_header: Optional[str] = Depends(get_token_from_header),
    token_cookie: Optional[str] = Depends(get_token_from_cookie),
) -> Optional[User]:
    """
    Get current user from JWT token.
    
    Checks both Authorization header and cookie.
    Returns None if no valid token is found (for optional auth).
    """
    token = token_header or token_cookie
    
    if not token:
        return None
    
    token_data = auth_service.verify_token(token)
    if not token_data:
        return None
    
    user = auth_service.get_user(token_data.username)
    if not user:
        return None
    
    return User(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login,
    )


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Get current active user (required authentication).
    
    Raises 401 if not authenticated or user is inactive.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current admin user (requires admin privileges).
    
    Raises 403 if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    
    return current_user


def optional_auth(
    current_user: Optional[User] = Depends(get_current_user),
) -> Optional[User]:
    """
    Optional authentication - returns user if authenticated, None otherwise.
    
    Use this for endpoints that work both with and without authentication,
    but provide additional features for authenticated users.
    """
    return current_user
