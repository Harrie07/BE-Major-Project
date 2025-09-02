# app/models/models.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey
# --- FIX 1: Import Base from app.db.database, DO NOT redefine it ---
from app.db.database import Base # Import the Base instance defined in database.py
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
logger.info("Loading models.py...")

# --- Define your models using the imported Base ---
class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parameters = Column(JSON)  # Store job parameters as JSON
    result_url = Column(String(255))  # URL to the processed result
    error_message = Column(String(500))

class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    # ForeignKey is now correctly imported
    job_id = Column(Integer, ForeignKey("jobs.id"))
    description = Column(String(255)) # Add some fields for testing

logger.info("Models Job and Detection defined.")
