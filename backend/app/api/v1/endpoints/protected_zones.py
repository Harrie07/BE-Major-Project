from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape
import logging

from app.db.database import get_db
from app.models.models import ProtectedZone
from app.models.schemas import ProtectedZoneCreate, ProtectedZoneResponse, PaginationParams

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ProtectedZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_protected_zone(
    zone_data: ProtectedZoneCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new protected zone (mangrove, CRZ, floodplain, etc.)
    """
    try:
        # Convert GeoJSON to Shapely geometry
        geom = shape(zone_data.geometry)
        
        # Validate geometry
        if not geom.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid geometry provided"
            )
        
        # Create protected zone object
        db_zone = ProtectedZone(
            name=zone_data.name,
            zone_type=zone_data.zone_type,
            description=zone_data.description,
            geometry=from_shape(geom, srid=4326),
            source=zone_data.source
        )
        
        # Save to database
        db.add(db_zone)
        db.commit()
        db.refresh(db_zone)
        
        logger.info(f"Created protected zone: {db_zone.id}")
        
        return ProtectedZoneResponse(
            id=db_zone.id,
            name=db_zone.name,
            zone_type=db_zone.zone_type,
            description=db_zone.description,
            geometry=zone_data.geometry,
            source=db_zone.source,
            last_updated=db_zone.last_updated,
            created_at=db_zone.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating protected zone: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create protected zone: {str(e)}"
        )


@router.get("/", response_model=List[ProtectedZoneResponse])
async def list_protected_zones(
    zone_type: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    List protected zones with optional filtering by zone type
    """
    try:
        # Build query
        query = db.query(ProtectedZone)
        
        if zone_type:
            query = query.filter(ProtectedZone.zone_type == zone_type)
        
        # Apply pagination
        zones = query.order_by(ProtectedZone.created_at.desc()).offset(pagination.skip).limit(pagination.limit).all()
        
        # Convert to response format
        response_zones = []
        for zone in zones:
            # Convert PostGIS geometry to GeoJSON
            geom = to_shape(zone.geometry)
            geojson = json.loads(json.dumps(geom.__geo_interface__))
            
            response_zones.append(ProtectedZoneResponse(
                id=zone.id,
                name=zone.name,
                zone_type=zone.zone_type,
                description=zone.description,
                geometry=geojson,
                source=zone.source,
                last_updated=zone.last_updated,
                created_at=zone.created_at
            ))
        
        return response_zones
        
    except Exception as e:
        logger.error(f"Error listing protected zones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve protected zones: {str(e)}"
        )


@router.get("/types")
async def get_zone_types(db: Session = Depends(get_db)):
    """
    Get all available zone types
    """
    try:
        result = db.execute(
            "SELECT DISTINCT zone_type FROM protected_zones ORDER BY zone_type"
        ).fetchall()
        
        zone_types = [row[0] for row in result]
        
        return {
            "zone_types": zone_types,
            "count": len(zone_types)
        }
        
    except Exception as e:
        logger.error(f"Error getting zone types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve zone types: {str(e)}"
        )


@router.get("/intersect/{job_id}")
async def check_intersections_with_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Check which detections from a job intersect with protected zones
    """
    try:
        # Verify job exists
        from app.models.models import ChangeDetectionJob
        job = db.query(ChangeDetectionJob).filter(ChangeDetectionJob.id == job_id).first()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with id {job_id} not found"
            )
        
        # SQL query to find intersections
        intersection_query = """
        SELECT 
            d.id as detection_id,
            d.confidence_score,
            pz.id as zone_id,
            pz.name as zone_name,
            pz.zone_type,
            ST_Area(ST_Intersection(d.geometry, pz.geometry)) as intersection_area
        FROM detections d
        JOIN protected_zones pz ON ST_Intersects(d.geometry, pz.geometry)
        WHERE d.job_id = :job_id
        ORDER BY d.confidence_score DESC
        """
        
        results = db.execute(intersection_query, {"job_id": job_id}).fetchall()
        
        # Group by detection
        intersections = {}
        for row in results:
            detection_id = row.detection_id
            if detection_id not in intersections:
                intersections[detection_id] = {
                    "detection_id": detection_id,
                    "confidence_score": row.confidence_score,
                    "intersecting_zones": []
                }
            
            intersections[detection_id]["intersecting_zones"].append({
                "zone_id": row.zone_id,
                "zone_name": row.zone_name,
                "zone_type": row.zone_type,
                "intersection_area": row.intersection_area
            })
        
        return {
            "job_id": job_id,
            "intersections": list(intersections.values()),
            "total_intersections": len(intersections)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking intersections for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check intersections: {str(e)}"
        )


@router.delete("/{zone_id}")
async def delete_protected_zone(
    zone_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a protected zone
    """
    try:
        zone = db.query(ProtectedZone).filter(ProtectedZone.id == zone_id).first()
        
        if not zone:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Protected zone with id {zone_id} not found"
            )
        
        # Delete zone
        db.delete(zone)
        db.commit()
        
        logger.info(f"Deleted protected zone: {zone_id}")
        
        return {"message": f"Protected zone {zone_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting protected zone {zone_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete protected zone: {str(e)}"
        )