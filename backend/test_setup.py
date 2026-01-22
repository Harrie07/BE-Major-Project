#!/usr/bin/env python3
"""
Test script to verify all services are working on Windows
"""



import sys
import os
import psycopg2
import redis
from minio import Minio
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

def test_postgresql():
    """Test PostgreSQL connection and PostGIS"""
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            database=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            port=settings.POSTGRES_PORT
        )
        cursor = conn.cursor()
        
        # Test PostGIS
        cursor.execute("SELECT PostGIS_Version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL with PostGIS connected: {version}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("Make sure PostgreSQL service is running:")
        print("  net start postgresql-x64-15")
        return False

def test_redis():
    """Test Redis connection"""
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=5
        )
        r.ping()
        print("✅ Redis connected successfully")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("Make sure Redis is installed and running:")
        print("  Download from: https://github.com/tporadowski/redis/releases")
        print("  Or use WSL: sudo service redis-server start")
        return False

def test_minio():
    """Test MinIO connection"""
    try:
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        
        # Try to list buckets
        buckets = client.list_buckets()
        print(f"✅ MinIO connected successfully. Buckets: {[b.name for b in buckets]}")
        
        # Create our bucket if it doesn't exist
        bucket_name = settings.MINIO_BUCKET_NAME
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"✅ Created bucket: {bucket_name}")
        else:
            print(f"✅ Bucket {bucket_name} already exists")
            
        return True
    except Exception as e:
        print(f"❌ MinIO connection failed: {e}")
        print("Make sure MinIO is running:")
        print("  minio.exe server minio-data --console-address \":9001\"")
        return False

def test_titiler():
    """Test Titiler service"""
    try:
        response = requests.get(f"{settings.TITILER_ENDPOINT}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ Titiler service is running")
            return True
        else:
            print(f"❌ Titiler service returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Titiler connection failed: {e}")
        print("Make sure Titiler is running:")
        print("  uvicorn titiler.core.main:app --host 0.0.0.0 --port 8001")
        return False

def check_windows_services():
    """Check Windows services status"""
    import subprocess
    
    print("🔍 Checking Windows services...")
    
    services_to_check = [
        "postgresql-x64-16",
        # "Redis"     
    ]
    
    for service in services_to_check:
        try:
            result = subprocess.run(
                ["sc", "query", service], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if "RUNNING" in result.stdout:
                print(f"✅ {service} service is running")
            else:
                print(f"⚠️ {service} service is not running")
        except:
            print(f"❓ Could not check {service} service status")

def main():
    """Run all tests"""
    print("🔄 Testing Mumbai Geo-AI Backend Setup (Windows)...\n")
    
    # Check services first
    check_windows_services()
    print()
    
    tests = [
        ("PostgreSQL + PostGIS", test_postgresql),
        ("Redis", test_redis),
        ("MinIO", test_minio),
        ("Titiler", test_titiler),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing {name}...")
        results.append(test_func())
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*60)
    print(f"Setup Test Results: {passed}/{total} services working")
    
    if passed == total:
        print("🎉 All services are ready! You can proceed with the backend development.")
        print("\nQuick start commands:")
        print("  start_services.bat  - Start all services")
        print("  stop_services.bat   - Stop all services")
    else:
        print("⚠️  Some services need attention before proceeding.")
        print("\nTroubleshooting:")
        print("  1. Make sure you ran start_services.bat as Administrator")
        print("  2. Check Windows Firewall settings")
        print("  3. Verify PostgreSQL and Redis are properly installed")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())