"""
Notification Service - Send alerts via Email, SMS, and Webhooks
Uses free/student-friendly options:
- Email: SMTP (Gmail, Outlook)
- SMS: Twilio free trial
- Webhook: POST requests
"""
from typing import List, Optional, Dict, Any
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

from app.core.config import settings
from app.models.alert_models import Alert, AlertNotification
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Email notification service using SMTP
    Works with Gmail, Outlook, or any SMTP server
    """
    
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', self.smtp_username)
        self.enabled = self.smtp_username and self.smtp_password
    
    def send_email(
        self, 
        to_email: str, 
        subject: str, 
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send email notification
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            
        Returns:
            bool: True if sent successfully
        """
        if not self.enabled:
            logger.warning("Email service not configured. Skipping email send.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add plain text part
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                msg.attach(html_part)
            
            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_alert_email(self, alert: Alert, recipient: str) -> bool:
        """
        Send alert notification email
        
        Args:
            alert: Alert object
            recipient: Recipient email address
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"🚨 {alert.severity} Alert: {alert.alert_type}"
        
        # Plain text body
        body = f"""
Mumbai Geo-AI Alert Notification
================================

Alert ID: {alert.alert_id}
Severity: {alert.severity}
Type: {alert.alert_type}
Status: {alert.status}
Priority: {alert.priority}

Detection Details:
-----------------
Date: {alert.detection_date}
Ward: {alert.ward or 'N/A'}
Zone: {alert.zone or 'N/A'}
Vegetation Loss: {alert.vegetation_loss_pct}% 
Area Affected: {alert.area_affected_ha} hectares
Confidence: {alert.confidence_score * 100 if alert.confidence_score else 'N/A'}%

Action Required:
---------------
Please review this alert and take appropriate action.

View Details: {settings.FRONTEND_URL}/alerts/{alert.alert_id}

---
This is an automated notification from Mumbai Geo-AI Alert System.
        """
        
        # HTML body
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {'#dc2626' if alert.severity == 'CRITICAL' else '#ea580c' if alert.severity == 'HIGH' else '#f59e0b'}; 
                   color: white; padding: 20px; border-radius: 5px; }}
        .content {{ background: #f9fafb; padding: 20px; margin: 20px 0; border-radius: 5px; }}
        .detail {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #4b5563; }}
        .button {{ background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; 
                  border-radius: 5px; display: inline-block; margin-top: 20px; }}
        .footer {{ color: #6b7280; font-size: 12px; margin-top: 30px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 {alert.severity} Alert: {alert.alert_type}</h2>
        </div>
        
        <div class="content">
            <div class="detail">
                <span class="label">Alert ID:</span> {alert.alert_id}
            </div>
            <div class="detail">
                <span class="label">Severity:</span> {alert.severity}
            </div>
            <div class="detail">
                <span class="label">Detection Date:</span> {alert.detection_date.strftime('%Y-%m-%d %H:%M')}
            </div>
            <div class="detail">
                <span class="label">Location:</span> Ward {alert.ward or 'N/A'}, Zone {alert.zone or 'N/A'}
            </div>
            <div class="detail">
                <span class="label">Vegetation Loss:</span> {alert.vegetation_loss_pct}%
            </div>
            <div class="detail">
                <span class="label">Area Affected:</span> {alert.area_affected_ha} hectares
            </div>
            <div class="detail">
                <span class="label">Confidence:</span> {alert.confidence_score * 100 if alert.confidence_score else 'N/A'}%
            </div>
            
            <a href="{settings.FRONTEND_URL}/alerts/{alert.alert_id}" class="button">
                View Alert Details
            </a>
        </div>
        
        <div class="footer">
            <p>This is an automated notification from Mumbai Geo-AI Alert System.</p>
            <p>Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
        """
        
        return self.send_email(recipient, subject, body, html_body)


class SMSNotificationService:
    """
    SMS notification service using Twilio
    Free trial: $15 credit (send ~400 SMS)
    Sign up: https://www.twilio.com/try-twilio
    """
    
    def __init__(self):
        self.account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
        self.auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
        self.from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)
        self.enabled = all([self.account_sid, self.auth_token, self.from_number])
        
        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.warning("Twilio library not installed. Run: pip install twilio")
                self.enabled = False
    
    def send_sms(self, to_number: str, message: str) -> bool:
        """
        Send SMS notification
        
        Args:
            to_number: Recipient phone number (E.164 format: +919876543210)
            message: SMS message (max 160 chars recommended)
            
        Returns:
            bool: True if sent successfully
        """
        if not self.enabled:
            logger.warning("SMS service not configured. Skipping SMS send.")
            return False
        
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(f"SMS sent successfully to {to_number}: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return False
    
    def send_alert_sms(self, alert: Alert, recipient: str) -> bool:
        """
        Send alert notification SMS
        
        Args:
            alert: Alert object
            recipient: Recipient phone number
            
        Returns:
            bool: True if sent successfully
        """
        # Keep message concise (SMS limit)
        message = (
            f"🚨 {alert.severity} Alert [{alert.alert_id}]\n"
            f"Type: {alert.alert_type}\n"
            f"Location: Ward {alert.ward or 'N/A'}\n"
            f"Loss: {alert.vegetation_loss_pct}%\n"
            f"Area: {alert.area_affected_ha}ha\n"
            f"View: {settings.FRONTEND_URL}/alerts/{alert.alert_id}"
        )
        
        return self.send_sms(recipient, message)


class WebhookNotificationService:
    """
    Webhook notification service
    Send HTTP POST requests to configured endpoints
    Free - works with Slack, Discord, Microsoft Teams, custom APIs
    """
    
    def send_webhook(self, url: str, payload: Dict[str, Any]) -> bool:
        """
        Send webhook POST request
        
        Args:
            url: Webhook URL
            payload: JSON payload to send
            
        Returns:
            bool: True if sent successfully
        """
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Webhook sent successfully to {url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook to {url}: {str(e)}")
            return False
    
    def send_alert_webhook(self, alert: Alert, webhook_url: str) -> bool:
        """
        Send alert notification via webhook
        
        Args:
            alert: Alert object
            webhook_url: Webhook URL
            
        Returns:
            bool: True if sent successfully
        """
        payload = {
            "alert_id": alert.alert_id,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
            "status": alert.status,
            "priority": alert.priority,
            "detection_date": alert.detection_date.isoformat(),
            "ward": alert.ward,
            "zone": alert.zone,
            "vegetation_loss_pct": alert.vegetation_loss_pct,
            "area_affected_ha": alert.area_affected_ha,
            "confidence_score": alert.confidence_score,
            "view_url": f"{settings.FRONTEND_URL}/alerts/{alert.alert_id}"
        }
        
        return self.send_webhook(webhook_url, payload)
    
    def send_slack_alert(self, alert: Alert, webhook_url: str) -> bool:
        """
        Send alert to Slack using webhook
        Get webhook URL: https://api.slack.com/messaging/webhooks
        
        Args:
            alert: Alert object
            webhook_url: Slack webhook URL
            
        Returns:
            bool: True if sent successfully
        """
        color = {
            'CRITICAL': '#dc2626',
            'HIGH': '#ea580c',
            'MEDIUM': '#f59e0b',
            'LOW': '#10b981'
        }.get(alert.severity, '#6b7280')
        
        payload = {
            "text": f"🚨 {alert.severity} Alert: {alert.alert_type}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Alert ID", "value": alert.alert_id, "short": True},
                        {"title": "Severity", "value": alert.severity, "short": True},
                        {"title": "Location", "value": f"Ward {alert.ward}, Zone {alert.zone}", "short": True},
                        {"title": "Vegetation Loss", "value": f"{alert.vegetation_loss_pct}%", "short": True},
                        {"title": "Area Affected", "value": f"{alert.area_affected_ha} ha", "short": True},
                        {"title": "Confidence", "value": f"{alert.confidence_score * 100:.1f}%" if alert.confidence_score else "N/A", "short": True},
                    ],
                    "actions": [
                        {
                            "type": "button",
                            "text": "View Alert",
                            "url": f"{settings.FRONTEND_URL}/alerts/{alert.alert_id}"
                        }
                    ]
                }
            ]
        }
        
        return self.send_webhook(webhook_url, payload)


class NotificationService:
    """
    Main notification service - coordinates all notification channels
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailNotificationService()
        self.sms_service = SMSNotificationService()
        self.webhook_service = WebhookNotificationService()
    
    def send_alert_notifications(
        self,
        alert: Alert,
        channels: List[str],
        recipients: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Send alert notifications via multiple channels
        
        Args:
            alert: Alert object
            channels: List of channels to use ['EMAIL', 'SMS', 'WEBHOOK']
            recipients: Dict with lists of recipients for each channel
                {
                    'emails': ['user@example.com'],
                    'phones': ['+919876543210'],
                    'webhooks': ['https://hooks.slack.com/...']
                }
                
        Returns:
            dict: Summary of sent notifications
        """
        results = {
            'total_sent': 0,
            'total_failed': 0,
            'details': []
        }
        
        # Send emails
        if 'EMAIL' in channels and recipients.get('emails'):
            for email in recipients['emails']:
                success = self.email_service.send_alert_email(alert, email)
                
                # Log notification
                self._log_notification(
                    alert_id=alert.id,
                    channel='EMAIL',
                    recipient=email,
                    success=success
                )
                
                if success:
                    results['total_sent'] += 1
                else:
                    results['total_failed'] += 1
                
                results['details'].append({
                    'channel': 'EMAIL',
                    'recipient': email,
                    'success': success
                })
        
        # Send SMS
        if 'SMS' in channels and recipients.get('phones'):
            for phone in recipients['phones']:
                success = self.sms_service.send_alert_sms(alert, phone)
                
                self._log_notification(
                    alert_id=alert.id,
                    channel='SMS',
                    recipient=phone,
                    success=success
                )
                
                if success:
                    results['total_sent'] += 1
                else:
                    results['total_failed'] += 1
                
                results['details'].append({
                    'channel': 'SMS',
                    'recipient': phone,
                    'success': success
                })
        
        # Send webhooks
        if 'WEBHOOK' in channels and recipients.get('webhooks'):
            for webhook in recipients['webhooks']:
                success = self.webhook_service.send_alert_webhook(alert, webhook)
                
                self._log_notification(
                    alert_id=alert.id,
                    channel='WEBHOOK',
                    recipient=webhook,
                    success=success
                )
                
                if success:
                    results['total_sent'] += 1
                else:
                    results['total_failed'] += 1
                
                results['details'].append({
                    'channel': 'WEBHOOK',
                    'recipient': webhook,
                    'success': success
                })
        
        # Update alert status if notifications sent
        if results['total_sent'] > 0:
            alert.status = 'NOTIFIED'
            alert.notified_at = datetime.utcnow()
            alert.notified_contacts = [
                d['recipient'] for d in results['details'] if d['success']
            ]
            self.db.commit()
        
        return results
    
    def _log_notification(
        self,
        alert_id: int,
        channel: str,
        recipient: str,
        success: bool
    ):
        """Log notification attempt to database"""
        notification = AlertNotification(
            alert_id=alert_id,
            channel=channel,
            recipient=recipient,
            delivery_status='DELIVERED' if success else 'FAILED'
        )
        self.db.add(notification)
        self.db.commit()
