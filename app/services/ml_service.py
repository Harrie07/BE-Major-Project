import torch
import torch.nn as nn
import numpy as np
import xarray as xr
from typing import Dict, Any, List, Tuple
import logging
from datetime import datetime
import os

from app.core.config import settings

logger = logging.getLogger(__name__)


class MLService:
    """Service for running ML change detection models"""
    
    def __init__(self):
        self.device = torch.device(settings.DEVICE)
        self.model = None
        self.model_version = "1.0.0"
        self.model_loaded = False
        
        # Load model if available
        if os.path.exists(settings.MODEL_PATH):
            self.load_model(settings.MODEL_PATH)
    
    def load_model(self, model_path: str):
        """Load the trained change detection model"""
        try:
            # Load model checkpoint
            checkpoint = torch.load(model_path, map_location=self.device)
            
            # Initialize model architecture (adjust based on your model)
            # This is a placeholder - replace with your actual model architecture
            from segmentation_models_pytorch import Unet
            
            self.model = Unet(
                encoder_name="resnet34",
                encoder_weights=None,
                in_channels=8,  # 4 bands * 2 dates
                classes=1,  # Binary change detection
                activation='sigmoid'
            )
            
            # Load model weights
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.to(self.device)
            self.model.eval()
            
            # Get model metadata
            self.model_version = checkpoint.get('version', '1.0.0')
            
            self.model_loaded = True
            logger.info(f"Loaded change detection model: {model_path}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.model_loaded = False
            raise
    
    def preprocess_imagery(
        self,
        before_data: xr.DataArray,
        after_data: xr.DataArray
    ) -> torch.Tensor:
        """
        Preprocess imagery for model input
        
        Args:
            before_data: Before image data
            after_data: After image data
            
        Returns:
            Preprocessed tensor ready for model input
        """
        try:
            # Ensure both images have the same shape and bands
            if before_data.shape != after_data.shape:
                raise ValueError("Before and after images must have the same shape")
            
            # Convert to numpy arrays
            before_np = before_data.values
            after_np = after_data.values
            
            # Normalize values (adjust based on your preprocessing)
            if "sentinel-2" in str(before_data.attrs.get('collection', '')):
                # Sentinel-2 normalization (0-10000 to 0-1)
                before_np = np.clip(before_np / 10000.0, 0, 1)
                after_np = np.clip(after_np / 10000.0, 0, 1)
            else:
                # Sentinel-1 normalization (dB values)
                before_np = np.clip((before_np + 30) / 50.0, 0, 1)
                after_np = np.clip((after_np + 30) / 50.0, 0, 1)
            
            # Stack before and after images
            # Shape: (bands, height, width) -> (bands*2, height, width)
            stacked = np.concatenate([before_np, after_np], axis=0)
            
            # Convert to tensor and add batch dimension
            tensor = torch.from_numpy(stacked).float().unsqueeze(0)  # (1, channels, H, W)
            
            logger.info(f"Preprocessed imagery shape: {tensor.shape}")
            return tensor
            
        except Exception as e:
            logger.error(f"Error preprocessing imagery: {e}")
            raise
    
    def run_inference(self, input_tensor: torch.Tensor) -> np.ndarray:
        """
        Run model inference
        
        Args:
            input_tensor: Preprocessed input tensor
            
        Returns:
            Change probability map as numpy array
        """
        try:
            if not self.model_loaded:
                raise Exception("Model not loaded. Please load a model first.")
            
            with torch.no_grad():
                # Move to device
                input_tensor = input_tensor.to(self.device)
                
                # Run inference
                output = self.model(input_tensor)
                
                # Convert to numpy and remove batch dimension
                change_map = output.cpu().numpy().squeeze()  # (H, W)
                
            logger.info(f"Inference completed. Output shape: {change_map.shape}")
            return change_map
            
        except Exception as e:
            logger.error(f"Error running inference: {e}")
            raise
    
    def postprocess_results(
        self,
        change_map: np.ndarray,
        before_data: xr.DataArray,
        confidence_threshold: float = 0.5,
        min_area_sqm: float = 25.0
    ) -> Dict[str, Any]:
        """
        Postprocess model results to extract detections
        
        Args:
            change_map: Raw model output
            before_data: Original imagery for coordinate reference
            confidence_threshold: Minimum confidence for detection
            min_area_sqm: Minimum area for valid detection
            
        Returns:
            Dictionary with change_map and detections
        """
        try:
            from skimage.measure import regionprops, label
            from shapely.geometry import Polygon
            import rasterio.features
            
            # Threshold the change map
            binary_mask = change_map > confidence_threshold
            
            # Label connected components
            labeled_mask = label(binary_mask)
            
            # Extract regions
            regions = regionprops(labeled_mask, intensity_image=change_map)
            
            detections = []
            for region in regions:
                # Calculate area in square meters
                pixel_area = abs(before_data.rio.resolution()[0] * before_data.rio.resolution()[1])
                area_sqm = region.area * pixel_area
                
                # Filter by minimum area
                if area_sqm < min_area_sqm:
                    continue
                
                # Get mean confidence score
                confidence_score = float(region.mean_intensity)
                
                # Extract polygon geometry
                mask = labeled_mask == region.label
                
                # Convert mask to polygon using rasterio
                transform = before_data.rio.transform()
                
                polygons = list(rasterio.features.shapes(
                    mask.astype(np.uint8),
                    transform=transform
                ))
                
                if not polygons:
                    continue
                
                # Get the largest polygon
                largest_poly = max(polygons, key=lambda x: Polygon(x[0]['coordinates'][0]).area)
                
                # Create detection object
                detection = {
                    "geometry": largest_poly[0],
                    "confidence_score": confidence_score,
                    "area_sqm": area_sqm,
                    "change_type": "new_construction" if confidence_score > 0.8 else "unknown",
                    "flagged": False,
                    "flag_reasons": []
                }
                
                detections.append(detection)
            
            # Create result xarray for the change map (for COG export)
            change_map_xr = xr.DataArray(
                change_map,
                dims=["y", "x"],
                coords={
                    "y": before_data.coords["y"],
                    "x": before_data.coords["x"]
                },
                attrs={
                    "crs": before_data.rio.crs,
                    "transform": before_data.rio.transform(),
                    "nodata": np.nan
                }
            )
            
            logger.info(f"Extracted {len(detections)} detections from change map")
            
            return {
                "change_map": change_map_xr,
                "detections": detections,
                "metadata": {
                    "confidence_threshold": confidence_threshold,
                    "min_area_sqm": min_area_sqm,
                    "total_detections": len(detections),
                    "processed_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error postprocessing results: {e}")
            raise
    
    def run_change_detection(
        self,
        before_data: xr.DataArray,
        after_data: xr.DataArray,
        aoi_geometry: Dict[str, Any],
        confidence_threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Complete change detection pipeline
        
        Args:
            before_data: Before image data
            after_data: After image data
            aoi_geometry: AOI geometry for clipping
            confidence_threshold: Detection threshold
            
        Returns:
            Complete results including change map and detections
        """
        try:
            logger.info("Starting change detection pipeline...")
            
            # Step 1: Preprocess imagery
            input_tensor = self.preprocess_imagery(before_data, after_data)
            
            # Step 2: Run model inference
            if self.model_loaded:
                change_map = self.run_inference(input_tensor)
            else:
                # Fallback: simple difference for demonstration
                logger.warning("Model not loaded, using simple difference method")
                change_map = self._simple_difference_detection(before_data, after_data)
            
            # Step 3: Postprocess results
            results = self.postprocess_results(
                change_map=change_map,
                before_data=before_data,
                confidence_threshold=confidence_threshold
            )
            
            logger.info("Change detection pipeline completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error in change detection pipeline: {e}")
            raise
    
    def _simple_difference_detection(
        self,
        before_data: xr.DataArray,
        after_data: xr.DataArray
    ) -> np.ndarray:
        """
        Simple difference-based change detection (fallback method)
        """
        try:
            logger.info("Using simple difference detection method")
            
            # Calculate NDVI for both images (assuming RGB+NIR bands)
            def calculate_ndvi(data):
                if data.shape[0] >= 4:  # Has NIR band
                    nir = data[3].values  # NIR band
                    red = data[0].values  # Red band
                    ndvi = (nir - red) / (nir + red + 1e-8)
                    return np.clip(ndvi, -1, 1)
                else:
                    # Use simple brightness if no NIR
                    return np.mean(data.values, axis=0)
            
            before_ndvi = calculate_ndvi(before_data)
            after_ndvi = calculate_ndvi(after_data)
            
            # Calculate difference
            diff = np.abs(after_ndvi - before_ndvi)
            
            # Normalize to 0-1
            change_map = np.clip(diff / np.percentile(diff, 95), 0, 1)
            
            return change_map
            
        except Exception as e:
            logger.error(f"Error in simple difference detection: {e}")
            raise
    
    def get_model_version(self) -> str:
        """Get current model version"""
        return self.model_version
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "version": self.model_version,
            "loaded": self.model_loaded,
            "device": str(self.device),
            "model_path": settings.MODEL_PATH,
            "architecture": "U-Net" if self.model_loaded else "Simple Difference"
        }