"""
Clean API router for Mumbai Geo-AI Backend.
This version avoids problematic imports and works with your existing models.
"""
from app.api.v1.endpoints import alerts
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any
import logging
from datetime import datetime
from pydantic import BaseModel

from app.db.database import get_db
from app.models.models import Job, Detection
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create the main API router
api_router = APIRouter()

# --- Pydantic Models for Requests ---
class JobCreate(BaseModel):
    name: str
    parameters: Optional[Dict[Any, Any]] = {}

class DetectionCreate(BaseModel):
    job_id: int
    description: str

# --- Job Management Endpoints ---
@api_router.get("/jobs/", tags=["Jobs"])
async def list_jobs(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """List all jobs with pagination."""
    try:
        jobs = db.query(Job).offset(skip).limit(limit).all()
        total_jobs = db.query(Job).count()
        return {
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "parameters": job.parameters,
                    "result_url": job.result_url,
                    "error_message": job.error_message
                } for job in jobs
            ],
            "total": total_jobs,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch jobs: {str(e)}"
        )

@api_router.post("/jobs/", tags=["Jobs"], status_code=status.HTTP_201_CREATED)
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new job."""
    try:
        db_job = Job(
            name=job_data.name,
            parameters=job_data.parameters,
            status="pending"
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        return {
            "id": db_job.id,
            "name": db_job.name,
            "status": db_job.status,
            "created_at": db_job.created_at.isoformat() if db_job.created_at else None,
            "parameters": db_job.parameters,
            "message": "Job created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )

@api_router.get("/jobs/{job_id}", tags=["Jobs"])
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job by ID."""
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        return {
            "id": job.id,
            "name": job.name,
            "status": job.status,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "parameters": job.parameters,
            "result_url": job.result_url,
            "error_message": job.error_message
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch job: {str(e)}"
        )

# --- Detection Management Endpoints ---
@api_router.get("/detections/", tags=["Detections"])
async def list_detections(
    skip: int = 0, 
    limit: int = 100, 
    job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List all detections with optional job filtering."""
    try:
        query = db.query(Detection)
        if job_id:
            query = query.filter(Detection.job_id == job_id)
        
        detections = query.offset(skip).limit(limit).all()
        total_detections = query.count()
        
        return {
            "detections": [
                {
                    "id": detection.id,
                    "job_id": detection.job_id,
                    "description": detection.description
                } for detection in detections
            ],
            "total": total_detections,
            "skip": skip,
            "limit": limit,
            "filtered_by_job_id": job_id
        }
    except Exception as e:
        logger.error(f"Error fetching detections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch detections: {str(e)}"
        )

@api_router.post("/detections/", tags=["Detections"], status_code=status.HTTP_201_CREATED)
async def create_detection(detection_data: DetectionCreate, db: Session = Depends(get_db)):
    """Create a new detection."""
    try:
        # Verify the job exists
        job = db.query(Job).filter(Job.id == detection_data.job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {detection_data.job_id} not found"
            )
        
        db_detection = Detection(
            job_id=detection_data.job_id,
            description=detection_data.description
        )
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        return {
            "id": db_detection.id,
            "job_id": db_detection.job_id,
            "description": db_detection.description,
            "message": "Detection created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating detection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create detection: {str(e)}"
        )

# --- Database Information Endpoints ---
@api_router.get("/database/tables", tags=["Database"])
async def list_database_tables(db: Session = Depends(get_db)):
    """List all tables in the database."""
    try:
        result = db.execute(text("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [{"name": row[0], "type": row[1]} for row in result]
        return {
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {str(e)}"
        )

@api_router.get("/database/test", tags=["Database"])
async def test_database_connection(db: Session = Depends(get_db)):
    """Test database connection and return detailed info."""
    try:
        # Test basic connection
        db.execute(text("SELECT 1"))
        
        # Get PostgreSQL version
        version_result = db.execute(text("SELECT version()"))
        db_version = version_result.scalar()
        
        # Get current timestamp
        time_result = db.execute(text("SELECT NOW()"))
        current_time = time_result.scalar()
        
        # Count records in each table
        job_count = db.query(Job).count()
        detection_count = db.query(Detection).count()
        
        return {
            "status": "connected",
            "database_version": db_version,
            "current_time": str(current_time),
            "table_counts": {
                "jobs": job_count,
                "detections": detection_count
            },
            "connection_info": "Database is fully accessible"
        }
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database test failed: {str(e)}"
        )

# --- Mumbai-Specific Endpoints ---
@api_router.get("/mumbai/bounds", tags=["Mumbai"])
async def get_mumbai_bounds():
    """Get Mumbai's geographical bounds."""
    return {
        "bounds": settings.MUMBAI_BOUNDS,
        "crs": settings.DEFAULT_CRS,
        "mumbai_crs": settings.MUMBAI_CRS,
        "description": "Geographical boundaries of Mumbai"
    }

@api_router.get("/mumbai/districts", tags=["Mumbai"])
async def get_mumbai_districts():
    """Get list of Mumbai districts."""
    from app.core.config import MUMBAI_DISTRICTS
    return {
        "districts": MUMBAI_DISTRICTS,
        "count": len(MUMBAI_DISTRICTS)
    }

@api_router.get("/mumbai/protected-zones", tags=["Mumbai"])
async def get_protected_zones():
    """Get list of protected zone types in Mumbai."""
    from app.core.config import MUMBAI_PROTECTED_ZONES
    return {
        "protected_zones": MUMBAI_PROTECTED_ZONES,
        "count": len(MUMBAI_PROTECTED_ZONES)
    }

# --- System Information Endpoints ---
@api_router.get("/system/info", tags=["System"])
async def get_system_info():
    """Get system configuration information."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "default_crs": settings.DEFAULT_CRS,
        "mumbai_crs": settings.MUMBAI_CRS,
        "max_aoi_size": settings.MAX_AOI_SIZE_SQM,
        "min_aoi_size": settings.MIN_AOI_SIZE_SQM,
        "api_base_path": settings.API_V1_STR
    }

# --- Test Endpoints for Verification ---
@api_router.get("/test/simple", tags=["Testing"])
async def simple_test():
    """Simple test endpoint that doesn't require database."""
    return {
        "message": "Mumbai Geo-AI API is working!",
        "timestamp": datetime.now().isoformat(),
        "endpoints_available": True
    }

# Include alert-related routes
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])