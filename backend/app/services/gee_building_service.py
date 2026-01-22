import ee
from typing import List, Dict, Any
from shapely.geometry import shape, mapping
from geopandas import GeoDataFrame
import json

class GEEBuildingService:
    """
    Service to fetch building footprints from Google Earth Engine
    Replaces OSM Overpass API with 100x better data
    """
    
    def __init__(self, project_id: str):
        """Initialize Earth Engine with your project"""
        ee.Initialize(project='your-gee-project-id')
        self.open_buildings = ee.FeatureCollection(
            'GOOGLE/Research/open-buildings/v3/polygons'
        )
    
    def get_buildings_for_aoi(
        self, 
        aoi_geometry: Dict[str, Any], 
        confidence_threshold: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Fetch building footprints from GEE Open Buildings for given AOI
        
        Args:
            aoi_geometry: GeoJSON geometry (from your AOI model)
            confidence_threshold: Building confidence filter (0.65-1.0)
            
        Returns:
            List of building features with confidence scores
        """
        
        # Convert GeoJSON to EE Geometry
        aoi_ee = ee.Geometry(aoi_geometry)
        
        # Filter buildings to AOI and confidence
        buildings_filtered = self.open_buildings.filterBounds(aoi_ee).filter(
            ee.Filter.gte('confidence', confidence_threshold)
        )
        
        # Get feature count
        count = buildings_filtered.size().getInfo()
        print(f"Found {count} buildings with confidence >= {confidence_threshold}")
        
        # Convert to GeoJSON (limit to 5000 features for performance)
        buildings_geojson = buildings_filtered.limit(5000).getInfo()
        
        # Extract features with Mumbai-specific metadata
        features = []
        for feature in buildings_geojson['features']:
            features.append({
                'type': 'Feature',
                'geometry': feature['geometry'],
                'properties': {
                    'confidence': feature['properties']['confidence'],
                    'area_sqm': feature['properties']['area_in_meters'],
                    'source': 'google_open_buildings',
                    'plus_code': feature['properties'].get('full_plus_code', None)
                }
            })
        
        return features
    
    def validate_new_construction(
        self,
        detected_buildings: List[Dict],
        reference_year_geometry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate detected changes against GEE building footprints
        
        Args:
            detected_buildings: Your ML-detected new constructions
            reference_year_geometry: AOI geometry
            
        Returns:
            Validated detections with overlap analysis
        """
        
        # Get reference buildings from GEE
        reference_buildings = self.get_buildings_for_aoi(reference_year_geometry)
        
        validated = []
        for detection in detected_buildings:
            # Check if detection overlaps with known buildings
            is_new_construction = self._check_if_new(
                detection, 
                reference_buildings
            )
            
            detection['validation'] = {
                'is_new_construction': is_new_construction,
                'reference_source': 'google_open_buildings',
                'confidence': detection.get('confidence', 0.0)
            }
            validated.append(detection)
        
        return validated
    
    def _check_if_new(
        self, 
        detection: Dict, 
        reference_buildings: List[Dict]
    ) -> bool:
        """Check if detection is truly new vs existing building"""
        from shapely.geometry import shape
        from shapely.ops import unary_union
        
        detection_geom = shape(detection['geometry'])
        
        # Create spatial index for efficiency
        reference_geoms = [shape(b['geometry']) for b in reference_buildings]
        
        # Check overlap with existing buildings
        for ref_geom in reference_geoms:
            if detection_geom.intersects(ref_geom):
                overlap_pct = (
                    detection_geom.intersection(ref_geom).area / 
                    detection_geom.area
                )
                if overlap_pct > 0.5:  # 50% overlap threshold
                    return False  # Existing building
        
        return True  # New construction
