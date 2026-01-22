"""
Alert system database models
Handles vegetation loss alerts, notification rules, and alert tracking
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ARRAY, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from geoalchemy2 import Geometry

# Create a separate Base for alert models
AlertBase = declarative_base()


class Alert(AlertBase):
    """
    Main alerts table - stores detected vegetation loss alerts
    """
    __tablename__ = "alerts"
    __table_args__ = {'extend_existing': True}  # ✅ Allow redefinition

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, nullable=False, index=True)
    job_id = Column(Integer, nullable=True)
    
    # Detection details
    detection_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    aoi = Column(Geometry(geometry_type='POLYGON', srid=4326), nullable=False)
    ward = Column(String(50), nullable=True)
    zone = Column(String(50), nullable=True)
    
    # Alert classification
    severity = Column(String(20), nullable=False)
    alert_type = Column(String(50), nullable=False)
    
    # Metrics
    vegetation_loss_pct = Column(Float, nullable=True)
    area_affected_ha = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Status tracking
    status = Column(String(20), default='PENDING')
    priority = Column(Integer, default=3)
    
    # Notification tracking
    notified_at = Column(DateTime(timezone=True), nullable=True)
    notified_contacts = Column(ARRAY(Text), nullable=True)
    
    # Resolution tracking
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(200), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Media and reports
    detection_image_url = Column(String(500), nullable=True)
    report_pdf_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AlertRule(AlertBase):
    """
    Alert rules table - defines conditions for triggering alerts
    """
    __tablename__ = "alert_rules"
    __table_args__ = {'extend_existing': True}  # ✅ Allow redefinition

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), unique=True, nullable=False)
    
    # Trigger thresholds
    min_vegetation_loss_pct = Column(Float, nullable=True)
    min_area_ha = Column(Float, nullable=True)
    min_confidence = Column(Float, nullable=True)
    zone_types = Column(ARRAY(Text), nullable=True)
    
    # Alert settings
    severity = Column(String(20), nullable=True)
    
    # Notification settings
    notification_channels = Column(ARRAY(Text), nullable=True)
    recipient_emails = Column(ARRAY(Text), nullable=True)
    recipient_phones = Column(ARRAY(Text), nullable=True)
    
    # Rule behavior
    cooldown_hours = Column(Integer, default=24)
    active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AlertNotification(AlertBase):
    """
    Alert notifications table - tracks notification delivery
    """
    __tablename__ = "alert_notifications"
    __table_args__ = {'extend_existing': True}  # ✅ Allow redefinition

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey('alerts.id'), nullable=False)
    
    # Notification details
    channel = Column(String(20), nullable=False)
    recipient = Column(String(200), nullable=False)
    
    # Delivery tracking
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    delivery_status = Column(String(20), nullable=True)
    
    # Content
    message_body = Column(Text, nullable=True)
    response_received = Column(Text, nullable=True)
