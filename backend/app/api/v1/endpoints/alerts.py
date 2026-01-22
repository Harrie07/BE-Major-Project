"""
Alert API Endpoints
Handles HTTP endpoints for alert management
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models.schemas.alert_schemas import (
    AlertCreate, AlertUpdate, AlertResponse, AlertListResponse,
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
    AlertStats, DashboardStats, AlertStatus, AlertSeverity
)
from app.services.alert_service import AlertService, AlertRuleService
from app.db.database import get_db

router = APIRouter()


# Dependency to get alert service
def get_alert_service(db: Session = Depends(get_db)) -> AlertService:
    """Dependency injection for AlertService"""
    return AlertService(db)


def get_alert_rule_service(db: Session = Depends(get_db)) -> AlertRuleService:
    """Dependency injection for AlertRuleService"""
    return AlertRuleService(db)


# ==================== ALERT ENDPOINTS ====================

@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_data: AlertCreate,
    service: AlertService = Depends(get_alert_service)
):
    """
    Create a new alert
    
    - **alert_id**: Unique identifier for the alert
    - **severity**: Alert severity (LOW, MEDIUM, HIGH, CRITICAL)
    - **alert_type**: Type of alert (VEGETATION_LOSS, ENCROACHMENT, etc.)
    - **aoi**: GeoJSON polygon of affected area
    """
    try:
        alert = await service.create_alert(alert_data)
        return alert
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create alert: {str(e)}"
        )


@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    status_filter: Optional[AlertStatus] = Query(None, alias="status", description="Filter by status"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    date_from: Optional[datetime] = Query(None, description="Filter alerts from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter alerts until this date"),
    service: AlertService = Depends(get_alert_service)
):
    """
    List all alerts with optional filtering and pagination
    
    **Filters:**
    - status: PENDING, NOTIFIED, ACKNOWLEDGED, RESOLVED, DISMISSED
    - severity: LOW, MEDIUM, HIGH, CRITICAL
    - zone: Zone name
    - date_from/date_to: Date range filter
    """
    try:
        result = await service.list_alerts(
            skip=skip,
            limit=limit,
            status=status_filter.value if status_filter else None,
            severity=severity.value if severity else None,
            zone=zone,
            date_from=date_from,
            date_to=date_to
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alerts: {str(e)}"
        )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    service: AlertService = Depends(get_alert_service)
):
    """
    Get a specific alert by ID
    """
    alert = await service.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert


@router.get("/by-alert-id/{alert_id}", response_model=AlertResponse)
async def get_alert_by_alert_id(
    alert_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """
    Get a specific alert by alert_id string (e.g., ALT-ABC123)
    """
    alert = await service.get_alert_by_alert_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with alert_id {alert_id} not found"
        )
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    alert_update: AlertUpdate,
    service: AlertService = Depends(get_alert_service)
):
    """
    Update an alert's status or details
    """
    alert = await service.update_alert(alert_id, alert_update)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = Query(..., description="Name or ID of person acknowledging"),
    service: AlertService = Depends(get_alert_service)
):
    """
    Acknowledge an alert (mark as seen/being handled)
    """
    alert = await service.acknowledge_alert(alert_id, acknowledged_by)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    resolution_notes: Optional[str] = Query(None, description="Notes about resolution"),
    service: AlertService = Depends(get_alert_service)
):
    """
    Mark an alert as resolved
    """
    alert = await service.resolve_alert(alert_id, resolution_notes)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert


@router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: int,
    reason: Optional[str] = Query(None, description="Reason for dismissal"),
    service: AlertService = Depends(get_alert_service)
):
    """
    Dismiss an alert (mark as false positive)
    """
    alert = await service.dismiss_alert(alert_id, reason)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID {alert_id} not found"
        )
    return alert


@router.get("/statistics/overview", response_model=AlertStats)
async def get_alert_statistics(
    service: AlertService = Depends(get_alert_service)
):
    """
    Get overall alert statistics
    
    Returns counts by status, severity, and average response times
    """
    try:
        stats = await service.get_alert_statistics()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get("/statistics/dashboard", response_model=DashboardStats)
async def get_dashboard_statistics(
    service: AlertService = Depends(get_alert_service)
):
    """
    Get dashboard statistics (today, week, month)
    
    Returns:
    - Alert counts for today/week/month
    - Critical pending alerts
    - Average vegetation loss
    - Total area affected
    - Top affected zones
    """
    try:
        stats = await service.get_dashboard_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )


# ==================== ALERT RULE ENDPOINTS ====================

@router.post("/rules/", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    service: AlertRuleService = Depends(get_alert_rule_service)
):
    """
    Create a new alert rule
    
    Rules define conditions for triggering alerts and notification settings
    """
    try:
        rule = await service.create_rule(rule_data)
        return rule
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create rule: {str(e)}"
        )


@router.get("/rules/", response_model=List[AlertRuleResponse])
async def list_alert_rules(
    active_only: bool = Query(False, description="Return only active rules"),
    service: AlertRuleService = Depends(get_alert_rule_service)
):
    """
    List all alert rules
    """
    try:
        rules = await service.list_rules(active_only=active_only)
        return rules
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list rules: {str(e)}"
        )


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: int,
    service: AlertRuleService = Depends(get_alert_rule_service)
):
    """
    Get a specific alert rule by ID
    """
    rule = await service.get_rule_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found"
        )
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    rule_update: AlertRuleUpdate,
    service: AlertRuleService = Depends(get_alert_rule_service)
):
    """
    Update an alert rule
    """
    rule = await service.update_rule(rule_id, rule_update)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found"
        )
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: int,
    service: AlertRuleService = Depends(get_alert_rule_service)
):
    """
    Delete an alert rule
    """
    success = await service.delete_rule(rule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule with ID {rule_id} not found"
        )
    return None
