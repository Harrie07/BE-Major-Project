from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape
import logging

from app.db.database import get_db
from app.models.models import AOI
from app.models.schemas import AOICreate, AOIResponse, PaginationParams

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=AOIResponse, status_code=status.HTTP_201_CREATED)
async def create_aoi(
    aoi_data: AOICreate,
    db: Session = Depends(get_db)
):
    """
    Create a new Area of Interest (AOI)
    
    - **name**: Optional name for the AOI
    - **description**: Optional description
    - **geometry**: GeoJSON MultiPolygon geometry
    """
    try:
        # Convert GeoJSON to Shapely geometry
        geom = shape(aoi_data.geometry)
        
        # Validate geometry
        if not geom.is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid geometry provided"
            )
        
        # Create AOI object
        db_aoi = AOI(
            name=aoi_data.name,
            description=aoi_data.description,
            geometry=from_shape(geom, srid=4326)
        )
        
        # Save to database
        db.add(db_aoi)
        db.commit()
        db.refresh(db_aoi)
        
        logger.info(f"Created AOI: {db_aoi.id}")
        
        # Convert back to response format
        return AOIResponse(
            id=db_aoi.id,
            name=db_aoi.name,
            description=db_aoi.description,
            geometry=aoi_data.geometry,
            created_at=db_aoi.created_at,
            updated_at=db_aoi.updated_at
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating AOI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create AOI: {str(e)}"
        )


@router.get("/", response_model=List[AOIResponse])
async def list_aois(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    List all Areas of Interest with pagination
    """
    try:
        # Query AOIs with pagination
        aois = db.query(AOI).offset(pagination.skip).limit(pagination.limit).all()
        
        # Convert to response format
        response_aois = []
        for aoi in aois:
            # Convert PostGIS geometry back to GeoJSON
            geom = to_shape(aoi.geometry)
            geojson = json.loads(json.dumps(geom.__geo_interface__))
            
            response_aois.append(AOIResponse(
                id=aoi.id,
                name=aoi.name,
                description=aoi.description,
                geometry=geojson,
                created_at=aoi.created_at,
                updated_at=aoi.updated_at
            ))
        
        return response_aois
        
    except Exception as e:
        logger.error(f"Error listing AOIs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve AOIs: {str(e)}"
        )


@router.get("/{aoi_id}", response_model=AOIResponse)
async def get_aoi(
    aoi_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific Area of Interest by ID
    """
    try:
        # Query AOI by ID
        aoi = db.query(AOI).filter(AOI.id == aoi_id).first()
        
        if not aoi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AOI with id {aoi_id} not found"
            )
        
        # Convert PostGIS geometry to GeoJSON
        geom = to_shape(aoi.geometry)
        geojson = json.loads(json.dumps(geom.__geo_interface__))
        
        return AOIResponse(
            id=aoi.id,
            name=aoi.name,
            description=aoi.description,
            geometry=geojson,
            created_at=aoi.created_at,
            updated_at=aoi.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AOI {aoi_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve AOI: {str(e)}"
        )


@router.delete("/{aoi_id}")
async def delete_aoi(
    aoi_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete an Area of Interest
    """
    try:
        # Check if AOI exists
        aoi = db.query(AOI).filter(AOI.id == aoi_id).first()
        
        if not aoi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AOI with id {aoi_id} not found"
            )
        
        # Check if AOI has associated jobs
        if aoi.jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete AOI with associated jobs"
            )
        
        # Delete AOI
        db.delete(aoi)
        db.commit()
        
        logger.info(f"Deleted AOI: {aoi_id}")
        
        return {"message": f"AOI {aoi_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting AOI {aoi_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete AOI: {str(e)}"
        )


@router.get("/{aoi_id}/bounds")
async def get_aoi_bounds(
    aoi_id: str,
    db: Session = Depends(get_db)
):
    """
    Get bounding box of an AOI
    """
    try:
        # Query AOI
        aoi = db.query(AOI).filter(AOI.id == aoi_id).first()
        
        if not aoi:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AOI with id {aoi_id} not found"
            )
        
        # Get bounds using PostGIS
        result = db.execute(f"""
            SELECT 
                ST_XMin(geometry) as min_lon,
                ST_YMin(geometry) as min_lat,
                ST_XMax(geometry) as max_lon,
                ST_YMax(geometry) as max_lat
            FROM aois WHERE id = '{aoi_id}'
        """).first()
        
        return {
            "aoi_id": aoi_id,
            "bounds": {
                "min_lon": result.min_lon,
                "min_lat": result.min_lat,
                "max_lon": result.max_lon,
                "max_lat": result.max_lat
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AOI bounds {aoi_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get AOI bounds: {str(e)}"
        )