# 🗄️ Database Setup Guide - Mumbai Geo-AI Project

## 📋 What We've Built

### ✅ **Step 15 - Database Foundation - COMPLETED**

We have successfully created:

1. **Complete SQLAlchemy Models** (9 tables with spatial support)
2. **Initial Database Migration** (creates all tables with indexes)
3. **Database Initialization Script** (with sample Mumbai data)
4. **Full Requirements** (145+ geospatial/ML dependencies)

### 🏗️ Database Schema Overview

Our database includes these **9 core tables**:

| Table | Purpose | Key Features |
|-------|---------|-------------|
| **users** | Authentication & user management | JWT auth, admin roles |
| **areas_of_interest** | AOIs for change detection | PostGIS geometry, user ownership |
| **jobs** | Change detection job tracking | Status, progress, results |
| **detections** | ML-detected changes | Confidence scores, geometry |
| **protected_zones** | Mumbai protected areas | Zone types, regulations |
| **detection_violations** | Violations in protected zones | Severity, overlap analysis |
| **satellite_images** | Image metadata tracking | STAC URLs, cloud coverage |
| **alerts** | User notifications | Email/SMS status |
| **system_logs** | Audit trail | User actions, API calls |

---

## 🚀 Quick Setup Instructions

### Step 1: Install PostgreSQL + PostGIS

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgis postgresql-14-postgis-3
sudo systemctl start postgresql
```

**macOS:**
```bash
brew install postgresql postgis
brew services start postgresql
```

**Windows:**
- Download PostgreSQL from [official site](https://www.postgresql.org/download/windows/)
- Download PostGIS from [PostGIS downloads](https://postgis.net/windows_downloads/)

### Step 2: Create Database

```bash
# Access PostgreSQL as superuser
sudo -u postgres psql

# Create database and user
CREATE DATABASE mumbai_geoai_dev;
CREATE USER geoai_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE mumbai_geoai_dev TO geoai_user;

# Enable PostGIS
\c mumbai_geoai_dev
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
\q
```

### Step 3: Install Python Dependencies

```bash
# Install all database dependencies
pip install -r requirements-db.txt

# Or install core dependencies only:
pip install sqlalchemy==2.0.23 alembic==1.12.1 psycopg2-binary==2.9.9 geoalchemy2==0.14.2 shapely==2.0.2
```

### Step 4: Configure Environment

Create/update your `.env` file:
```bash
# Database Configuration
DB_USER=geoai_user
DB_PASSWORD=secure_password_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mumbai_geoai_dev

# Full Database URL
DATABASE_URL=postgresql://geoai_user:secure_password_here@localhost:5432/mumbai_geoai_dev

# Security (for Step 16)
SECRET_KEY=your-secret-key-minimum-32-characters
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional: External Services
REDIS_URL=redis://localhost:6379
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### Step 5: Run Database Migration

```bash
# Navigate to your project root
cd /path/to/mumbai-geoai-project

# Run the database initialization
python scripts/init_db.py --env development --admin-email admin@yourcompany.com

# This will:
# ✅ Run Alembic migration (create all tables)
# ✅ Create admin user
# ✅ Add sample AOI in Mumbai
# ✅ Create protected zones (parks, heritage sites)
# ✅ Generate sample detection job with results
```

---

## 📊 Database Schema Details

### 🔐 User Management
```sql
-- Users table with authentication
users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  username VARCHAR(100) UNIQUE NOT NULL,
  hashed_password VARCHAR(255) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  is_admin BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 🗺️ Spatial Tables
```sql
-- Areas of Interest with PostGIS geometry
areas_of_interest (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  geometry GEOMETRY(POLYGON, 4326) NOT NULL,  -- WGS84
  user_id INTEGER REFERENCES users(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Spatial index for fast geometric queries
CREATE INDEX ix_aoi_geometry ON areas_of_interest USING GIST (geometry);
```

### 🤖 Job Processing
```sql
-- Change detection jobs
jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aoi_id UUID REFERENCES areas_of_interest(id),
  user_id INTEGER REFERENCES users(id),
  status jobstatus DEFAULT 'PENDING',  -- PENDING, RUNNING, COMPLETED, FAILED
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  cloud_threshold FLOAT DEFAULT 0.2,
  change_threshold FLOAT DEFAULT 0.5,
  progress INTEGER DEFAULT 0,  -- 0-100%
  result_summary JSON,
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 🎯 Detection Results
```sql
-- ML detection results
detections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES jobs(id),
  geometry GEOMETRY(POLYGON, 4326) NOT NULL,
  detection_type detectiontype NOT NULL,  -- NEW_CONSTRUCTION, DEMOLISHED, etc.
  confidence_score FLOAT NOT NULL,
  area_sqm FLOAT NOT NULL,
  before_image_url VARCHAR(512),
  after_image_url VARCHAR(512),
  attributes JSON,  -- Additional ML model outputs
  is_verified BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 🛡️ Protected Zones (Mumbai Specific)

Our initialization script creates **4 sample protected zones**:

### 1. Sanjay Gandhi National Park
- **Type**: FOREST
- **Location**: Borivali, Mumbai
- **Regulation**: Wildlife Protection Act
- **Authority**: Maharashtra Forest Department

### 2. Mahim Creek Mangroves  
- **Type**: WETLAND
- **Location**: Mahim, Mumbai
- **Regulation**: Coastal Regulation Zone (CRZ)
- **Authority**: Maharashtra Coastal Zone Management Authority

### 3. Gateway of India Heritage Zone
- **Type**: HERITAGE
- **Location**: Colaba, Mumbai
- **Regulation**: Heritage structure protection
- **Authority**: Archaeological Survey of India

### 4. Bandra-Worli Sea Link Buffer Zone
- **Type**: COASTAL
- **Location**: Between Bandra and Worli
- **Regulation**: Coastal regulation around infrastructure
- **Authority**: Mumbai Port Trust

---

## 🧪 Testing Your Database

### Verify Installation
```bash
python -c "
from sqlalchemy import create_engine, text
from app.models.database import User, AreaOfInterest, Job

# Test connection
engine = create_engine('your_database_url_here')
with engine.connect() as conn:
    # Test PostGIS
    result = conn.execute(text('SELECT PostGIS_Version();'))
    print('✅ PostGIS Version:', result.scalar())
    
    # Test spatial query
    result = conn.execute(text('SELECT COUNT(*) FROM areas_of_interest;'))
    print('✅ AOI Count:', result.scalar())
    
    print('🎉 Database setup successful!')
"
```

### Sample Queries
```python
from app.models.database import User, AreaOfInterest, Detection
from sqlalchemy.orm import sessionmaker

# Get all high-confidence detections
high_conf_detections = session.query(Detection).filter(
    Detection.confidence_score >= 0.8
).all()

# Get AOIs near a point (spatial query)
from geoalchemy2 import func
nearby_aois = session.query(AreaOfInterest).filter(
    func.ST_DWithin(
        AreaOfInterest.geometry,
        func.ST_Point(72.8777, 19.0760),  # Mumbai coordinates
        0.01  # ~1km radius
    )
).all()
```

---

## 📈 What's Next: Step 16

Now that our database is ready, we can move to **Step 16: Configuration & Security**:

1. **`app/core/config.py`** - Environment settings
2. **`app/core/security.py`** - JWT authentication
3. **Update FastAPI** - Wire database sessions
4. **Test APIs** - Full integration testing

---

## 🆘 Troubleshooting

### Common Issues

**PostGIS Extension Error:**
```bash
# Solution: Install PostGIS properly
sudo apt install postgresql-14-postgis-3
sudo -u postgres psql -d mumbai_geoai_dev -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

**Permission Denied:**
```bash
# Solution: Grant proper permissions
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE mumbai_geoai_dev TO geoai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO geoai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO geoai_user;
```

**Migration Fails:**
```bash
# Solution: Reset Alembic
rm -rf app/db/migrations/versions/*.py
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

**Python Import Errors:**
```bash
# Solution: Install missing dependencies
pip install -r requirements-db.txt
# or install individually:
pip install sqlalchemy alembic psycopg2-binary geoalchemy2
```

---

## ✅ Success Checklist

- [ ] PostgreSQL installed and running
- [ ] PostGIS extension enabled
- [ ] Database and user created
- [ ] Python dependencies installed
- [ ] Environment variables configured
- [ ] Migration script executed successfully
- [ ] Sample data created
- [ ] Spatial queries working
- [ ] Admin user can login

Once all items are checked, you're ready for **Step 16: Configuration & Security**! 🚀