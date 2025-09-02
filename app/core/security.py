"""
Security utilities for Mumbai Geo-AI Project.
Handles JWT authentication, password hashing, and authorization.
"""

from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status
from pydantic import BaseModel
import secrets
import string

from .config import get_settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Get settings
settings = get_settings()


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token data for validation."""
    user_id: Optional[int] = None
    email: Optional[str] = None
    permissions: list[str] = []


class JWTTokens:
    """JWT token management."""
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            data: Data to encode in token
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        return jwt.encode(
            to_encode, 
            settings.SECRET_KEY, 
            algorithm=settings.ALGORITHM
        )
    
    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token.
        
        Args:
            data: Data to encode in token
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        return jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            token_type: Expected token type (access/refresh)
            
        Returns:
            Decoded token data or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Check token type
            if payload.get("type") != token_type:
                return None
                
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                return None
                
            return payload
            
        except JWTError:
            return None
    
    @staticmethod
    def create_token_pair(user_data: Dict[str, Any]) -> Token:
        """
        Create both access and refresh tokens.
        
        Args:
            user_data: User information to encode
            
        Returns:
            Token pair (access + refresh)
        """
        access_token = JWTTokens.create_access_token(user_data)
        refresh_token = JWTTokens.create_refresh_token({
            "user_id": user_data.get("user_id"),
            "email": user_data.get("email")
        })
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )


class PasswordManager:
    """Password hashing and verification."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password from database
            
        Returns:
            True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_random_password(length: int = 12) -> str:
        """
        Generate a random password.
        
        Args:
            length: Password length
            
        Returns:
            Random password string
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class APIKeyManager:
    """API key management for service-to-service authentication."""
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_api_key_hash(api_key: str) -> str:
        """Create a hash of an API key for storage."""
        return pwd_context.hash(api_key)
    
    @staticmethod
    def verify_api_key(api_key: str, hashed_key: str) -> bool:
        """Verify an API key against its hash."""
        return pwd_context.verify(api_key, hashed_key)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self._requests = {}  # {identifier: [timestamp, ...]}
    
    def is_allowed(
        self, 
        identifier: str, 
        limit: int = None, 
        window: int = 60
    ) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit: Maximum requests per window
            window: Time window in seconds
            
        Returns:
            True if request is allowed
        """
        if limit is None:
            limit = settings.RATE_LIMIT_PER_MINUTE
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        # Clean old requests
        if identifier in self._requests:
            self._requests[identifier] = [
                req_time for req_time in self._requests[identifier]
                if req_time > window_start
            ]
        else:
            self._requests[identifier] = []
        
        # Check limit
        if len(self._requests[identifier]) >= limit:
            return False
        
        # Add current request
        self._requests[identifier].append(now)
        return True


class PermissionChecker:
    """Permission-based authorization."""
    
    # Define permission levels
    PERMISSIONS = {
        "read": 1,
        "write": 2, 
        "admin": 3,
        "super_admin": 4
    }
    
    @staticmethod
    def has_permission(user_permissions: list[str], required_permission: str) -> bool:
        """
        Check if user has required permission.
        
        Args:
            user_permissions: List of user permissions
            required_permission: Required permission level
            
        Returns:
            True if user has permission
        """
        if not user_permissions:
            return False
            
        required_level = PermissionChecker.PERMISSIONS.get(required_permission, 0)
        
        for perm in user_permissions:
            user_level = PermissionChecker.PERMISSIONS.get(perm, 0)
            if user_level >= required_level:
                return True
        
        return False
    
    @staticmethod
    def check_resource_access(
        user_id: int, 
        resource_owner_id: int, 
        user_permissions: list[str]
    ) -> bool:
        """
        Check if user can access a resource.
        
        Args:
            user_id: ID of requesting user
            resource_owner_id: ID of resource owner
            user_permissions: User's permissions
            
        Returns:
            True if access is allowed
        """
        # User owns the resource
        if user_id == resource_owner_id:
            return True
        
        # User has admin permissions
        if PermissionChecker.has_permission(user_permissions, "admin"):
            return True
        
        return False


# Security exceptions
class SecurityException(HTTPException):
    """Base security exception."""
    pass


class AuthenticationException(SecurityException):
    """Authentication failed."""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationException(SecurityException):
    """Authorization failed."""
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class RateLimitException(SecurityException):
    """Rate limit exceeded."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": "60"}
        )


# Utility functions
def get_password_hash(password: str) -> str:
    """Convenience function for password hashing."""
    return PasswordManager.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Convenience function for password verification."""
    return PasswordManager.verify_password(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any]) -> str:
    """Convenience function for token creation."""
    return JWTTokens.create_access_token(data)


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Convenience function for token verification."""
    return JWTTokens.verify_token(token)


# Initialize rate limiter instance
rate_limiter = RateLimiter()