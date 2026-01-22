from backend.app.database import SessionLocal
from backend.app.models import AlertRule

def seed_alert_rules():
    db = SessionLocal()
    
    rules = [
        AlertRule(
            rule_name="critical_mangrove_loss",
            min_vegetation_loss_pct=15.0,
            min_area_ha=2.0,
            min_confidence=0.75,
            zone_types=["CRZ-I", "CRZ-II"],
            severity="CRITICAL",
            notification_channels=["sms", "email", "dashboard"],
            recipient_emails=["bmc-commissioner@mumbai.gov.in"],
            recipient_phones=["+919876543210"],
            cooldown_hours=12
        ),
        AlertRule(
            rule_name="high_crz_violation",
            min_vegetation_loss_pct=10.0,
            min_area_ha=1.0,
            min_confidence=0.70,
            zone_types=["CRZ-I", "CRZ-II", "CRZ-III"],
            severity="HIGH",
            notification_channels=["email", "dashboard"],
            recipient_emails=["ward-officer@mumbai.gov.in"],
            cooldown_hours=24
        ),
        AlertRule(
            rule_name="moderate_vegetation_loss",
            min_vegetation_loss_pct=5.0,
            min_area_ha=0.5,
            min_confidence=0.65,
            zone_types=[],  # Any zone
            severity="MODERATE",
            notification_channels=["dashboard"],
            recipient_emails=[],
            cooldown_hours=48
        )
    ]
    
    for rule in rules:
        db.add(rule)
    db.commit()
    
    print(f"✅ Seeded {len(rules)} alert rules")

if __name__ == "__main__":
    seed_alert_rules()
