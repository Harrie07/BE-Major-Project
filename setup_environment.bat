# setup_environment.bat (Windows)
@echo off
echo Setting up Mumbai Geo-AI Backend environment...

REM Set PROJ_LIB for Windows
set PROJ_LIB=C:\Users\Acer\mumbai-geo-ai-backend\venv\Lib\site-packages\rasterio\proj_data

REM Set other environment variables
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_USER=mumbai_user
set POSTGRES_PASSWORD=janmoksathi
set POSTGRES_DB=mumbai_geo_ai
set REDIS_HOST=localhost
set REDIS_PORT=6379
set MINIO_ENDPOINT=localhost:9000
set TITILER_ENDPOINT=http://localhost:8001

echo Environment variables set successfully!
echo PROJ_LIB=%PROJ_LIB%
echo Ready to start services...

# ---

# setup_environment.sh (Linux/Mac)
#!/bin/bash
echo "Setting up Mumbai Geo-AI Backend environment..."

# Set PROJ_LIB for Linux/Mac
export PROJ_LIB="$(python -c 'import rasterio; print(rasterio.env.data_dir())')"

# Set other environment variables  
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=mumbai_user
export POSTGRES_PASSWORD=janmoksathi
export POSTGRES_DB=mumbai_geo_ai
export REDIS_HOST=localhost
export REDIS_PORT=6379
export MINIO_ENDPOINT=localhost:9000
export TITILER_ENDPOINT=http://localhost:8001

echo "Environment variables set successfully!"
echo "PROJ_LIB=$PROJ_LIB"
echo "Ready to start services..."

# ---

# Docker Commands Reference

# 1. BUILD CLEAN (if dependency conflicts)
# docker-compose build --no-cache

# 2. START ALL SERVICES
# docker-compose up -d

# 3. VIEW LOGS
# docker-compose logs -f app
# docker-compose logs -f titiler
# docker-compose logs -f worker

# 4. RESTART SPECIFIC SERVICE
# docker-compose restart app

# 5. ENTER CONTAINER FOR DEBUGGING
# docker-compose exec app bash
# docker-compose exec db psql -U mumbai_user -d mumbai_geo_ai

# 6. STOP ALL SERVICES
# docker-compose down

# 7. STOP AND REMOVE VOLUMES (CLEAN RESET)
# docker-compose down -v

# ---

# Local Development Commands

# 1. START MAIN API (Terminal 1)
# python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 2. START TITILER (Terminal 2) 
# python start_titiler.py

# 3. START REDIS WORKER (Terminal 3)
# rq worker ml_processing --url redis://localhost:6379/0

# 4. RUN TESTS
# pytest tests/ -v

# 5. CHECK API DOCS
# Open http://localhost:8000/docs (Main API)
# Open http://localhost:8001/docs (TiTiler)

# ---

# Database Commands

# 1. CREATE MIGRATION
# alembic revision --autogenerate -m "Description"

# 2. APPLY MIGRATIONS  
# alembic upgrade head

# 3. CONNECT TO LOCAL DB
# psql -h localhost -U mumbai_user -d mumbai_geo_ai

# 4. CONNECT TO DOCKER DB
# docker-compose exec db psql -U mumbai_user -d mumbai_geo_ai