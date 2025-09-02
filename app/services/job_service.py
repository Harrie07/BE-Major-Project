# app/services/job_service.py
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
import json

# --- FIX 1: Import the correct model - Job instead of ChangeDetectionJob ---
# Also import JobStatus enum if needed for internal logic (though using .value is preferred)
from app.models.models import Job, AOI, Detection, JobStatusEnum 
from app.models.schemas import JobStatus, JobCreate, JobStatusUpdate

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing change detection jobs"""
    
    async def create_job(self, db: Session, job_data: JobCreate) -> Job:
        """Create a new change detection job"""
        try:
            # Validate AOI exists (if you have AOI model and logic)
            # aoi = db.query(AOI).filter(AOI.id == job_data.aoi_id).first()
            # if not aoi:
            #     raise ValueError(f"AOI with id {job_data.aoi_id} not found")
            
            # --- FIX 2: Create job record using Job model and set the name field ---
            # Construct processing parameters dictionary
            processing_params = {
                "cloud_cover_threshold": job_data.cloud_cover_threshold,
                "satellite_type": job_data.satellite_type,
                # Add other parameters from job_data as needed
            }
            
            # Create the Job instance using the correct model
            db_job = Job(
                # --- KEY FIX: Set the 'name' field ---
                name=job_data.name, # Use the name provided in the JobCreate schema
                # --- --- 
                status=JobStatus.PENDING, # Use the Enum, SQLAlchemy should handle conversion if column is String/Enum
                date_from=job_data.date_from,
                date_to=job_data.date_to,
                cloud_cover_threshold=job_data.cloud_cover_threshold,
                satellite_type=job_data.satellite_type,
                processing_params=processing_params # Store parameters as JSON
                # result_url, error_message, etc. will be set later
            )
            
            # Save to database
            db.add(db_job)
            db.commit()
            db.refresh(db_job)
            
            logger.info(f"Created job: {db_job.id} with name: '{db_job.name}'") # Log the name
            return db_job
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating job: {e}")
            raise # Re-raise the exception for the caller (endpoint) to handle
    
    async def get_job(self, db: Session, job_id: int) -> Optional[Job]: # --- FIX: job_id should be int (assuming your model uses Integer PK) ---
        """Get job by ID"""
        try:
            # Query the database for the job with the given ID
            job = db.query(Job).filter(Job.id == job_id).first()
            return job
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            return None # Return None on error, let caller decide how to handle
    
    async def list_jobs(
        self,
        db: Session,
        aoi_id: Optional[str] = None,
        status_filter: Optional[JobStatus] = None,
        skip: int = 0,
        limit: int = 100 # Increased default limit
    ) -> List[Job]:
        """List jobs with optional filtering"""
        try:
            # Start building the query
            query = db.query(Job)
            
            # Apply optional filters
            if aoi_id:
                # Assuming your Job model has an aoi_id column
                query = query.filter(Job.aoi_id == aoi_id)
            
            if status_filter:
                # Filter by job status enum
                query = query.filter(Job.status == status_filter)
            
            # Order by creation date descending, apply pagination
            jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
            return jobs
            
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return [] # Return empty list on error

    async def update_job_status(
        self,
        db: Session,
        job_id: int,
        status_update: JobStatusUpdate
    ) -> Optional[Job]:
        """Update job status and metadata"""
        try:
            # Get the job from the database
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return None # Indicate job not found
            
            # --- Update fields based on status_update ---
            # Update status
            if status_update.status is not None:
                 # Ensure status is an enum member before assigning
                if isinstance(status_update.status, JobStatus):
                    job.status = status_update.status
                else:
                    # If it's a string, try to convert it to the enum
                    try:
                        job.status = JobStatus(status_update.status)
                    except ValueError:
                        logger.warning(f"Invalid status value '{status_update.status}' provided for job {job_id}")
                        # Optionally raise an error or ignore
                        
            # Update progress
            if status_update.progress is not None:
                job.progress = status_update.progress
            
            # Update error message
            if status_update.error_message is not None:
                job.error_message = status_update.error_message
            
            # Update result URLs
            if status_update.result_cog_url is not None:
                job.result_cog_url = status_update.result_cog_url
            
            if status_update.vector_results_url is not None:
                job.vector_results_url = status_update.vector_results_url

            # Update timestamps based on status transitions
            current_time = datetime.utcnow()
            if status_update.status == JobStatus.PROCESSING and job.started_at is None:
                job.started_at = current_time
            elif status_update.status in [JobStatus.COMPLETED, JobStatus.FAILED] and job.completed_at is None:
                job.completed_at = current_time
                # Optionally update progress to 100% on completion
                if status_update.status == JobStatus.COMPLETED:
                    job.progress = 100.0

            # Update the updated_at timestamp
            job.updated_at = current_time
            
            # Commit changes to the database
            db.commit()
            db.refresh(job) # Refresh the job instance with updated data from DB
            
            logger.info(f"Updated job {job_id} status to {status_update.status}")
            return job
            
        except Exception as e:
            db.rollback() # Rollback changes on error
            logger.error(f"Error updating job {job_id}: {e}")
            return None # Return None to indicate failure

    # --- Methods adapted from the "fixed" version you provided (simplified for core logic) ---
    
    async def get_job_details(self, db: Session, job_id: int) -> Optional[Dict[str, Any]]:
        """Get complete job details (simplified version)"""
        try:
            job = await self.get_job(db, job_id)
            if not job:
                return None
            
            # Convert job object to a dictionary for response
            # In a full implementation, you'd likely use Pydantic models for serialization
            job_details = {
                "id": job.id,
                "name": job.name,
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status), # Handle enum/string
                "date_from": job.date_from.isoformat() if job.date_from else None,
                "date_to": job.date_to.isoformat() if job.date_to else None,
                "satellite_type": job.satellite_type,
                "cloud_cover_threshold": job.cloud_cover_threshold,
                "progress": job.progress,
                "processing_params": job.processing_params,
                "result_cog_url": job.result_cog_url,
                "vector_results_url": job.vector_results_url,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "error_message": job.error_message,
                # Add other fields as needed
            }
            
            return job_details
            
        except Exception as e:
            logger.error(f"Error getting job details {job_id}: {e}")
            return None

    async def save_detection_results(
        self,
        db: Session,
        job_id: int,
        detections_data: list, # List of detection dictionaries
        result_cog_url: str,
        vector_results_url: str
    ) -> bool:
        """Save detection results to database (stub implementation)"""
        try:
            # Verify job exists
            job = await self.get_job(db, job_id)
            if not job:
                logger.error(f"Job {job_id} not found for saving results")
                return False

            # --- Placeholder Logic ---
            # In a real implementation, you would:
            # 1. Clear existing detections for this job (if replacing)
            #    db.query(Detection).filter(Detection.job_id == job_id).delete()
            # 2. Iterate through detections_data
            # 3. For each detection, create a Detection model instance
            #    - Convert geometry (e.g., using shapely and geoalchemy2)
            #    - Set fields (job_id, geometry, confidence_score, etc.)
            #    - db.add(detection_instance)
            # 4. Update the Job record with result URLs and status
            #    job.result_cog_url = result_cog_url
            #    job.vector_results_url = vector_results_url
            #    job.status = JobStatus.COMPLETED
            #    job.completed_at = datetime.utcnow()
            #    job.progress = 100.0
            # 5. db.commit()

            logger.info(f"Stub: Would save {len(detections_data)} detections for job {job_id}")
            logger.info(f"Stub: Result COG URL: {result_cog_url}")
            logger.info(f"Stub: Vector Results URL: {vector_results_url}")

            # Simulate successful save for now
            # Update job status to completed
            from app.models.schemas import JobStatusUpdate as StatusUpdateSchema # Avoid naming conflict
            status_update = StatusUpdateSchema(
                status=JobStatus.COMPLETED,
                progress=100.0,
                result_cog_url=result_cog_url,
                vector_results_url=vector_results_url
            )
            updated_job = await self.update_job_status(db, job_id, status_update)
            
            if updated_job:
                logger.info(f"Saved detection results for job {job_id}")
                return True
            else:
                logger.error(f"Failed to update job {job_id} after saving results")
                return False
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving detection results for job {job_id}: {e}")
            return False

    async def get_job_logs(self, job_id: int) -> List[str]:
        """Get processing logs for a job (stub implementation)"""
        try:
            # In a real implementation, fetch logs from a log store (e.g., file, database, Redis)
            return [
                f"[INFO] Job {job_id} created.",
                f"[INFO] Job {job_id} queued for processing.",
                # Add more dynamic log entries based on actual job history
            ]
        except Exception as e:
            logger.error(f"Error getting job logs {job_id}: {e}")
            return []

    # --- Synchronous methods for worker (adapted from "fixed" version) ---
    # These are typically used by the RQ worker which runs synchronously

    def get_pending_jobs(self, db: Session, limit: int = 10) -> List[int]:
        """Get pending jobs for processing (synchronous for worker)"""
        try:
            # Query for jobs with PENDING status, ordered by creation time
            jobs = db.query(Job).filter(
                Job.status == JobStatus.PENDING
            ).order_by(Job.created_at).limit(limit).all()
            
            # Return list of job IDs
            return [job.id for job in jobs]
            
        except Exception as e:
            logger.error(f"Error getting pending jobs: {e}")
            return []

    def mark_job_failed(self, db: Session, job_id: int, error_message: str) -> bool:
        """Mark job as failed with error message (synchronous for worker)"""
        try:
            # Get the job
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.warning(f"Attempted to mark non-existent job {job_id} as failed.")
                return False # Job doesn't exist
            
            # Update job fields
            job.status = JobStatus.FAILED
            job.error_message = error_message
            job.completed_at = datetime.utcnow()
            # Optionally reset progress
            job.progress = 0.0 
            
            # Commit the changes
            db.commit()
            logger.info(f"Marked job {job_id} as failed.")
            return True # Success
            
        except Exception as e:
            db.rollback() # Rollback on error
            logger.error(f"Error marking job {job_id} as failed: {e}")
            return False # Failure
