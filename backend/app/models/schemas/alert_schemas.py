"""
Pydantic schemas for Alert API
Handles request/response validation
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


# Enums for validation
class AlertSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    PENDING = "PENDING"
    NOTIFIED = "NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class AlertType(str, Enum):
    VEGETATION_LOSS = "VEGETATION_LOSS"
    ENCROACHMENT = "ENCROACHMENT"
    DEFORESTATION = "DEFORESTATION"
    ILLEGAL_CONSTRUCTION = "ILLEGAL_CONSTRUCTION"


class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"
    PUSH = "PUSH"


# Alert Schemas
class AlertBase(BaseModel):
    """Base alert schema"""
    alert_id: str = Field(..., description="Unique alert identifier")
    severity: AlertSeverity
    alert_type: AlertType
    ward: Optional[str] = None
    zone: Optional[str] = None
    vegetation_loss_pct: Optional[float] = None
    area_affected_ha: Optional[float] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=1)


class AlertCreate(AlertBase):
    """Schema for creating new alerts"""
    job_id: Optional[int] = None
    aoi: dict = Field(..., description="GeoJSON polygon")
    detection_image_url: Optional[str] = None
    
    @validator('aoi')
    def validate_aoi(cls, v):
        """Validate GeoJSON format"""
        if 'type' not in v or 'coordinates' not in v:
            raise ValueError("AOI must be valid GeoJSON")
        if v['type'] not in ['Polygon', 'MultiPolygon']:
            raise ValueError("AOI must be a Polygon or MultiPolygon")
        return v


class AlertUpdate(BaseModel):
    """Schema for updating alerts"""
    status: Optional[AlertStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None


class AlertResponse(AlertBase):
    """Schema for alert responses"""
    id: int
    job_id: Optional[int]
    status: AlertStatus
    priority: int
    detection_date: datetime
    notified_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
    detection_image_url: Optional[str]
    report_pdf_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # For SQLAlchemy ORM compatibility


class AlertListResponse(BaseModel):
    """Schema for paginated alert list"""
    total: int
    page: int
    page_size: int
    alerts: List[AlertResponse]


# Alert Rule Schemas
class AlertRuleBase(BaseModel):
    """Base alert rule schema"""
    rule_name: str = Field(..., min_length=3, max_length=100)
    min_vegetation_loss_pct: Optional[float] = Field(None, ge=0, le=100)
    min_area_ha: Optional[float] = Field(None, ge=0)
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    zone_types: Optional[List[str]] = None
    severity: Optional[AlertSeverity] = None
    cooldown_hours: int = Field(24, ge=0)
    active: bool = True


class AlertRuleCreate(AlertRuleBase):
    """Schema for creating alert rules"""
    notification_channels: Optional[List[NotificationChannel]] = None
    recipient_emails: Optional[List[str]] = None
    recipient_phones: Optional[List[str]] = None
    
    @validator('recipient_emails')
    def validate_emails(cls, v):
        """Basic email validation"""
        if v:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            for email in v:
                if not re.match(email_pattern, email):
                    raise ValueError(f"Invalid email: {email}")
        return v


class AlertRuleUpdate(BaseModel):
    """Schema for updating alert rules"""
    min_vegetation_loss_pct: Optional[float] = Field(None, ge=0, le=100)
    min_area_ha: Optional[float] = Field(None, ge=0)
    min_confidence: Optional[float] = Field(None, ge=0, le=1)
    notification_channels: Optional[List[NotificationChannel]] = None
    recipient_emails: Optional[List[str]] = None
    recipient_phones: Optional[List[str]] = None
    active: Optional[bool] = None


class AlertRuleResponse(AlertRuleBase):
    """Schema for alert rule responses"""
    id: int
    notification_channels: Optional[List[str]]
    recipient_emails: Optional[List[str]]
    recipient_phones: Optional[List[str]]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Alert Notification Schemas
class NotificationCreate(BaseModel):
    """Schema for creating notifications"""
    alert_id: int
    channel: NotificationChannel
    recipient: str
    message_body: Optional[str] = None


class NotificationResponse(BaseModel):
    """Schema for notification responses"""
    id: int
    alert_id: int
    channel: str
    recipient: str
    sent_at: datetime
    delivery_status: Optional[str]
    message_body: Optional[str]
    
    class Config:
        from_attributes = True


# Statistics Schemas
class AlertStats(BaseModel):
    """Alert statistics schema"""
    total_alerts: int
    pending: int
    notified: int
    acknowledged: int
    resolved: int
    dismissed: int
    high_severity: int
    critical_severity: int
    avg_response_time_hours: Optional[float]


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    alerts_today: int
    alerts_this_week: int
    alerts_this_month: int
    critical_pending: int
    avg_vegetation_loss_pct: Optional[float]
    total_area_affected_ha: Optional[float]
    top_affected_zones: List[dict]
