#!/usr/bin/env python3
"""
Database Initialization Script for Mumbai Geo-AI Project

This script helps initialize the database with:
1. Running Alembic migrations
2. Creating sample data for development
3. Setting up protected zones for Mumbai
4. Creating admin user

Usage:
    python init_db.py --env development
    python init_db.py --env production --admin-email admin@example.com
"""

import asyncio
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
import os
import sys
from typing import Optional

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from passlib.context import CryptContext
from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from app.models.database import (
    User, AreaOfInterest, ProtectedZone, Job, Detection,
    JobStatus, DetectionType, ZoneType, Base
)
from app.core.config import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_database_url(env: str) -> str:
    """Create database URL based on environment"""
    if env == "development":
        return "postgresql://postgres:password@localhost:5432/mumbai_geoai_dev"
    elif env == "test":
        return "postgresql://postgres:password@localhost:5432/mumbai_geoai_test"
    elif env == "production":
        # In production, get from environment variables
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "mumbai_geoai")
        
        if not password:
            raise ValueError("DB_PASSWORD environment variable is required for production")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"Unknown environment: {env}")


def run_alembic_upgrade(database_url: str):
    """Run Alembic migrations to upgrade database to head"""
    print("Running Alembic migrations...")
    
    # Create Alembic config
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "app/db/migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    
    # Run upgrade to head
    try:
        command.upgrade(alembic_cfg, "head")
        print("✅ Database migrations completed successfully")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise


def create_admin_user(session, email: str, password: str = "admin123") -> User:
    """Create admin user if not exists"""
    existing_user = session.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"✅ Admin user already exists: {email}")
        return existing_user
    
    hashed_password = pwd_context.hash(password)
    admin_user = User(
        email=email,
        username="admin",
        hashed_password=hashed_password,
        is_active=True,
        is_admin=True
    )
    session.add(admin_user)
    session.commit()
    print(f"✅ Created admin user: {email}")
    return admin_user


def create_sample_aoi(session, user: User) -> AreaOfInterest:
    """Create sample Area of Interest in Mumbai"""
    # Sample AOI covering part of South Mumbai (approximately Colaba area)
    mumbai_polygon = Polygon([
        [72.8081, 18.9067],  # Southwest
        [72.8381, 18.9067],  # Southeast
        [72.8381, 18.9367],  # Northeast
        [72.8081, 18.9367],  # Northwest
        [72.8081, 18.9067]   # Close polygon
    ])
    
    aoi = AreaOfInterest(
        name="South Mumbai - Colaba Area",
        description="Sample area for change detection testing in South Mumbai",
        geometry=from_shape(mumbai_polygon),
        user_id=user.id
    )
    session.add(aoi)
    session.commit()
    print("✅ Created sample Area of Interest")
    return aoi


def create_protected_zones(session):
    """Create sample protected zones in Mumbai"""
    protected_zones = [
        {
            "name": "Sanjay Gandhi National Park",
            "zone_type": ZoneType.FOREST,
            "geometry": Polygon([
                [72.8869, 19.2094],
                [72.9269, 19.2094],
                [72.9269, 19.2494],
                [72.8869, 19.2494],
                [72.8869, 19.2094]
            ]),
            "regulation_details": "National Park under Wildlife Protection Act",
            "authority": "Maharashtra Forest Department",
            "notification_number": "WLP-1996-001"
        },
        {
            "name": "Mahim Creek Mangroves",
            "zone_type": ZoneType.WETLAND,
            "geometry": Polygon([
                [72.8469, 19.0394],
                [72.8669, 19.0394],
                [72.8669, 19.0594],
                [72.8469, 19.0594],
                [72.8469, 19.0394]
            ]),
            "regulation_details": "Protected mangrove area under CRZ regulations",
            "authority": "Maharashtra Coastal Zone Management Authority",
            "notification_number": "CRZ-2005-012"
        },
        {
            "name": "Gateway of India Heritage Zone",
            "zone_type": ZoneType.HERITAGE,
            "geometry": Polygon([
                [72.8324, 18.9218],
                [72.8364, 18.9218],
                [72.8364, 18.9258],
                [72.8324, 18.9258],
                [72.8324, 18.9218]
            ]),
            "regulation_details": "Heritage structure protection zone",
            "authority": "Archaeological Survey of India",
            "notification_number": "ASI-MH-2010-005"
        },
        {
            "name": "Bandra-Worli Sea Link Buffer Zone",
            "zone_type": ZoneType.COASTAL,
            "geometry": Polygon([
                [72.8169, 19.0294],
                [72.8269, 19.0294],
                [72.8269, 19.0394],
                [72.8169, 19.0394],
                [72.8169, 19.0294]
            ]),
            "regulation_details": "Coastal regulation zone around sea link",
            "authority": "Mumbai Port Trust",
            "notification_number": "MPT-2008-018"
        }
    ]
    
    for zone_data in protected_zones:
        existing_zone = session.query(ProtectedZone).filter(
            ProtectedZone.name == zone_data["name"]
        ).first()
        
        if not existing_zone:
            zone = ProtectedZone(
                name=zone_data["name"],
                zone_type=zone_data["zone_type"],
                geometry=from_shape(zone_data["geometry"]),
                regulation_details=zone_data["regulation_details"],
                authority=zone_data["authority"],
                notification_number=zone_data["notification_number"],
                effective_date=date(2010, 1, 1),
                is_active=True
            )
            session.add(zone)
    
    session.commit()
    print("✅ Created sample protected zones")


def create_sample_job(session, aoi: AreaOfInterest, user: User) -> Job:
    """Create a sample completed job with detections"""
    job = Job(
        aoi_id=aoi.id,
        user_id=user.id,
        status=JobStatus.COMPLETED,
        start_date=date.today() - timedelta(days=365),  # 1 year ago
        end_date=date.today() - timedelta(days=30),     # 1 month ago
        cloud_threshold=0.2,
        change_threshold=0.5,
        progress=100,
        result_summary={
            "total_detections": 3,
            "high_confidence_detections": 2,
            "protected_zone_violations": 1,
            "total_area_changed_sqm": 5000
        },
        started_at=datetime.utcnow() - timedelta(hours=2),
        completed_at=datetime.utcnow() - timedelta(hours=1)
    )
    session.add(job)
    session.commit()
    
    # Create sample detections for this job
    detections = [
        {
            "geometry": Polygon([
                [72.8181, 18.9167],
                [72.8191, 18.9167],
                [72.8191, 18.9177],
                [72.8181, 18.9177],
                [72.8181, 18.9167]
            ]),
            "detection_type": DetectionType.NEW_CONSTRUCTION,
            "confidence_score": 0.85,
            "area_sqm": 2000
        },
        {
            "geometry": Polygon([
                [72.8281, 18.9267],
                [72.8291, 18.9267],
                [72.8291, 18.9277],
                [72.8281, 18.9277],
                [72.8281, 18.9267]
            ]),
            "detection_type": DetectionType.NEW_CONSTRUCTION,
            "confidence_score": 0.72,
            "area_sqm": 1500
        },
        {
            "geometry": Polygon([
                [72.8381, 18.9167],
                [72.8391, 18.9167],
                [72.8391, 18.9177],
                [72.8381, 18.9177],
                [72.8381, 18.9167]
            ]),
            "detection_type": DetectionType.MODIFIED,
            "confidence_score": 0.68,
            "area_sqm": 1500
        }
    ]
    
    for det_data in detections:
        detection = Detection(
            job_id=job.id,
            geometry=from_shape(det_data["geometry"]),
            detection_type=det_data["detection_type"],
            confidence_score=det_data["confidence_score"],
            area_sqm=det_data["area_sqm"],
            attributes={
                "building_type": "residential",
                "estimated_floors": 3
            }
        )
        session.add(detection)
    
    session.commit()
    print("✅ Created sample job with detections")
    return job


def verify_database_setup(session):
    """Verify that database setup was successful"""
    print("\n🔍 Verifying database setup...")
    
    # Check table counts
    counts = {
        "Users": session.query(User).count(),
        "Areas of Interest": session.query(AreaOfInterest).count(),
        "Protected Zones": session.query(ProtectedZone).count(),
        "Jobs": session.query(Job).count(),
        "Detections": session.query(Detection).count(),
    }
    
    print("📊 Database Statistics:")
    for table, count in counts.items():
        print(f"  • {table}: {count} records")
    
    # Test spatial queries
    try:
        # Test PostGIS functionality
        result = session.execute(text("SELECT PostGIS_Version()")).scalar()
        print(f"✅ PostGIS Version: {result}")
        
        # Test spatial index
        aoi = session.query(AreaOfInterest).first()
        if aoi:
            session.execute(text(
                "SELECT ST_Area(ST_Transform(geometry, 3857)) FROM areas_of_interest WHERE id = :id"
            ), {"id": str(aoi.id)}).scalar()
            print("✅ Spatial queries working correctly")
        
    except Exception as e:
        print(f"⚠️ Spatial query test failed: {e}")
    
    print("✅ Database verification completed")


def main():
    """Main function to initialize database"""
    parser = argparse.ArgumentParser(description="Initialize Mumbai Geo-AI database")
    parser.add_argument(
        "--env", 
        choices=["development", "test", "production"],
        default="development",
        help="Environment to initialize"
    )
    parser.add_argument(
        "--admin-email",
        default="admin@mumbai-geoai.com",
        help="Admin user email address"
    )
    parser.add_argument(
        "--admin-password",
        default="admin123",
        help="Admin user password (use strong password for production)"
    )
    parser.add_argument(
        "--skip-sample-data",
        action="store_true",
        help="Skip creating sample data"
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing database before creating (WARNING: destructive)"
    )
    
    args = parser.parse_args()
    
    # Validate production settings
    if args.env == "production":
        if args.admin_password == "admin123":
            print("⚠️ WARNING: Using default password in production is not secure!")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                return
    
    try:
        # Create database URL
        database_url = create_database_url(args.env)
        print(f"🚀 Initializing {args.env} database...")
        
        # Create engine and session
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Drop existing database if requested
        if args.drop_existing:
            print("⚠️ Dropping existing database...")
            Base.metadata.drop_all(bind=engine)
        
        # Run migrations
        run_alembic_upgrade(database_url)
        
        # Create session for data operations
        session = SessionLocal()
        
        try:
            # Create admin user
            admin_user = create_admin_user(session, args.admin_email, args.admin_password)
            
            # Create sample data (unless skipped)
            if not args.skip_sample_data and args.env != "production":
                print("📝 Creating sample data...")
                
                # Create sample AOI
                sample_aoi = create_sample_aoi(session, admin_user)
                
                # Create protected zones
                create_protected_zones(session)
                
                # Create sample job
                create_sample_job(session, sample_aoi, admin_user)
            
            # Verify setup
            verify_database_setup(session)
            
            print(f"\n🎉 Database initialization completed successfully!")
            print(f"📧 Admin login: {args.admin_email}")
            if args.env != "production":
                print(f"🔑 Admin password: {args.admin_password}")
            
        finally:
            session.close()
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()