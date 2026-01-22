"""
Worker tasks for processing change detection jobs
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

from app.services.job_service import JobService
from app.services.stac_service import STACService
from app.services.storage_service import StorageService
from app.services.ml_service import MLService
from app.services.validation_service import ValidationService
from app.models.schemas import JobStatus

# Configure logging for workers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
job_service = JobService()
stac_service = STACService()
storage_service = StorageService()
ml_service = MLService()
validation_service = ValidationService()


def process_change_detection_job(job_id: str) -> Dict[str, Any]:
    """
    Main worker function to process a change detection job
    
    This function handles the complete workflow:
    1. Fetch satellite imagery
    2. Preprocess and clip to AOI
    3. Run ML change detection
    4. Validate against protected zones
    5. Save results
    """
    
    logger.info(f"Starting processing for job {job_id}")
    
    try:
        # Update job status to processing
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=0.0)
        
        # Get job details
        job_details = job_service.get_job_details(job_id)
        if not job_details:
            raise Exception(f"Job {job_id} not found")
        
        # Extract parameters
        aoi_geometry = job_details["aoi_geometry"]
        date_from = job_details["date_from"]
        date_to = job_details["date_to"]
        cloud_cover_max = job_details["cloud_cover_threshold"]
        
        # Step 1: Get AOI bounds
        logger.info("Step 1: Calculating AOI bounds...")
        bbox = _get_bbox_from_geometry(aoi_geometry)
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=10.0)
        
        # Step 2: Search for imagery
        logger.info("Step 2: Searching for satellite imagery...")
        before_image, after_image, satellite_type = stac_service.get_best_imagery_pair(
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            cloud_cover_max=cloud_cover_max
        )
        
        if not before_image or not after_image:
            raise Exception("No suitable imagery found for the specified dates and area")
        
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=20.0)
        
        # Step 3: Load and preprocess imagery
        logger.info("Step 3: Loading and preprocessing imagery...")
        
        # Load before image
        before_data = stac_service.load_and_clip_image(before_image, bbox)
        logger.info(f"Loaded before image: {before_image['id']}")
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=35.0)
        
        # Load after image
        after_data = stac_service.load_and_clip_image(after_image, bbox)
        logger.info(f"Loaded after image: {after_image['id']}")
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=50.0)
        
        # Step 4: Run change detection ML model
        logger.info("Step 4: Running change detection model...")
        
        change_results = ml_service.run_change_detection(
            before_data=before_data,
            after_data=after_data,
            aoi_geometry=aoi_geometry
        )
        
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=75.0)
        
        # Step 5: Validate detections against protected zones
        logger.info("Step 5: Validating against protected zones...")
        
        validated_detections = validation_service.validate_detections(
            detections=change_results["detections"],
            aoi_geometry=aoi_geometry
        )
        
        job_service.update_job_status(job_id, JobStatus.PROCESSING, progress=85.0)
        
        # Step 6: Save results to storage
        logger.info("Step 6: Saving results...")
        
        # Save change heatmap as COG
        cog_filename = f"change_detection_{job_id}.tif"
        cog_url = storage_service.save_cog(
            data=change_results["change_map"],
            filename=cog_filename
        )
        
        # Save detections as GeoJSON
        vector_filename = f"detections_{job_id}.geojson"
        vector_url = storage_service.save_geojson(
            detections=validated_detections,
            filename=vector_filename
        )
        
        # Step 7: Save to database
        logger.info("Step 7: Saving to database...")
        
        success = job_service.save_detection_results(
            job_id=job_id,
            detections_data=validated_detections,
            result_cog_url=cog_url,
            vector_results_url=vector_url
        )
        
        if not success:
            raise Exception("Failed to save results to database")
        
        # Update job as completed
        job_service.update_job_status(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress=100.0,
            model_version=ml_service.get_model_version()
        )
        
        logger.info(f"Successfully completed job {job_id}")
        
        return {
            "job_id": job_id,
            "status": "completed",
            "satellite_type": satellite_type,
            "before_image": before_image["id"],
            "after_image": after_image["id"],
            "detections_count": len(validated_detections),
            "flagged_count": sum(1 for d in validated_detections if d.get("flagged", False)),
            "cog_url": cog_url,
            "vector_url": vector_url
        }
        
    except Exception as e:
        error_msg = f"Job processing failed: {str(e)}"
        logger.error(f"Error in job {job_id}: {error_msg}")
        
        # Mark job as failed
        job_service.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message=error_msg
        )
        
        raise e


def _get_bbox_from_geometry(geometry: Dict[str, Any]) -> List[float]:
    """Extract bounding box from GeoJSON geometry"""
    try:
        from shapely.geometry import shape
        
        geom = shape(geometry)
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        
        return [bounds[0], bounds[1], bounds[2], bounds[3]]  # [min_lon, min_lat, max_lon, max_lat]
        
    except Exception as e:
        logger.error(f"Error extracting bbox from geometry: {e}")
        raise


def cleanup_old_jobs() -> Dict[str, Any]:
    """
    Cleanup task to remove old job data and temporary files
    """
    try:
        from datetime import datetime, timedelta
        from app.db.database import SessionLocal
        from app.models.models import ChangeDetectionJob
        
        db = SessionLocal()
        
        # Find jobs older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_jobs = db.query(ChangeDetectionJob).filter(
            ChangeDetectionJob.created_at < cutoff_date,
            ChangeDetectionJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED])
        ).all()
        
        cleaned_count = 0
        for job in old_jobs:
            try:
                # Remove files from storage
                if job.result_cog_url:
                    storage_service.delete_file_from_url(job.result_cog_url)
                if job.vector_results_url:
                    storage_service.delete_file_from_url(job.vector_results_url)
                
                # Remove job record (cascades to detections)
                db.delete(job)
                cleaned_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to cleanup job {job.id}: {e}")
                continue
        
        db.commit()
        db.close()
        
        logger.info(f"Cleaned up {cleaned_count} old jobs")
        
        return {
            "cleaned_jobs": cleaned_count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        raise


def test_worker_connection() -> Dict[str, Any]:
    """
    Test task to verify worker is functioning
    """
    import time
    
    logger.info("Test worker task started")
    time.sleep(2)  # Simulate some work
    
    return {
        "message": "Worker is functioning correctly",
        "timestamp": datetime.utcnow().isoformat(),
        "worker_id": os.getpid()
    }