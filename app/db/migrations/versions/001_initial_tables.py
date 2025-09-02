"""Initial migration: Create all core tables

Revision ID: 001_initial_tables
Revises: 
Create Date: 2025-08-29 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '001_initial_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    
    # Create custom enum types
    job_status_enum = postgresql.ENUM(
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
        name='jobstatus',
        create_type=False
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)
    
    detection_type_enum = postgresql.ENUM(
        'NEW_CONSTRUCTION', 'DEMOLISHED', 'MODIFIED', 'UNKNOWN',
        name='detectiontype',
        create_type=False
    )
    detection_type_enum.create(op.get_bind(), checkfirst=True)
    
    zone_type_enum = postgresql.ENUM(
        'FOREST', 'WETLAND', 'COASTAL', 'HERITAGE', 'NO_DEVELOPMENT',
        name='zonetype',
        create_type=False
    )
    zone_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    
    # Create areas_of_interest table
    op.create_table(
        'areas_of_interest',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('geometry', geoalchemy2.Geometry('POLYGON', srid=4326), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_aoi_geometry', 'areas_of_interest', ['geometry'], postgresql_using='gist')
    op.create_index(op.f('ix_areas_of_interest_name'), 'areas_of_interest', ['name'])
    op.create_index(op.f('ix_areas_of_interest_user_id'), 'areas_of_interest', ['user_id'])
    
    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aoi_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', job_status_enum, nullable=False, default='PENDING'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('cloud_threshold', sa.Float(), nullable=False, default=0.2),
        sa.Column('change_threshold', sa.Float(), nullable=False, default=0.5),
        sa.Column('priority', sa.Integer(), nullable=False, default=1),
        sa.Column('progress', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['aoi_id'], ['areas_of_interest.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_aoi_id'), 'jobs', ['aoi_id'])
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'])
    op.create_index(op.f('ix_jobs_user_id'), 'jobs', ['user_id'])
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'])
    
    # Create protected_zones table
    op.create_table(
        'protected_zones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('zone_type', zone_type_enum, nullable=False),
        sa.Column('geometry', geoalchemy2.Geometry('MULTIPOLYGON', srid=4326), nullable=False),
        sa.Column('regulation_details', sa.Text(), nullable=True),
        sa.Column('authority', sa.String(length=255), nullable=True),
        sa.Column('notification_number', sa.String(length=100), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_protected_zones_geometry', 'protected_zones', ['geometry'], postgresql_using='gist')
    op.create_index(op.f('ix_protected_zones_name'), 'protected_zones', ['name'])
    op.create_index(op.f('ix_protected_zones_zone_type'), 'protected_zones', ['zone_type'])
    op.create_index(op.f('ix_protected_zones_is_active'), 'protected_zones', ['is_active'])
    
    # Create detections table
    op.create_table(
        'detections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('geometry', geoalchemy2.Geometry('POLYGON', srid=4326), nullable=False),
        sa.Column('detection_type', detection_type_enum, nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('area_sqm', sa.Float(), nullable=False),
        sa.Column('before_image_url', sa.String(length=512), nullable=True),
        sa.Column('after_image_url', sa.String(length=512), nullable=True),
        sa.Column('change_mask_url', sa.String(length=512), nullable=True),
        sa.Column('attributes', sa.JSON(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('verified_by_user_id', sa.Integer(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detections_geometry', 'detections', ['geometry'], postgresql_using='gist')
    op.create_index(op.f('ix_detections_job_id'), 'detections', ['job_id'])
    op.create_index(op.f('ix_detections_detection_type'), 'detections', ['detection_type'])
    op.create_index(op.f('ix_detections_confidence_score'), 'detections', ['confidence_score'])
    op.create_index(op.f('ix_detections_is_verified'), 'detections', ['is_verified'])
    
    # Create detection_violations table (for detections in protected zones)
    op.create_table(
        'detection_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('detection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('protected_zone_id', sa.Integer(), nullable=False),
        sa.Column('violation_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False, default='MEDIUM'),
        sa.Column('overlap_area_sqm', sa.Float(), nullable=False),
        sa.Column('overlap_percentage', sa.Float(), nullable=False),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, default=True),
        sa.Column('flagged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['protected_zone_id'], ['protected_zones.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_detection_violations_detection_id'), 'detection_violations', ['detection_id'])
    op.create_index(op.f('ix_detection_violations_protected_zone_id'), 'detection_violations', ['protected_zone_id'])
    op.create_index(op.f('ix_detection_violations_is_flagged'), 'detection_violations', ['is_flagged'])
    op.create_index(op.f('ix_detection_violations_severity'), 'detection_violations', ['severity'])
    
    # Create satellite_images table (for tracking processed images)
    op.create_table(
        'satellite_images',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_date', sa.Date(), nullable=False),
        sa.Column('satellite', sa.String(length=50), nullable=False),
        sa.Column('scene_id', sa.String(length=100), nullable=False),
        sa.Column('cloud_coverage', sa.Float(), nullable=False),
        sa.Column('geometry', geoalchemy2.Geometry('POLYGON', srid=4326), nullable=False),
        sa.Column('stac_item_url', sa.String(length=512), nullable=True),
        sa.Column('cog_url', sa.String(length=512), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=512), nullable=True),
        sa.Column('processing_status', sa.String(length=50), nullable=False, default='PENDING'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_satellite_images_geometry', 'satellite_images', ['geometry'], postgresql_using='gist')
    op.create_index(op.f('ix_satellite_images_job_id'), 'satellite_images', ['job_id'])
    op.create_index(op.f('ix_satellite_images_image_date'), 'satellite_images', ['image_date'])
    op.create_index(op.f('ix_satellite_images_satellite'), 'satellite_images', ['satellite'])
    op.create_index(op.f('ix_satellite_images_scene_id'), 'satellite_images', ['scene_id'], unique=True)
    
    # Create alerts table (for notifications)
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('detection_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, default='INFO'),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
        sa.Column('email_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('sms_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_user_id'), 'alerts', ['user_id'])
    op.create_index(op.f('ix_alerts_alert_type'), 'alerts', ['alert_type'])
    op.create_index(op.f('ix_alerts_severity'), 'alerts', ['severity'])
    op.create_index(op.f('ix_alerts_is_read'), 'alerts', ['is_read'])
    op.create_index(op.f('ix_alerts_created_at'), 'alerts', ['created_at'])
    
    # Create system_logs table (for audit trail)
    op.create_table(
        'system_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_logs_user_id'), 'system_logs', ['user_id'])
    op.create_index(op.f('ix_system_logs_action'), 'system_logs', ['action'])
    op.create_index(op.f('ix_system_logs_resource_type'), 'system_logs', ['resource_type'])
    op.create_index(op.f('ix_system_logs_created_at'), 'system_logs', ['created_at'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('system_logs')
    op.drop_table('alerts')
    op.drop_table('satellite_images')
    op.drop_table('detection_violations')
    op.drop_table('detections')
    op.drop_table('protected_zones')
    op.drop_table('jobs')
    op.drop_table('areas_of_interest')
    op.drop_table('users')
    
    # Drop custom enum types
    op.execute('DROP TYPE IF EXISTS zonetype')
    op.execute('DROP TYPE IF EXISTS detectiontype')
    op.execute('DROP TYPE IF EXISTS jobstatus')