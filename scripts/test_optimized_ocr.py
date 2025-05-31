#!/usr/bin/env python3
"""
Optimized OCR Performance Testing Script

Test and benchmark the optimized OCR service to validate performance improvements.
"""

import sys
import time
import asyncio
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
import json
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.optimized_ocr import (
    OptimizedOCRService, OCRConfig, ImagePreprocessor,
    create_optimized_ocr, get_ocr_service
)
from core.logger import get_logger

logger = get_logger("OCRTest")

class OCRPerformanceTest:
    """OCR performance testing suite"""
    
    def __init__(self):
        self.results = {}
        
    def create_test_images(self) -> List[np.ndarray]:
        """Create test images for OCR benchmarking"""
        test_images = []
        
        # Test image 1: Simple text
        img1 = np.ones((50, 200, 3), dtype=np.uint8) * 255
        cv2.putText(img1, "Hello World", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        test_images.append(img1)
        
        # Test image 2: Numbers and letters  
        img2 = np.ones((60, 300, 3), dtype=np.uint8) * 255
        cv2.putText(img2, "ABC123XYZ", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
        test_images.append(img2)
        
        # Test image 3: Small text
        img3 = np.ones((40, 150, 3), dtype=np.uint8) * 255
        cv2.putText(img3, "small text", (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        test_images.append(img3)
        
        # Test image 4: Noisy text
        img4 = np.ones((70, 250, 3), dtype=np.uint8) * 255
        cv2.putText(img4, "NOISY TEXT", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        # Add noise
        noise = np.random.randint(0, 50, img4.shape, dtype=np.uint8)
        img4 = cv2.add(img4, noise)
        test_images.append(img4)
        
        # Test image 5: Low contrast
        img5 = np.ones((50, 200, 3), dtype=np.uint8) * 200
        cv2.putText(img5, "Low Contrast", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)
        test_images.append(img5)
        
        logger.info(f"Created {len(test_images)} test images")
        return test_images
    
    def test_preprocessing_performance(self):
        """Test image preprocessing performance"""
        logger.info("🧪 Testing image preprocessing performance")
        
        test_images = self.create_test_images()
        preprocessor = ImagePreprocessor()
        config = OCRConfig()
        
        # Test each preprocessing step
        preprocessing_times = {
            'resize': [],
            'denoise': [],
            'enhance_contrast': [],
            'sharpen': [],
            'binarize': [],
            'full_pipeline': []
        }
        
        for img in test_images:
            # Convert to grayscale first
            gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            
            # Test individual steps
            start = time.perf_counter()
            preprocessor.resize_for_ocr(img)
            preprocessing_times['resize'].append(time.perf_counter() - start)
            
            start = time.perf_counter()
            preprocessor.denoise_image(gray_img)
            preprocessing_times['denoise'].append(time.perf_counter() - start)
            
            start = time.perf_counter()
            preprocessor.enhance_contrast(gray_img)
            preprocessing_times['enhance_contrast'].append(time.perf_counter() - start)
            
            start = time.perf_counter()
            preprocessor.sharpen_image(gray_img)
            preprocessing_times['sharpen'].append(time.perf_counter() - start)
            
            start = time.perf_counter()
            preprocessor.binarize_image(gray_img)
            preprocessing_times['binarize'].append(time.perf_counter() - start)
            
            # Test full pipeline
            start = time.perf_counter()
            preprocessor.preprocess_image(img, config)
            preprocessing_times['full_pipeline'].append(time.perf_counter() - start)
        
        # Calculate averages
        avg_times = {
            step: sum(times) / len(times) * 1000  # Convert to milliseconds
            for step, times in preprocessing_times.items()
        }
        
        self.results['preprocessing'] = avg_times
        
        logger.info("✅ Preprocessing performance results:")
        for step, avg_time in avg_times.items():
            logger.info(f"  {step}: {avg_time:.2f} ms")
    
    def test_ocr_engine_performance(self):
        """Test different OCR engines performance"""
        logger.info("🔍 Testing OCR engine performance")
        
        test_images = self.create_test_images()
        
        # Test with different configurations
        configs = {
            'basic': OCRConfig(
                cache_enabled=False,
                denoise=False,
                sharpen=False,
                contrast_enhance=False
            ),
            'optimized': OCRConfig(
                cache_enabled=True,
                denoise=True,
                sharpen=True,
                contrast_enhance=True
            )
        }
        
        results = {}
        
        for config_name, config in configs.items():
            logger.info(f"Testing {config_name} configuration")
            
            ocr_service = OptimizedOCRService(config)
            
            processing_times = []
            confidences = []
            text_lengths = []
            
            for i, img in enumerate(test_images):
                try:
                    start = time.perf_counter()
                    result = ocr_service.process_image(img)
                    processing_time = time.perf_counter() - start
                    
                    processing_times.append(processing_time)
                    confidences.append(result.confidence)
                    text_lengths.append(len(result.text))
                    
                    logger.debug(f"  Image {i+1}: {result.text[:20]}... (conf: {result.confidence:.2f})")
                    
                except Exception as e:
                    logger.error(f"  Image {i+1} failed: {e}")
                    processing_times.append(float('inf'))
                    confidences.append(0.0)
                    text_lengths.append(0)
            
            # Calculate statistics
            valid_times = [t for t in processing_times if t != float('inf')]
            
            results[config_name] = {
                'avg_processing_time': sum(valid_times) / len(valid_times) if valid_times else 0,
                'avg_confidence': sum(confidences) / len(confidences),
                'avg_text_length': sum(text_lengths) / len(text_lengths),
                'success_rate': len(valid_times) / len(test_images),
                'total_images': len(test_images)
            }
            
            # Get performance stats
            perf_stats = ocr_service.get_performance_stats()
            results[config_name]['performance_stats'] = perf_stats
            
            ocr_service.shutdown()
        
        self.results['ocr_engines'] = results
        
        logger.info("✅ OCR engine performance results:")
        for config_name, stats in results.items():
            logger.info(f"  {config_name}:")
            logger.info(f"    Avg processing time: {stats['avg_processing_time']*1000:.2f} ms")
            logger.info(f"    Avg confidence: {stats['avg_confidence']:.2f}")
            logger.info(f"    Success rate: {stats['success_rate']*100:.1f}%")
    
    def test_caching_performance(self):
        """Test caching effectiveness"""
        logger.info("💾 Testing caching performance")
        
        test_images = self.create_test_images()
        
        # Create OCR service with caching enabled
        config = OCRConfig(cache_enabled=True, cache_size=100)
        ocr_service = OptimizedOCRService(config)
        
        # First pass - no cache
        first_pass_times = []
        for img in test_images:
            start = time.perf_counter()
            result = ocr_service.process_image(img)
            first_pass_times.append(time.perf_counter() - start)
        
        # Second pass - with cache
        second_pass_times = []
        for img in test_images:
            start = time.perf_counter()
            result = ocr_service.process_image(img)
            second_pass_times.append(time.perf_counter() - start)
        
        # Calculate improvement
        avg_first = sum(first_pass_times) / len(first_pass_times)
        avg_second = sum(second_pass_times) / len(second_pass_times)
        improvement = (avg_first - avg_second) / avg_first * 100
        
        cache_stats = ocr_service.cache.stats()
        
        self.results['caching'] = {
            'first_pass_avg_time': avg_first,
            'second_pass_avg_time': avg_second,
            'speed_improvement_percent': improvement,
            'cache_hit_rate': cache_stats['hit_rate'],
            'cache_size': cache_stats['size']
        }
        
        logger.info("✅ Caching performance results:")
        logger.info(f"  First pass avg: {avg_first*1000:.2f} ms")
        logger.info(f"  Second pass avg: {avg_second*1000:.2f} ms")
        logger.info(f"  Speed improvement: {improvement:.1f}%")
        logger.info(f"  Cache hit rate: {cache_stats['hit_rate']*100:.1f}%")
        
        ocr_service.shutdown()
    
    async def test_batch_processing(self):
        """Test batch processing performance"""
        logger.info("📦 Testing batch processing performance")
        
        test_images = self.create_test_images() * 4  # 20 images total
        
        config = OCRConfig(batch_size=4, max_workers=4)
        ocr_service = OptimizedOCRService(config)
        
        # Test sequential processing
        start = time.perf_counter()
        sequential_results = []
        for img in test_images:
            result = ocr_service.process_image(img)
            sequential_results.append(result)
        sequential_time = time.perf_counter() - start
        
        # Clear cache for fair comparison
        ocr_service.clear_cache()
        
        # Test batch processing
        start = time.perf_counter()
        batch_results = await ocr_service.process_batch(test_images)
        batch_time = time.perf_counter() - start
        
        # Calculate improvement
        improvement = (sequential_time - batch_time) / sequential_time * 100
        
        self.results['batch_processing'] = {
            'sequential_time': sequential_time,
            'batch_time': batch_time,
            'speed_improvement_percent': improvement,
            'images_processed': len(test_images),
            'sequential_rate': len(test_images) / sequential_time,
            'batch_rate': len(test_images) / batch_time
        }
        
        logger.info("✅ Batch processing results:")
        logger.info(f"  Sequential time: {sequential_time:.2f} s")
        logger.info(f"  Batch time: {batch_time:.2f} s")
        logger.info(f"  Speed improvement: {improvement:.1f}%")
        logger.info(f"  Sequential rate: {len(test_images) / sequential_time:.1f} img/s")
        logger.info(f"  Batch rate: {len(test_images) / batch_time:.1f} img/s")
        
        ocr_service.shutdown()
    
    async def run_all_tests(self):
        """Run all performance tests"""
        logger.info("🚀 Starting comprehensive OCR performance tests")
        
        start_time = time.time()
        
        # Run all tests
        self.test_preprocessing_performance()
        self.test_ocr_engine_performance()
        self.test_caching_performance()
        await self.test_batch_processing()
        
        total_time = time.time() - start_time
        
        # Generate summary
        self.results['summary'] = {
            'total_test_time': total_time,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_count': 4
        }
        
        logger.info(f"✅ All tests completed in {total_time:.2f} seconds")
        
        # Save results
        self.save_results()
        self.print_summary()
        
        return self.results
    
    def save_results(self):
        """Save test results to file"""
        results_dir = Path("profiling_results")
        results_dir.mkdir(exist_ok=True)
        
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        results_file = results_dir / f"ocr_performance_test_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"📄 Results saved to: {results_file}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("🔍 OCR PERFORMANCE TEST SUMMARY")
        print("="*80)
        
        if 'preprocessing' in self.results:
            print("\n📊 PREPROCESSING PERFORMANCE:")
            for step, time_ms in self.results['preprocessing'].items():
                print(f"  {step}: {time_ms:.2f} ms")
        
        if 'ocr_engines' in self.results:
            print("\n🔍 OCR ENGINE COMPARISON:")
            for config, stats in self.results['ocr_engines'].items():
                print(f"  {config}:")
                print(f"    Processing time: {stats['avg_processing_time']*1000:.2f} ms")
                print(f"    Confidence: {stats['avg_confidence']:.2f}")
                print(f"    Success rate: {stats['success_rate']*100:.1f}%")
        
        if 'caching' in self.results:
            cache_results = self.results['caching']
            print(f"\n💾 CACHING EFFECTIVENESS:")
            print(f"  Speed improvement: {cache_results['speed_improvement_percent']:.1f}%")
            print(f"  Cache hit rate: {cache_results.get('cache_hit_rate', 0)*100:.1f}%")
        
        if 'batch_processing' in self.results:
            batch_results = self.results['batch_processing']
            print(f"\n📦 BATCH PROCESSING:")
            print(f"  Speed improvement: {batch_results['speed_improvement_percent']:.1f}%")
            print(f"  Processing rate: {batch_results['batch_rate']:.1f} images/sec")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Run tests
    test_suite = OCRPerformanceTest()
    
    # Run async tests
    asyncio.run(test_suite.run_all_tests())

if __name__ == "__main__":
    main() 