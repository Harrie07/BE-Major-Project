# app/models/schemas.py
"""
Pydantic schemas for Mumbai Geo-AI Project.
Defines data validation and serialization models using Pydantic v2.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# --- ENUMERATIONS ---

class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SatelliteType(str, Enum):
    """Satellite type enumeration"""
    SENTINEL1 = "sentinel-1"
    SENTINEL2 = "sentinel-2"


class ChangeType(str, Enum):
    """Change detection type enumeration"""
    NEW_CONSTRUCTION = "new_construction"
    DEMOLITION = "demolition"
    MODIFICATION = "modification"
    UNKNOWN = "unknown"


# --- AOI SCHEMAS ---

class AOICreate(BaseModel):
    """Schema for creating AOI"""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    geometry: Dict[str, Any]  # GeoJSON MultiPolygon

    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate GeoJSON geometry"""
        if not isinstance(v, dict):
            raise ValueError("Geometry must be a dictionary")
        if v.get("type") != "MultiPolygon":
            raise ValueError("Geometry must be of type MultiPolygon")
        # Add more detailed GeoJSON validation here if needed
        return v

    model_config = ConfigDict(from_attributes=True)


class AOIResponse(BaseModel):
    """Schema for AOI response"""
    id: int # Assuming integer ID
    name: Optional[str]
    description: Optional[str]
    geometry: Dict[str, Any] # GeoJSON geometry
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# --- JOB SCHEMAS ---
# Updated to match your Job model

class JobCreate(BaseModel):
    """Schema for creating change detection job"""
    # --- FIX: Add name field to match Job model ---
    name: Optional[str] = Field(None, max_length=255, description="Name of the job")
    # --- ---
    aoi_id: int # Assuming integer AOI ID
    date_from: datetime = Field(..., description="Start date for analysis")
    date_to: datetime = Field(..., description="End date for analysis")
    cloud_cover_threshold: float = Field(20.0, ge=0, le=100, description="Maximum cloud cover percentage")
    satellite_type: Optional[SatelliteType] = Field(None, description="Satellite type for analysis")

    @field_validator('date_to')
    @classmethod
    def validate_dates(cls, v: datetime, values: Any) -> datetime:
        """Validate that date_to is after date_from"""
        # Pydantic v2 validator signature is slightly different
        # values is now a ValidationInfo object, use values.data to access other fields
        if 'date_from' in values and v <= values['date_from']:
            raise ValueError("date_to must be after date_from")
        return v

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """Schema for job response - Updated to match Job model"""
    # --- FIXES based on your Job model ---
    id: int # Changed from str to int to match Job model
    name: Optional[str] # Add name field
    status: str # Changed to str to match Job model (enum value as string)
    # Renamed fields to match your Job model attributes
    date_from: datetime
    date_to: datetime
    cloud_cover_threshold: float
    satellite_type: Optional[str] # Use string representation
    progress: Optional[float] # Add progress field
    processing_params: Optional[Dict[str, Any]] # Add processing_params field
    result_cog_url: Optional[str] # Add result_cog_url field
    vector_results_url: Optional[str] # Add vector_results_url field
    model_version: Optional[str] # Add model_version field
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime] # Add started_at field
    completed_at: Optional[datetime] # Add completed_at field
    updated_at: Optional[datetime] # Add updated_at field
    # --- ---

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdate(BaseModel):
    """Schema for updating job status"""
    status: JobStatus
    progress: Optional[float] = Field(None, ge=0, le=100)
    error_message: Optional[str] = Field(None, max_length=500)
    result_cog_url: Optional[str] = Field(None, max_length=500)
    vector_results_url: Optional[str] = Field(None, max_length=500)
    model_version: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(from_attributes=True)


# --- DETECTION SCHEMAS ---

class DetectionCreate(BaseModel):
    """Schema for creating detection"""
    job_id: int # Assuming integer Job ID
    geometry: Dict[str, Any] # GeoJSON Polygon or MultiPolygon
    confidence_score: float = Field(..., ge=0, le=1)
    area_sqm: Optional[float] = Field(None, gt=0)
    change_type: Optional[ChangeType] = Field(None, description="Type of change detected")
    flagged: bool = Field(False, description="Whether the detection is flagged for review")
    flag_reasons: Optional[List[str]] = Field(None, description="Reasons for flagging")

    model_config = ConfigDict(from_attributes=True)


class DetectionResponse(BaseModel):
    """Schema for detection response"""
    id: int # Assuming integer ID
    job_id: int
    geometry: Dict[str, Any] # GeoJSON geometry
    confidence_score: float
    area_sqm: Optional[float]
    change_type: Optional[str] # Use string representation
    flagged: bool
    flag_reasons: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DetectionSummary(BaseModel):
    """Schema for detection summary"""
    id: int
    confidence_score: float
    area_sqm: Optional[float]
    change_type: Optional[str] # Use string representation
    flagged: bool
    flag_reasons: Optional[List[str]]

    model_config = ConfigDict(from_attributes=True)


# --- PROTECTED ZONE SCHEMAS ---

class ProtectedZoneCreate(BaseModel):
    """Schema for creating protected zone"""
    name: str = Field(..., max_length=255)
    zone_type: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    geometry: Dict[str, Any] # GeoJSON MultiPolygon
    source: Optional[str] = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class ProtectedZoneResponse(BaseModel):
    """Schema for protected zone response"""
    id: int # Assuming integer ID
    name: str
    zone_type: str
    description: Optional[str]
    geometry: Dict[str, Any] # GeoJSON geometry
    source: Optional[str]
    last_updated: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- ALERT SCHEMAS ---

class AlertCreate(BaseModel):
    """Schema for creating alert"""
    detection_id: int # Assuming integer Detection ID
    alert_type: str = Field(..., max_length=50) # sms, email
    recipient: str = Field(..., max_length=255)
    message: str = Field(..., max_length=1000)


class AlertResponse(BaseModel):
    """Schema for alert response"""
    id: int # Assuming integer ID
    detection_id: int
    alert_type: str
    recipient: str
    message: str
    sent: bool
    sent_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- UTILITY SCHEMAS ---

class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of items to return")

    model_config = ConfigDict(from_attributes=True)


class BoundingBox(BaseModel):
    """Schema for bounding box"""
    min_lon: float = Field(..., ge=-180, le=180)
    min_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)

    @field_validator('max_lon')
    @classmethod
    def validate_longitude(cls, v: float, values: Any) -> float:
        if 'min_lon' in values and v <= values['min_lon']:
            raise ValueError("max_lon must be greater than min_lon")
        return v

    @field_validator('max_lat')
    @classmethod
    def validate_latitude(cls, v: float, values: Any) -> float:
        if 'min_lat' in values and v <= values['min_lat']:
            raise ValueError("max_lat must be greater than min_lat")
        return v

    model_config = ConfigDict(from_attributes=True)


class TileResponse(BaseModel):
    """Schema for tile response"""
    cog_url: str
    tile_url: str
    bounds: BoundingBox
    metadata: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


# --- ERROR SCHEMAS ---

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
