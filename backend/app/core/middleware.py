"""
Middleware components for Mumbai Geo-AI Project.
Handles CORS, logging, error handling, and request processing.
"""

import time
import uuid
import json
import logging
from typing import Callable, Optional
from datetime import datetime

from fastapi import Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .config import get_settings
from .security import RateLimitException, AuthenticationException, AuthorizationException


# Configure logger
logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request/response logging and monitoring.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response with logging.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with added headers
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "content_length": request.headers.get("content-length"),
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": process_time,
                    "response_size": response.headers.get("content-length"),
                }
            )
            
            return response
            
        except Exception as e:
            # Calculate error time
            process_time = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "process_time": process_time,
                },
                exc_info=True
            )
            
            # Re-raise exception
            raise e


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for centralized error handling and formatting.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle exceptions and format error responses.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response or formatted error response
        """
        try:
            return await call_next(request)
            
        except AuthenticationException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "authentication_failed",
                    "message": e.detail,
                    "request_id": getattr(request.state, "request_id", None)
                },
                headers=e.headers
            )
            
        except AuthorizationException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "authorization_failed", 
                    "message": e.detail,
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
            
        except RateLimitException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "rate_limit_exceeded",
                    "message": e.detail,
                    "request_id": getattr(request.state, "request_id", None)
                },
                headers=e.headers
            )
            
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "http_exception",
                    "message": e.detail,
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
            
        except ValueError as e:
            logger.error(f"Value error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=400,
                content={
                    "error": "validation_error",
                    "message": str(e),
                    "request_id": getattr(request.state, "request_id", None)
                }
            )
            
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "An unexpected error occurred",
                    "request_id": getattr(request.state, "request_id", None)
                }
            )


class DatabaseMiddleware(BaseHTTPMiddleware):
    """
    Middleware for database connection handling.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle database connections and transactions.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with database handling
        """
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Log database-related errors
            if "database" in str(e).lower() or "sql" in str(e).lower():
                logger.error(
                    "Database error occurred",
                    extra={
                        "request_id": getattr(request.state, "request_id", None),
                        "error": str(e),
                        "url": str(request.url)
                    },
                    exc_info=True
                )
            
            raise e


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to responses.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle response compression.
    """
    
    def __init__(self, app: ASGIApp, minimum_size: int = 1024):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add compression headers based on request.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with compression handling
        """
        # Check if client accepts compression
        accept_encoding = request.headers.get("accept-encoding", "")
        
        response = await call_next(request)
        
        # Add compression hint for large responses
        content_length = response.headers.get("content-length")
        if (content_length and 
            int(content_length) > self.minimum_size and
            "gzip" in accept_encoding.lower()):
            response.headers["X-Compression-Hint"] = "enabled"
        
        return response


class GeospatialMiddleware(BaseHTTPMiddleware):
    """
    Middleware for geospatial request handling.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle geospatial-specific request processing.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with geospatial handling
        """
        # Check if this is a geospatial endpoint
        is_geospatial = any(path in str(request.url) for path in [
            "/aoi", "/tiles", "/zones", "/detections"
        ])
        
        if is_geospatial:
            # Add geospatial headers
            request.state.is_geospatial = True
            
            # Validate geospatial content type for POST/PUT requests
            if request.method in ["POST", "PUT"]:
                content_type = request.headers.get("content-type", "")
                if ("geojson" in content_type.lower() or 
                    "application/json" in content_type.lower()):
                    request.state.geospatial_content = True
        
        response = await call_next(request)
        
        # Add geospatial response headers
        if is_geospatial:
            response.headers["X-Geospatial-Endpoint"] = "true"
            response.headers["X-Coordinate-System"] = "EPSG:4326"
        
        return response


def setup_cors_middleware(app, settings):
    """
    Setup CORS middleware with appropriate settings.
    
    Args:
        app: FastAPI application
        settings: Application settings
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time", 
            "X-Geospatial-Endpoint",
            "X-Coordinate-System"
        ]
    )


def setup_trusted_host_middleware(app, settings):
    """
    Setup trusted host middleware for production.
    
    Args:
        app: FastAPI application
        settings: Application settings
    """
    if settings.is_production:
        allowed_hosts = [
            "mumbai-geoai.com",
            "*.mumbai-geoai.com",
            "api.mumbai-geoai.com"
        ]
        
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts
        )


def setup_all_middleware(app):
    """
    Setup all middleware in the correct order.
    
    Args:
        app: FastAPI application
    """
    settings = get_settings()
    
    # Order matters - add in reverse order of execution
    
    # Security headers (last to execute, first to add)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Compression handling
    app.add_middleware(CompressionMiddleware)
    
    # Geospatial handling
    app.add_middleware(GeospatialMiddleware)
    
    # Database handling
    app.add_middleware(DatabaseMiddleware)
    
    # Error handling
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Request logging (first to execute, last to add)
    app.add_middleware(LoggingMiddleware)
    
    # CORS middleware
    setup_cors_middleware(app, settings)
    
    # Trusted host middleware for production
    setup_trusted_host_middleware(app, settings)


# Health check endpoint middleware
class HealthCheckMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle health check requests quickly.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Handle health check requests.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Quick health check response or normal processing
        """
        if request.url.path in ["/health", "/healthz", "/ping"]:
            return JSONResponse(
                content={
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": get_settings().APP_VERSION
                }
            )
        
        return await call_next(request)