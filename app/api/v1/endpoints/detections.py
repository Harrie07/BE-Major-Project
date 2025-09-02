from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from geoalchemy2.shape import to_shape
import logging

from app.db.database import get_db
from app.models.models import Detection, ChangeDetectionJob
from app.models.schemas import (
    DetectionResponse, DetectionSummary, PaginationParams, TileResponse
)
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/by_job/{job_id}", response_model=List[DetectionSummary])
async def get_detections_by_job(
    job_id: str,
    min_confidence: Optional[float] = 0.5,
    flagged_only: Optional[bool] = False,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    Get all detections for a specific job
    
    - **job_id**: Change detection job ID
    - **min_confidence**: Minimum confidence score filter
    - **flagged_only**: Show only flagged detections
    """
    try:
        # Verify job exists
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        # Build query with filters
        query = db.query(Detection).filter(Detection.job_id == job_id)
        
        if min_confidence:
            query = query.filter(Detection.confidence_score >= min_confidence)
        
        if flagged_only:
            query = query.filter(Detection.flagged == True)
        
        # Apply pagination and ordering
        detections = query.order_by(Detection.confidence_score.desc()).offset(pagination.skip).limit(pagination.limit).all()
        
        # Convert to summary format
        response_detections = []
        for detection in detections:
            response_detections.append(DetectionSummary(
                id=detection.id,
                confidence_score=detection.confidence_score,
                area_sqm=detection.area_sqm,
                change_type=detection.change_type,
                flagged=detection.flagged,
                flag_reasons=detection.flag_reasons
            ))
        
        return response_detections
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detections for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detections: {str(e)}"
        )


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection(
    detection_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific detection
    """
    try:
        detection = db.query(Detection).filter(Detection.id == detection_id).first()
        
        if not detection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detection with id {detection_id} not found"
            )
        
        # Convert PostGIS geometry to GeoJSON
        geom = to_shape(detection.geometry)
        geojson = json.loads(json.dumps(geom.__geo_interface__))
        
        return DetectionResponse(
            id=detection.id,
            job_id=detection.job_id,
            geometry=geojson,
            confidence_score=detection.confidence_score,
            area_sqm=detection.area_sqm,
            change_type=detection.change_type,
            flagged=detection.flagged,
            flag_reasons=detection.flag_reasons,
            created_at=detection.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection {detection_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detection: {str(e)}"
        )


@router.get("/by_job/{job_id}/geojson")
async def get_detections_geojson(
    job_id: str,
    min_confidence: Optional[float] = 0.5,
    flagged_only: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """
    Get all detections for a job as a GeoJSON FeatureCollection
    
    This is useful for mapping libraries that expect GeoJSON format.
    """
    try:
        # Verify job exists
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        # Build query with filters
        query = db.query(Detection).filter(Detection.job_id == job_id)
        
        if min_confidence:
            query = query.filter(Detection.confidence_score >= min_confidence)
        
        if flagged_only:
            query = query.filter(Detection.flagged == True)
        
        detections = query.all()
        
        # Convert to GeoJSON FeatureCollection
        features = []
        for detection in detections:
            # Convert PostGIS geometry to GeoJSON
            geom = to_shape(detection.geometry)
            geojson_geom = json.loads(json.dumps(geom.__geo_interface__))
            
            feature = {
                "type": "Feature",
                "geometry": geojson_geom,
                "properties": {
                    "id": detection.id,
                    "job_id": detection.job_id,
                    "confidence_score": detection.confidence_score,
                    "area_sqm": detection.area_sqm,
                    "change_type": detection.change_type,
                    "flagged": detection.flagged,
                    "flag_reasons": detection.flag_reasons,
                    "created_at": detection.created_at.isoformat()
                }
            }
            features.append(feature)
        
        geojson_response = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "job_id": job_id,
                "total_features": len(features),
                "filters": {
                    "min_confidence": min_confidence,
                    "flagged_only": flagged_only
                }
            }
        }
        
        return geojson_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detections GeoJSON for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detections GeoJSON: {str(e)}"
        )


@router.get("/tiles/cog_url/{job_id}")
async def get_detection_cog_url(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the COG URL for a job's change detection heatmap
    
    This URL can be used with Titiler to generate map tiles.
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
        
        # Generate Titiler tile URL
        titiler_base = settings.TITILER_ENDPOINT
        tile_url = f"{titiler_base}/cog/tiles/{{z}}/{{x}}/{{y}}?url={job.result_cog_url}"
        
        return {
            "job_id": job_id,
            "cog_url": job.result_cog_url,
            "tile_url": tile_url,
            "titiler_info_url": f"{titiler_base}/cog/info?url={job.result_cog_url}",
            "titiler_preview_url": f"{titiler_base}/cog/preview?url={job.result_cog_url}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting COG URL for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get COG URL: {str(e)}"
        )


@router.get("/stats/{job_id}")
async def get_detection_stats(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get statistics about detections for a job
    """
    try:
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        # Get detection statistics using SQL
        stats_query = """
        SELECT 
            COUNT(*) as total_detections,
            COUNT(*) FILTER (WHERE flagged = true) as flagged_count,
            AVG(confidence_score) as avg_confidence,
            MAX(confidence_score) as max_confidence,
            MIN(confidence_score) as min_confidence,
            SUM(area_sqm) as total_area_sqm,
            COUNT(*) FILTER (WHERE confidence_score >= 0.8) as high_confidence_count,
            COUNT(*) FILTER (WHERE confidence_score >= 0.5 AND confidence_score < 0.8) as medium_confidence_count,
            COUNT(*) FILTER (WHERE confidence_score < 0.5) as low_confidence_count
        FROM detections 
        WHERE job_id = :job_id
        """
        
        result = db.execute(stats_query, {"job_id": job_id}).first()
        
        return {
            "job_id": job_id,
            "total_detections": result.total_detections or 0,
            "flagged_count": result.flagged_count or 0,
            "avg_confidence": round(result.avg_confidence or 0, 3),
            "max_confidence": result.max_confidence or 0,
            "min_confidence": result.min_confidence or 0,
            "total_area_sqm": result.total_area_sqm or 0,
            "confidence_distribution": {
                "high": result.high_confidence_count or 0,  # >= 0.8
                "medium": result.medium_confidence_count or 0,  # 0.5-0.8
                "low": result.low_confidence_count or 0  # < 0.5
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection stats for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detection statistics: {str(e)}"
        )