# backend/app/models/alert.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ARRAY, ForeignKey, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
from .base import Base  # Assuming you have a Base model

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Link to detection job
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    detection_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Location data (PostGIS geometry)
    aoi = Column(Geometry('POLYGON', srid=4326), nullable=False)
    ward = Column(String(50))  # Mumbai ward
    zone = Column(String(50))  # CRZ-I, CRZ-II, etc.
    
    # Severity & type
    severity = Column(String(20), nullable=False, index=True)  # CRITICAL, HIGH, MODERATE, LOW
    alert_type = Column(String(50), nullable=False)  # MANGROVE_LOSS, CRZ_VIOLATION, etc.
    
    # Detection metrics
    vegetation_loss_pct = Column(Float)
    area_affected_ha = Column(Float)
    confidence_score = Column(Float)
    
    # Alert status
    status = Column(String(20), default="PENDING", index=True)  # PENDING, SENT, ACKNOWLEDGED, RESOLVED
    priority = Column(Integer, default=3)  # 1=highest, 5=lowest
    
    # Notification tracking
    notified_at = Column(DateTime)
    notified_contacts = Column(ARRAY(String))
    
    # Response tracking
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(200))
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    
    # Evidence files
    detection_image_url = Column(String(500))
    report_pdf_url = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="alerts")


class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), unique=True, nullable=False)
    
    # Trigger conditions
    min_vegetation_loss_pct = Column(Float)
    min_area_ha = Column(Float)
    min_confidence = Column(Float)
    zone_types = Column(ARRAY(String))  # CRZ-I, CRZ-II, etc.
    
    # Alert configuration
    severity = Column(String(20))
    notification_channels = Column(ARRAY(String))  # ['email', 'sms', 'dashboard']
    
    # Recipients
    recipient_emails = Column(ARRAY(String))
    recipient_phones = Column(ARRAY(String))
    
    # Spam prevention
    cooldown_hours = Column(Integer, default=24)
    active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertNotification(Base):
    __tablename__ = "alert_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    
    channel = Column(String(20))  # email, sms, dashboard
    recipient = Column(String(200))
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivery_status = Column(String(20))  # sent, delivered, failed
    message_body = Column(Text)
    response_received = Column(Text)
    
    # Relationship
    alert = relationship("Alert")
# backend/app/models/alert.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ARRAY, ForeignKey, Text
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from datetime import datetime
from .base import Base  # Assuming you have a Base model

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Link to detection job
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    detection_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Location data (PostGIS geometry)
    aoi = Column(Geometry('POLYGON', srid=4326), nullable=False)
    ward = Column(String(50))  # Mumbai ward
    zone = Column(String(50))  # CRZ-I, CRZ-II, etc.
    
    # Severity & type
    severity = Column(String(20), nullable=False, index=True)  # CRITICAL, HIGH, MODERATE, LOW
    alert_type = Column(String(50), nullable=False)  # MANGROVE_LOSS, CRZ_VIOLATION, etc.
    
    # Detection metrics
    vegetation_loss_pct = Column(Float)
    area_affected_ha = Column(Float)
    confidence_score = Column(Float)
    
    # Alert status
    status = Column(String(20), default="PENDING", index=True)  # PENDING, SENT, ACKNOWLEDGED, RESOLVED
    priority = Column(Integer, default=3)  # 1=highest, 5=lowest
    
    # Notification tracking
    notified_at = Column(DateTime)
    notified_contacts = Column(ARRAY(String))
    
    # Response tracking
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(200))
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    
    # Evidence files
    detection_image_url = Column(String(500))
    report_pdf_url = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="alerts")


class AlertRule(Base):
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), unique=True, nullable=False)
    
    # Trigger conditions
    min_vegetation_loss_pct = Column(Float)
    min_area_ha = Column(Float)
    min_confidence = Column(Float)
    zone_types = Column(ARRAY(String))  # CRZ-I, CRZ-II, etc.
    
    # Alert configuration
    severity = Column(String(20))
    notification_channels = Column(ARRAY(String))  # ['email', 'sms', 'dashboard']
    
    # Recipients
    recipient_emails = Column(ARRAY(String))
    recipient_phones = Column(ARRAY(String))
    
    # Spam prevention
    cooldown_hours = Column(Integer, default=24)
    active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertNotification(Base):
    __tablename__ = "alert_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    
    channel = Column(String(20))  # email, sms, dashboard
    recipient = Column(String(200))
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivery_status = Column(String(20))  # sent, delivered, failed
    message_body = Column(Text)
    response_received = Column(Text)
    
    # Relationship
    alert = relationship("Alert")
