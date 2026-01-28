"""
Authentication service with JWT token management.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import secrets
import base64

from jose import JWTError, jwt
from passlib.context import CryptContext

from .models import User, UserCreate, UserInDB, Token, TokenData

logger = logging.getLogger(__name__)

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration (from environment or defaults)
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-key-change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


class AuthService:
    """
    Authentication service providing:
    - User registration and storage
    - Password hashing and verification
    - JWT token generation and validation
    
    Note: This uses in-memory storage for simplicity.
    In production, integrate with PostgreSQL via SQLAlchemy.
    """
    
    def __init__(self):
        # In-memory user storage (replace with database in production)
        self._users: Dict[str, UserInDB] = {}
        self._user_id_counter = 1
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user from environment variables"""
        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "Changeme123")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@marketscout.local")
        
        if admin_username not in self._users:
            try:
                self._users[admin_username] = UserInDB(
                    id=self._user_id_counter,
                    username=admin_username,
                    email=admin_email,
                    password_hash=self.hash_password(admin_password),
                    is_active=True,
                    is_admin=True,
                    created_at=datetime.now(),
                    last_login=None,
                )
                self._user_id_counter += 1
                logger.info(f"Created default admin user: {admin_username}")
            except Exception as e:
                logger.error(f"Failed to create default admin: {e}")
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_user(self, username: str) -> Optional[UserInDB]:
        """Get user by username"""
        return self._users.get(username.lower())
    
    def get_user_by_id(self, user_id: int) -> Optional[UserInDB]:
        """Get user by ID"""
        for user in self._users.values():
            if user.id == user_id:
                return user
        return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """Authenticate user with username and password"""
        user = self.get_user(username)
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        username = user_data.username.lower()
        
        # Check if user already exists
        if username in self._users:
            raise ValueError(f"User '{username}' already exists")
        
        # Check if email already exists
        if user_data.email:
            for existing_user in self._users.values():
                if existing_user.email == user_data.email:
                    raise ValueError(f"Email '{user_data.email}' already registered")
        
        # Create user
        user = UserInDB(
            id=self._user_id_counter,
            username=username,
            email=user_data.email,
            password_hash=self.hash_password(user_data.password),
            is_active=True,
            is_admin=False,
            created_at=datetime.now(),
            last_login=None,
        )
        
        self._users[username] = user
        self._user_id_counter += 1
        
        logger.info(f"Created new user: {username}")
        
        # Return user without password hash
        return User(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
        )
    
    def create_access_token(
        self, 
        user: UserInDB,
        expires_delta: Optional[timedelta] = None
    ) -> Token:
        """Create JWT access token for user"""
        if expires_delta is None:
            expires_delta = timedelta(hours=JWT_EXPIRY_HOURS)
        
        expire = datetime.utcnow() + expires_delta
        
        to_encode = {
            "sub": user.username,
            "user_id": user.id,
            "is_admin": user.is_admin,
            "exp": expire,
        }
        
        access_token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        
        # Update last login
        user.last_login = datetime.now()
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=int(expires_delta.total_seconds()),
            user=User(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username: str = payload.get("sub")
            user_id: int = payload.get("user_id")
            is_admin: bool = payload.get("is_admin", False)
            exp = payload.get("exp")
            
            if username is None:
                return None
            
            return TokenData(
                username=username,
                user_id=user_id,
                is_admin=is_admin,
                exp=datetime.fromtimestamp(exp) if exp else None,
            )
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None
    
    def change_password(
        self, 
        username: str, 
        current_password: str, 
        new_password: str
    ) -> bool:
        """Change user password"""
        user = self.authenticate_user(username, current_password)
        if not user:
            return False
        
        user.password_hash = self.hash_password(new_password)
        logger.info(f"Password changed for user: {username}")
        return True
    
    def list_users(self) -> list[User]:
        """List all users (admin only)"""
        return [
            User(
                id=u.id,
                username=u.username,
                email=u.email,
                is_active=u.is_active,
                is_admin=u.is_admin,
                created_at=u.created_at,
                last_login=u.last_login,
            )
            for u in self._users.values()
        ]
    
    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user account"""
        user = self.get_user(username)
        if not user:
            return False
        user.is_active = False
        logger.info(f"Deactivated user: {username}")
        return True
    
    def activate_user(self, username: str) -> bool:
        """Activate a user account"""
        user = self.get_user(username)
        if not user:
            return False
        user.is_active = True
        logger.info(f"Activated user: {username}")
        return True


# Global auth service instance
auth_service = AuthService()
