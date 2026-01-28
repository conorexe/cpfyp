"""
Authentication module for MarketScout.

Provides JWT-based authentication with:
- User registration and login
- Password hashing with bcrypt
- JWT token generation and validation
- Role-based access control
"""

from .models import User, UserCreate, UserLogin, Token, TokenData
from .service import AuthService
from .dependencies import get_current_user, get_current_active_user, get_admin_user

__all__ = [
    "User",
    "UserCreate", 
    "UserLogin",
    "Token",
    "TokenData",
    "AuthService",
    "get_current_user",
    "get_current_active_user",
    "get_admin_user",
]
