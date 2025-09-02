from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import requests
import logging

from app.db.database import get_db
from app.models.models import ChangeDetectionJob
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info/{job_id}")
async def get_tile_info(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get tile information for a job's COG including bounds, statistics, etc.
    """
    try:
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        if not job.result_cog_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No COG result available for job {job_id}"
            )
        
        # Get info from Titiler
        titiler_info_url = f"{settings.TITILER_ENDPOINT}/cog/info"
        
        try:
            response = requests.get(
                titiler_info_url,
                params={"url": job.result_cog_url},
                timeout=30
            )
            response.raise_for_status()
            
            tile_info = response.json()
            
            # Add our job metadata
            tile_info["job_id"] = job_id
            tile_info["job_status"] = job.status
            tile_info["processing_date"] = job.completed_at.isoformat() if job.completed_at else None
            
            return tile_info
            
        except requests.RequestException as e:
            logger.error(f"Titiler request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to get tile information from Titiler service"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tile info for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tile information: {str(e)}"
        )


@router.get("/preview/{job_id}")
async def get_tile_preview(
    job_id: str,
    width: int = 512,
    height: int = 512,
    db: Session = Depends(get_db)
):
    """
    Get a preview image of the change detection result
    """
    try:
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        if not job.result_cog_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No COG result available for job {job_id}"
            )
        
        # Get preview from Titiler
        titiler_preview_url = f"{settings.TITILER_ENDPOINT}/cog/preview.png"
        
        try:
            response = requests.get(
                titiler_preview_url,
                params={
                    "url": job.result_cog_url,
                    "width": width,
                    "height": height,
                    "colormap_name": "viridis"  # Good colormap for change detection
                },
                timeout=60
            )
            response.raise_for_status()
            
            # Return the image directly
            return response.content
            
        except requests.RequestException as e:
            logger.error(f"Titiler preview request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to generate preview from Titiler service"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tile preview for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate preview: {str(e)}"
        )


@router.get("/wmts/{job_id}")
async def get_wmts_capabilities(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get WMTS capabilities for a job's COG
    """
    try:
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        if not job.result_cog_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No COG result available for job {job_id}"
            )
        
        # Generate WMTS URLs
        base_url = settings.TITILER_ENDPOINT
        
        wmts_info = {
            "job_id": job_id,
            "cog_url": job.result_cog_url,
            "wmts": {
                "tile_url": f"{base_url}/cog/tiles/{{z}}/{{x}}/{{y}}.png?url={job.result_cog_url}",
                "tile_json_url": f"{base_url}/cog/tilejson.json?url={job.result_cog_url}",
                "wmts_xml_url": f"{base_url}/cog/WMTSCapabilities.xml?url={job.result_cog_url}",
                "info_url": f"{base_url}/cog/info?url={job.result_cog_url}"
            },
            "tile_matrix_sets": ["WebMercatorQuad"],
            "supported_formats": ["png", "jpg", "webp"],
            "colormap_options": ["viridis", "plasma", "hot", "cool", "gray"]
        }
        
        return wmts_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting WMTS capabilities for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get WMTS capabilities: {str(e)}"
        )


@router.get("/bounds/{job_id}")
async def get_tile_bounds(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the geographic bounds of a job's result tiles
    """
    try:
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        if not job.result_cog_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No COG result available for job {job_id}"
            )
        
        # Get bounds from Titiler
        titiler_info_url = f"{settings.TITILER_ENDPOINT}/cog/bounds"
        
        try:
            response = requests.get(
                titiler_info_url,
                params={"url": job.result_cog_url},
                timeout=30
            )
            response.raise_for_status()
            
            bounds_data = response.json()
            
            return {
                "job_id": job_id,
                "bounds": bounds_data.get("bounds"),
                "crs": bounds_data.get("crs", "EPSG:4326")
            }
            
        except requests.RequestException as e:
            logger.error(f"Titiler bounds request failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to get bounds from Titiler service"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tile bounds for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tile bounds: {str(e)}"
        )