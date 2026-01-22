# app/main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from typing import List

# Import your settings, database, and models
from app.core.config import settings
from app.api.v1.api import api_router  # Import the API router
from app.db.database import engine, get_db, Base
from app.models import models # Import models to ensure they are registered with Base

# Configure logging based on settings
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Lifespan Events ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events: startup and shutdown."""
    logger.info("🚀 Starting Mumbai Geo-AI Backend...")

    # --- Startup ---
    try:
        # --- CRITICAL: Ensure models are imported BEFORE create_all ---
        logger.info(f"Number of tables registered with Base.metadata BEFORE create_all: {len(Base.metadata.tables)}")
        if len(Base.metadata.tables) == 0:
             logger.warning("Warning: No tables found in Base.metadata. Check if models are correctly imported and use the right Base instance.")

        # Log the database URL being used (mask password)
        masked_url = settings.DATABASE_URL.replace(
            settings.DATABASE_URL.split("@")[0].split("//")[1] + "@", 
            "***@"
        ) if "@" in settings.DATABASE_URL else settings.DATABASE_URL
        logger.info(f"Attempting to connect and create tables for database: {masked_url}")

        # Create database tables if they don't exist
        logger.info("Attempting to create tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully")

        # Verify connection works
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        # You might want to raise here to prevent startup if DB is critical
        # raise

    logger.info("✅ Application startup complete")
    yield
    # --- Shutdown ---
    logger.info("🛑 Shutting down Mumbai Geo-AI Backend...")

# --- Create FastAPI App ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Geo-AI system for detecting new/illegal construction in Mumbai using satellite imagery analysis",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# --- Configure CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# --- Include API Routes ---
app.include_router(api_router, prefix=settings.API_V1_STR)

# --- Root Endpoint ---
@app.get("/")
async def root():
    """Root endpoint providing basic API information."""
    return {
        "message": "Mumbai Geo-AI Backend API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_endpoints": f"{settings.API_V1_STR}/",
        "status": "running"
    }

# --- Enhanced Health Check ---
from sqlalchemy import text
from sqlalchemy.orm import Session

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint that verifies database connectivity."""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        # Get table count
        result = db.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        table_count = result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "tables_count": table_count,
            "app_name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "api_version": settings.API_V1_STR
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: Database connection failed - {str(e)}"
        )

# --- Main Execution Block ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )