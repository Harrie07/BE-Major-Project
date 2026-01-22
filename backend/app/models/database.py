"""
SQLAlchemy models for Mumbai Geo-AI Change Detection System

This module defines all database models including spatial tables for:
- Users and authentication
- Areas of Interest (AOI) with geometry
- Change detection jobs and results
- Protected zones and violations
- Satellite imagery tracking
- Alert and logging systems
"""

from datetime import datetime, date
from typing import Optional, List
import uuid
import enum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, Date, DateTime, 
    JSON, ForeignKey, Enum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import shape


# Database base class
Base = declarative_base()


# Enum definitions
class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING" 
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DetectionType(str, enum.Enum):
    NEW_CONSTRUCTION = "NEW_CONSTRUCTION"
    DEMOLISHED = "DEMOLISHED"
    MODIFIED = "MODIFIED"
    UNKNOWN = "UNKNOWN"


class ZoneType(str, enum.Enum):
    FOREST = "FOREST"
    WETLAND = "WETLAND"
    COASTAL = "COASTAL"
    HERITAGE = "HERITAGE"
    NO_DEVELOPMENT = "NO_DEVELOPMENT"


# Base model with common fields
class BaseModel(Base):
    __abstract__ = True
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(BaseModel):
    """User management and authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    areas_of_interest = relationship("AreaOfInterest", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    verified_detections = relationship("Detection", back_populates="verified_by", foreign_keys="Detection.verified_by_user_id")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    system_logs = relationship("SystemLog", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"


class AreaOfInterest(BaseModel):
    """Areas of Interest for change detection analysis"""
    __tablename__ = "areas_of_interest"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="areas_of_interest")
    jobs = relationship("Job", back_populates="aoi", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AreaOfInterest(id={self.id}, name='{self.name}')>"
    
    @property
    def geometry_geojson(self):
        """Convert geometry to GeoJSON format"""
        if self.geometry:
            return to_shape(self.geometry).__geo_interface__
        return None
    
    def set_geometry_from_geojson(self, geojson_dict):
        """Set geometry from GeoJSON dictionary"""
        if geojson_dict:
            self.geometry = from_shape(shape(geojson_dict))


class Job(BaseModel):
    """Change detection jobs"""
    __tablename__ = "jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aoi_id = Column(UUID(as_uuid=True), ForeignKey('areas_of_interest.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    
    # Job parameters
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    cloud_threshold = Column(Float, nullable=False, default=0.2)
    change_threshold = Column(Float, nullable=False, default=0.5)
    priority = Column(Integer, nullable=False, default=1)
    
    # Job status and results
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    error_message = Column(Text)
    result_summary = Column(JSON)  # Summary statistics
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    aoi = relationship("AreaOfInterest", back_populates="jobs")
    user = relationship("User", back_populates="jobs")
    detections = relationship("Detection", back_populates="job", cascade="all, delete-orphan")
    satellite_images = relationship("SatelliteImage", back_populates="job", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="job")
    
    def __repr__(self):
        return f"<Job(id={self.id}, status='{self.status}', aoi_id={self.aoi_id})>"
    
    @property
    def duration_seconds(self):
        """Calculate job duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_active(self):
        """Check if job is currently running"""
        return self.status in [JobStatus.PENDING, JobStatus.RUNNING]


class ProtectedZone(BaseModel):
    """Protected areas where construction is restricted"""
    __tablename__ = "protected_zones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    zone_type = Column(Enum(ZoneType), nullable=False, index=True)
    geometry = Column(Geometry('MULTIPOLYGON', srid=4326), nullable=False)
    
    # Regulatory information
    regulation_details = Column(Text)
    authority = Column(String(255))  # Governing authority
    notification_number = Column(String(100))  # Official notification ID
    effective_date = Column(Date)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    violations = relationship("DetectionViolation", back_populates="protected_zone", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ProtectedZone(id={self.id}, name='{self.name}', type='{self.zone_type}')>"
    
    @property
    def geometry_geojson(self):
        """Convert geometry to GeoJSON format"""
        if self.geometry:
            return to_shape(self.geometry).__geo_interface__
        return None


class Detection(BaseModel):
    """Change detection results"""
    __tablename__ = "detections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    detection_type = Column(Enum(DetectionType), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, index=True)
    area_sqm = Column(Float, nullable=False)
    
    # Image URLs
    before_image_url = Column(String(512))
    after_image_url = Column(String(512))
    change_mask_url = Column(String(512))
    
    # Additional attributes from ML model
    attributes = Column(JSON)  # Store additional detection metadata
    
    # Human verification
    is_verified = Column(Boolean, default=False, nullable=False, index=True)
    verification_notes = Column(Text)
    verified_by_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    verified_at = Column(DateTime(timezone=True))
    
    # Relationships
    job = relationship("Job", back_populates="detections")
    verified_by = relationship("User", back_populates="verified_detections", foreign_keys=[verified_by_user_id])
    violations = relationship("DetectionViolation", back_populates="detection", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="detection")
    
    def __repr__(self):
        return f"<Detection(id={self.id}, type='{self.detection_type}', confidence={self.confidence_score:.2f})>"
    
    @property
    def geometry_geojson(self):
        """Convert geometry to GeoJSON format"""
        if self.geometry:
            return to_shape(self.geometry).__geo_interface__
        return None
    
    @property
    def area_hectares(self):
        """Convert area to hectares"""
        return self.area_sqm / 10000 if self.area_sqm else 0
    
    def verify(self, user_id: int, notes: Optional[str] = None):
        """Mark detection as verified by a user"""
        self.is_verified = True
        self.verified_by_user_id = user_id
        self.verified_at = datetime.utcnow()
        if notes:
            self.verification_notes = notes


class DetectionViolation(BaseModel):
    """Violations when detections overlap with protected zones"""
    __tablename__ = "detection_violations"
    
    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(UUID(as_uuid=True), ForeignKey('detections.id', ondelete='CASCADE'), nullable=False, index=True)
    protected_zone_id = Column(Integer, ForeignKey('protected_zones.id', ondelete='CASCADE'), nullable=False, index=True)
    
    violation_type = Column(String(100), nullable=False)  # e.g., "CONSTRUCTION_IN_FOREST"
    severity = Column(String(50), nullable=False, default="MEDIUM", index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    overlap_area_sqm = Column(Float, nullable=False)
    overlap_percentage = Column(Float, nullable=False)  # % of detection in protected zone
    
    # Status tracking
    is_flagged = Column(Boolean, default=True, nullable=False, index=True)
    flagged_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    
    # Relationships
    detection = relationship("Detection", back_populates="violations")
    protected_zone = relationship("ProtectedZone", back_populates="violations")
    
    def __repr__(self):
        return f"<DetectionViolation(id={self.id}, type='{self.violation_type}', severity='{self.severity}')>"
    
    @property
    def overlap_hectares(self):
        """Convert overlap area to hectares"""
        return self.overlap_area_sqm / 10000 if self.overlap_area_sqm else 0
    
    def resolve(self, notes: Optional[str] = None):
        """Mark violation as resolved"""
        self.is_flagged = False
        self.resolved_at = datetime.utcnow()
        if notes:
            self.resolution_notes = notes


class SatelliteImage(BaseModel):
    """Satellite images used in change detection jobs"""
    __tablename__ = "satellite_images"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    image_date = Column(Date, nullable=False, index=True)
    satellite = Column(String(50), nullable=False, index=True)  # Sentinel-2, Landsat-8, etc.
    scene_id = Column(String(100), nullable=False, unique=True, index=True)
    cloud_coverage = Column(Float, nullable=False)
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=False)
    
    # STAC and processing URLs
    stac_item_url = Column(String(512))
    cog_url = Column(String(512))  # Cloud Optimized GeoTIFF URL
    thumbnail_url = Column(String(512))
    
    # Processing status
    processing_status = Column(String(50), nullable=False, default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    image_metadata = Column(JSON)  # Additional STAC metadata
    
    # Relationships
    job = relationship("Job", back_populates="satellite_images")
    
    def __repr__(self):
        return f"<SatelliteImage(id={self.id}, satellite='{self.satellite}', date={self.image_date})>"
    
    @property
    def geometry_geojson(self):
        """Convert geometry to GeoJSON format"""
        if self.geometry:
            return to_shape(self.geometry).__geo_interface__
        return None
    
    @property
    def is_low_cloud(self):
        """Check if image has acceptable cloud coverage"""
        return self.cloud_coverage <= 0.2  # Default threshold


class Alert(BaseModel):
    """User notifications and alerts"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    detection_id = Column(UUID(as_uuid=True), ForeignKey('detections.id', ondelete='CASCADE'))
    job_id = Column(UUID(as_uuid=True), ForeignKey('jobs.id', ondelete='CASCADE'))
    
    alert_type = Column(String(50), nullable=False, index=True)  # JOB_COMPLETED, VIOLATION_DETECTED, etc.
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="INFO", index=True)  # INFO, WARNING, ERROR, CRITICAL
    
    # Status tracking
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    email_sent = Column(Boolean, default=False, nullable=False)
    sms_sent = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="alerts")
    detection = relationship("Detection", back_populates="alerts")
    job = relationship("Job", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity}')>"
    
    def mark_as_read(self):
        """Mark alert as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    @classmethod
    def create_job_completion_alert(cls, user_id: int, job_id: str, detections_count: int):
        """Create alert for job completion"""
        return cls(
            user_id=user_id,
            job_id=job_id,
            alert_type="JOB_COMPLETED",
            title="Change Detection Job Completed",
            message=f"Your change detection job has completed with {detections_count} detections found.",
            severity="INFO"
        )
    
    @classmethod
    def create_violation_alert(cls, user_id: int, detection_id: str, zone_name: str):
        """Create alert for protected zone violation"""
        return cls(
            user_id=user_id,
            detection_id=detection_id,
            alert_type="VIOLATION_DETECTED",
            title="Protected Zone Violation Detected",
            message=f"Construction detected in protected area: {zone_name}",
            severity="CRITICAL"
        )


class SystemLog(BaseModel):
    """System audit logs"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), index=True)
    action = Column(String(100), nullable=False, index=True)  # CREATE_JOB, DELETE_AOI, etc.
    resource_type = Column(String(50), nullable=False, index=True)  # JOB, AOI, DETECTION, etc.
    resource_id = Column(String(100), index=True)
    details = Column(JSON)  # Additional context data
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(512))
    
    # Relationships
    user = relationship("User", back_populates="system_logs")
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, action='{self.action}', resource='{self.resource_type}')>"
    
    @classmethod
    def log_action(cls, session: Session, user_id: Optional[int], action: str, 
                   resource_type: str, resource_id: Optional[str] = None, 
                   details: Optional[dict] = None, ip_address: Optional[str] = None,
                   user_agent: Optional[str] = None):
        """Create a new system log entry"""
        log_entry = cls(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        session.add(log_entry)
        session.commit()
        return log_entry


# Utility functions for database operations
def create_tables(engine):
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_model_by_name(name: str):
    """Get SQLAlchemy model class by name"""
    model_map = {
        'User': User,
        'AreaOfInterest': AreaOfInterest,
        'Job': Job,
        'ProtectedZone': ProtectedZone,
        'Detection': Detection,
        'DetectionViolation': DetectionViolation,
        'SatelliteImage': SatelliteImage,
        'Alert': Alert,
        'SystemLog': SystemLog,
    }
    return model_map.get(name)


# Database query helpers
class DatabaseQueries:
    """Collection of common database queries"""
    
    @staticmethod
    def get_active_jobs(session: Session, user_id: Optional[int] = None):
        """Get all active (pending/running) jobs"""
        query = session.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
        )
        if user_id:
            query = query.filter(Job.user_id == user_id)
        return query.order_by(Job.created_at.desc()).all()
    
    @staticmethod
    def get_recent_detections(session: Session, user_id: Optional[int] = None, 
                            limit: int = 50):
        """Get recent detections with high confidence"""
        query = session.query(Detection).filter(
            Detection.confidence_score >= 0.7
        )
        if user_id:
            query = query.join(Job).filter(Job.user_id == user_id)
        return query.order_by(Detection.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_violations_in_zone(session: Session, zone_id: int, 
                              active_only: bool = True):
        """Get all violations in a specific protected zone"""
        query = session.query(DetectionViolation).filter(
            DetectionViolation.protected_zone_id == zone_id
        )
        if active_only:
            query = query.filter(DetectionViolation.is_flagged == True)
        return query.order_by(DetectionViolation.flagged_at.desc()).all()
    
    @staticmethod
    def get_user_statistics(session: Session, user_id: int):
        """Get summary statistics for a user"""
        stats = {}
        
        # Job statistics
        stats['total_jobs'] = session.query(Job).filter(Job.user_id == user_id).count()
        stats['active_jobs'] = session.query(Job).filter(
            Job.user_id == user_id,
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
        ).count()
        stats['completed_jobs'] = session.query(Job).filter(
            Job.user_id == user_id,
            Job.status == JobStatus.COMPLETED
        ).count()
        
        # Detection statistics
        detection_query = session.query(Detection).join(Job).filter(Job.user_id == user_id)
        stats['total_detections'] = detection_query.count()
        stats['verified_detections'] = detection_query.filter(Detection.is_verified == True).count()
        stats['high_confidence_detections'] = detection_query.filter(Detection.confidence_score >= 0.8).count()
        
        # AOI statistics
        stats['total_aois'] = session.query(AreaOfInterest).filter(AreaOfInterest.user_id == user_id).count()
        
        # Alert statistics
        stats['unread_alerts'] = session.query(Alert).filter(
            Alert.user_id == user_id,
            Alert.is_read == False
        ).count()
        
        return stats