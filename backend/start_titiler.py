#!/usr/bin/env python3
"""
TiTiler Core application with proper error handling and version compatibility.
NOW RUNS ON PORT 8001 to avoid conflict with Mumbai Geo-AI Backend.
"""

import os
import logging
from typing import Optional
import inspect

from fastapi import FastAPI
from titiler.core.factory import TilerFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Create the FastAPI app with proper metadata
    app = FastAPI(
        title="TiTiler Core API",
        description="Cloud Optimized GeoTIFF (COG) tile server for Mumbai Geo-AI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Create tiler factory with version-compatible parameters
    # Check what parameters TilerFactory accepts
    factory_signature = inspect.signature(TilerFactory.__init__)
    factory_params = list(factory_signature.parameters.keys())
    
    logger.info(f"Available TilerFactory parameters: {factory_params}")
    
    # Build kwargs based on available parameters
    tiler_kwargs = {}
    
    # Add parameters only if they exist in this version
    if 'router_prefix' in factory_params:
        tiler_kwargs['router_prefix'] = "/cog"
    if 'add_preview' in factory_params:
        tiler_kwargs['add_preview'] = True
    if 'add_part' in factory_params:
        tiler_kwargs['add_part'] = True
    if 'add_viewer' in factory_params:
        tiler_kwargs['add_viewer'] = True
    
    logger.info(f"Using TilerFactory with parameters: {tiler_kwargs}")
    
    # Create tiler factory
    tiler = TilerFactory(**tiler_kwargs)
    
    # Include the tiler router
    app.include_router(tiler.router, tags=["Cloud Optimized GeoTIFF"])
    
    # Add health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "titiler-core", "port": 8001}
    
    # Add root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "title": "TiTiler Core API for Mumbai Geo-AI",
            "description": "Cloud Optimized GeoTIFF tile server running on port 8001",
            "docs": "/docs",
            "health": "/health",
            "mumbai_api": "http://localhost:8000"
        }
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    # FIXED: Use port 8001 instead of 8000
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))  # Changed from 8000 to 8001
    workers = int(os.getenv("WORKERS", "1"))
    log_level = os.getenv("LOG_LEVEL", "info")
    
    logger.info(f"Starting TiTiler Core server on {host}:{port}")
    
    # Run the server
    uvicorn.run(
        "start_titiler:app",
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
        reload=False,  # Disable in production
        access_log=True
    )