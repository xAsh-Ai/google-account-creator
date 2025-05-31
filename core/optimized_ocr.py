"""
Optimized OCR Service for Google Account Creator

High-performance OCR service with advanced optimizations:
- Image preprocessing and enhancement
- Result caching and memoization
- Batch processing capabilities
- GPU acceleration support
- Parallel processing
- Memory-efficient image handling
- Performance monitoring and profiling

This service aims to reduce OCR processing time by 50-70% compared to the basic implementation.
"""

import cv2
import numpy as np
import hashlib
import pickle
import os
import time
import threading
import asyncio
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache, wraps
import logging
from datetime import datetime, timedelta
import json
import base64
from PIL import Image, ImageEnhance, ImageFilter
import multiprocessing as mp

# Performance monitoring
from core.profiler import profile_function, get_profiler

logger = logging.getLogger(__name__)

@dataclass
class OCRResult:
    """OCR result with metadata"""
    text: str
    confidence: float
    processing_time: float
    image_hash: str
    preprocessing_applied: List[str]
    model_used: str
    bounding_boxes: Optional[List[Dict]] = None
    characters_detected: Optional[int] = None

@dataclass 
class OCRConfig:
    """OCR configuration and optimization settings"""
    # Caching settings
    cache_enabled: bool = True
    cache_size: int = 1000
    cache_ttl_hours: int = 24
    
    # Image preprocessing
    auto_enhance: bool = True
    denoise: bool = True
    sharpen: bool = True
    contrast_enhance: bool = True
    
    # Performance settings
    use_gpu: bool = True
    batch_size: int = 4
    max_workers: int = 4
    timeout_seconds: int = 30
    
    # Quality settings
    min_confidence: float = 0.7
    retry_on_low_confidence: bool = True
    max_retries: int = 2

class ImageCache:
    """High-performance image result cache"""
    
    def __init__(self, max_size: int = 1000, ttl_hours: int = 24):
        self.max_size = max_size
        self.ttl_seconds = ttl_hours * 3600
        self.cache: Dict[str, Tuple[OCRResult, float]] = {}
        self.access_times: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, timestamp) in self.cache.items()
                if current_time - timestamp > self.ttl_seconds
            ]
            for key in expired_keys:
                del self.cache[key]
                del self.access_times[key]
    
    def _evict_lru(self):
        """Evict least recently used items"""
        if len(self.cache) >= self.max_size:
            with self._lock:
                # Sort by access time and remove oldest
                sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])
                num_to_remove = len(self.cache) - self.max_size + 1
                
                for key, _ in sorted_items[:num_to_remove]:
                    if key in self.cache:
                        del self.cache[key]
                        del self.access_times[key]
    
    def get(self, image_hash: str) -> Optional[OCRResult]:
        """Get cached result"""
        with self._lock:
            if image_hash in self.cache:
                result, timestamp = self.cache[image_hash]
                current_time = time.time()
                
                # Check if expired
                if current_time - timestamp > self.ttl_seconds:
                    del self.cache[image_hash]
                    del self.access_times[image_hash]
                    return None
                
                # Update access time
                self.access_times[image_hash] = current_time
                return result
            
            return None
    
    def put(self, image_hash: str, result: OCRResult):
        """Cache result"""
        with self._lock:
            self._cleanup_expired()
            self._evict_lru()
            
            current_time = time.time()
            self.cache[image_hash] = (result, current_time)
            self.access_times[image_hash] = current_time
    
    def clear(self):
        """Clear all cache"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': getattr(self, '_hits', 0) / max(getattr(self, '_requests', 1), 1),
                'oldest_entry_age': time.time() - min(
                    (timestamp for _, timestamp in self.cache.values()),
                    default=time.time()
                )
            }

class ImagePreprocessor:
    """Advanced image preprocessing for optimal OCR"""
    
    @staticmethod
    @profile_function
    def calculate_image_hash(image: np.ndarray) -> str:
        """Calculate hash for image caching"""
        # Use image content hash for caching
        image_bytes = cv2.imencode('.png', image)[1].tobytes()
        return hashlib.sha256(image_bytes).hexdigest()[:16]
    
    @staticmethod
    @profile_function
    def resize_for_ocr(image: np.ndarray, target_height: int = 64) -> np.ndarray:
        """Resize image to optimal size for OCR"""
        height, width = image.shape[:2]
        
        # Calculate optimal scale
        if height < target_height:
            scale = target_height / height
            new_width = int(width * scale)
            new_height = target_height
            
            # Use high-quality interpolation
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        return image
    
    @staticmethod
    @profile_function
    def denoise_image(image: np.ndarray) -> np.ndarray:
        """Remove noise from image"""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Apply multiple denoising techniques
        # Gaussian blur for general noise
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # Bilateral filter to preserve edges
        denoised = cv2.bilateralFilter(denoised, 9, 75, 75)
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
        
        return denoised
    
    @staticmethod
    @profile_function
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Enhance image contrast for better OCR"""
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)
        
        # Additional contrast stretching
        min_val, max_val = np.percentile(enhanced, [5, 95])
        enhanced = np.clip((enhanced - min_val) * 255 / (max_val - min_val), 0, 255).astype(np.uint8)
        
        return enhanced
    
    @staticmethod
    @profile_function  
    def sharpen_image(image: np.ndarray) -> np.ndarray:
        """Sharpen image for better text recognition"""
        # Unsharp mask
        gaussian = cv2.GaussianBlur(image, (0, 0), 2.0)
        sharpened = cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
        
        # Additional sharpening kernel
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1], 
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(sharpened, -1, kernel)
        
        return np.clip(sharpened, 0, 255).astype(np.uint8)
    
    @staticmethod
    @profile_function
    def binarize_image(image: np.ndarray) -> np.ndarray:
        """Convert to binary image with optimal threshold"""
        # Try multiple binarization methods and choose best
        methods = [
            lambda img: cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
            lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),
            lambda img: cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
        ]
        
        best_image = None
        best_score = 0
        
        for method in methods:
            try:
                binary = method(image)
                # Score based on text-like regions
                score = ImagePreprocessor._score_binarization(binary)
                if score > best_score:
                    best_score = score
                    best_image = binary
            except Exception:
                continue
        
        return best_image if best_image is not None else methods[0](image)
    
    @staticmethod
    def _score_binarization(binary_image: np.ndarray) -> float:
        """Score binarization quality"""
        # Count connected components (text regions)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_image, connectivity=8)
        
        # Filter components by size (typical text characteristics)
        text_components = 0
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            width = stats[i, cv2.CC_STAT_WIDTH] 
            height = stats[i, cv2.CC_STAT_HEIGHT]
            
            # Text-like aspect ratio and size
            if 5 < area < 1000 and 0.1 < width/height < 10:
                text_components += 1
        
        return text_components
    
    @classmethod
    @profile_function
    def preprocess_image(cls, image: np.ndarray, config: OCRConfig) -> Tuple[np.ndarray, List[str]]:
        """Apply comprehensive image preprocessing"""
        applied_steps = []
        processed = image.copy()
        
        try:
            # Resize to optimal size
            processed = cls.resize_for_ocr(processed)
            applied_steps.append("resize")
            
            # Convert to grayscale if needed
            if len(processed.shape) == 3:
                processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
                applied_steps.append("grayscale")
            
            # Apply denoising
            if config.denoise:
                processed = cls.denoise_image(processed)
                applied_steps.append("denoise")
            
            # Enhance contrast
            if config.contrast_enhance:
                processed = cls.enhance_contrast(processed)
                applied_steps.append("contrast")
            
            # Sharpen image
            if config.sharpen:
                processed = cls.sharpen_image(processed)
                applied_steps.append("sharpen")
            
            # Binarization
            processed = cls.binarize_image(processed)
            applied_steps.append("binarize")
            
        except Exception as e:
            logger.warning(f"Preprocessing error: {e}, using original image")
            processed = image
            applied_steps = ["error_fallback"]
        
        return processed, applied_steps

class OptimizedOCRService:
    """High-performance OCR service with comprehensive optimizations"""
    
    def __init__(self, config: OCRConfig = None):
        self.config = config or OCRConfig()
        self.cache = ImageCache(self.config.cache_size, self.config.cache_ttl_hours)
        self.preprocessor = ImagePreprocessor()
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'total_processing_time': 0,
            'average_confidence': 0,
            'preprocessing_time': 0
        }
        
        # Thread pool for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_workers)
        
        # Try to initialize OCR engines
        self._init_ocr_engines()
        
        logger.info(f"OptimizedOCRService initialized with config: {self.config}")
    
    def _init_ocr_engines(self):
        """Initialize available OCR engines"""
        self.ocr_engines = {}
        
        # Try to initialize different OCR engines
        engines_to_try = [
            ('tesseract', self._init_tesseract),
            ('paddleocr', self._init_paddleocr),
            ('easyocr', self._init_easyocr)
        ]
        
        for engine_name, init_func in engines_to_try:
            try:
                engine = init_func()
                if engine:
                    self.ocr_engines[engine_name] = engine
                    logger.info(f"✅ {engine_name} OCR engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize {engine_name}: {e}")
        
        if not self.ocr_engines:
            logger.warning("⚠️ No OCR engines available, using fallback")
            self.ocr_engines['fallback'] = self._create_fallback_engine()
    
    def _init_tesseract(self):
        """Initialize Tesseract OCR"""
        try:
            import pytesseract
            # Test if tesseract is working
            pytesseract.get_tesseract_version()
            return pytesseract
        except:
            return None
    
    def _init_paddleocr(self):
        """Initialize PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
            return PaddleOCR(use_angle_cls=True, lang='en', use_gpu=self.config.use_gpu)
        except:
            return None
    
    def _init_easyocr(self):
        """Initialize EasyOCR"""
        try:
            import easyocr
            return easyocr.Reader(['en'], gpu=self.config.use_gpu)
        except:
            return None
    
    def _create_fallback_engine(self):
        """Create fallback OCR engine"""
        class FallbackOCR:
            def image_to_string(self, image, **kwargs):
                return "OCR_FALLBACK_TEXT"
            
            def ocr(self, image):
                return [("OCR_FALLBACK_TEXT", 0.5)]
        
        return FallbackOCR()
    
    @profile_function
    def process_image(self, image: Union[np.ndarray, str, Path], engine: str = None) -> OCRResult:
        """Process single image with OCR"""
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                raise ValueError(f"Could not load image: {image}")
        
        # Calculate image hash for caching
        image_hash = self.preprocessor.calculate_image_hash(image)
        
        # Check cache first
        if self.config.cache_enabled:
            cached_result = self.cache.get(image_hash)
            if cached_result:
                self.stats['cache_hits'] += 1
                logger.debug(f"Cache hit for image {image_hash[:8]}")
                return cached_result
        
        # Preprocess image
        preprocess_start = time.time()
        processed_image, applied_steps = self.preprocessor.preprocess_image(image, self.config)
        preprocess_time = time.time() - preprocess_start
        self.stats['preprocessing_time'] += preprocess_time
        
        # Select OCR engine
        selected_engine = engine or self._select_best_engine()
        ocr_engine = self.ocr_engines.get(selected_engine, list(self.ocr_engines.values())[0])
        
        # Perform OCR
        text, confidence = self._run_ocr(processed_image, ocr_engine, selected_engine)
        
        # Check confidence and retry if needed
        if (confidence < self.config.min_confidence and 
            self.config.retry_on_low_confidence and 
            len(applied_steps) > 1):
            
            logger.debug(f"Low confidence {confidence:.2f}, retrying with minimal preprocessing")
            # Retry with minimal preprocessing
            minimal_processed, minimal_steps = self.preprocessor.preprocess_image(
                image, OCRConfig(denoise=False, sharpen=False)
            )
            retry_text, retry_confidence = self._run_ocr(minimal_processed, ocr_engine, selected_engine)
            
            if retry_confidence > confidence:
                text, confidence = retry_text, retry_confidence
                applied_steps = minimal_steps
        
        processing_time = time.time() - start_time
        self.stats['total_processing_time'] += processing_time
        self.stats['average_confidence'] = (
            (self.stats['average_confidence'] * (self.stats['total_requests'] - 1) + confidence) /
            self.stats['total_requests']
        )
        
        # Create result
        result = OCRResult(
            text=text,
            confidence=confidence,
            processing_time=processing_time,
            image_hash=image_hash,
            preprocessing_applied=applied_steps,
            model_used=selected_engine
        )
        
        # Cache result
        if self.config.cache_enabled and confidence >= self.config.min_confidence:
            self.cache.put(image_hash, result)
        
        logger.debug(f"OCR completed: {len(text)} chars, {confidence:.2f} confidence, {processing_time:.3f}s")
        return result
    
    def _select_best_engine(self) -> str:
        """Select best available OCR engine"""
        # Priority order based on typical performance
        priority_order = ['paddleocr', 'easyocr', 'tesseract', 'fallback']
        
        for engine in priority_order:
            if engine in self.ocr_engines:
                return engine
        
        return list(self.ocr_engines.keys())[0]
    
    def _run_ocr(self, image: np.ndarray, engine, engine_name: str) -> Tuple[str, float]:
        """Run OCR with specific engine"""
        try:
            if engine_name == 'tesseract':
                import pytesseract
                text = engine.image_to_string(image, config='--psm 8').strip()
                # Tesseract doesn't provide confidence easily, estimate based on text quality
                confidence = min(0.95, len(text) / 20) if text else 0.1
                
            elif engine_name == 'paddleocr':
                results = engine.ocr(image, cls=True)
                if results and results[0]:
                    texts_with_conf = [(item[1][0], item[1][1]) for item in results[0]]
                    text = ' '.join([t[0] for t in texts_with_conf])
                    confidence = sum([t[1] for t in texts_with_conf]) / len(texts_with_conf)
                else:
                    text, confidence = "", 0.0
                    
            elif engine_name == 'easyocr':
                results = engine.readtext(image)
                if results:
                    text = ' '.join([item[1] for item in results])
                    confidence = sum([item[2] for item in results]) / len(results)
                else:
                    text, confidence = "", 0.0
                    
            else:  # fallback
                text = engine.image_to_string(image)
                confidence = 0.5
                
            return text.strip(), confidence
            
        except Exception as e:
            logger.error(f"OCR engine {engine_name} failed: {e}")
            return "", 0.0
    
    @profile_function
    async def process_batch(self, images: List[Union[np.ndarray, str, Path]], 
                          engine: str = None) -> List[OCRResult]:
        """Process multiple images in parallel"""
        logger.info(f"Processing batch of {len(images)} images")
        
        # Create batches based on config
        batches = [images[i:i + self.config.batch_size] 
                  for i in range(0, len(images), self.config.batch_size)]
        
        all_results = []
        
        for batch in batches:
            # Process batch in parallel
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    self.executor, 
                    self.process_image,
                    image,
                    engine
                )
                for image in batch
            ]
            
            try:
                batch_results = await asyncio.wait_for(
                    asyncio.gather(*tasks), 
                    timeout=self.config.timeout_seconds
                )
                all_results.extend(batch_results)
                
            except asyncio.TimeoutError:
                logger.error(f"Batch processing timeout after {self.config.timeout_seconds}s")
                # Add empty results for failed images
                all_results.extend([
                    OCRResult("", 0.0, 0.0, "", [], "timeout") 
                    for _ in batch
                ])
        
        logger.info(f"Batch processing completed: {len(all_results)} results")
        return all_results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        cache_stats = self.cache.stats()
        
        return {
            'processing_stats': {
                'total_requests': self.stats['total_requests'],
                'cache_hit_rate': self.stats['cache_hits'] / max(self.stats['total_requests'], 1),
                'average_processing_time': (
                    self.stats['total_processing_time'] / max(self.stats['total_requests'], 1)
                ),
                'average_confidence': self.stats['average_confidence'],
                'average_preprocessing_time': (
                    self.stats['preprocessing_time'] / max(self.stats['total_requests'], 1)
                )
            },
            'cache_stats': cache_stats,
            'config': {
                'cache_enabled': self.config.cache_enabled,
                'batch_size': self.config.batch_size,
                'max_workers': self.config.max_workers,
                'engines_available': list(self.ocr_engines.keys())
            }
        }
    
    def clear_cache(self):
        """Clear OCR cache"""
        self.cache.clear()
        logger.info("OCR cache cleared")
    
    def shutdown(self):
        """Shutdown OCR service"""
        self.executor.shutdown(wait=True)
        self.clear_cache()
        logger.info("OptimizedOCRService shutdown completed")

# Factory function for easy instantiation
def create_optimized_ocr(
    cache_size: int = 1000,
    use_gpu: bool = True,
    batch_size: int = 4,
    max_workers: int = 4
) -> OptimizedOCRService:
    """Create optimized OCR service with custom configuration"""
    config = OCRConfig(
        cache_size=cache_size,
        use_gpu=use_gpu,
        batch_size=batch_size,
        max_workers=max_workers
    )
    return OptimizedOCRService(config)

# Global instance for singleton access
_global_ocr_service: Optional[OptimizedOCRService] = None

def get_ocr_service() -> OptimizedOCRService:
    """Get global OCR service instance"""
    global _global_ocr_service
    if _global_ocr_service is None:
        _global_ocr_service = create_optimized_ocr()
    return _global_ocr_service 