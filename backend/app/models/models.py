# app/models/models.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry  # ← Add this import
# --- FIX 1: Import Base from app.db.database, DO NOT redefine it ---
from app.db.database import Base # Import the Base instance defined in database.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.info("Loading models.py...")

# ========================================
# AOI Model (ADD THIS)
# ========================================
class AOI(Base):
    """Area of Interest model"""
    __tablename__ = "aois"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    ward = Column(String(50), nullable=True)
    geometry = Column(Geometry('MULTIPOLYGON', srid=4326), nullable=False)
    area_sqm = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("Job", back_populates="aoi")
    
    def __repr__(self):
        return f"<AOI(id={self.id}, name='{self.name}', ward='{self.ward}')>"

# ========================================
# Job Model (UPDATED)
# ========================================
class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    aoi_id = Column(Integer, ForeignKey("aois.id"), nullable=True)  # ← Add this
    name = Column(String(100))
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parameters = Column(JSON)  # Store job parameters as JSON
    result_url = Column(String(255))  # URL to the processed result
    error_message = Column(String(500))
    
    # Relationships
    aoi = relationship("AOI", back_populates="jobs")  # ← Add this
    detections = relationship("Detection", back_populates="job")  # ← Add this
    
    def __repr__(self):
        return f"<Job(id={self.id}, name='{self.name}', status='{self.status}')>"

# ========================================
# Detection Model (UPDATED)
# ========================================
class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    description = Column(String(255))  # Add some fields for testing
    geometry = Column(Geometry('POLYGON', srid=4326), nullable=True)  # ← Add this
    confidence_score = Column(Float, nullable=True)  # ← Add this
    area_sqm = Column(Float, nullable=True)  # ← Add this
    flagged = Column(Boolean, default=False)  # ← Add this
    change_type = Column(String(50), nullable=True)  # ← Add this
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="detections")  # ← Add this
    
    def __repr__(self):
        return f"<Detection(id={self.id}, job_id={self.job_id}, flagged={self.flagged})>"

logger.info("Models AOI, Job, and Detection defined successfully.")
