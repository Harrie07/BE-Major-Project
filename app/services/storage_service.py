import os
import json
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional
from minio import Minio
from minio.error import S3Error
import xarray as xr
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file storage using MinIO (S3-compatible)"""
    
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        
        self.bucket_name = settings.MINIO_BUCKET_NAME
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Error creating bucket: {e}")
            raise
    
    def save_cog(self, data: xr.DataArray, filename: str) -> str:
        """
        Save xarray data as COG to storage
        
        Args:
            data: Input xarray DataArray
            filename: Output filename (should end with .tif)
            
        Returns:
            Public URL to the saved COG
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Save as COG using rio-cogeo
            from rio_cogeo.cogeo import cog_translate
            from rio_cogeo.profiles import cog_profiles
            
            # First save as regular GeoTIFF
            temp_regular = temp_path.replace(".tif", "_regular.tif")
            data.rio.to_raster(temp_regular)
            
            # Convert to COG
            profile = cog_profiles.get("lzw")
            profile.update({
                "BLOCKXSIZE": 512,
                "BLOCKYSIZE": 512,
                "COMPRESS": "LZW",
                "INTERLEAVE": "pixel"
            })
            
            cog_translate(
                temp_regular,
                temp_path,
                profile,
                in_memory=False,
                quiet=True
            )
            
            # Upload to MinIO
            object_name = f"cogs/{filename}"
            
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=temp_path,
                content_type="image/tiff"
            )
            
            # Generate public URL
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
            
            # Cleanup temporary files
            os.unlink(temp_path)
            if os.path.exists(temp_regular):
                os.unlink(temp_regular)
            
            logger.info(f"Saved COG: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error saving COG {filename}: {e}")
            # Cleanup on error
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            if 'temp_regular' in locals() and os.path.exists(temp_regular):
                os.unlink(temp_regular)
            raise
    
    def save_geojson(self, detections: List[Dict[str, Any]], filename: str) -> str:
        """
        Save detections as GeoJSON to storage
        
        Args:
            detections: List of detection dictionaries
            filename: Output filename (should end with .geojson)
            
        Returns:
            Public URL to the saved GeoJSON
        """
        try:
            # Create GeoJSON FeatureCollection
            features = []
            for detection in detections:
                feature = {
                    "type": "Feature",
                    "geometry": detection["geometry"],
                    "properties": {
                        key: value for key, value in detection.items() 
                        if key != "geometry"
                    }
                }
                features.append(feature)
            
            geojson_data = {
                "type": "FeatureCollection",
                "features": features,
                "metadata": {
                    "total_features": len(features),
                    "generated_at": datetime.utcnow().isoformat()
                }
            }
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix=".geojson", delete=False) as temp_file:
                json.dump(geojson_data, temp_file, indent=2)
                temp_path = temp_file.name
            
            # Upload to MinIO
            object_name = f"vectors/{filename}"
            
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=temp_path,
                content_type="application/geo+json"
            )
            
            # Generate public URL
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
            
            # Cleanup
            os.unlink(temp_path)
            
            logger.info(f"Saved GeoJSON: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error saving GeoJSON {filename}: {e}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def save_file(self, file_path: str, object_name: str, content_type: str = None) -> str:
        """
        Save a local file to storage
        
        Args:
            file_path: Path to local file
            object_name: Object name in storage
            content_type: MIME type
            
        Returns:
            Public URL to the saved file
        """
        try:
            self.client.fput_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=content_type
            )
            
            url = f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{object_name}"
            logger.info(f"Saved file: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}")
            raise
    
    def delete_file_from_url(self, url: str) -> bool:
        """Delete file from storage using its URL"""
        try:
            # Extract object name from URL
            # URL format: http://localhost:9000/bucket-name/object-name
            url_parts = url.split(f"/{self.bucket_name}/")
            if len(url_parts) != 2:
                logger.error(f"Invalid URL format: {url}")
                return False
            
            object_name = url_parts[1]
            
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Deleted file: {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file {url}: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in storage with optional prefix filter"""
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag,
                    "url": f"http://{settings.MINIO_ENDPOINT}/{self.bucket_name}/{obj.object_name}"
                })
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []


def _get_bbox_from_geometry(geometry: Dict[str, Any]) -> List[float]:
    """Extract bounding box from GeoJSON geometry"""
    try:
        from shapely.geometry import shape
        
        geom = shape(geometry)
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        
        return [bounds[0], bounds[1], bounds[2], bounds[3]]  # [min_lon, min_lat, max_lon, max_lat]
        
    except Exception as e:
        logger.error(f"Error extracting bbox: {e}")
        raise