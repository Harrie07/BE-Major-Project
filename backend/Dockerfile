# Dockerfile

# Use Python 3.11 slim for better compatibility and faster builds
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for geospatial libraries (GDAL, Proj, GEOS)
# These are often prerequisites for rasterio, shapely, fiona, geopandas
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    libproj-dev \
    proj-data \
    libgeos-dev \
    libspatialindex-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for GDAL and PROJ (important for rasterio)
# Point PROJ_LIB to the system-installed data, not the one from rasterio wheel initially
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV PROJ_LIB=/usr/share/proj
ENV GDAL_DATA=/usr/share/gdal
ENV PYTHONPATH=/app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
# Use --break-system-packages cautiously, but often needed in slim images with system deps
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install additional geospatial Python packages that need system libs
# These often fail if installed via requirements.txt alone due to build dependencies
RUN pip install --no-cache-dir \
    rasterio==1.3.9 \
    geopandas==0.14.1 \
    shapely==2.0.2 \
    fiona==1.9.5 \
    pyproj==3.6.1

# Copy the rest of the application code
COPY . .

# Create necessary directories (if your app needs them)
RUN mkdir -p /app/data /app/uploads /app/outputs /app/logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - runs your Mumbai Geo-AI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
