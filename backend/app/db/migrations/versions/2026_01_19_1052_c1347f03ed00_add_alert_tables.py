"""add_alert_tables

Revision ID: c1347f03ed00
Revises: <put the previous revision ID here>
Create Date: 2026-01-19 10:52

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c1347f03ed00'
down_revision = '001_initial_tables' # Change this to your previous migration ID if exists
branch_labels = None
depends_on = None


def upgrade():
    # Create alerts table
    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            alert_id VARCHAR(100) UNIQUE NOT NULL,
            job_id INTEGER REFERENCES jobs(id),
            detection_date TIMESTAMP NOT NULL DEFAULT NOW(),
            aoi GEOMETRY(POLYGON, 4326) NOT NULL,
            ward VARCHAR(50),
            zone VARCHAR(50),
            severity VARCHAR(20) NOT NULL,
            alert_type VARCHAR(50) NOT NULL,
            vegetation_loss_pct FLOAT,
            area_affected_ha FLOAT,
            confidence_score FLOAT,
            status VARCHAR(20) DEFAULT 'PENDING',
            priority INTEGER DEFAULT 3,
            notified_at TIMESTAMP,
            notified_contacts TEXT[],
            acknowledged_at TIMESTAMP,
            acknowledged_by VARCHAR(200),
            resolution_notes TEXT,
            resolved_at TIMESTAMP,
            detection_image_url VARCHAR(500),
            report_pdf_url VARCHAR(500),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_alert_id ON alerts(alert_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_spatial ON alerts USING GIST(aoi);
    """)
    
    # Create alert_rules table
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id SERIAL PRIMARY KEY,
            rule_name VARCHAR(100) UNIQUE NOT NULL,
            min_vegetation_loss_pct FLOAT,
            min_area_ha FLOAT,
            min_confidence FLOAT,
            zone_types TEXT[],
            severity VARCHAR(20),
            notification_channels TEXT[],
            recipient_emails TEXT[],
            recipient_phones TEXT[],
            cooldown_hours INTEGER DEFAULT 24,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create alert_notifications table
    op.execute("""
        CREATE TABLE IF NOT EXISTS alert_notifications (
            id SERIAL PRIMARY KEY,
            alert_id INTEGER REFERENCES alerts(id),
            channel VARCHAR(20),
            recipient VARCHAR(200),
            sent_at TIMESTAMP DEFAULT NOW(),
            delivery_status VARCHAR(20),
            message_body TEXT,
            response_received TEXT
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS alert_notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
