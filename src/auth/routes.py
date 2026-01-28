"""
Authentication API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm

from .models import User, UserCreate, UserLogin, Token, PasswordChange
from .service import auth_service
from .dependencies import get_current_active_user, get_admin_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user account.
    
    Password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    """
    try:
        user = auth_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=Token)
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate and receive JWT token.
    
    The token can be used in:
    - Authorization header: `Bearer <token>`
    - Cookie: `access_token=<token>`
    """
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    token = auth_service.create_access_token(user)
    
    # Also set cookie for browser-based access
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        max_age=token.expires_in,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )
    
    return token


@router.post("/login/json", response_model=Token)
async def login_json(response: Response, credentials: UserLogin):
    """
    Alternative login endpoint accepting JSON body.
    """
    user = auth_service.authenticate_user(credentials.username, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    token = auth_service.create_access_token(user)
    
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        max_age=token.expires_in,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    
    return token


@router.post("/logout")
async def logout(response: Response):
    """
    Logout by clearing the auth cookie.
    
    Note: JWT tokens cannot be truly invalidated server-side.
    Client should also discard the token.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current authenticated user's information.
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
):
    """
    Change the current user's password.
    """
    success = auth_service.change_password(
        current_user.username,
        password_data.current_password,
        password_data.new_password,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    return {"message": "Password changed successfully"}


# Admin-only routes

@router.get("/users", response_model=list[User])
async def list_users(admin: User = Depends(get_admin_user)):
    """
    List all users (admin only).
    """
    return auth_service.list_users()


@router.post("/users/{username}/deactivate")
async def deactivate_user(
    username: str,
    admin: User = Depends(get_admin_user),
):
    """
    Deactivate a user account (admin only).
    """
    if username == admin.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )
    
    success = auth_service.deactivate_user(username)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )
    
    return {"message": f"User '{username}' deactivated"}


@router.post("/users/{username}/activate")
async def activate_user(
    username: str,
    admin: User = Depends(get_admin_user),
):
    """
    Activate a user account (admin only).
    """
    success = auth_service.activate_user(username)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )
    
    return {"message": f"User '{username}' activated"}
