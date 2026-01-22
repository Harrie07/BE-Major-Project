# app/api/v1/endpoints/jobs.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from app.db.database import get_db
from app.models.models import ChangeDetectionJob, AOI
from app.models.schemas import (
    JobCreate, JobResponse, JobStatusUpdate, PaginationParams, JobStatus
)
from app.services.job_service import JobService
from app.services.queue_service import QueueService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_job_service() -> JobService:
    """Dependency to get JobService instance"""
    return JobService()


def get_queue_service() -> QueueService:
    """Dependency to get QueueService instance"""  
    return QueueService()


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    queue_service: QueueService = Depends(get_queue_service)
):
    """
    Create a new change detection job
    
    This endpoint creates a job and queues it for processing.
    The job will run asynchronously in the background.
    """
    try:
        # Use JobService to create the job (proper service layer)
        job = await job_service.create_job(db, job_data)
        
        # Queue job for processing
        try:
            queue_id = await queue_service.enqueue_change_detection_job(job.id)
            logger.info(f"Job {job.id} queued with queue ID: {queue_id}")
        except Exception as e:
            logger.warning(f"Failed to queue job {job.id}: {e}")
            # Job is created but not queued - can be processed later
        
        logger.info(f"Created change detection job: {job.id}")
        
        # Convert to response model
        return JobResponse.from_orm(job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service)
):
    """
    Get job status and details by job ID
    """
    try:
        job = await job_service.get_job(db, job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        return JobResponse.from_orm(job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}"
        )


@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    aoi_id: Optional[str] = None,
    status_filter: Optional[JobStatus] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service)
):
    """
    List jobs with optional filtering
    
    - **aoi_id**: Filter by AOI ID
    - **status_filter**: Filter by job status
    """
    try:
        # Use JobService to get filtered jobs
        jobs = await job_service.list_jobs(
            db=db,
            aoi_id=aoi_id,
            status_filter=status_filter,
            skip=pagination.skip,
            limit=pagination.limit
        )
        
        # Convert to response format
        return [JobResponse.from_orm(job) for job in jobs]
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )


@router.patch("/{job_id}/status", response_model=JobResponse)
async def update_job_status(
    job_id: str,
    status_update: JobStatusUpdate,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service)
):
    """
    Update job status, progress, and results
    
    This endpoint is typically used by the job processing workers.
    """
    try:
        # Use JobService to update job
        updated_job = await job_service.update_job_status(
            db=db,
            job_id=job_id,
            status_update=status_update
        )
        
        if not updated_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        logger.info(f"Updated job {job_id} status to {status_update.status}")
        
        return JobResponse.from_orm(updated_job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job: {str(e)}"
        )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    queue_service: QueueService = Depends(get_queue_service)
):
    """
    Cancel a job (if pending) or mark as cancelled
    """
    try:
        # Get job using service
        job = await job_service.get_job(db, job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        if job.status == JobStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel completed job"
            )
        
        # Try to cancel from queue if pending
        if job.status == JobStatus.PENDING:
            try:
                await queue_service.cancel_job(job_id)
            except Exception as e:
                logger.warning(f"Failed to cancel job from queue: {e}")
        
        # Use JobService to update job status
        status_update = JobStatusUpdate(
            status=JobStatus.FAILED,
            error_message="Job cancelled by user"
        )
        
        await job_service.update_job_status(db, job_id, status_update)
        
        logger.info(f"Cancelled job: {job_id}")
        
        return {"message": f"Job {job_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}"
        )


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    db: Session = Depends(get_db),
    job_service: JobService = Depends(get_job_service)
):
    """
    Get processing logs for a job
    """
    try:
        job = await job_service.get_job(db, job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        # Get logs from job service
        logs = await job_service.get_job_logs(job_id)
        
        return {
            "job_id": job_id,
            "logs": logs,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting logs for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job logs: {str(e)}"
        )