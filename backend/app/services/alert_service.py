"""
Alert Service - Business logic for managing alerts
Handles alert creation, updates, notifications, and statistics
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON
import json
import uuid

from app.models.alert_models import Alert, AlertRule, AlertNotification
from app.models.schemas.alert_schemas import (
    AlertCreate, AlertUpdate, AlertResponse, 
    AlertRuleCreate, AlertRuleUpdate,
    AlertStats, DashboardStats
)


class AlertService:
    """
    Service class for alert operations
    Handles CRUD operations and business logic for alerts
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_alert(self, alert_data: AlertCreate) -> Alert:
        """
        Create a new alert from detection results
        """
        # Convert GeoJSON to PostGIS geometry
        aoi_geojson = json.dumps(alert_data.aoi)
        
        # Generate unique alert_id if not provided
        if not alert_data.alert_id:
            alert_data.alert_id = f"ALT-{uuid.uuid4().hex[:12].upper()}"
        
        # Create alert object
        new_alert = Alert(
            alert_id=alert_data.alert_id,
            job_id=alert_data.job_id,
            detection_date=datetime.utcnow(),
            aoi=func.ST_GeomFromGeoJSON(aoi_geojson),
            ward=alert_data.ward,
            zone=alert_data.zone,
            severity=alert_data.severity.value,
            alert_type=alert_data.alert_type.value,
            vegetation_loss_pct=alert_data.vegetation_loss_pct,
            area_affected_ha=alert_data.area_affected_ha,
            confidence_score=alert_data.confidence_score,
            detection_image_url=alert_data.detection_image_url,
            status='PENDING',
            priority=self._calculate_priority(alert_data)
        )
        
        self.db.add(new_alert)
        await self.db.commit()
        await self.db.refresh(new_alert)
        
        return new_alert
    
    async def get_alert_by_id(self, alert_id: int) -> Optional[Alert]:
        """Get alert by ID"""
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()
    
    async def get_alert_by_alert_id(self, alert_id: str) -> Optional[Alert]:
        """Get alert by alert_id string"""
        result = await self.db.execute(
            select(Alert).where(Alert.alert_id == alert_id)
        )
        return result.scalar_one_or_none()
    
    async def list_alerts(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        zone: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        List alerts with filtering and pagination
        """
        # Build query with filters
        query = select(Alert)
        
        filters = []
        if status:
            filters.append(Alert.status == status)
        if severity:
            filters.append(Alert.severity == severity)
        if zone:
            filters.append(Alert.zone == zone)
        if date_from:
            filters.append(Alert.detection_date >= date_from)
        if date_to:
            filters.append(Alert.detection_date <= date_to)
        
        if filters:
            query = query.where(and_(*filters))
        
        # Get total count
        count_query = select(func.count()).select_from(Alert)
        if filters:
            count_query = count_query.where(and_(*filters))
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination and ordering
        query = query.order_by(desc(Alert.detection_date)).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        alerts = result.scalars().all()
        
        return {
            "total": total,
            "page": skip // limit + 1 if limit > 0 else 1,
            "page_size": limit,
            "alerts": alerts
        }
    
    async def update_alert(self, alert_id: int, alert_update: AlertUpdate) -> Optional[Alert]:
        """
        Update alert status and details
        """
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return None
        
        # Update fields
        update_data = alert_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == 'status' and value:
                setattr(alert, field, value.value)
                
                # Set timestamps based on status
                if value.value == 'ACKNOWLEDGED' and not alert.acknowledged_at:
                    alert.acknowledged_at = datetime.utcnow()
                elif value.value == 'RESOLVED' and not alert.resolved_at:
                    alert.resolved_at = datetime.utcnow()
            else:
                setattr(alert, field, value)
        
        alert.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(alert)
        
        return alert
    
    async def acknowledge_alert(self, alert_id: int, acknowledged_by: str) -> Optional[Alert]:
        """Mark alert as acknowledged"""
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return None
        
        alert.status = 'ACKNOWLEDGED'
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(alert)
        
        return alert
    
    async def resolve_alert(
        self, 
        alert_id: int, 
        resolution_notes: Optional[str] = None
    ) -> Optional[Alert]:
        """Mark alert as resolved"""
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return None
        
        alert.status = 'RESOLVED'
        alert.resolution_notes = resolution_notes
        alert.resolved_at = datetime.utcnow()
        alert.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(alert)
        
        return alert
    
    async def dismiss_alert(self, alert_id: int, reason: Optional[str] = None) -> Optional[Alert]:
        """Mark alert as dismissed (false positive)"""
        alert = await self.get_alert_by_id(alert_id)
        if not alert:
            return None
        
        alert.status = 'DISMISSED'
        alert.resolution_notes = f"Dismissed: {reason}" if reason else "Dismissed"
        alert.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(alert)
        
        return alert
    
    async def get_alert_statistics(self) -> AlertStats:
        """Get overall alert statistics"""
        # Count by status
        status_counts = await self.db.execute(
            select(
                Alert.status,
                func.count(Alert.id).label('count')
            ).group_by(Alert.status)
        )
        
        status_dict = {row.status: row.count for row in status_counts}
        
        # Count by severity
        severity_counts = await self.db.execute(
            select(
                func.count(Alert.id).label('count')
            ).where(
                or_(Alert.severity == 'HIGH', Alert.severity == 'CRITICAL')
            )
        )
        
        high_critical_count = severity_counts.scalar() or 0
        
        # Calculate average response time
        response_times = await self.db.execute(
            select(
                func.avg(
                    func.extract('epoch', Alert.acknowledged_at - Alert.detection_date) / 3600
                ).label('avg_hours')
            ).where(Alert.acknowledged_at.isnot(None))
        )
        
        avg_response_hours = response_times.scalar()
        
        return AlertStats(
            total_alerts=sum(status_dict.values()),
            pending=status_dict.get('PENDING', 0),
            notified=status_dict.get('NOTIFIED', 0),
            acknowledged=status_dict.get('ACKNOWLEDGED', 0),
            resolved=status_dict.get('RESOLVED', 0),
            dismissed=status_dict.get('DISMISSED', 0),
            high_severity=high_critical_count,
            critical_severity=high_critical_count,
            avg_response_time_hours=avg_response_hours
        )
    
    async def get_dashboard_stats(self) -> DashboardStats:
        """Get dashboard statistics for today, week, month"""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Alerts today
        today_result = await self.db.execute(
            select(func.count(Alert.id)).where(Alert.detection_date >= today_start)
        )
        alerts_today = today_result.scalar() or 0
        
        # Alerts this week
        week_result = await self.db.execute(
            select(func.count(Alert.id)).where(Alert.detection_date >= week_start)
        )
        alerts_this_week = week_result.scalar() or 0
        
        # Alerts this month
        month_result = await self.db.execute(
            select(func.count(Alert.id)).where(Alert.detection_date >= month_start)
        )
        alerts_this_month = month_result.scalar() or 0
        
        # Critical pending
        critical_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                and_(
                    Alert.severity == 'CRITICAL',
                    Alert.status == 'PENDING'
                )
            )
        )
        critical_pending = critical_result.scalar() or 0
        
        # Average vegetation loss
        avg_loss_result = await self.db.execute(
            select(func.avg(Alert.vegetation_loss_pct)).where(
                Alert.vegetation_loss_pct.isnot(None)
            )
        )
        avg_vegetation_loss = avg_loss_result.scalar()
        
        # Total area affected
        area_result = await self.db.execute(
            select(func.sum(Alert.area_affected_ha)).where(
                Alert.area_affected_ha.isnot(None)
            )
        )
        total_area_affected = area_result.scalar()
        
        # Top affected zones
        zones_result = await self.db.execute(
            select(
                Alert.zone,
                func.count(Alert.id).label('alert_count'),
                func.sum(Alert.area_affected_ha).label('total_area')
            ).where(
                Alert.zone.isnot(None)
            ).group_by(Alert.zone).order_by(desc('alert_count')).limit(5)
        )
        
        top_zones = [
            {
                "zone": row.zone,
                "alert_count": row.alert_count,
                "total_area_ha": float(row.total_area) if row.total_area else 0
            }
            for row in zones_result
        ]
        
        return DashboardStats(
            alerts_today=alerts_today,
            alerts_this_week=alerts_this_week,
            alerts_this_month=alerts_this_month,
            critical_pending=critical_pending,
            avg_vegetation_loss_pct=avg_vegetation_loss,
            total_area_affected_ha=total_area_affected,
            top_affected_zones=top_zones
        )
    
    def _calculate_priority(self, alert_data: AlertCreate) -> int:
        """
        Calculate alert priority (1=Highest, 5=Lowest) based on severity and metrics
        """
        severity_priority = {
            'CRITICAL': 1,
            'HIGH': 2,
            'MEDIUM': 3,
            'LOW': 4
        }
        
        priority = severity_priority.get(alert_data.severity.value, 3)
        
        # Adjust based on area affected
        if alert_data.area_affected_ha and alert_data.area_affected_ha > 10:
            priority = max(1, priority - 1)
        
        return priority


class AlertRuleService:
    """
    Service class for alert rule operations
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_rule(self, rule_data: AlertRuleCreate) -> AlertRule:
        """Create new alert rule"""
        new_rule = AlertRule(**rule_data.dict())
        
        self.db.add(new_rule)
        await self.db.commit()
        await self.db.refresh(new_rule)
        
        return new_rule
    
    async def get_rule_by_id(self, rule_id: int) -> Optional[AlertRule]:
        """Get rule by ID"""
        result = await self.db.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        return result.scalar_one_or_none()
    
    async def list_rules(self, active_only: bool = False) -> List[AlertRule]:
        """List all alert rules"""
        query = select(AlertRule)
        
        if active_only:
            query = query.where(AlertRule.active == True)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_rule(self, rule_id: int, rule_update: AlertRuleUpdate) -> Optional[AlertRule]:
        """Update alert rule"""
        rule = await self.get_rule_by_id(rule_id)
        if not rule:
            return None
        
        update_data = rule_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)
        
        await self.db.commit()
        await self.db.refresh(rule)
        
        return rule
    
    async def delete_rule(self, rule_id: int) -> bool:
        """Delete alert rule"""
        rule = await self.get_rule_by_id(rule_id)
        if not rule:
            return False
        
        await self.db.delete(rule)
        await self.db.commit()
        
        return True
    
    async def evaluate_rules(self, alert: Alert) -> List[AlertRule]:
        """
        Evaluate which rules are triggered by an alert
        Returns list of matching rules
        """
        # Get all active rules
        rules = await self.list_rules(active_only=True)
        
        matching_rules = []
        
        for rule in rules:
            if self._rule_matches_alert(rule, alert):
                matching_rules.append(rule)
        
        return matching_rules
    
    def _rule_matches_alert(self, rule: AlertRule, alert: Alert) -> bool:
        """Check if alert matches rule conditions"""
        # Check vegetation loss threshold
        if rule.min_vegetation_loss_pct:
            if not alert.vegetation_loss_pct or alert.vegetation_loss_pct < rule.min_vegetation_loss_pct:
                return False
        
        # Check area threshold
        if rule.min_area_ha:
            if not alert.area_affected_ha or alert.area_affected_ha < rule.min_area_ha:
                return False
        
        # Check confidence threshold
        if rule.min_confidence:
            if not alert.confidence_score or alert.confidence_score < rule.min_confidence:
                return False
        
        # Check zone types
        if rule.zone_types and alert.zone:
            if alert.zone not in rule.zone_types:
                return False
        
        return True
