#!/usr/bin/env python3
"""
OCR Utilities - Optical Character Recognition module for UI element detection

This module provides comprehensive OCR functionality for recognizing and locating
UI elements in Android screenshots, optimized for Google account creation automation.

Author: Google Account Creator Team
Version: 0.1.0
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import json
import hashlib

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import easyocr

# Configure logging
logger = logging.getLogger(__name__)

class OCRError(Exception):
    """Custom exception for OCR operations."""
    pass

class OCRUtils:
    """
    Comprehensive OCR utility class for Android UI element recognition.
    
    This class provides methods for image preprocessing, text recognition,
    element localization, and performance optimization.
    """
    
    def __init__(self, languages: List[str] = ['en'], gpu: bool = False, cache_dir: str = "data/ocr_cache"):
        """
        Initialize OCR utilities.
        
        Args:
            languages: List of languages for OCR recognition
            gpu: Whether to use GPU acceleration
            cache_dir: Directory for OCR result caching
        """
        self.languages = languages
        self.gpu = gpu
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize EasyOCR reader
        try:
            logger.info(f"Initializing EasyOCR with languages: {languages}")
            self.reader = easyocr.Reader(languages, gpu=gpu)
            logger.info("EasyOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            raise OCRError(f"EasyOCR initialization failed: {e}")
        
        # Common UI element patterns for Google account creation
        self.ui_patterns = {
            'email_field': ['email', 'gmail', 'address', '@'],
            'password_field': ['password', 'passwd', 'pwd'],
            'name_field': ['first name', 'last name', 'name'],
            'phone_field': ['phone', 'number', 'mobile'],
            'next_button': ['next', 'continue', 'proceed'],
            'create_button': ['create', 'sign up', 'register'],
            'skip_button': ['skip', 'not now', 'maybe later'],
            'error_text': ['error', 'invalid', 'required', 'try again'],
            'success_text': ['success', 'complete', 'welcome'],
        }
        
        logger.info(f"OCR Utils initialized with cache directory: {cache_dir}")

    # ========== IMAGE PREPROCESSING METHODS ==========
    
    def preprocess_image_for_ocr(self, image_path: str, output_path: str = None, 
                                enhancement_level: str = "medium") -> Optional[str]:
        """
        Preprocess image for optimal OCR performance.
        
        Args:
            image_path: Path to input image
            output_path: Path for processed image (None for auto-generated)
            enhancement_level: "light", "medium", "heavy" processing level
            
        Returns:
            Optional[str]: Path to processed image or None if failed
        """
        try:
            if not Path(image_path).exists():
                raise OCRError(f"Image file not found: {image_path}")
            
            # Generate output path if not provided
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_preprocessed.png"
            
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                raise OCRError(f"Could not load image: {image_path}")
            
            # Apply preprocessing based on enhancement level
            if enhancement_level == "light":
                processed_img = self._light_preprocessing(img)
            elif enhancement_level == "medium":
                processed_img = self._medium_preprocessing(img)
            elif enhancement_level == "heavy":
                processed_img = self._heavy_preprocessing(img)
            else:
                raise OCRError(f"Invalid enhancement level: {enhancement_level}")
            
            # Save processed image
            cv2.imwrite(str(output_path), processed_img)
            
            logger.debug(f"Preprocessed image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return None

    def _light_preprocessing(self, img: np.ndarray) -> np.ndarray:
        """
        Light preprocessing for clear, high-quality images.
        
        Args:
            img: Input image as numpy array
            
        Returns:
            np.ndarray: Processed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply slight Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Simple binary thresholding
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh

    def _medium_preprocessing(self, img: np.ndarray) -> np.ndarray:
        """
        Medium preprocessing for standard quality images.
        
        Args:
            img: Input image as numpy array
            
        Returns:
            np.ndarray: Processed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Adaptive thresholding for better handling of varying lighting
        adaptive_thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up the image
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_CLOSE, kernel)
        
        # Remove small noise
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
        
        return cleaned

    def _heavy_preprocessing(self, img: np.ndarray) -> np.ndarray:
        """
        Heavy preprocessing for low-quality or problematic images.
        
        Args:
            img: Input image as numpy array
            
        Returns:
            np.ndarray: Processed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while preserving edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(filtered)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        
        # Adaptive thresholding
        adaptive_thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 2
        )
        
        # More aggressive morphological operations
        kernel_small = np.ones((2, 2), np.uint8)
        kernel_large = np.ones((3, 3), np.uint8)
        
        # Remove noise
        opened = cv2.morphologyEx(adaptive_thresh, cv2.MORPH_OPEN, kernel_small)
        
        # Close gaps in text
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_large)
        
        # Final erosion to make text cleaner
        eroded = cv2.erode(closed, kernel_small, iterations=1)
        
        return eroded

    def enhance_contrast_and_brightness(self, image_path: str, contrast: float = 1.2, 
                                      brightness: int = 10, output_path: str = None) -> Optional[str]:
        """
        Enhance image contrast and brightness for better OCR results.
        
        Args:
            image_path: Path to input image
            contrast: Contrast multiplier (1.0 = no change)
            brightness: Brightness adjustment (-100 to 100)
            output_path: Path for enhanced image
            
        Returns:
            Optional[str]: Path to enhanced image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_enhanced.png"
            
            # Load image using PIL for better color handling
            with Image.open(image_path) as img:
                # Enhance contrast
                contrast_enhancer = ImageEnhance.Contrast(img)
                img = contrast_enhancer.enhance(contrast)
                
                # Enhance brightness
                brightness_enhancer = ImageEnhance.Brightness(img)
                img = brightness_enhancer.enhance(1 + brightness / 100)
                
                # Save enhanced image
                img.save(output_path)
                
            logger.debug(f"Enhanced image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            return None

    def sharpen_image(self, image_path: str, strength: float = 1.0, output_path: str = None) -> Optional[str]:
        """
        Sharpen image to improve text clarity.
        
        Args:
            image_path: Path to input image
            strength: Sharpening strength (0.0 to 2.0)
            output_path: Path for sharpened image
            
        Returns:
            Optional[str]: Path to sharpened image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_sharpened.png"
            
            with Image.open(image_path) as img:
                # Apply unsharp mask filter
                sharpener = ImageEnhance.Sharpness(img)
                img = sharpener.enhance(1 + strength)
                
                # Additional edge enhancement using filter
                if strength > 1.0:
                    img = img.filter(ImageFilter.EDGE_ENHANCE)
                
                img.save(output_path)
                
            logger.debug(f"Sharpened image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image sharpening failed: {e}")
            return None

    def denoise_image(self, image_path: str, output_path: str = None) -> Optional[str]:
        """
        Remove noise from image for cleaner OCR input.
        
        Args:
            image_path: Path to input image
            output_path: Path for denoised image
            
        Returns:
            Optional[str]: Path to denoised image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_denoised.png"
            
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                raise OCRError(f"Could not load image: {image_path}")
            
            # Apply non-local means denoising
            if len(img.shape) == 3:  # Color image
                denoised = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
            else:  # Grayscale image
                denoised = cv2.fastNlMeansDenoising(img, None, 10, 7, 21)
            
            # Save denoised image
            cv2.imwrite(str(output_path), denoised)
            
            logger.debug(f"Denoised image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image denoising failed: {e}")
            return None

    def correct_skew(self, image_path: str, output_path: str = None) -> Optional[str]:
        """
        Correct skewed text in images.
        
        Args:
            image_path: Path to input image
            output_path: Path for corrected image
            
        Returns:
            Optional[str]: Path to corrected image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_skew_corrected.png"
            
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                raise OCRError(f"Could not load image: {image_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Find lines using Hough transform
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None:
                # Calculate average angle of detected lines
                angles = []
                for rho, theta in lines[:, 0]:
                    angle = theta * 180 / np.pi
                    # Convert to rotation angle
                    if angle > 90:
                        angle = angle - 180
                    angles.append(angle)
                
                # Get median angle for robustness
                median_angle = np.median(angles)
                
                # Rotate image to correct skew
                height, width = img.shape[:2]
                center = (width // 2, height // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                corrected = cv2.warpAffine(img, rotation_matrix, (width, height), 
                                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                
                logger.debug(f"Corrected skew by {median_angle:.2f} degrees")
            else:
                # No lines detected, return original image
                corrected = img
                logger.debug("No skew detected")
            
            # Save corrected image
            cv2.imwrite(str(output_path), corrected)
            
            logger.debug(f"Skew-corrected image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Skew correction failed: {e}")
            return None

    def crop_region_of_interest(self, image_path: str, x: int, y: int, width: int, height: int, 
                               output_path: str = None) -> Optional[str]:
        """
        Crop a specific region from the image for focused OCR.
        
        Args:
            image_path: Path to input image
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height
            output_path: Path for cropped image
            
        Returns:
            Optional[str]: Path to cropped image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_roi_{x}_{y}_{width}_{height}.png"
            
            # Load image
            with Image.open(image_path) as img:
                # Crop the region
                cropped = img.crop((x, y, x + width, y + height))
                
                # Save cropped image
                cropped.save(output_path)
                
            logger.debug(f"Cropped region saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image cropping failed: {e}")
            return None

    def resize_for_optimal_ocr(self, image_path: str, target_dpi: int = 300, 
                              output_path: str = None) -> Optional[str]:
        """
        Resize image to optimal DPI for OCR (typically 300 DPI).
        
        Args:
            image_path: Path to input image
            target_dpi: Target DPI for OCR optimization
            output_path: Path for resized image
            
        Returns:
            Optional[str]: Path to resized image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_ocr_optimized.png"
            
            with Image.open(image_path) as img:
                # Calculate scaling factor based on current DPI
                current_dpi = img.info.get('dpi', (72, 72))[0]  # Default to 72 DPI
                scale_factor = target_dpi / current_dpi
                
                # Calculate new dimensions
                new_width = int(img.width * scale_factor)
                new_height = int(img.height * scale_factor)
                
                # Resize image using high-quality resampling
                resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save with target DPI
                resized.save(output_path, dpi=(target_dpi, target_dpi))
                
            logger.debug(f"OCR-optimized image saved: {output_path} ({target_dpi} DPI)")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image resizing for OCR failed: {e}")
            return None

    def create_preprocessing_pipeline(self, image_path: str, pipeline_config: Dict, 
                                    output_path: str = None) -> Optional[str]:
        """
        Apply a custom preprocessing pipeline to an image.
        
        Args:
            image_path: Path to input image
            pipeline_config: Configuration dictionary for preprocessing steps
            output_path: Path for processed image
            
        Returns:
            Optional[str]: Path to processed image or None if failed
        """
        try:
            if output_path is None:
                input_path = Path(image_path)
                output_path = input_path.parent / f"{input_path.stem}_pipeline_processed.png"
            
            current_path = image_path
            temp_files = []
            
            # Apply each preprocessing step in order
            for step, params in pipeline_config.items():
                if step == "enhance_contrast":
                    temp_path = self.enhance_contrast_and_brightness(
                        current_path, 
                        contrast=params.get('contrast', 1.2),
                        brightness=params.get('brightness', 10)
                    )
                elif step == "sharpen":
                    temp_path = self.sharpen_image(
                        current_path,
                        strength=params.get('strength', 1.0)
                    )
                elif step == "denoise":
                    temp_path = self.denoise_image(current_path)
                elif step == "correct_skew":
                    temp_path = self.correct_skew(current_path)
                elif step == "resize_for_ocr":
                    temp_path = self.resize_for_optimal_ocr(
                        current_path,
                        target_dpi=params.get('target_dpi', 300)
                    )
                elif step == "preprocess":
                    temp_path = self.preprocess_image_for_ocr(
                        current_path,
                        enhancement_level=params.get('level', 'medium')
                    )
                else:
                    logger.warning(f"Unknown preprocessing step: {step}")
                    continue
                
                if temp_path:
                    if current_path != image_path:  # Don't delete original
                        temp_files.append(current_path)
                    current_path = temp_path
                else:
                    logger.error(f"Preprocessing step '{step}' failed")
                    break
            
            # Move final result to output path
            if current_path != output_path:
                import shutil
                shutil.move(current_path, output_path)
            
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    Path(temp_file).unlink()
                except Exception:
                    pass
            
            logger.debug(f"Pipeline processed image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Preprocessing pipeline failed: {e}")
            return None

    def get_image_quality_metrics(self, image_path: str) -> Dict[str, float]:
        """
        Analyze image quality metrics to determine optimal preprocessing approach.
        
        Args:
            image_path: Path to input image
            
        Returns:
            Dict[str, float]: Quality metrics including contrast, brightness, sharpness, etc.
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                raise OCRError(f"Could not load image: {image_path}")
            
            # Convert to grayscale for analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Calculate various quality metrics
            metrics = {}
            
            # Contrast (standard deviation of pixel intensities)
            metrics['contrast'] = float(np.std(gray))
            
            # Brightness (mean pixel intensity)
            metrics['brightness'] = float(np.mean(gray))
            
            # Sharpness (Laplacian variance)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            metrics['sharpness'] = float(laplacian.var())
            
            # Noise estimation (using median absolute deviation)
            median = np.median(gray)
            mad = np.median(np.abs(gray - median))
            metrics['noise_level'] = float(mad)
            
            # Edge density (indicator of text presence)
            edges = cv2.Canny(gray, 50, 150)
            metrics['edge_density'] = float(np.sum(edges > 0) / edges.size)
            
            logger.debug(f"Image quality metrics: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Quality metrics calculation failed: {e}")
            return {}

    def suggest_preprocessing_config(self, image_path: str) -> Dict:
        """
        Suggest optimal preprocessing configuration based on image quality analysis.
        
        Args:
            image_path: Path to input image
            
        Returns:
            Dict: Suggested preprocessing pipeline configuration
        """
        try:
            metrics = self.get_image_quality_metrics(image_path)
            config = {}
            
            if not metrics:
                # Default configuration if analysis fails
                return {
                    "preprocess": {"level": "medium"},
                    "enhance_contrast": {"contrast": 1.2, "brightness": 10}
                }
            
            # Determine preprocessing needs based on metrics
            contrast = metrics.get('contrast', 50)
            brightness = metrics.get('brightness', 127)
            sharpness = metrics.get('sharpness', 100)
            noise_level = metrics.get('noise_level', 10)
            
            # Low contrast images
            if contrast < 30:
                config["enhance_contrast"] = {"contrast": 1.5, "brightness": 20}
            elif contrast < 50:
                config["enhance_contrast"] = {"contrast": 1.2, "brightness": 10}
            
            # Dark or bright images
            if brightness < 80:
                config.setdefault("enhance_contrast", {})["brightness"] = 30
            elif brightness > 180:
                config.setdefault("enhance_contrast", {})["brightness"] = -20
            
            # Blurry images
            if sharpness < 50:
                config["sharpen"] = {"strength": 1.5}
            elif sharpness < 100:
                config["sharpen"] = {"strength": 1.0}
            
            # Noisy images
            if noise_level > 15:
                config["denoise"] = {}
            
            # Always apply basic preprocessing
            if noise_level > 20 or contrast < 40 or sharpness < 60:
                config["preprocess"] = {"level": "heavy"}
            elif noise_level > 10 or contrast < 60:
                config["preprocess"] = {"level": "medium"}
            else:
                config["preprocess"] = {"level": "light"}
            
            # Resize for OCR if image is very small or very large
            with Image.open(image_path) as img:
                width, height = img.size
                if width < 800 or height < 600:
                    config["resize_for_ocr"] = {"target_dpi": 300}
                elif width > 2000 or height > 2000:
                    config["resize_for_ocr"] = {"target_dpi": 200}
            
            logger.debug(f"Suggested preprocessing config: {config}")
            return config
            
        except Exception as e:
            logger.error(f"Preprocessing config suggestion failed: {e}")
            return {"preprocess": {"level": "medium"}}

    # ========== TEXT RECOGNITION METHODS ==========
    
    def perform_ocr(self, image_path: str, confidence_threshold: float = 0.5, 
                   use_cache: bool = True) -> List[Dict]:
        """
        Perform OCR on an image and return detected text with coordinates.
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence score for text detection
            use_cache: Whether to use cached results
            
        Returns:
            List[Dict]: List of detected text elements with format:
                       [{'text': str, 'confidence': float, 'bbox': (x1, y1, x2, y2)}]
        """
        try:
            if not Path(image_path).exists():
                raise OCRError(f"Image file not found: {image_path}")
            
            # Check cache first
            if use_cache:
                cached_result = self._get_cached_ocr_result(image_path)
                if cached_result:
                    logger.debug(f"Using cached OCR result for {image_path}")
                    return cached_result
            
            # Perform OCR
            logger.info(f"Performing OCR on {image_path}")
            start_time = time.time()
            
            results = self.reader.readtext(image_path)
            
            # Format results
            formatted_results = []
            for bbox, text, confidence in results:
                if confidence >= confidence_threshold:
                    # Convert bbox to (x1, y1, x2, y2) format
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    x1, x2 = min(x_coords), max(x_coords)
                    y1, y2 = min(y_coords), max(y_coords)
                    
                    formatted_results.append({
                        'text': text.strip(),
                        'confidence': float(confidence),
                        'bbox': (int(x1), int(y1), int(x2), int(y2))
                    })
            
            processing_time = time.time() - start_time
            logger.info(f"OCR completed in {processing_time:.2f}s, found {len(formatted_results)} text elements")
            
            # Cache results
            if use_cache:
                self._cache_ocr_result(image_path, formatted_results)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            raise OCRError(f"OCR processing failed: {e}")

    def perform_ocr_with_preprocessing(self, image_path: str, enhancement_level: str = "auto",
                                     confidence_threshold: float = 0.5, use_cache: bool = True) -> List[Dict]:
        """
        Perform OCR with automatic preprocessing for optimal results.
        
        Args:
            image_path: Path to image file
            enhancement_level: "auto", "light", "medium", "heavy"
            confidence_threshold: Minimum confidence score
            use_cache: Whether to use cached results
            
        Returns:
            List[Dict]: OCR results with preprocessing applied
        """
        try:
            # Determine preprocessing config
            if enhancement_level == "auto":
                config = self.suggest_preprocessing_config(image_path)
            else:
                config = {"preprocess": {"level": enhancement_level}}
            
            # Apply preprocessing
            preprocessed_path = self.create_preprocessing_pipeline(image_path, config)
            if not preprocessed_path:
                logger.warning("Preprocessing failed, using original image")
                preprocessed_path = image_path
            
            # Perform OCR on preprocessed image
            results = self.perform_ocr(preprocessed_path, confidence_threshold, use_cache)
            
            # Clean up temporary preprocessed file if it's different from original
            if preprocessed_path != image_path:
                try:
                    Path(preprocessed_path).unlink()
                except Exception:
                    pass
            
            return results
            
        except Exception as e:
            logger.error(f"OCR with preprocessing failed: {e}")
            return []

    def extract_text_only(self, image_path: str, confidence_threshold: float = 0.5) -> List[str]:
        """
        Extract only text strings from OCR results.
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[str]: List of detected text strings
        """
        try:
            results = self.perform_ocr(image_path, confidence_threshold)
            return [result['text'] for result in results]
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return []

    def get_all_text_as_string(self, image_path: str, confidence_threshold: float = 0.5,
                              separator: str = " ") -> str:
        """
        Get all detected text as a single string.
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence score
            separator: String to join text elements
            
        Returns:
            str: All text joined by separator
        """
        try:
            text_list = self.extract_text_only(image_path, confidence_threshold)
            return separator.join(text_list)
        except Exception as e:
            logger.error(f"String extraction failed: {e}")
            return ""

    def find_text_by_pattern(self, image_path: str, pattern: str, case_sensitive: bool = False,
                           confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Find text elements matching a specific pattern.
        
        Args:
            image_path: Path to image file
            pattern: Regex pattern or plain text to search for
            case_sensitive: Whether search should be case sensitive
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[Dict]: Matching text elements with coordinates
        """
        try:
            import re
            
            results = self.perform_ocr(image_path, confidence_threshold)
            matches = []
            
            for result in results:
                text = result['text']
                if not case_sensitive:
                    text = text.lower()
                    pattern_to_use = pattern.lower()
                else:
                    pattern_to_use = pattern
                
                # Try regex first, fall back to simple substring search
                try:
                    if re.search(pattern_to_use, text):
                        matches.append(result)
                except re.error:
                    # If regex fails, use simple substring search
                    if pattern_to_use in text:
                        matches.append(result)
            
            logger.debug(f"Found {len(matches)} text elements matching pattern: {pattern}")
            return matches
            
        except Exception as e:
            logger.error(f"Pattern search failed: {e}")
            return []

    def find_text_containing_keywords(self, image_path: str, keywords: List[str],
                                    match_all: bool = False, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Find text elements containing specific keywords.
        
        Args:
            image_path: Path to image file
            keywords: List of keywords to search for
            match_all: If True, text must contain all keywords; if False, any keyword
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[Dict]: Matching text elements
        """
        try:
            results = self.perform_ocr(image_path, confidence_threshold)
            matches = []
            
            for result in results:
                text = result['text'].lower()
                keyword_matches = [keyword.lower() in text for keyword in keywords]
                
                if match_all:
                    # All keywords must be present
                    if all(keyword_matches):
                        matches.append(result)
                else:
                    # Any keyword must be present
                    if any(keyword_matches):
                        matches.append(result)
            
            logger.debug(f"Found {len(matches)} text elements containing keywords: {keywords}")
            return matches
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def analyze_text_layout(self, image_path: str, confidence_threshold: float = 0.5) -> Dict:
        """
        Analyze the layout of text elements in the image.
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Layout analysis including text blocks, lines, and reading order
        """
        try:
            results = self.perform_ocr(image_path, confidence_threshold)
            
            if not results:
                return {"text_blocks": [], "total_elements": 0, "reading_order": []}
            
            # Sort by reading order (top-left to bottom-right)
            sorted_results = sorted(results, key=lambda x: (x['bbox'][1], x['bbox'][0]))
            
            # Group into text blocks based on proximity
            text_blocks = self._group_text_into_blocks(sorted_results)
            
            # Calculate average dimensions
            widths = [bbox[2] - bbox[0] for result in results for bbox in [result['bbox']]]
            heights = [bbox[3] - bbox[1] for result in results for bbox in [result['bbox']]]
            
            analysis = {
                "text_blocks": text_blocks,
                "total_elements": len(results),
                "reading_order": [result['text'] for result in sorted_results],
                "average_text_width": sum(widths) / len(widths) if widths else 0,
                "average_text_height": sum(heights) / len(heights) if heights else 0,
                "text_distribution": self._analyze_text_distribution(results)
            }
            
            logger.debug(f"Text layout analysis completed: {len(text_blocks)} blocks, {len(results)} elements")
            return analysis
            
        except Exception as e:
            logger.error(f"Text layout analysis failed: {e}")
            return {"text_blocks": [], "total_elements": 0, "reading_order": []}

    def extract_numbers_and_dates(self, image_path: str, confidence_threshold: float = 0.5) -> Dict:
        """
        Extract numbers, dates, and other structured data from text.
        
        Args:
            image_path: Path to image file
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Extracted structured data (numbers, dates, emails, etc.)
        """
        try:
            import re
            
            text_elements = self.extract_text_only(image_path, confidence_threshold)
            all_text = " ".join(text_elements)
            
            # Define regex patterns for common data types
            patterns = {
                'numbers': r'\b\d+\.?\d*\b',
                'dates': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
                'emails': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'phone_numbers': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',
                'urls': r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                'currency': r'\$\d+\.?\d*|\d+\.?\d*\s*(?:USD|EUR|GBP|JPY|KRW)',
            }
            
            extracted_data = {}
            for data_type, pattern in patterns.items():
                matches = re.findall(pattern, all_text)
                extracted_data[data_type] = list(set(matches))  # Remove duplicates
            
            logger.debug(f"Extracted structured data: {extracted_data}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Structured data extraction failed: {e}")
            return {}

    def compare_ocr_results(self, image1_path: str, image2_path: str, 
                           confidence_threshold: float = 0.5) -> Dict:
        """
        Compare OCR results between two images.
        
        Args:
            image1_path: Path to first image
            image2_path: Path to second image
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Comparison results with similarities and differences
        """
        try:
            results1 = self.extract_text_only(image1_path, confidence_threshold)
            results2 = self.extract_text_only(image2_path, confidence_threshold)
            
            set1 = set(results1)
            set2 = set(results2)
            
            comparison = {
                "common_text": list(set1.intersection(set2)),
                "unique_to_image1": list(set1 - set2),
                "unique_to_image2": list(set2 - set1),
                "similarity_ratio": len(set1.intersection(set2)) / len(set1.union(set2)) if set1.union(set2) else 0,
                "total_text_elements": {"image1": len(results1), "image2": len(results2)}
            }
            
            logger.debug(f"OCR comparison completed: {comparison['similarity_ratio']:.2f} similarity")
            return comparison
            
        except Exception as e:
            logger.error(f"OCR comparison failed: {e}")
            return {}

    # ========== CACHING METHODS ==========
    
    def _get_cache_key(self, image_path: str) -> str:
        """Generate cache key for an image based on path and modification time."""
        try:
            file_path = Path(image_path)
            if not file_path.exists():
                return None
            
            # Use file path, size, and modification time for cache key
            stat = file_path.stat()
            key_data = f"{file_path}_{stat.st_size}_{stat.st_mtime}"
            return hashlib.md5(key_data.encode()).hexdigest()
        except Exception:
            return None

    def _get_cached_ocr_result(self, image_path: str) -> Optional[List[Dict]]:
        """Retrieve cached OCR result if available and valid."""
        try:
            cache_key = self._get_cache_key(image_path)
            if not cache_key:
                return None
            
            cache_file = self.cache_dir / f"{cache_key}.json"
            if not cache_file.exists():
                return None
            
            # Check cache age (expire after 24 hours)
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age > 24 * 3600:  # 24 hours
                cache_file.unlink()
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            return cached_data.get('results', [])
            
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e}")
            return None

    def _cache_ocr_result(self, image_path: str, results: List[Dict]) -> None:
        """Cache OCR results for future use."""
        try:
            cache_key = self._get_cache_key(image_path)
            if not cache_key:
                return
            
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            cache_data = {
                'image_path': str(image_path),
                'timestamp': time.time(),
                'results': results
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"OCR results cached: {cache_file}")
            
        except Exception as e:
            logger.debug(f"Cache storage failed: {e}")

    def clear_ocr_cache(self, max_age_hours: int = 24) -> int:
        """
        Clear old OCR cache files.
        
        Args:
            max_age_hours: Maximum age of cache files to keep
            
        Returns:
            int: Number of files deleted
        """
        try:
            deleted_count = 0
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        cache_file.unlink()
                        deleted_count += 1
                except Exception:
                    continue
            
            if deleted_count > 0:
                logger.info(f"Cleared {deleted_count} old cache files")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_cache_info(self) -> Dict:
        """
        Get information about the OCR cache.
        
        Returns:
            Dict: Cache statistics
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "cache_directory": str(self.cache_dir),
                "total_files": len(cache_files),
                "total_size_mb": total_size / (1024 * 1024),
                "oldest_file": min((f.stat().st_mtime for f in cache_files), default=0),
                "newest_file": max((f.stat().st_mtime for f in cache_files), default=0)
            }
            
        except Exception as e:
            logger.error(f"Cache info retrieval failed: {e}")
            return {}

    # ========== HELPER METHODS ==========
    
    def _group_text_into_blocks(self, text_results: List[Dict], proximity_threshold: int = 50) -> List[Dict]:
        """Group nearby text elements into logical blocks."""
        if not text_results:
            return []
        
        blocks = []
        current_block = [text_results[0]]
        
        for i in range(1, len(text_results)):
            current = text_results[i]
            previous = text_results[i-1]
            
            # Calculate vertical distance between text elements
            vertical_distance = abs(current['bbox'][1] - previous['bbox'][3])
            
            if vertical_distance <= proximity_threshold:
                current_block.append(current)
            else:
                # Start new block
                blocks.append({
                    'texts': [item['text'] for item in current_block],
                    'combined_text': ' '.join(item['text'] for item in current_block),
                    'bbox': self._get_combined_bbox(current_block),
                    'element_count': len(current_block)
                })
                current_block = [current]
        
        # Add the last block
        if current_block:
            blocks.append({
                'texts': [item['text'] for item in current_block],
                'combined_text': ' '.join(item['text'] for item in current_block),
                'bbox': self._get_combined_bbox(current_block),
                'element_count': len(current_block)
            })
        
        return blocks

    def _get_combined_bbox(self, text_elements: List[Dict]) -> Tuple[int, int, int, int]:
        """Calculate combined bounding box for multiple text elements."""
        if not text_elements:
            return (0, 0, 0, 0)
        
        x1 = min(element['bbox'][0] for element in text_elements)
        y1 = min(element['bbox'][1] for element in text_elements)
        x2 = max(element['bbox'][2] for element in text_elements)
        y2 = max(element['bbox'][3] for element in text_elements)
        
        return (x1, y1, x2, y2)

    def _analyze_text_distribution(self, text_results: List[Dict]) -> Dict:
        """Analyze the spatial distribution of text elements."""
        if not text_results:
            return {}
        
        # Calculate image bounds
        all_x = [coord for result in text_results for coord in [result['bbox'][0], result['bbox'][2]]]
        all_y = [coord for result in text_results for coord in [result['bbox'][1], result['bbox'][3]]]
        
        image_width = max(all_x) - min(all_x)
        image_height = max(all_y) - min(all_y)
        
        # Divide into quadrants and count text elements
        mid_x = min(all_x) + image_width / 2
        mid_y = min(all_y) + image_height / 2
        
        quadrants = {"top_left": 0, "top_right": 0, "bottom_left": 0, "bottom_right": 0}
        
        for result in text_results:
            center_x = (result['bbox'][0] + result['bbox'][2]) / 2
            center_y = (result['bbox'][1] + result['bbox'][3]) / 2
            
            if center_x < mid_x and center_y < mid_y:
                quadrants["top_left"] += 1
            elif center_x >= mid_x and center_y < mid_y:
                quadrants["top_right"] += 1
            elif center_x < mid_x and center_y >= mid_y:
                quadrants["bottom_left"] += 1
            else:
                quadrants["bottom_right"] += 1
        
        return {
            "quadrant_distribution": quadrants,
            "image_bounds": {
                "width": image_width,
                "height": image_height,
                "min_x": min(all_x),
                "min_y": min(all_y),
                "max_x": max(all_x),
                "max_y": max(all_y)
            }
        }

    # ========== ELEMENT LOCALIZATION METHODS ==========
    
    def find_ui_element_by_type(self, image_path: str, element_type: str, 
                               confidence_threshold: float = 0.5) -> Optional[Dict]:
        """
        Find UI elements by type (email_field, password_field, etc.).
        
        Args:
            image_path: Path to screenshot
            element_type: Type of UI element to find
            confidence_threshold: Minimum confidence score
            
        Returns:
            Optional[Dict]: Element information with coordinates or None if not found
        """
        try:
            if element_type not in self.ui_patterns:
                logger.warning(f"Unknown UI element type: {element_type}")
                return None
            
            # Get search keywords for this element type
            keywords = self.ui_patterns[element_type]
            
            # Find text elements containing these keywords
            matches = self.find_text_containing_keywords(image_path, keywords, 
                                                       match_all=False, 
                                                       confidence_threshold=confidence_threshold)
            
            if not matches:
                logger.debug(f"No {element_type} found in image")
                return None
            
            # Select the best match based on confidence and keyword relevance
            best_match = self._select_best_ui_element_match(matches, keywords, element_type)
            
            if best_match:
                logger.info(f"Found {element_type} at {best_match['bbox']}")
                return {
                    'element_type': element_type,
                    'text': best_match['text'],
                    'confidence': best_match['confidence'],
                    'bbox': best_match['bbox'],
                    'center': self._get_bbox_center(best_match['bbox']),
                    'click_coords': self._get_optimal_click_coordinates(best_match['bbox'], element_type)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"UI element search failed for {element_type}: {e}")
            return None

    def find_all_ui_elements(self, image_path: str, confidence_threshold: float = 0.5) -> Dict[str, Dict]:
        """
        Find all recognizable UI elements in the image.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict[str, Dict]: Dictionary of found elements by type
        """
        try:
            found_elements = {}
            
            for element_type in self.ui_patterns.keys():
                element = self.find_ui_element_by_type(image_path, element_type, confidence_threshold)
                if element:
                    found_elements[element_type] = element
            
            logger.info(f"Found {len(found_elements)} UI elements: {list(found_elements.keys())}")
            return found_elements
            
        except Exception as e:
            logger.error(f"UI element search failed: {e}")
            return {}

    def find_buttons_by_text(self, image_path: str, button_texts: List[str], 
                           confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Find buttons by their text content.
        
        Args:
            image_path: Path to screenshot
            button_texts: List of button text to search for
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[Dict]: List of found buttons with coordinates
        """
        try:
            all_buttons = []
            
            for button_text in button_texts:
                matches = self.find_text_by_pattern(image_path, button_text, 
                                                  case_sensitive=False, 
                                                  confidence_threshold=confidence_threshold)
                
                for match in matches:
                    # Check if this looks like a button (reasonable size and position)
                    if self._is_likely_button(match['bbox']):
                        button_info = {
                            'text': match['text'],
                            'confidence': match['confidence'],
                            'bbox': match['bbox'],
                            'center': self._get_bbox_center(match['bbox']),
                            'click_coords': self._get_optimal_click_coordinates(match['bbox'], 'button')
                        }
                        all_buttons.append(button_info)
            
            # Remove duplicates based on proximity
            unique_buttons = self._remove_duplicate_elements(all_buttons)
            
            logger.info(f"Found {len(unique_buttons)} buttons")
            return unique_buttons
            
        except Exception as e:
            logger.error(f"Button search failed: {e}")
            return []

    def find_input_fields(self, image_path: str, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Find input fields by detecting labels and field indicators.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[Dict]: List of found input fields with their types and coordinates
        """
        try:
            input_fields = []
            
            # Define field indicators
            field_indicators = {
                'email': ['email', 'e-mail', '@', 'gmail', 'address'],
                'password': ['password', 'pwd', 'pass', 'confirm password'],
                'name': ['first name', 'last name', 'full name', 'name'],
                'phone': ['phone', 'mobile', 'number', 'tel'],
                'username': ['username', 'user name', 'login'],
                'birthday': ['birthday', 'birth date', 'date of birth', 'dob'],
                'gender': ['gender', 'sex', 'male', 'female'],
                'recovery': ['recovery', 'backup', 'alternate']
            }
            
            # Get all text elements
            all_text = self.perform_ocr(image_path, confidence_threshold)
            
            # Analyze each text element for field indicators
            for text_element in all_text:
                text_lower = text_element['text'].lower()
                
                for field_type, indicators in field_indicators.items():
                    for indicator in indicators:
                        if indicator in text_lower:
                            # Found potential field label, look for input area nearby
                            input_coords = self._find_input_area_near_label(text_element['bbox'], all_text)
                            
                            if input_coords:
                                field_info = {
                                    'field_type': field_type,
                                    'label_text': text_element['text'],
                                    'label_bbox': text_element['bbox'],
                                    'input_bbox': input_coords,
                                    'input_center': self._get_bbox_center(input_coords),
                                    'click_coords': self._get_optimal_click_coordinates(input_coords, 'input_field')
                                }
                                input_fields.append(field_info)
                            break
            
            # Remove duplicates and overlapping fields
            unique_fields = self._remove_duplicate_input_fields(input_fields)
            
            logger.info(f"Found {len(unique_fields)} input fields")
            return unique_fields
            
        except Exception as e:
            logger.error(f"Input field search failed: {e}")
            return []

    def find_navigation_elements(self, image_path: str, confidence_threshold: float = 0.5) -> Dict:
        """
        Find navigation elements like back buttons, next buttons, skip options.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Navigation elements organized by type
        """
        try:
            navigation_elements = {
                'back_buttons': [],
                'next_buttons': [],
                'skip_buttons': [],
                'menu_buttons': [],
                'close_buttons': []
            }
            
            # Define navigation text patterns
            nav_patterns = {
                'back_buttons': ['back', '←', '‹', 'previous', 'prev'],
                'next_buttons': ['next', '→', '›', 'continue', 'proceed', 'forward'],
                'skip_buttons': ['skip', 'not now', 'maybe later', 'do this later'],
                'menu_buttons': ['menu', '☰', '≡', 'options', 'settings'],
                'close_buttons': ['close', '×', '✕', 'cancel', 'dismiss']
            }
            
            for nav_type, patterns in nav_patterns.items():
                for pattern in patterns:
                    matches = self.find_text_by_pattern(image_path, pattern, 
                                                      case_sensitive=False, 
                                                      confidence_threshold=confidence_threshold)
                    
                    for match in matches:
                        if self._is_likely_navigation_element(match['bbox'], nav_type):
                            nav_info = {
                                'text': match['text'],
                                'confidence': match['confidence'],
                                'bbox': match['bbox'],
                                'center': self._get_bbox_center(match['bbox']),
                                'click_coords': self._get_optimal_click_coordinates(match['bbox'], nav_type)
                            }
                            navigation_elements[nav_type].append(nav_info)
            
            # Remove duplicates within each category
            for nav_type in navigation_elements:
                navigation_elements[nav_type] = self._remove_duplicate_elements(navigation_elements[nav_type])
            
            total_found = sum(len(elements) for elements in navigation_elements.values())
            logger.info(f"Found {total_found} navigation elements")
            
            return navigation_elements
            
        except Exception as e:
            logger.error(f"Navigation element search failed: {e}")
            return {}

    def find_error_messages(self, image_path: str, confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Find error messages and warnings on the screen.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            List[Dict]: List of found error messages
        """
        try:
            error_indicators = [
                'error', 'invalid', 'incorrect', 'wrong', 'failed', 'required',
                'must', 'cannot', 'unable', 'try again', 'please', 'check',
                'verify', 'confirm', 'missing', 'empty', 'fill', 'enter'
            ]
            
            error_messages = []
            
            for indicator in error_indicators:
                matches = self.find_text_by_pattern(image_path, indicator, 
                                                  case_sensitive=False, 
                                                  confidence_threshold=confidence_threshold)
                
                for match in matches:
                    # Check if this looks like an error message (usually red text or specific positioning)
                    if self._is_likely_error_message(match):
                        error_info = {
                            'message': match['text'],
                            'confidence': match['confidence'],
                            'bbox': match['bbox'],
                            'center': self._get_bbox_center(match['bbox']),
                            'severity': self._assess_error_severity(match['text'])
                        }
                        error_messages.append(error_info)
            
            # Remove duplicates and sort by severity
            unique_errors = self._remove_duplicate_elements(error_messages)
            unique_errors.sort(key=lambda x: x['severity'], reverse=True)
            
            logger.info(f"Found {len(unique_errors)} error messages")
            return unique_errors
            
        except Exception as e:
            logger.error(f"Error message search failed: {e}")
            return []

    def find_captcha_elements(self, image_path: str, confidence_threshold: float = 0.5) -> Optional[Dict]:
        """
        Find CAPTCHA elements on the screen.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            Optional[Dict]: CAPTCHA information if found
        """
        try:
            captcha_indicators = [
                'captcha', 'recaptcha', 'verify', 'robot', 'human',
                "i'm not a robot", 'prove you are human', 'security check'
            ]
            
            for indicator in captcha_indicators:
                matches = self.find_text_by_pattern(image_path, indicator, 
                                                  case_sensitive=False, 
                                                  confidence_threshold=confidence_threshold)
                
                if matches:
                    # Analyze the area around CAPTCHA text for interactive elements
                    captcha_region = self._analyze_captcha_region(image_path, matches[0]['bbox'])
                    
                    captcha_info = {
                        'type': self._identify_captcha_type(matches[0]['text']),
                        'text': matches[0]['text'],
                        'bbox': matches[0]['bbox'],
                        'region': captcha_region,
                        'click_coords': self._get_optimal_click_coordinates(matches[0]['bbox'], 'captcha')
                    }
                    
                    logger.info(f"Found CAPTCHA: {captcha_info['type']}")
                    return captcha_info
            
            return None
            
        except Exception as e:
            logger.error(f"CAPTCHA search failed: {e}")
            return None

    def get_screen_layout_analysis(self, image_path: str, confidence_threshold: float = 0.5) -> Dict:
        """
        Comprehensive analysis of the screen layout and UI elements.
        
        Args:
            image_path: Path to screenshot
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Complete layout analysis
        """
        try:
            logger.info("Starting comprehensive screen layout analysis")
            
            analysis = {
                'ui_elements': self.find_all_ui_elements(image_path, confidence_threshold),
                'input_fields': self.find_input_fields(image_path, confidence_threshold),
                'navigation': self.find_navigation_elements(image_path, confidence_threshold),
                'error_messages': self.find_error_messages(image_path, confidence_threshold),
                'captcha': self.find_captcha_elements(image_path, confidence_threshold),
                'text_layout': self.analyze_text_layout(image_path, confidence_threshold),
                'screen_type': self._identify_screen_type(image_path, confidence_threshold)
            }
            
            # Add interaction suggestions
            analysis['interaction_suggestions'] = self._generate_interaction_suggestions(analysis)
            
            logger.info("Screen layout analysis completed")
            return analysis
            
        except Exception as e:
            logger.error(f"Screen layout analysis failed: {e}")
            return {}

    # ========== HELPER METHODS FOR ELEMENT LOCALIZATION ==========
    
    def _select_best_ui_element_match(self, matches: List[Dict], keywords: List[str], 
                                    element_type: str) -> Optional[Dict]:
        """Select the best match for a UI element based on relevance and confidence."""
        if not matches:
            return None
        
        scored_matches = []
        
        for match in matches:
            score = match['confidence']
            text_lower = match['text'].lower()
            
            # Boost score for exact keyword matches
            for keyword in keywords:
                if keyword in text_lower:
                    score += 0.1
                    
            # Boost score for element-specific patterns
            if element_type == 'email_field' and '@' in text_lower:
                score += 0.2
            elif element_type == 'password_field' and len(text_lower) < 15:  # Password labels are usually short
                score += 0.1
            
            scored_matches.append((score, match))
        
        # Return the highest scoring match
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return scored_matches[0][1]

    def _get_bbox_center(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """Calculate the center point of a bounding box."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _get_optimal_click_coordinates(self, bbox: Tuple[int, int, int, int], 
                                     element_type: str) -> Tuple[int, int]:
        """Calculate optimal click coordinates for different element types."""
        x1, y1, x2, y2 = bbox
        
        if element_type in ['input_field', 'email_field', 'password_field']:
            # For input fields, click slightly right of center to avoid labels
            return (x1 + int((x2 - x1) * 0.7), (y1 + y2) // 2)
        elif element_type in ['button', 'next_button', 'back_button']:
            # For buttons, click in the center
            return ((x1 + x2) // 2, (y1 + y2) // 2)
        elif element_type == 'captcha':
            # For CAPTCHA, click in the center
            return ((x1 + x2) // 2, (y1 + y2) // 2)
        else:
            # Default to center
            return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _is_likely_button(self, bbox: Tuple[int, int, int, int]) -> bool:
        """Check if a bounding box is likely to be a button."""
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        
        # Buttons are usually rectangular and not too thin
        aspect_ratio = width / height if height > 0 else 0
        
        return (
            width >= 30 and width <= 400 and  # Reasonable width
            height >= 20 and height <= 100 and  # Reasonable height
            0.5 <= aspect_ratio <= 8  # Not too thin or too wide
        )

    def _is_likely_navigation_element(self, bbox: Tuple[int, int, int, int], nav_type: str) -> bool:
        """Check if a bounding box is likely to be a navigation element."""
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        
        if nav_type in ['back_buttons', 'close_buttons']:
            # Back and close buttons are usually smaller and near edges
            return width <= 150 and height <= 80
        elif nav_type in ['next_buttons']:
            # Next buttons can be larger
            return width <= 300 and height <= 100
        elif nav_type in ['skip_buttons']:
            # Skip buttons are usually text-based and medium sized
            return width <= 200 and height <= 60
        else:
            return True  # Default to accepting

    def _is_likely_error_message(self, text_element: Dict) -> bool:
        """Check if a text element is likely to be an error message."""
        text = text_element['text'].lower()
        
        # Error messages often contain specific words
        error_words = ['error', 'invalid', 'required', 'try again', 'incorrect']
        has_error_word = any(word in text for word in error_words)
        
        # Error messages are usually not too long
        reasonable_length = 5 <= len(text) <= 200
        
        return has_error_word and reasonable_length

    def _assess_error_severity(self, error_text: str) -> int:
        """Assess the severity of an error message (1-10 scale)."""
        text_lower = error_text.lower()
        
        if any(word in text_lower for word in ['required', 'must', 'cannot']):
            return 8  # High severity
        elif any(word in text_lower for word in ['invalid', 'incorrect', 'wrong']):
            return 6  # Medium severity
        elif any(word in text_lower for word in ['please', 'try again', 'check']):
            return 4  # Low severity
        else:
            return 2  # Very low severity

    def _find_input_area_near_label(self, label_bbox: Tuple[int, int, int, int], 
                                   all_text: List[Dict]) -> Optional[Tuple[int, int, int, int]]:
        """Find input area near a label."""
        x1, y1, x2, y2 = label_bbox
        
        # Look for empty areas or field indicators near the label
        search_radius = 100
        
        # Common input field area would be below or to the right of label
        potential_areas = [
            (x1, y2, x2 + 200, y2 + 50),  # Below label
            (x2, y1, x2 + 200, y2),       # Right of label
        ]
        
        for area in potential_areas:
            # Check if this area doesn't overlap with other text
            overlaps = False
            for text_elem in all_text:
                if self._boxes_overlap(area, text_elem['bbox']):
                    overlaps = True
                    break
            
            if not overlaps:
                return area
        
        return None

    def _boxes_overlap(self, box1: Tuple[int, int, int, int], 
                      box2: Tuple[int, int, int, int]) -> bool:
        """Check if two bounding boxes overlap."""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        return not (x2_1 < x1_2 or x2_2 < x1_1 or y2_1 < y1_2 or y2_2 < y1_1)

    def _remove_duplicate_elements(self, elements: List[Dict], 
                                 proximity_threshold: int = 30) -> List[Dict]:
        """Remove duplicate elements based on proximity."""
        if not elements:
            return []
        
        unique_elements = []
        
        for element in elements:
            is_duplicate = False
            
            for unique_elem in unique_elements:
                # Check if elements are too close to each other
                center1 = element.get('center', self._get_bbox_center(element['bbox']))
                center2 = unique_elem.get('center', self._get_bbox_center(unique_elem['bbox']))
                
                distance = ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5
                
                if distance < proximity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_elements.append(element)
        
        return unique_elements

    def _remove_duplicate_input_fields(self, fields: List[Dict]) -> List[Dict]:
        """Remove duplicate input fields, keeping the best match for each type."""
        if not fields:
            return []
        
        field_types = {}
        
        for field in fields:
            field_type = field['field_type']
            
            if field_type not in field_types:
                field_types[field_type] = field
            else:
                # Keep the field with better positioning or more specific label
                current = field_types[field_type]
                if len(field['label_text']) > len(current['label_text']):
                    field_types[field_type] = field
        
        return list(field_types.values())

    def _analyze_captcha_region(self, image_path: str, captcha_bbox: Tuple[int, int, int, int]) -> Dict:
        """Analyze the region around a CAPTCHA for interactive elements."""
        # This would involve more complex image analysis
        # For now, return basic region information
        x1, y1, x2, y2 = captcha_bbox
        
        return {
            'checkbox_area': (x1 - 50, y1 - 20, x1, y1 + 20),
            'image_area': (x1, y2, x2, y2 + 100),
            'text_input_area': (x1, y2 + 100, x2, y2 + 140)
        }

    def _identify_captcha_type(self, captcha_text: str) -> str:
        """Identify the type of CAPTCHA based on text."""
        text_lower = captcha_text.lower()
        
        if 'recaptcha' in text_lower:
            return 'recaptcha'
        elif 'robot' in text_lower:
            return 'checkbox_captcha'
        elif 'image' in text_lower:
            return 'image_captcha'
        elif 'audio' in text_lower:
            return 'audio_captcha'
        else:
            return 'unknown_captcha'

    def _identify_screen_type(self, image_path: str, confidence_threshold: float) -> str:
        """Identify the type of screen being displayed."""
        try:
            all_text = self.get_all_text_as_string(image_path, confidence_threshold).lower()
            
            # Define screen type indicators
            screen_indicators = {
                'login': ['sign in', 'log in', 'email', 'password', 'forgot password'],
                'registration': ['create account', 'sign up', 'register', 'first name', 'last name'],
                'verification': ['verify', 'code', 'phone number', 'sms', 'enter code'],
                'privacy': ['privacy', 'terms', 'policy', 'agree', 'accept'],
                'personal_info': ['birthday', 'gender', 'recovery', 'phone'],
                'captcha': ['captcha', 'recaptcha', 'robot', 'verify you are human'],
                'error': ['error', 'something went wrong', 'try again', 'problem'],
                'success': ['welcome', 'success', 'complete', 'congratulations']
            }
            
            # Score each screen type
            scores = {}
            for screen_type, indicators in screen_indicators.items():
                score = sum(1 for indicator in indicators if indicator in all_text)
                if score > 0:
                    scores[screen_type] = score
            
            if scores:
                # Return the screen type with the highest score
                return max(scores.items(), key=lambda x: x[1])[0]
            else:
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Screen type identification failed: {e}")
            return 'unknown'

    def _generate_interaction_suggestions(self, analysis: Dict) -> List[str]:
        """Generate suggestions for interacting with the current screen."""
        suggestions = []
        
        try:
            screen_type = analysis.get('screen_type', 'unknown')
            ui_elements = analysis.get('ui_elements', {})
            input_fields = analysis.get('input_fields', [])
            navigation = analysis.get('navigation', {})
            error_messages = analysis.get('error_messages', [])
            captcha = analysis.get('captcha')
            
            # Add suggestions based on screen type and available elements
            if screen_type == 'login':
                if 'email_field' in ui_elements:
                    suggestions.append("Fill in email address")
                if 'password_field' in ui_elements:
                    suggestions.append("Enter password")
                if navigation.get('next_buttons'):
                    suggestions.append("Click sign in button")
                    
            elif screen_type == 'registration':
                for field in input_fields:
                    suggestions.append(f"Fill in {field['field_type']} field")
                if navigation.get('next_buttons'):
                    suggestions.append("Proceed to next step")
                    
            elif screen_type == 'verification':
                suggestions.append("Check phone for verification code")
                if input_fields:
                    suggestions.append("Enter verification code")
                    
            elif screen_type == 'captcha':
                if captcha:
                    suggestions.append(f"Complete {captcha['type']} verification")
                    
            # Add error-specific suggestions
            if error_messages:
                suggestions.append("Address error messages before proceeding")
                for error in error_messages:
                    if 'required' in error['message'].lower():
                        suggestions.append("Fill in required fields")
                    elif 'invalid' in error['message'].lower():
                        suggestions.append("Correct invalid information")
            
            # Add navigation suggestions
            if navigation.get('skip_buttons'):
                suggestions.append("Option to skip this step available")
            if navigation.get('back_buttons'):
                suggestions.append("Go back to previous step if needed")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}")
            return ["Unable to generate interaction suggestions"]

    # ========== PERFORMANCE OPTIMIZATION METHODS ==========
    
    def batch_process_images(self, image_paths: List[str], confidence_threshold: float = 0.5,
                           use_cache: bool = True, max_workers: int = 4) -> Dict[str, List[Dict]]:
        """
        Process multiple images in parallel for better performance.
        
        Args:
            image_paths: List of image file paths
            confidence_threshold: Minimum confidence score
            use_cache: Whether to use cached results
            max_workers: Maximum number of worker threads
            
        Returns:
            Dict[str, List[Dict]]: OCR results for each image
        """
        try:
            import concurrent.futures
            import threading
            
            logger.info(f"Starting batch processing of {len(image_paths)} images with {max_workers} workers")
            start_time = time.time()
            
            results = {}
            lock = threading.Lock()
            
            def process_single_image(image_path: str) -> None:
                try:
                    ocr_result = self.perform_ocr(image_path, confidence_threshold, use_cache)
                    with lock:
                        results[image_path] = ocr_result
                except Exception as e:
                    logger.error(f"Failed to process {image_path}: {e}")
                    with lock:
                        results[image_path] = []
            
            # Process images in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_single_image, path) for path in image_paths]
                concurrent.futures.wait(futures)
            
            processing_time = time.time() - start_time
            successful_results = sum(1 for r in results.values() if r)
            
            logger.info(f"Batch processing completed in {processing_time:.2f}s")
            logger.info(f"Successfully processed {successful_results}/{len(image_paths)} images")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return {}

    def batch_find_ui_elements(self, image_paths: List[str], element_types: List[str],
                             confidence_threshold: float = 0.5, max_workers: int = 4) -> Dict[str, Dict]:
        """
        Find UI elements in multiple images in parallel.
        
        Args:
            image_paths: List of image file paths
            element_types: List of UI element types to search for
            confidence_threshold: Minimum confidence score
            max_workers: Maximum number of worker threads
            
        Returns:
            Dict[str, Dict]: UI elements found in each image
        """
        try:
            import concurrent.futures
            import threading
            
            logger.info(f"Batch UI element search in {len(image_paths)} images for {element_types}")
            start_time = time.time()
            
            results = {}
            lock = threading.Lock()
            
            def find_elements_in_image(image_path: str) -> None:
                try:
                    image_elements = {}
                    for element_type in element_types:
                        element = self.find_ui_element_by_type(image_path, element_type, confidence_threshold)
                        if element:
                            image_elements[element_type] = element
                    
                    with lock:
                        results[image_path] = image_elements
                        
                except Exception as e:
                    logger.error(f"UI element search failed for {image_path}: {e}")
                    with lock:
                        results[image_path] = {}
            
            # Process images in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(find_elements_in_image, path) for path in image_paths]
                concurrent.futures.wait(futures)
            
            processing_time = time.time() - start_time
            total_elements_found = sum(len(elements) for elements in results.values())
            
            logger.info(f"Batch UI element search completed in {processing_time:.2f}s")
            logger.info(f"Found {total_elements_found} total elements across all images")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch UI element search failed: {e}")
            return {}

    def optimize_ocr_settings(self, test_images: List[str], target_accuracy: float = 0.85) -> Dict:
        """
        Automatically optimize OCR settings for best performance on given test images.
        
        Args:
            test_images: List of representative test images
            target_accuracy: Target accuracy threshold
            
        Returns:
            Dict: Optimized settings configuration
        """
        try:
            logger.info(f"Optimizing OCR settings on {len(test_images)} test images")
            
            # Test different preprocessing configurations
            test_configs = [
                {"preprocess": {"level": "light"}},
                {"preprocess": {"level": "medium"}},
                {"preprocess": {"level": "heavy"}},
                {"enhance_contrast": {"contrast": 1.2, "brightness": 10}, "preprocess": {"level": "medium"}},
                {"sharpen": {"strength": 1.0}, "preprocess": {"level": "medium"}},
                {"denoise": {}, "preprocess": {"level": "medium"}},
            ]
            
            config_results = []
            
            for i, config in enumerate(test_configs):
                logger.info(f"Testing configuration {i+1}/{len(test_configs)}")
                total_confidence = 0
                total_elements = 0
                processing_times = []
                
                for image_path in test_images:
                    start_time = time.time()
                    
                    # Apply preprocessing
                    preprocessed_path = self.create_preprocessing_pipeline(image_path, config)
                    if not preprocessed_path:
                        preprocessed_path = image_path
                    
                    # Perform OCR
                    results = self.perform_ocr(preprocessed_path, confidence_threshold=0.3, use_cache=False)
                    
                    processing_time = time.time() - start_time
                    processing_times.append(processing_time)
                    
                    # Calculate metrics
                    if results:
                        total_confidence += sum(r['confidence'] for r in results)
                        total_elements += len(results)
                    
                    # Clean up
                    if preprocessed_path != image_path:
                        try:
                            Path(preprocessed_path).unlink()
                        except Exception:
                            pass
                
                # Calculate average metrics
                avg_confidence = total_confidence / total_elements if total_elements > 0 else 0
                avg_processing_time = sum(processing_times) / len(processing_times)
                
                config_results.append({
                    'config': config,
                    'avg_confidence': avg_confidence,
                    'avg_processing_time': avg_processing_time,
                    'total_elements_found': total_elements,
                    'score': avg_confidence * 0.7 + (1 / avg_processing_time) * 0.3  # Weighted score
                })
            
            # Select best configuration
            best_config = max(config_results, key=lambda x: x['score'])
            
            logger.info(f"Best configuration found with score {best_config['score']:.3f}")
            logger.info(f"Average confidence: {best_config['avg_confidence']:.3f}")
            logger.info(f"Average processing time: {best_config['avg_processing_time']:.2f}s")
            
            return {
                'optimal_config': best_config['config'],
                'performance_metrics': best_config,
                'all_results': config_results
            }
            
        except Exception as e:
            logger.error(f"OCR settings optimization failed: {e}")
            return {}

    def create_ocr_performance_report(self, image_paths: List[str], 
                                    confidence_threshold: float = 0.5) -> Dict:
        """
        Generate a comprehensive performance report for OCR operations.
        
        Args:
            image_paths: List of test images
            confidence_threshold: Minimum confidence score
            
        Returns:
            Dict: Performance report with detailed metrics
        """
        try:
            logger.info(f"Generating OCR performance report for {len(image_paths)} images")
            start_time = time.time()
            
            report = {
                'total_images': len(image_paths),
                'processing_times': [],
                'confidence_scores': [],
                'text_elements_found': [],
                'cache_hits': 0,
                'cache_misses': 0,
                'errors': [],
                'image_quality_metrics': []
            }
            
            for image_path in image_paths:
                try:
                    # Check if result is cached
                    cached_result = self._get_cached_ocr_result(image_path)
                    if cached_result:
                        report['cache_hits'] += 1
                    else:
                        report['cache_misses'] += 1
                    
                    # Measure processing time
                    process_start = time.time()
                    results = self.perform_ocr(image_path, confidence_threshold)
                    process_time = time.time() - process_start
                    
                    report['processing_times'].append(process_time)
                    
                    if results:
                        confidences = [r['confidence'] for r in results]
                        report['confidence_scores'].extend(confidences)
                        report['text_elements_found'].append(len(results))
                    else:
                        report['text_elements_found'].append(0)
                    
                    # Get image quality metrics
                    quality_metrics = self.get_image_quality_metrics(image_path)
                    if quality_metrics:
                        quality_metrics['image_path'] = image_path
                        report['image_quality_metrics'].append(quality_metrics)
                    
                except Exception as e:
                    error_info = {'image_path': image_path, 'error': str(e)}
                    report['errors'].append(error_info)
                    logger.error(f"Error processing {image_path}: {e}")
            
            total_time = time.time() - start_time
            
            # Calculate summary statistics
            if report['processing_times']:
                report['performance_summary'] = {
                    'total_processing_time': total_time,
                    'avg_processing_time_per_image': sum(report['processing_times']) / len(report['processing_times']),
                    'min_processing_time': min(report['processing_times']),
                    'max_processing_time': max(report['processing_times']),
                    'images_per_second': len(image_paths) / total_time
                }
            
            if report['confidence_scores']:
                report['accuracy_summary'] = {
                    'avg_confidence': sum(report['confidence_scores']) / len(report['confidence_scores']),
                    'min_confidence': min(report['confidence_scores']),
                    'max_confidence': max(report['confidence_scores']),
                    'high_confidence_ratio': len([c for c in report['confidence_scores'] if c > 0.8]) / len(report['confidence_scores'])
                }
            
            if report['text_elements_found']:
                report['detection_summary'] = {
                    'total_elements_found': sum(report['text_elements_found']),
                    'avg_elements_per_image': sum(report['text_elements_found']) / len(report['text_elements_found']),
                    'max_elements_in_image': max(report['text_elements_found']),
                    'images_with_no_text': len([c for c in report['text_elements_found'] if c == 0])
                }
            
            report['cache_summary'] = {
                'cache_hit_rate': report['cache_hits'] / (report['cache_hits'] + report['cache_misses']) if (report['cache_hits'] + report['cache_misses']) > 0 else 0,
                'cache_effectiveness': report['cache_hits']
            }
            
            logger.info("OCR performance report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Performance report generation failed: {e}")
            return {}

    def warm_up_ocr_engine(self, sample_images: List[str] = None) -> bool:
        """
        Warm up the OCR engine for better performance in subsequent operations.
        
        Args:
            sample_images: List of sample images to use for warm-up
            
        Returns:
            bool: True if warm-up successful
        """
        try:
            logger.info("Warming up OCR engine...")
            
            if not sample_images:
                # Create a simple test image if none provided
                import numpy as np
                from PIL import Image, ImageDraw, ImageFont
                
                # Create a simple test image with text
                img = Image.new('RGB', (300, 100), color='white')
                draw = ImageDraw.Draw(img)
                
                try:
                    # Try to use a system font
                    font = ImageFont.truetype("arial.ttf", 20)
                except:
                    font = ImageFont.load_default()
                
                draw.text((10, 40), "Test OCR Warm-up", fill='black', font=font)
                
                # Save test image
                test_image_path = self.cache_dir / "warmup_test.png"
                img.save(test_image_path)
                sample_images = [str(test_image_path)]
            
            # Perform OCR on sample images to warm up the engine
            warmup_start = time.time()
            
            for image_path in sample_images:
                try:
                    self.perform_ocr(image_path, use_cache=False)
                except Exception as e:
                    logger.warning(f"Warm-up failed for {image_path}: {e}")
            
            warmup_time = time.time() - warmup_start
            logger.info(f"OCR engine warmed up in {warmup_time:.2f}s")
            
            # Clean up test image if we created one
            if len(sample_images) == 1 and sample_images[0].endswith("warmup_test.png"):
                try:
                    Path(sample_images[0]).unlink()
                except Exception:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"OCR engine warm-up failed: {e}")
            return False

    def monitor_performance(self, operation_name: str = "OCR Operation") -> 'PerformanceMonitor':
        """
        Create a performance monitor context manager for tracking operation metrics.
        
        Args:
            operation_name: Name of the operation being monitored
            
        Returns:
            PerformanceMonitor: Context manager for performance monitoring
        """
        return PerformanceMonitor(operation_name)

    def get_system_resource_usage(self) -> Dict:
        """
        Get current system resource usage for performance monitoring.
        
        Returns:
            Dict: System resource information
        """
        try:
            import psutil
            
            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_total_gb': memory.total / (1024**3),
                'memory_available_gb': memory.available / (1024**3),
                'memory_percent': memory.percent,
                'disk_total_gb': disk.total / (1024**3),
                'disk_free_gb': disk.free / (1024**3),
                'disk_percent': (disk.used / disk.total) * 100
            }
            
        except ImportError:
            logger.warning("psutil not available, cannot get system resource usage")
            return {}
        except Exception as e:
            logger.error(f"Failed to get system resource usage: {e}")
            return {}

    def optimize_cache_size(self, target_size_mb: int = 100) -> int:
        """
        Optimize cache size by removing old entries to stay within target size.
        
        Args:
            target_size_mb: Target cache size in megabytes
            
        Returns:
            int: Number of cache files removed
        """
        try:
            cache_info = self.get_cache_info()
            current_size_mb = cache_info.get('total_size_mb', 0)
            
            if current_size_mb <= target_size_mb:
                logger.debug(f"Cache size ({current_size_mb:.1f}MB) within target ({target_size_mb}MB)")
                return 0
            
            logger.info(f"Optimizing cache size from {current_size_mb:.1f}MB to {target_size_mb}MB")
            
            # Get all cache files sorted by modification time (oldest first)
            cache_files = list(self.cache_dir.glob("*.json"))
            cache_files.sort(key=lambda f: f.stat().st_mtime)
            
            removed_count = 0
            total_size_removed = 0
            
            for cache_file in cache_files:
                try:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink()
                    removed_count += 1
                    total_size_removed += file_size
                    
                    # Check if we've reached target size
                    current_size_mb = (cache_info['total_size_mb'] * 1024 * 1024 - total_size_removed) / (1024 * 1024)
                    if current_size_mb <= target_size_mb:
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to remove cache file {cache_file}: {e}")
            
            logger.info(f"Cache optimization completed: removed {removed_count} files ({total_size_removed / (1024*1024):.1f}MB)")
            return removed_count
            
        except Exception as e:
            logger.error(f"Cache optimization failed: {e}")
            return 0

    def benchmark_ocr_performance(self, test_images: List[str], iterations: int = 3) -> Dict:
        """
        Benchmark OCR performance with multiple iterations for accurate timing.
        
        Args:
            test_images: List of test images
            iterations: Number of iterations to run
            
        Returns:
            Dict: Benchmark results
        """
        try:
            logger.info(f"Benchmarking OCR performance with {len(test_images)} images, {iterations} iterations")
            
            benchmark_results = {
                'test_images': test_images,
                'iterations': iterations,
                'iteration_results': [],
                'summary': {}
            }
            
            for iteration in range(iterations):
                logger.info(f"Running benchmark iteration {iteration + 1}/{iterations}")
                
                iteration_start = time.time()
                iteration_results = {
                    'iteration': iteration + 1,
                    'processing_times': [],
                    'total_elements': 0,
                    'avg_confidence': 0
                }
                
                total_confidence = 0
                total_elements = 0
                
                for image_path in test_images:
                    start_time = time.time()
                    results = self.perform_ocr(image_path, use_cache=False)  # Don't use cache for benchmarking
                    processing_time = time.time() - start_time
                    
                    iteration_results['processing_times'].append(processing_time)
                    
                    if results:
                        total_elements += len(results)
                        total_confidence += sum(r['confidence'] for r in results)
                
                iteration_results['total_elements'] = total_elements
                iteration_results['avg_confidence'] = total_confidence / total_elements if total_elements > 0 else 0
                iteration_results['total_time'] = time.time() - iteration_start
                iteration_results['images_per_second'] = len(test_images) / iteration_results['total_time']
                
                benchmark_results['iteration_results'].append(iteration_results)
            
            # Calculate summary statistics
            all_processing_times = []
            all_images_per_second = []
            all_avg_confidences = []
            
            for result in benchmark_results['iteration_results']:
                all_processing_times.extend(result['processing_times'])
                all_images_per_second.append(result['images_per_second'])
                all_avg_confidences.append(result['avg_confidence'])
            
            benchmark_results['summary'] = {
                'avg_processing_time_per_image': sum(all_processing_times) / len(all_processing_times),
                'min_processing_time': min(all_processing_times),
                'max_processing_time': max(all_processing_times),
                'avg_images_per_second': sum(all_images_per_second) / len(all_images_per_second),
                'avg_confidence_across_runs': sum(all_avg_confidences) / len(all_avg_confidences),
                'performance_consistency': 1 - (max(all_images_per_second) - min(all_images_per_second)) / max(all_images_per_second)
            }
            
            logger.info("OCR performance benchmark completed")
            logger.info(f"Average processing: {benchmark_results['summary']['avg_processing_time_per_image']:.3f}s per image")
            logger.info(f"Average throughput: {benchmark_results['summary']['avg_images_per_second']:.1f} images/second")
            
            return benchmark_results
            
        except Exception as e:
            logger.error(f"OCR performance benchmark failed: {e}")
            return {}

class PerformanceMonitor:
    """Context manager for monitoring OCR operation performance."""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.memory_before = None
        self.memory_after = None
        
    def __enter__(self):
        self.start_time = time.time()
        try:
            import psutil
            self.memory_before = psutil.virtual_memory().used
        except ImportError:
            self.memory_before = None
        
        logger.debug(f"Starting performance monitoring for: {self.operation_name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        try:
            import psutil
            self.memory_after = psutil.virtual_memory().used
        except ImportError:
            self.memory_after = None
        
        duration = self.end_time - self.start_time
        memory_diff = (self.memory_after - self.memory_before) / (1024*1024) if self.memory_before and self.memory_after else 0
        
        logger.info(f"Performance report for '{self.operation_name}':")
        logger.info(f"  Duration: {duration:.3f}s")
        if memory_diff != 0:
            logger.info(f"  Memory change: {memory_diff:+.1f}MB")
        
        # Log warning if operation took too long
        if duration > 10:
            logger.warning(f"Operation '{self.operation_name}' took {duration:.1f}s - consider optimization")
    
    def get_duration(self) -> float:
        """Get the duration of the monitored operation."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0 