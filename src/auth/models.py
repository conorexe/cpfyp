"""
Authentication data models using Pydantic.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    
    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must be alphanumeric with underscores only')
        return v.lower()


class UserCreate(UserBase):
    """User registration model"""
    password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str


class User(UserBase):
    """User model returned from API"""
    id: int
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserInDB(User):
    """User model with password hash (internal use only)"""
    password_hash: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiration
    user: User


class TokenData(BaseModel):
    """Data decoded from JWT token"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    is_admin: bool = False
    exp: Optional[datetime] = None


class PasswordChange(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v
