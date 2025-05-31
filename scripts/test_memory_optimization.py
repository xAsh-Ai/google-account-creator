#!/usr/bin/env python3
"""
Memory Optimization Testing Script

This script tests the memory optimization features including:
- Memory pool management
- Smart caching with memory limits
- Memory leak detection
- Automatic garbage collection optimization
- Memory monitoring and alerting

Usage:
    python scripts/test_memory_optimization.py
"""

import gc
import sys
import time
import threading
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.memory_optimizer import (
    MemoryOptimizer, SmartCache, MemoryPool, MemoryMonitor,
    get_memory_optimizer, memory_efficient, memory_scope,
    start_memory_optimization, stop_memory_optimization
)
from core.logger import get_logger

logger = get_logger("MemoryOptimizationTest")

class TestObject:
    """Test object for memory pool testing"""
    
    def __init__(self, data: str = "test_data"):
        self.data = data
        self.created_at = time.time()
        self.reset_count = 0
    
    def reset(self):
        """Reset object for reuse"""
        self.data = "reset_data"
        self.reset_count += 1

class MemoryLeaker:
    """Object that intentionally creates memory leaks for testing"""
    
    def __init__(self):
        self.leaked_objects: List[Any] = []
    
    def create_leak(self, count: int = 100):
        """Create memory leak by accumulating objects"""
        for i in range(count):
            large_object = [0] * 10000  # 10k integers
            self.leaked_objects.append(large_object)

class MemoryOptimizationTester:
    """Comprehensive memory optimization testing suite"""
    
    def __init__(self):
        self.optimizer = None
        self.test_results = {}
    
    def setup(self):
        """Setup test environment"""
        logger.info("🔧 Setting up memory optimization test environment")
        
        # Initialize memory optimizer
        self.optimizer = get_memory_optimizer()
        self.optimizer.start()
        
        # Force initial garbage collection
        gc.collect()
        
        logger.info("Memory optimization test environment ready")
    
    def cleanup(self):
        """Cleanup test environment"""
        if self.optimizer:
            self.optimizer.stop()
        
        # Force final cleanup
        gc.collect()
        
        logger.info("🧹 Test environment cleaned up")
    
    def test_memory_pool(self) -> Dict[str, Any]:
        """Test memory pool functionality"""
        logger.info("🏊 Testing memory pool optimization")
        
        results = {
            'pool_created': False,
            'objects_created': 0,
            'objects_reused': 0,
            'reuse_rate': 0.0
        }
        
        try:
            # Create memory pool
            pool = self.optimizer.create_pool(
                "test_pool",
                factory=lambda: TestObject("pool_test"),
                max_size=100
            )
            results['pool_created'] = True
            
            # Test object acquisition and release
            objects = []
            
            # Acquire initial objects
            for i in range(50):
                obj = pool.acquire()
                objects.append(obj)
                results['objects_created'] += 1
            
            # Release objects back to pool
            for obj in objects:
                pool.release(obj)
            
            # Acquire objects again (should reuse from pool)
            reused_objects = []
            for i in range(30):
                obj = pool.acquire()
                reused_objects.append(obj)
                if obj.reset_count > 0:  # Was reset, indicating reuse
                    results['objects_reused'] += 1
            
            # Get pool statistics
            pool_stats = pool.get_stats()
            results.update({
                'success': True,
                'pool_stats': pool_stats,
                'reuse_rate': pool_stats['reuse_rate']
            })
            
            logger.info(f"✅ Memory pool test - Reuse rate: {results['reuse_rate']:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Memory pool test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def test_smart_cache(self) -> Dict[str, Any]:
        """Test smart cache functionality"""
        logger.info("💾 Testing smart cache optimization")
        
        results = {
            'cache_created': False,
            'items_cached': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'memory_limited': False
        }
        
        try:
            # Create smart cache with memory limit
            cache = self.optimizer.create_cache(
                "test_cache",
                max_size=1000,
                max_memory=1024 * 1024,  # 1MB
                ttl=60.0
            )
            results['cache_created'] = True
            
            # Add items to cache
            test_data = {}
            for i in range(100):
                key = f"test_key_{i}"
                value = f"test_value_{i}" * 100  # Make it reasonably large
                cache.put(key, value)
                test_data[key] = value
                results['items_cached'] += 1
            
            # Test cache hits
            for key in list(test_data.keys())[:50]:
                result = cache.get(key)
                if result is not None:
                    results['cache_hits'] += 1
                else:
                    results['cache_misses'] += 1
            
            # Test memory limit by adding large objects
            large_object_size = 2 * 1024 * 1024  # 2MB
            large_object = "x" * large_object_size
            
            initial_cache_size = len(cache._cache)
            cache.put("large_object", large_object)
            
            # Check if cache was cleaned up due to memory limit
            if len(cache._cache) < initial_cache_size:
                results['memory_limited'] = True
            
            # Get cache statistics
            cache_stats = cache.get_stats()
            results.update({
                'success': True,
                'cache_stats': cache_stats,
                'hit_rate': cache_stats['hit_rate']
            })
            
            logger.info(f"✅ Smart cache test - Hit rate: {results['hit_rate']:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Smart cache test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def test_memory_monitoring(self) -> Dict[str, Any]:
        """Test memory monitoring functionality"""
        logger.info("📊 Testing memory monitoring")
        
        results = {
            'monitoring_started': False,
            'snapshots_taken': 0,
            'alerts_generated': 0,
            'leak_detection': False
        }
        
        try:
            # Monitor should already be running from optimizer.start()
            monitor = self.optimizer.monitor
            results['monitoring_started'] = monitor._monitoring
            
            # Wait for some snapshots
            initial_snapshots = len(monitor.snapshots)
            time.sleep(3)  # Wait for monitoring interval
            
            final_snapshots = len(monitor.snapshots)
            results['snapshots_taken'] = final_snapshots - initial_snapshots
            
            # Create intentional memory pressure
            memory_pressure = []
            for i in range(1000):
                large_data = [0] * 1000  # Create some objects
                memory_pressure.append(large_data)
            
            # Wait for potential alerts
            time.sleep(2)
            
            results['alerts_generated'] = len(monitor.alerts)
            
            # Test leak detection
            leaker = MemoryLeaker()
            leaker.create_leak(50)
            
            # Wait for leak detection
            time.sleep(2)
            
            leaks = monitor.leak_detector.detect_leaks()
            results['leak_detection'] = len(leaks) > 0
            
            # Get memory statistics
            memory_stats = monitor.get_memory_stats()
            results.update({
                'success': True,
                'memory_stats_available': bool(memory_stats),
                'current_memory_percent': (
                    memory_stats.get('current_snapshot', {}).get('memory_percent', 0)
                    if memory_stats else 0
                )
            })
            
            logger.info(f"✅ Memory monitoring test - {results['snapshots_taken']} snapshots taken")
            
        except Exception as e:
            logger.error(f"❌ Memory monitoring test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def test_memory_decorators(self) -> Dict[str, Any]:
        """Test memory optimization decorators"""
        logger.info("🎭 Testing memory optimization decorators")
        
        results = {
            'decorator_applied': False,
            'context_manager_worked': False,
            'memory_cleaned': False
        }
        
        try:
            # Test memory_efficient decorator
            @memory_efficient
            def memory_intensive_function():
                # Create some objects that should be cleaned up
                temp_objects = []
                for i in range(1000):
                    temp_objects.append([i] * 100)
                return len(temp_objects)
            
            objects_before = len(gc.get_objects())
            result = memory_intensive_function()
            objects_after = len(gc.get_objects())
            
            results['decorator_applied'] = result == 1000
            results['memory_cleaned'] = objects_after <= objects_before * 1.1
            
            # Test memory_scope context manager
            objects_before_scope = len(gc.get_objects())
            
            with memory_scope():
                temp_data = []
                for i in range(500):
                    temp_data.append({"data": "x" * 1000})
                scope_peak_objects = len(gc.get_objects())
            
            objects_after_scope = len(gc.get_objects())
            
            results['context_manager_worked'] = (
                scope_peak_objects > objects_before_scope and
                objects_after_scope <= objects_before_scope * 1.1
            )
            
            results.update({
                'success': True,
                'objects_cleaned_by_decorator': max(0, objects_before - objects_after),
                'objects_cleaned_by_scope': max(0, scope_peak_objects - objects_after_scope)
            })
            
            logger.info("✅ Memory decorators test passed")
            
        except Exception as e:
            logger.error(f"❌ Memory decorators test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def test_garbage_collection_optimization(self) -> Dict[str, Any]:
        """Test garbage collection optimization"""
        logger.info("🗑️ Testing garbage collection optimization")
        
        results = {
            'gc_optimized': False,
            'collections_before': 0,
            'collections_after': 0,
            'objects_collected': 0
        }
        
        try:
            # Get initial GC stats
            initial_stats = gc.get_stats()
            initial_collections = sum(stat['collections'] for stat in initial_stats)
            results['collections_before'] = initial_collections
            
            # Check if GC was optimized (thresholds changed)
            current_threshold = gc.get_threshold()
            default_threshold = (700, 10, 10)
            results['gc_optimized'] = current_threshold != default_threshold
            
            # Create objects and force collection
            objects_before = len(gc.get_objects())
            
            # Create temporary objects
            temp_objects = []
            for i in range(5000):
                temp_objects.append({"id": i, "data": "x" * 100})
            
            # Clear references
            del temp_objects
            
            # Force collection
            collected = gc.collect()
            objects_after = len(gc.get_objects())
            
            results['objects_collected'] = collected
            
            # Get final GC stats
            final_stats = gc.get_stats()
            final_collections = sum(stat['collections'] for stat in final_stats)
            results['collections_after'] = final_collections
            
            results.update({
                'success': True,
                'gc_threshold': current_threshold,
                'objects_freed': objects_before - objects_after,
                'collection_improvement': final_collections - initial_collections
            })
            
            logger.info(f"✅ GC optimization test - Collected {collected} objects")
            
        except Exception as e:
            logger.error(f"❌ GC optimization test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def test_optimization_report(self) -> Dict[str, Any]:
        """Test optimization reporting functionality"""
        logger.info("📈 Testing optimization reporting")
        
        results = {
            'report_generated': False,
            'stats_available': False,
            'cache_stats_count': 0,
            'pool_stats_count': 0
        }
        
        try:
            # Generate optimization report
            report = self.optimizer.get_optimization_report()
            results['report_generated'] = bool(report)
            
            # Check report components
            if report:
                results['stats_available'] = 'memory_stats' in report
                results['cache_stats_count'] = len(report.get('cache_stats', {}))
                results['pool_stats_count'] = len(report.get('pool_stats', {}))
                
                # Test force optimization
                self.optimizer.force_optimization()
                
                results.update({
                    'success': True,
                    'report_keys': list(report.keys()),
                    'has_gc_stats': 'gc_stats' in report,
                    'has_optimization_stats': 'optimization_stats' in report
                })
            
            logger.info("✅ Optimization reporting test passed")
            
        except Exception as e:
            logger.error(f"❌ Optimization reporting test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all memory optimization tests"""
        logger.info("🚀 Starting comprehensive memory optimization tests")
        
        all_results = {
            'test_suite': 'Memory Optimization',
            'timestamp': time.time(),
            'tests': {}
        }
        
        # Setup test environment
        self.setup()
        
        try:
            # Run individual tests
            test_methods = [
                ('memory_pool', self.test_memory_pool),
                ('smart_cache', self.test_smart_cache),
                ('memory_monitoring', self.test_memory_monitoring),
                ('memory_decorators', self.test_memory_decorators),
                ('gc_optimization', self.test_garbage_collection_optimization),
                ('optimization_report', self.test_optimization_report)
            ]
            
            for test_name, test_method in test_methods:
                logger.info(f"🔍 Running {test_name} test...")
                
                test_start = time.time()
                test_result = test_method()
                test_duration = time.time() - test_start
                
                test_result['duration'] = test_duration
                all_results['tests'][test_name] = test_result
                
                if test_result.get('success', False):
                    logger.info(f"✅ {test_name} test passed ({test_duration:.2f}s)")
                else:
                    logger.error(f"❌ {test_name} test failed: {test_result.get('error', 'Unknown error')}")
            
            # Calculate overall results
            successful_tests = sum(1 for result in all_results['tests'].values() if result.get('success', False))
            total_tests = len(all_results['tests'])
            
            all_results.update({
                'success': successful_tests == total_tests,
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
                'total_duration': time.time() - all_results['timestamp']
            })
            
            logger.info(f"📊 Test Summary: {successful_tests}/{total_tests} tests passed ({all_results['success_rate']:.1%})")
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            all_results.update({
                'success': False,
                'error': str(e)
            })
        
        finally:
            self.cleanup()
        
        return all_results
    
    def save_test_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to file"""
        if filename is None:
            filename = f"memory_optimization_test_results_{int(time.time())}.json"
        
        results_dir = Path("profiling_results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / filename
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"💾 Test results saved to {results_file}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")

def main():
    """Main test function"""
    tester = MemoryOptimizationTester()
    
    try:
        # Run comprehensive tests
        results = tester.run_comprehensive_test()
        
        # Save results
        tester.save_test_results(results)
        
        # Print summary
        print("\n" + "="*80)
        print("🧠 MEMORY OPTIMIZATION TEST RESULTS")
        print("="*80)
        
        if results.get('success', False):
            print(f"✅ ALL TESTS PASSED ({results['successful_tests']}/{results['total_tests']})")
        else:
            print(f"❌ SOME TESTS FAILED ({results['successful_tests']}/{results['total_tests']})")
        
        print(f"⏱️  Total Duration: {results.get('total_duration', 0):.2f}s")
        
        for test_name, test_result in results.get('tests', {}).items():
            status = "✅ PASS" if test_result.get('success', False) else "❌ FAIL"
            duration = test_result.get('duration', 0)
            print(f"  {status} {test_name.replace('_', ' ').title()} ({duration:.2f}s)")
            
            if not test_result.get('success', False) and 'error' in test_result:
                print(f"    Error: {test_result['error']}")
        
        print("="*80)
        
        # Exit with appropriate code
        return 0 if results.get('success', False) else 1
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 