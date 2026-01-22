"""
FastAPI dependencies for Mumbai Geo-AI Project.
Handles authentication, authorization, database sessions, and common dependencies.
"""

from typing import Optional, Generator, Annotated
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
import time
import psutil

from app.db.session import get_db, get_async_db
from app.models.database import User  # We'll need to create this User model
from app.core.config import get_settings, Settings
from app.core.security import (
    JWTTokens, TokenData, AuthenticationException, AuthorizationException,
    RateLimitException, PermissionChecker, rate_limiter
)


# Security scheme
security = HTTPBearer(auto_error=False)


def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """
    Extract and validate JWT token from Authorization header.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        Validated token data
        
    Raises:
        AuthenticationException: If token is invalid
    """
    if not credentials:
        raise AuthenticationException("Authorization header required")
    
    token = credentials.credentials
    payload = JWTTokens.verify_token(token, "access")
    
    if payload is None:
        raise AuthenticationException("Invalid or expired token")
    
    user_id = payload.get("user_id")
    email = payload.get("email")
    permissions = payload.get("permissions", [])
    
    if user_id is None:
        raise AuthenticationException("Invalid token payload")
    
    return TokenData(
        user_id=user_id,
        email=email,
        permissions=permissions
    )


def get_current_user(
    db: Session = Depends(get_db),
    token_data: TokenData = Depends(get_current_user_token)
) -> User:
    """
    Get current authenticated user from database.
    
    Args:
        db: Database session
        token_data: Validated token data
        
    Returns:
        Current user object
        
    Raises:
        AuthenticationException: If user not found
    """
    user = db.execute(
        select(User).where(User.id == token_data.user_id)
    ).scalar_one_or_none()
    
    if user is None:
        raise AuthenticationException("User not found")
    
    if not user.is_active:
        raise AuthenticationException("Inactive user")
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (convenience dependency).
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user object
        
    Raises:
        AuthenticationException: If user is inactive
    """
    if not current_user.is_active:
        raise AuthenticationException("Inactive user")
    
    return current_user


def get_admin_user(
    current_user: User = Depends(get_current_active_user),
    token_data: TokenData = Depends(get_current_user_token)
) -> User:
    """
    Require admin permissions.
    
    Args:
        current_user: Current active user
        token_data: Token data with permissions
        
    Returns:
        Admin user object
        
    Raises:
        AuthorizationException: If user is not admin
    """
    if not PermissionChecker.has_permission(token_data.permissions, "admin"):
        raise AuthorizationException("Admin permissions required")
    
    return current_user


def get_super_admin_user(
    current_user: User = Depends(get_current_active_user),
    token_data: TokenData = Depends(get_current_user_token)
) -> User:
    """
    Require super admin permissions.
    
    Args:
        current_user: Current active user
        token_data: Token data with permissions
        
    Returns:
        Super admin user object
        
    Raises:
        AuthorizationException: If user is not super admin
    """
    if not PermissionChecker.has_permission(token_data.permissions, "super_admin"):
        raise AuthorizationException("Super admin permissions required")
    
    return current_user


def check_api_key(
    request: Request,
    x_api_key: Annotated[Optional[str], Header()] = None,
    db: Session = Depends(get_db)
) -> bool:
    """
    Validate API key for service-to-service authentication.
    
    Args:
        request: FastAPI request object
        x_api_key: API key from X-API-Key header
        db: Database session
        
    Returns:
        True if API key is valid
        
    Raises:
        AuthenticationException: If API key is invalid
    """
    if not x_api_key:
        raise AuthenticationException("API key required")
    
    # TODO: Implement API key validation against database
    # For now, using a simple check
    settings = get_settings()
    if x_api_key != "dev-api-key":  # Replace with proper validation
        raise AuthenticationException("Invalid API key")
    
    return True


def rate_limit_check(
    request: Request,
    settings: Settings = Depends(get_settings)
) -> bool:
    """
    Check rate limits for the request.
    
    Args:
        request: FastAPI request object
        settings: Application settings
        
    Returns:
        True if request is allowed
        
    Raises:
        RateLimitException: If rate limit exceeded
    """
    # Use client IP as identifier
    client_ip = request.client.host if request.client else "unknown"
    
    if not rate_limiter.is_allowed(
        identifier=client_ip,
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window=60
    ):
        raise RateLimitException()
    
    return True


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get user from token if provided, otherwise return None.
    Used for endpoints that work with or without authentication.
    
    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token_data = get_current_user_token(credentials)
        return get_current_user(db, token_data)
    except AuthenticationException:
        return None


def check_resource_ownership(
    resource_owner_id: int,
    current_user: User = Depends(get_current_active_user),
    token_data: TokenData = Depends(get_current_user_token)
) -> bool:
    """
    Check if user owns a resource or has admin permissions.
    
    Args:
        resource_owner_id: ID of resource owner
        current_user: Current user
        token_data: Token data with permissions
        
    Returns:
        True if access is allowed
        
    Raises:
        AuthorizationException: If access is denied
    """
    if not PermissionChecker.check_resource_access(
        current_user.id, 
        resource_owner_id, 
        token_data.permissions
    ):
        raise AuthorizationException("Access denied to this resource")
    
    return True


def get_pagination(
    page: int = 1,
    limit: int = 50,
    settings: Settings = Depends(get_settings)
) -> dict:
    """
    Pagination parameters with validation.
    
    Args:
        page: Page number (1-based)
        limit: Items per page
        settings: Application settings
        
    Returns:
        Dictionary with offset and limit
        
    Raises:
        HTTPException: If parameters are invalid
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1"
        )
    
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 1000"
        )
    
    offset = (page - 1) * limit
    
    return {
        "offset": offset,
        "limit": limit,
        "page": page
    }


def validate_mumbai_coordinates(
    longitude: float,
    latitude: float,
    settings: Settings = Depends(get_settings)
) -> tuple[float, float]:
    """
    Validate coordinates are within Mumbai bounds.
    
    Args:
        longitude: Longitude coordinate
        latitude: Latitude coordinate
        settings: Application settings
        
    Returns:
        Validated coordinates tuple
        
    Raises:
        HTTPException: If coordinates are outside Mumbai bounds
    """
    bounds = settings.MUMBAI_BOUNDS
    
    if not (bounds["min_lon"] <= longitude <= bounds["max_lon"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Longitude must be between {bounds['min_lon']} and {bounds['max_lon']}"
        )
    
    if not (bounds["min_lat"] <= latitude <= bounds["max_lat"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Latitude must be between {bounds['min_lat']} and {bounds['max_lat']}"
        )
    
    return longitude, latitude


def get_user_context(
    current_user: User = Depends(get_current_active_user),
    token_data: TokenData = Depends(get_current_user_token),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get comprehensive user context for requests.
    
    Args:
        current_user: Current authenticated user
        token_data: Token data with permissions
        db: Database session
        
    Returns:
        User context dictionary
    """
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "permissions": token_data.permissions,
        "is_admin": PermissionChecker.has_permission(token_data.permissions, "admin"),
        "is_super_admin": PermissionChecker.has_permission(token_data.permissions, "super_admin"),
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


# Dependency aliases for common combinations
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
SuperAdminUser = Annotated[User, Depends(get_super_admin_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
DatabaseSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
UserContext = Annotated[dict, Depends(get_user_context)]
Pagination = Annotated[dict, Depends(get_pagination)]
TokenInfo = Annotated[TokenData, Depends(get_current_user_token)]


# Common dependency combinations
def get_authenticated_context() -> dict:
    """
    Get dependencies for authenticated endpoints.
    
    Returns:
        Dictionary of common authenticated dependencies
    """
    return {
        "current_user": Depends(get_current_active_user),
        "token_data": Depends(get_current_user_token),
        "db": Depends(get_db),
        "settings": Depends(get_settings)
    }


def get_admin_context() -> dict:
    """
    Get dependencies for admin endpoints.
    
    Returns:
        Dictionary of admin dependencies
    """
    return {
        "admin_user": Depends(get_admin_user),
        "token_data": Depends(get_current_user_token),
        "db": Depends(get_db),
        "settings": Depends(get_settings)
    }


# Custom dependency factory for resource-specific permissions
def require_permission(permission: str):
    """
    Factory function to create permission-checking dependency.
    
    Args:
        permission: Required permission level
        
    Returns:
        Dependency function that checks permission
    """
    def check_permission(
        token_data: TokenData = Depends(get_current_user_token)
    ) -> bool:
        if not PermissionChecker.has_permission(token_data.permissions, permission):
            raise AuthorizationException(f"{permission} permission required")
        return True
    
    return Depends(check_permission)


# Dependency for file upload validation
def validate_upload_file(
    content_type: Optional[str] = None,
    max_size: int = 50 * 1024 * 1024  # 50MB default
):
    """
    Factory for file upload validation dependency.
    
    Args:
        content_type: Expected content type
        max_size: Maximum file size in bytes
        
    Returns:
        File validation dependency
    """
    def validate_file(request: Request) -> bool:
        # Get content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {max_size} bytes"
            )
        
        # Check content type if specified
        if content_type:
            request_content_type = request.headers.get("content-type", "")
            if not request_content_type.startswith(content_type):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported content type. Expected: {content_type}"
                )
        
        return True
    
    return Depends(validate_file)


# Health check dependency (no authentication required)
def health_check_dependency() -> dict:
    """
    Dependency for health check endpoints.
    
    Returns:
        Basic system information
    """
    return {
        "timestamp": time.time(),
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }


# Job-specific dependencies
def get_job_processing_context(
    current_user: CurrentUser,
    db: DatabaseSession,
    settings: AppSettings
) -> dict:
    """
    Get context for job processing endpoints.
    
    Returns:
        Dictionary with user, db, and processing settings
    """
    return {
        "user": current_user,
        "db": db,
        "settings": settings,
        "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS_PER_USER,
        "default_cloud_threshold": settings.DEFAULT_CLOUD_THRESHOLD,
        "default_confidence_threshold": settings.DEFAULT_CONFIDENCE_THRESHOLD
    }


def validate_aoi_geometry(
    geometry_data: dict,
    settings: Settings = Depends(get_settings)
) -> dict:
    """
    Validate AOI geometry constraints.
    
    Args:
        geometry_data: GeoJSON-like geometry data
        settings: Application settings
        
    Returns:
        Validated geometry data
        
    Raises:
        HTTPException: If geometry is invalid
    """
    from shapely.geometry import shape
    from shapely.validation import make_valid
    
    try:
        # Parse geometry
        geom = shape(geometry_data)
        
        # Validate geometry
        if not geom.is_valid:
            geom = make_valid(geom)
        
        # Check area constraints
        area_sqkm = geom.area * 111.32 * 111.32  # Rough conversion to km²
        
        if area_sqkm > settings.MAX_AOI_AREA_SQKM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AOI area ({area_sqkm:.2f} km²) exceeds maximum allowed ({settings.MAX_AOI_AREA_SQKM} km²)"
            )
        
        if area_sqkm < settings.MIN_AOI_AREA_SQKM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AOI area ({area_sqkm:.2f} km²) below minimum required ({settings.MIN_AOI_AREA_SQKM} km²)"
            )
        
        # Check if within Mumbai bounds
        bounds = settings.MUMBAI_BOUNDS
        bbox = geom.bounds
        
        if not (bounds["min_lon"] <= bbox[0] and bbox[2] <= bounds["max_lon"] and
                bounds["min_lat"] <= bbox[1] and bbox[3] <= bounds["max_lat"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AOI geometry must be within Mumbai bounds"
            )
        
        return geometry_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid geometry: {str(e)}"
        )


def validate_date_range(
    start_date: str,
    end_date: str,
    settings: Settings = Depends(get_settings)
) -> tuple[str, str]:
    """
    Validate date range for satellite imagery requests.
    
    Args:
        start_date: Start date string (ISO format)
        end_date: End date string (ISO format)
        settings: Application settings
        
    Returns:
        Validated date tuple
        
    Raises:
        HTTPException: If dates are invalid
    """
    from datetime import datetime, timedelta
    
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use ISO format: {str(e)}"
        )
    
    # Check date order
    if start_dt >= end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before end date"
        )
    
    # Check minimum gap between dates
    min_gap = timedelta(days=settings.MIN_DATE_GAP_DAYS)
    if end_dt - start_dt < min_gap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum {settings.MIN_DATE_GAP_DAYS} days gap required between dates"
        )
    
    # Check maximum gap between dates
    max_gap = timedelta(days=settings.MAX_DATE_GAP_DAYS)
    if end_dt - start_dt > max_gap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {settings.MAX_DATE_GAP_DAYS} days gap allowed between dates"
        )
    
    # Check if dates are not too far in the past
    earliest_allowed = datetime.now() - timedelta(days=settings.MAX_HISTORICAL_DAYS)
    if start_dt < earliest_allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Start date cannot be more than {settings.MAX_HISTORICAL_DAYS} days in the past"
        )
    
    # Check if dates are not in the future
    if end_dt > datetime.now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be in the future"
        )
    
    return start_date, end_date


def check_user_job_limits(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
) -> bool:
    """
    Check if user can create new jobs based on limits.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        settings: Application settings
        
    Returns:
        True if user can create jobs
        
    Raises:
        HTTPException: If user has reached limits
    """
    from app.models.database import Job, JobStatus
    
    # Check active jobs limit
    active_jobs = db.execute(
        select(Job).where(
            Job.created_by == str(current_user.id),
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING])
        )
    ).scalars().all()
    
    if len(active_jobs) >= settings.MAX_CONCURRENT_JOBS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {settings.MAX_CONCURRENT_JOBS_PER_USER} concurrent jobs allowed"
        )
    
    # Check daily job limit
    from datetime import datetime, timedelta
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    daily_jobs = db.execute(
        select(Job).where(
            Job.created_by == str(current_user.id),
            Job.created_at >= today_start
        )
    ).scalars().all()
    
    if len(daily_jobs) >= settings.MAX_DAILY_JOBS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum {settings.MAX_DAILY_JOBS_PER_USER} jobs per day allowed"
        )
    
    return True


def get_detection_filters(
    confidence_min: Optional[float] = None,
    confidence_max: Optional[float] = None,
    is_flagged: Optional[bool] = None,
    review_status: Optional[str] = None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None
) -> dict:
    """
    Get detection filtering parameters.
    
    Args:
        confidence_min: Minimum confidence score
        confidence_max: Maximum confidence score
        is_flagged: Filter by flagged status
        review_status: Filter by review status
        area_min: Minimum area in square meters
        area_max: Maximum area in square meters
        
    Returns:
        Dictionary of validated filters
    """
    filters = {}
    
    if confidence_min is not None:
        if not 0.0 <= confidence_min <= 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="confidence_min must be between 0.0 and 1.0"
            )
        filters["confidence_min"] = confidence_min
    
    if confidence_max is not None:
        if not 0.0 <= confidence_max <= 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="confidence_max must be between 0.0 and 1.0"
            )
        filters["confidence_max"] = confidence_max
    
    if confidence_min is not None and confidence_max is not None:
        if confidence_min > confidence_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="confidence_min cannot be greater than confidence_max"
            )
    
    if is_flagged is not None:
        filters["is_flagged"] = is_flagged
    
    if review_status is not None:
        from app.models.database import DetectionStatus
        valid_statuses = [status.value for status in DetectionStatus]
        if review_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid review_status. Must be one of: {valid_statuses}"
            )
        filters["review_status"] = review_status
    
    if area_min is not None:
        if area_min < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="area_min must be >= 0"
            )
        filters["area_min"] = area_min
    
    if area_max is not None:
        if area_max < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="area_max must be >= 0"
            )
        filters["area_max"] = area_max
    
    if area_min is not None and area_max is not None:
        if area_min > area_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="area_min cannot be greater than area_max"
            )
    
    return filters


# Cache dependency for frequently accessed data
def get_cached_protected_zones(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings)
) -> list:
    """
    Get protected zones with caching.
    
    Args:
        db: Database session
        settings: Application settings
        
    Returns:
        List of active protected zones
    """
    # TODO: Implement Redis caching
    from app.models.database import ProtectedZone
    
    zones = db.execute(
        select(ProtectedZone).where(
            ProtectedZone.is_active == True
        )
    ).scalars().all()
    
    return zones


# WebSocket dependencies for real-time updates
def get_websocket_user(
    websocket,
    token: str
) -> Optional[User]:
    """
    Get user from WebSocket connection token.
    
    Args:
        websocket: WebSocket connection
        token: JWT token from query params
        
    Returns:
        User object if authenticated, None otherwise
    """
    try:
        payload = JWTTokens.verify_token(token, "access")
        if payload is None:
            return None
        
        # Get user from database
        # TODO: Implement database lookup
        return None  # Placeholder
        
    except Exception:
        return None


# Export commonly used dependency combinations
__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_admin_user", 
    "get_super_admin_user",
    "get_optional_user",
    "get_pagination",
    "validate_mumbai_coordinates",
    "validate_aoi_geometry",
    "validate_date_range",
    "check_user_job_limits",
    "get_detection_filters",
    "get_cached_protected_zones",
    "health_check_dependency",
    "CurrentUser",
    "AdminUser",
    "SuperAdminUser",
    "OptionalUser", 
    "DatabaseSession",
    "AppSettings",
    "UserContext",
    "Pagination",
    "TokenInfo",
    "require_permission",
    "validate_upload_file"
]