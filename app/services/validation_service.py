# app/services/validation_service.py
"""
Service for validating change detection results against protected zones.
"""

import logging
from typing import List, Dict, Any
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from app.core.config import settings
import json

logger = logging.getLogger(__name__)

class ValidationService:
    """Service for validating detections against protected zones."""
    
    def __init__(self):
        # Load protected zones from GeoJSON file
        self.protected_zones = self._load_protected_zones()
        # Prepare the geometry for faster intersection queries
        self.prepared_zones = prep(unary_union(self.protected_zones))
        
    def _load_protected_zones(self) -> List[Polygon]:
        """
        Load protected zones from a GeoJSON file.
        The file path should be configured in the app's settings.
        """
        try:
            if not os.path.exists(settings.PROTECTED_ZONES_GEOJSON):
                logger.warning(f"Protected zones file not found: {settings.PROTECTED_ZONES_GEOJSON}")
                return []
            
            with open(settings.PROTECTED_ZONES_GEOJSON, 'r') as f:
                geojson_data = json.load(f)
            
            # Extract geometries
            features = geojson_data.get('features', [])
            polygons = []
            
            for feature in features:
                geom = feature.get('geometry')
                if geom and geom['type'] == 'Polygon':
                    polygons.append(shape(geom))
                elif geom and geom['type'] == 'MultiPolygon':
                    # Handle MultiPolygon by converting to list of Polygons
                    for poly in shape(geom).geoms:
                        polygons.append(poly)
            
            logger.info(f"Loaded {len(polygons)} protected zone(s)")
            return polygons
            
        except Exception as e:
            logger.error(f"Error loading protected zones: {e}")
            return []
    
    def validate_detections(
        self,
        detections: List[Dict[str, Any]],
        aoi_geometry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate detections against protected zones.
        
        Args:
            detections: List of detection dictionaries
            aoi_geometry: AOI geometry to filter zones within the area
            
        Returns:
            List of validated detection dictionaries with added flagging information
        """
        try:
            # Convert AOI geometry to Shapely object
            aoig = shape(aoi_geometry)
            
            # Filter protected zones that intersect with the AOI
            relevant_zones = []
            for zone in self.protected_zones:
                if zone.intersects(aoig):
                    relevant_zones.append(zone)
            
            if not relevant_zones:
                logger.info("No protected zones found within AOI")
                return detections
            
            # Check each detection
            validated_detections = []
            for detection in detections:
                # Convert detection geometry to Shapely object
                det_geom = shape(detection['geometry'])
                
                # Check if this detection intersects with any protected zone
                is_in_protected_zone = False
                for zone in relevant_zones:
                    if det_geom.intersects(zone):
                        is_in_protected_zone = True
                        break
                
                # Add validation result
                updated_detection = detection.copy()
                updated_detection['flagged'] = is_in_protected_zone
                updated_detection['flag_reasons'] = []
                
                if is_in_protected_zone:
                    # Find which specific zones were intersected
                    intersecting_zones = []
                    for zone in relevant_zones:
                        if det_geom.intersects(zone):
                            # You could add more logic here to determine the type of zone
                            intersecting_zones.append(zone)
                    
                    # Add reason based on zone type (example - adjust based on your actual zones)
                    # This assumes your protected zones have a property like "zone_type"
                    for zone in intersecting_zones:
                        zone_type = zone.__geo_interface__['properties'].get('zone_type', 'protected_area')
                        updated_detection['flag_reasons'].append(f"Intersects {zone_type}")
                
                validated_detections.append(updated_detection)
            
            logger.info(f"Validated {len(validated_detections)} detections")
            return validated_detections
            
        except Exception as e:
            logger.error(f"Error validating detections: {e}")
            # Return original detections if validation fails
            return detections

# Instantiate the service for use in worker_tasks.py
# validation_service = ValidationService() # Handled inside worker_tasks.py instantiation