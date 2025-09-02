# test_job_creation.py
"""
Quick test script to verify job creation works
"""
from datetime import datetime, timedelta
from app.services.job_service import JobService
from app.models.schemas import JobCreate, SatelliteType
from app.db.database import SessionLocal

async def test_job_creation():
    """Test creating a job and verify it appears in database"""
    
    # Create test job data
    job_data = JobCreate(
        name="Test Change Detection Job",  # Now included in schema
        aoi_id="test-aoi-123",
        date_from=datetime.utcnow() - timedelta(days=30),
        date_to=datetime.utcnow(),
        cloud_cover_threshold=15.0,
        satellite_type=SatelliteType.SENTINEL2
    )
    
    # Create job
    db = SessionLocal()
    try:
        job_service = JobService()
        new_job = await job_service.create_job(db, job_data)
        
        print(f"✅ Job created successfully!")
        print(f"   ID: {new_job.id}")
        print(f"   Name: {new_job.name}")
        print(f"   Status: {new_job.status}")
        print(f"   Created: {new_job.created_at}")
        
        return new_job.id
        
    finally:
        db.close()

# Run the test
if __name__ == "__main__":
    import asyncio
    job_id = asyncio.run(test_job_creation())
    
    print(f"\n🔍 Now check in psql:")
    print(f"   SELECT id, name, status, created_at FROM jobs WHERE id = {job_id};")