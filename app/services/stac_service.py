import planetary_computer
import pystac_client
import stackstac
import xarray as xr
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
import logging
from shapely.geometry import box

from app.core.config import settings

logger = logging.getLogger(__name__)


class STACService:
    """Service for fetching satellite imagery from Microsoft Planetary Computer"""
    
    def __init__(self):
        # Sign with planetary computer if subscription key is available
        if settings.PC_SUBSCRIPTION_KEY:
            planetary_computer.settings.set_subscription_key(settings.PC_SUBSCRIPTION_KEY)
        
        # Initialize STAC client
        self.catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace
        )
    
    def search_imagery(
        self,
        bbox: List[float],  # [min_lon, min_lat, max_lon, max_lat]
        date_from: datetime,
        date_to: datetime,
        collections: List[str] = ["sentinel-2-l2a"],
        cloud_cover_max: float = 20.0,
        max_items: int = 10
    ) -> List[Dict]:
        """
        Search for satellite imagery using STAC
        
        Args:
            bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
            date_from: Start date
            date_to: End date
            collections: STAC collections to search
            cloud_cover_max: Maximum cloud cover percentage
            max_items: Maximum number of items to return
            
        Returns:
            List of STAC items with metadata
        """
        try:
            # Format dates for STAC
            date_range = f"{date_from.strftime('%Y-%m-%d')}/{date_to.strftime('%Y-%m-%d')}"
            
            # Build search query
            search_params = {
                "bbox": bbox,
                "datetime": date_range,
                "collections": collections,
                "limit": max_items
            }
            
            # Add cloud cover filter for optical imagery
            if "sentinel-2" in str(collections):
                search_params["query"] = {
                    "eo:cloud_cover": {"lt": cloud_cover_max}
                }
            
            # Execute search
            search = self.catalog.search(**search_params)
            items = list(search.items())
            
            logger.info(f"Found {len(items)} imagery items for bbox {bbox}")
            
            # Convert to simplified format
            results = []
            for item in items:
                item_info = {
                    "id": item.id,
                    "collection": item.collection_id,
                    "datetime": item.datetime.isoformat() if item.datetime else None,
                    "cloud_cover": item.properties.get("eo:cloud_cover"),
                    "bbox": item.bbox,
                    "assets": list(item.assets.keys()),
                    "item": item  # Store full item for later processing
                }
                results.append(item_info)
            
            # Sort by cloud cover for optical, by date for SAR
            if "sentinel-2" in str(collections):
                results.sort(key=lambda x: x.get("cloud_cover", 100))
            else:
                results.sort(key=lambda x: x.get("datetime", ""))
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching imagery: {e}")
            raise
    
    def get_best_imagery_pair(
        self,
        bbox: List[float],
        date_from: datetime,
        date_to: datetime,
        cloud_cover_max: float = 20.0
    ) -> Tuple[Optional[Dict], Optional[Dict], str]:
        """
        Find the best pair of images for change detection
        
        Returns:
            (before_image, after_image, satellite_type)
        """
        try:
            # First try Sentinel-2 (optical)
            logger.info("Searching for Sentinel-2 imagery...")
            
            # Search for before image (around date_from)
            before_search = self.search_imagery(
                bbox=bbox,
                date_from=date_from - timedelta(days=7),
                date_to=date_from + timedelta(days=7),
                collections=["sentinel-2-l2a"],
                cloud_cover_max=cloud_cover_max,
                max_items=5
            )
            
            # Search for after image (around date_to)
            after_search = self.search_imagery(
                bbox=bbox,
                date_from=date_to - timedelta(days=7),
                date_to=date_to + timedelta(days=7),
                collections=["sentinel-2-l2a"],
                cloud_cover_max=cloud_cover_max,
                max_items=5
            )
            
            if before_search and after_search:
                logger.info("Found suitable Sentinel-2 image pair")
                return before_search[0], after_search[0], "sentinel-2"
            
            # Fallback to Sentinel-1 (SAR) for cloudy conditions
            logger.info("Falling back to Sentinel-1 SAR imagery...")
            
            before_sar = self.search_imagery(
                bbox=bbox,
                date_from=date_from - timedelta(days=10),
                date_to=date_from + timedelta(days=10),
                collections=["sentinel-1-grd"],
                max_items=5
            )
            
            after_sar = self.search_imagery(
                bbox=bbox,
                date_from=date_to - timedelta(days=10),
                date_to=date_to + timedelta(days=10),
                collections=["sentinel-1-grd"],
                max_items=5
            )
            
            if before_sar and after_sar:
                logger.info("Found suitable Sentinel-1 image pair")
                return before_sar[0], after_sar[0], "sentinel-1"
            
            # No suitable imagery found
            logger.warning(f"No suitable imagery found for bbox {bbox} between {date_from} and {date_to}")
            return None, None, "none"
            
        except Exception as e:
            logger.error(f"Error finding imagery pair: {e}")
            raise
    
    def load_and_clip_image(
        self,
        stac_item: Dict,
        bbox: List[float],
        target_crs: str = "EPSG:32643",  # UTM Zone 43N for Mumbai
        resolution: float = 10.0  # 10m resolution
    ) -> xr.DataArray:
        """
        Load and clip STAC item to AOI
        
        Args:
            stac_item: STAC item information
            bbox: Bounding box to clip to
            target_crs: Target coordinate reference system
            resolution: Target resolution in meters
            
        Returns:
            Clipped and projected xarray DataArray
        """
        try:
            item = stac_item["item"]
            collection = stac_item["collection"]
            
            # Define bands based on satellite type
            if "sentinel-2" in collection:
                bands = ["B04", "B03", "B02", "B08"]  # RGB + NIR
            elif "sentinel-1" in collection:
                bands = ["vv", "vh"]  # SAR bands
            else:
                raise ValueError(f"Unsupported collection: {collection}")
            
            # Load data using stackstac
            stack = stackstac.stack(
                [item],
                assets=bands,
                bounds=bbox,
                snap_bounds=False,
                resolution=resolution
            )
            
            # Compute and load data
            data = stack.compute()
            
            logger.info(f"Loaded imagery: shape={data.shape}, bands={bands}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading and clipping image: {e}")
            raise
    
    def save_as_cog(
        self,
        data: xr.DataArray,
        output_path: str,
        compress: str = "lzw"
    ) -> str:
        """
        Save xarray data as Cloud Optimized GeoTIFF (COG)
        
        Args:
            data: Input xarray DataArray
            output_path: Output file path
            compress: Compression method
            
        Returns:
            Path to saved COG
        """
        try:
            from rio_cogeo.cogeo import cog_translate
            from rio_cogeo.profiles import cog_profiles
            
            # Create profile for COG
            profile = cog_profiles.get("lzw")
            profile.update({
                "BLOCKXSIZE": 512,
                "BLOCKYSIZE": 512,
                "COMPRESS": compress.upper(),
                "INTERLEAVE": "pixel"
            })
            
            # Save as regular GeoTIFF first
            temp_path = output_path.replace(".tif", "_temp.tif")
            data.rio.to_raster(temp_path)
            
            # Convert to COG
            cog_translate(
                temp_path,
                output_path,
                profile,
                in_memory=False,
                quiet=True
            )
            
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            logger.info(f"Saved COG: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error saving COG: {e}")
            raise
    
    def get_imagery_metadata(self, stac_item: Dict) -> Dict[str, Any]:
        """Extract metadata from STAC item"""
        try:
            item = stac_item["item"]
            
            metadata = {
                "id": item.id,
                "collection": item.collection_id,
                "datetime": item.datetime.isoformat() if item.datetime else None,
                "platform": item.properties.get("platform"),
                "instruments": item.properties.get("instruments"),
                "cloud_cover": item.properties.get("eo:cloud_cover"),
                "sun_azimuth": item.properties.get("view:sun_azimuth"),
                "sun_elevation": item.properties.get("view:sun_elevation"),
                "bbox": item.bbox,
                "epsg": item.properties.get("proj:epsg"),
                "gsd": item.properties.get("gsd"),  # Ground sample distance
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}
    
    def validate_imagery_quality(
        self,
        data: xr.DataArray,
        collection: str,
        min_valid_pixels: float = 0.8
    ) -> Tuple[bool, str]:
        """
        Validate imagery quality for change detection
        
        Args:
            data: Imagery data
            collection: Collection name
            min_valid_pixels: Minimum fraction of valid pixels required
            
        Returns:
            (is_valid, reason)
        """
        try:
            total_pixels = data.size
            
            if "sentinel-2" in collection:
                # Check for no-data values and clouds
                valid_pixels = np.sum(~np.isnan(data.values) & (data.values > 0))
                valid_fraction = valid_pixels / total_pixels
                
                if valid_fraction < min_valid_pixels:
                    return False, f"Too many invalid pixels: {valid_fraction:.2%} valid"
            
            elif "sentinel-1" in collection:
                # Check for reasonable SAR values
                valid_pixels = np.sum(np.isfinite(data.values))
                valid_fraction = valid_pixels / total_pixels
                
                if valid_fraction < min_valid_pixels:
                    return False, f"Too many invalid pixels: {valid_fraction:.2%} valid"
            
            return True, "Quality check passed"
            
        except Exception as e:
            logger.error(f"Error validating imagery quality: {e}")
            return False, f"Quality check failed: {str(e)}"