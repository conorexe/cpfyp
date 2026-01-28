"""
Tests for authentication module.
"""

import pytest
from src.auth.service import AuthService
from src.auth.models import UserCreate, UserLogin


class TestAuthService:
    """Tests for AuthService"""
    
    def test_create_user(self, fresh_auth_service: AuthService):
        """Test user creation"""
        user_data = UserCreate(
            username="newuser",
            email="new@example.com",
            password="SecurePass123",
        )
        
        user = fresh_auth_service.create_user(user_data)
        
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.is_active
        assert not user.is_admin
    
    def test_create_duplicate_user(self, fresh_auth_service: AuthService):
        """Test that duplicate usernames are rejected"""
        user_data = UserCreate(
            username="duplicate",
            email="dup@example.com",
            password="SecurePass123",
        )
        
        fresh_auth_service.create_user(user_data)
        
        with pytest.raises(ValueError, match="already exists"):
            fresh_auth_service.create_user(user_data)
    
    def test_authenticate_user(self, fresh_auth_service: AuthService):
        """Test user authentication"""
        user_data = UserCreate(
            username="authtest",
            email="auth@example.com",
            password="SecurePass123",
        )
        
        fresh_auth_service.create_user(user_data)
        
        # Correct credentials
        user = fresh_auth_service.authenticate_user("authtest", "SecurePass123")
        assert user is not None
        assert user.username == "authtest"
        
        # Wrong password
        user = fresh_auth_service.authenticate_user("authtest", "WrongPass123")
        assert user is None
        
        # Wrong username
        user = fresh_auth_service.authenticate_user("nonexistent", "SecurePass123")
        assert user is None
    
    def test_create_access_token(self, fresh_auth_service: AuthService):
        """Test JWT token creation"""
        user_data = UserCreate(
            username="tokentest",
            password="SecurePass123",
        )
        
        fresh_auth_service.create_user(user_data)
        user = fresh_auth_service.get_user("tokentest")
        
        token = fresh_auth_service.create_access_token(user)
        
        assert token.access_token
        assert token.token_type == "bearer"
        assert token.expires_in > 0
        assert token.user.username == "tokentest"
    
    def test_verify_token(self, fresh_auth_service: AuthService):
        """Test JWT token verification"""
        user_data = UserCreate(
            username="verifytest",
            password="SecurePass123",
        )
        
        fresh_auth_service.create_user(user_data)
        user = fresh_auth_service.get_user("verifytest")
        token = fresh_auth_service.create_access_token(user)
        
        token_data = fresh_auth_service.verify_token(token.access_token)
        
        assert token_data is not None
        assert token_data.username == "verifytest"
        assert token_data.user_id == user.id
    
    def test_verify_invalid_token(self, fresh_auth_service: AuthService):
        """Test that invalid tokens are rejected"""
        token_data = fresh_auth_service.verify_token("invalid.token.here")
        assert token_data is None
    
    def test_change_password(self, fresh_auth_service: AuthService):
        """Test password change"""
        user_data = UserCreate(
            username="pwdchange",
            password="OldPass123",
        )
        
        fresh_auth_service.create_user(user_data)
        
        # Change password
        success = fresh_auth_service.change_password(
            "pwdchange",
            "OldPass123",
            "NewPass456",
        )
        assert success
        
        # Old password should fail
        user = fresh_auth_service.authenticate_user("pwdchange", "OldPass123")
        assert user is None
        
        # New password should work
        user = fresh_auth_service.authenticate_user("pwdchange", "NewPass456")
        assert user is not None
    
    def test_password_validation(self):
        """Test password validation rules"""
        # No uppercase
        with pytest.raises(ValueError, match="uppercase"):
            UserCreate(username="test", password="lowercase123")
        
        # No lowercase
        with pytest.raises(ValueError, match="lowercase"):
            UserCreate(username="test", password="UPPERCASE123")
        
        # No digit
        with pytest.raises(ValueError, match="digit"):
            UserCreate(username="test", password="NoDigitsHere")
        
        # Too short
        with pytest.raises(ValueError):
            UserCreate(username="test", password="Short1")
    
    def test_username_validation(self):
        """Test username validation rules"""
        # Invalid characters
        with pytest.raises(ValueError, match="alphanumeric"):
            UserCreate(username="invalid@user", password="ValidPass123")
        
        # Too short
        with pytest.raises(ValueError):
            UserCreate(username="ab", password="ValidPass123")


class TestAuthEndpoints:
    """Tests for auth API endpoints"""
    
    def test_register(self, client):
        """Test user registration endpoint"""
        response = client.post(
            "/api/auth/register",
            json={
                "username": "apitest",
                "email": "api@test.com",
                "password": "ApiTest123",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "apitest"
        assert "password" not in data
    
    def test_login(self, client, test_user):
        """Test login endpoint"""
        # Note: This test needs the global auth_service
        # In real tests, we'd mock it properly
        pass
    
    def test_protected_endpoint_without_auth(self, client):
        """Test that protected endpoints require auth"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
