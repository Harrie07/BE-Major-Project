# app/core/config.py
"""
Configuration management for Mumbai Geo-AI Project.
Handles environment variables and application settings using Pydantic v2.
"""


from functools import lru_cache
from typing import Optional, List, Dict, Any, Union
# --- FIX: Import BaseSettings from the correct location for Pydantic v2 ---
from pydantic_settings import BaseSettings # <-- Correct import location
# Keep validator and Field from pydantic
from pydantic import validator, Field # <-- Correct import for other Pydantic features
import secrets
import os



class Settings(BaseSettings):
    """Application settings from environment variables."""


    # Application Settings
    APP_NAME: str = Field(default="Mumbai Geo-AI API", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment (development, staging, production)")


    # API Settings
    API_V1_STR: str = Field(default="/api/v1", description="API base path")
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32), description="Secret key for JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 8, description="Access token expiry (minutes)")
    REFRESH_TOKEN_EXPIRE_MINUTES: int = Field(default=60 * 24 * 30, description="Refresh token expiry (minutes)")


    # Security Settings
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    BCRYPT_ROUNDS: int = Field(default=12, description="BCrypt rounds for password hashing")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )


    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)


    # --- DATABASE CONFIGURATION ---
    # Use DATABASE_URL directly from environment variables
    # Example in .env or docker-compose: DATABASE_URL=postgresql://user:pass@host:port/dbname
    DATABASE_URL: str = Field(..., description="Database connection URL (postgresql://user:password@host:port/dbname)")
    # Optional individual components if needed for other logic, but DATABASE_URL takes precedence
    POSTGRES_USER: Optional[str] = Field(default=None, description="PostgreSQL username (fallback)")
    POSTGRES_PASSWORD: Optional[str] = Field(default=None, description="PostgreSQL password (fallback)")
    POSTGRES_DB: Optional[str] = Field(default=None, description="PostgreSQL database name (fallback)")
    POSTGRES_HOST: Optional[str] = Field(default=None, description="PostgreSQL host (fallback)")
    POSTGRES_PORT: Optional[int] = Field(default=None, description="PostgreSQL port (fallback)")


    # Database Settings
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")
    DATABASE_POOL_SIZE: int = Field(default=5, description="Database pool size")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, description="Database max overflow")


    # --- REDIS CONFIGURATION ---
    # Use REDIS_URL directly from environment variables
    # Example in .env or docker-compose: REDIS_URL=redis://host:port/db
    REDIS_URL: str = Field(..., description="Redis connection URL (redis://host:port/db)")
    # Optional individual components if needed for other logic, but REDIS_URL takes precedence
    REDIS_HOST: Optional[str] = Field(default=None, description="Redis host (fallback)")
    REDIS_PORT: Optional[int] = Field(default=None, description="Redis port (fallback)")
    REDIS_DB: Optional[int] = Field(default=None, description="Redis database number (fallback)")


    # Redis Settings (for job queue)
    REDIS_MAX_CONNECTIONS: int = Field(default=10, description="Max Redis connections")


    # --- MinIO/S3 Storage Settings ---
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="MinIO endpoint")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="MinIO access key")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="MinIO secret key")
    MINIO_SECURE: bool = Field(default=False, description="Use HTTPS for MinIO")
    MINIO_BUCKET_NAME: str = Field(default="mumbai-geoai", description="MinIO bucket name")


    # Alternative AWS S3 settings (if using S3 instead of MinIO)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS access key ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="AWS secret access key")
    AWS_REGION: str = Field(default="ap-south-1", description="AWS region (Mumbai)")
    S3_BUCKET_NAME: Optional[str] = Field(default=None, description="S3 bucket name")


    # --- Geospatial Settings ---
    DEFAULT_CRS: str = Field(default="EPSG:4326", description="Default CRS (WGS84)")
    MUMBAI_CRS: str = Field(default="EPSG:32643", description="Mumbai CRS (UTM Zone 43N)")
    MAX_AOI_SIZE_SQM: float = Field(default=100_000_000.0, description="Max AOI size (sq.m)")
    MIN_AOI_SIZE_SQM: float = Field(default=10_000.0, description="Min AOI size (sq.m)")


    # --- STAC Catalog Settings ---
    STAC_ENDPOINT: str = Field(
        default="https://earth-search.aws.element84.com/v1",
        description="STAC endpoint"
    )
    PLANETARY_COMPUTER_ENDPOINT: str = Field(
        default="https://planetarycomputer.microsoft.com/api/stac/v1",
        description="Planetary Computer STAC endpoint"
    )
    SENTINEL_HUB_CLIENT_ID: Optional[str] = Field(default=None, description="Sentinel Hub client ID")
    SENTINEL_HUB_CLIENT_SECRET: Optional[str] = Field(default=None, description="Sentinel Hub client secret")


    # --- ML Model Settings ---
    MODEL_BASE_PATH: str = Field(default="./models", description="Base path for models")
    MODEL_CACHE_SIZE: int = Field(default=1, description="Model cache size")
    INFERENCE_BATCH_SIZE: int = Field(default=4, description="Inference batch size")
    INFERENCE_DEVICE: str = Field(default="cpu", description="Inference device (cpu, cuda, mps)")


    # --- Processing Settings ---
    MAX_CONCURRENT_JOBS: int = Field(default=5, description="Max concurrent jobs")
    JOB_TIMEOUT_MINUTES: int = Field(default=60, description="Job timeout (minutes)")
    TILE_SIZE: int = Field(default=512, description="Tile size (pixels)")
    OVERLAP_SIZE: int = Field(default=64, description="Tile overlap (pixels)")


    # --- Email Notification Settings (Gmail/SMTP) ---
    SMTP_SERVER: str = Field(default="smtp.gmail.com", description="SMTP server address")
    SMTP_PORT: int = Field(default=587, description="SMTP port (587 for TLS, 465 for SSL)")
    SMTP_USERNAME: Optional[str] = Field(default=None, description="SMTP username (your email)")
    SMTP_PASSWORD: Optional[str] = Field(default=None, description="SMTP password (App password for Gmail)")
    FROM_EMAIL: Optional[str] = Field(default=None, description="Email 'from' address")
    SMTP_TLS: bool = Field(default=True, description="Use TLS for SMTP")
    
    # Legacy email settings (for backward compatibility)
    SMTP_HOST: Optional[str] = Field(default=None, description="SMTP host (legacy)")
    SMTP_USER: Optional[str] = Field(default=None, description="SMTP user (legacy)")
    EMAILS_FROM_EMAIL: Optional[str] = Field(default=None, description="Email from address (legacy)")
    EMAILS_FROM_NAME: Optional[str] = Field(default="Mumbai Geo-AI Alerts", description="Email from name")


    # --- SMS Settings (Twilio - Free Trial) ---
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, description="Twilio account SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, description="Twilio auth token")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, description="Twilio phone number (+15551234567)")


    # --- Frontend URL (for alert links in notifications) ---
    FRONTEND_URL: str = Field(default="http://localhost:3000", description="Frontend application URL")


    # --- Rate Limiting ---
    RATE_LIMIT_PER_MINUTE: int = Field(default=100, description="Rate limit per minute")
    RATE_LIMIT_BURST: int = Field(default=200, description="Rate limit burst")


    # --- Logging Settings ---
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    LOG_FILE: Optional[str] = Field(default="logs/mumbai-geoai.log", description="Log file path")
    LOG_ROTATION: str = Field(default="1 day", description="Log rotation interval")
    LOG_RETENTION: str = Field(default="30 days", description="Log retention period")


    # --- Monitoring Settings ---
    SENTRY_DSN: Optional[str] = Field(default=None, description="Sentry DSN")
    PROMETHEUS_MULTIPROC_DIR: Optional[str] = Field(default=None, description="Prometheus multiproc dir")


    # --- Mumbai-specific Settings ---
    MUMBAI_BOUNDS: Dict[str, float] = Field(
        default={
            "min_lon": 72.7760,
            "min_lat": 18.8900,
            "max_lon": 72.9781,
            "max_lat": 19.2760
        },
        description="Mumbai bounding box"
    )


    # Protected zones data source
    PROTECTED_ZONES_SHAPEFILE: Optional[str] = Field(default=None, description="Protected zones shapefile path")
    PROTECTED_ZONES_GEOJSON: Optional[str] = Field(
        default="./data/protected_zones.geojson",
        description="Protected zones GeoJSON path"
    )


    # --- ENVIRONMENT VARIABLES FROM .env or docker-compose ---
    PC_SUBSCRIPTION_KEY: Optional[str] = Field(default=None, description="Planetary Computer subscription key")
    PROJECT_NAME: str = Field(default="Mumbai Geo-AI Backend", description="Project name")
    MODEL_PATH: str = Field(
        default="./data/models/change_detection_model.pth",
        description="Path to change detection model"
    )
    DEVICE: str = Field(default="cpu", description="Device for model inference")
    TITILER_ENDPOINT: str = Field(default="http://localhost:8001", description="TiTiler endpoint")


    # --- Properties ---
    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for SQLAlchemy."""
        return self.DATABASE_URL


    @property
    def database_url_async(self) -> str:
        """Asynchronous database URL for async SQLAlchemy."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://") if self.DATABASE_URL else ""


    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"


    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"


    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        if self.is_production:
            # In production, only allow specific domains
            return [
                "https://mumbai-geoai.com",
                "https://www.mumbai-geoai.com",
                "https://app.mumbai-geoai.com"
            ]
        return self.CORS_ORIGINS


    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "allow"  # Allow extra fields



# --- SETTINGS INSTANCE ---
@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()



def get_settings_dependency() -> Settings:
    """Dependency for FastAPI to inject settings."""
    return get_settings()



# Create the settings instance for direct import
settings = get_settings()



# --- ENVIRONMENT-SPECIFIC CONFIGURATIONS ---
def get_database_url(settings_instance: Settings) -> str:
    """Get database URL based on environment."""
    return settings_instance.DATABASE_URL



def get_redis_url(settings_instance: Settings) -> str:
    """Get Redis URL based on environment."""
    return settings_instance.REDIS_URL



def get_storage_config(settings_instance: Settings) -> Dict[str, Any]:
    """Get storage configuration based on environment."""
    if settings_instance.is_production and settings_instance.S3_BUCKET_NAME:
        # Use S3 in production
        return {
            "type": "s3",
            "bucket": settings_instance.S3_BUCKET_NAME,
            "access_key": settings_instance.AWS_ACCESS_KEY_ID,
            "secret_key": settings_instance.AWS_SECRET_ACCESS_KEY,
            "region": settings_instance.AWS_REGION
        }
    else:
        # Use MinIO for development/testing
        return {
            "type": "minio",
            "endpoint": settings_instance.MINIO_ENDPOINT,
            "access_key": settings_instance.MINIO_ACCESS_KEY,
            "secret_key": settings_instance.MINIO_SECRET_KEY,
            "bucket": settings_instance.MINIO_BUCKET_NAME,
            "secure": settings_instance.MINIO_SECURE
        }



# --- MUMBAI-SPECIFIC CONSTANTS ---
MUMBAI_DISTRICTS = [
    "Mumbai City",
    "Mumbai Suburban",
    "Thane",
    "Palghar",
    "Raigad"
]


MUMBAI_PROTECTED_ZONES = [
    "Coastal Regulation Zone",
    "Forest Area",
    "National Park",
    "Wildlife Sanctuary",
    "Archaeological Site",
    "Water Body",
    "Green Belt",
    "Airport Zone"
]


# Satellite data sources priority order
SATELLITE_SOURCES_PRIORITY = [
    "sentinel-2-l2a",  # High resolution, free
    "landsat-c2-l2",   # Medium resolution, free
    "sentinel-1",      # SAR data
    "planet"           # Commercial high-resolution (if available)
]
