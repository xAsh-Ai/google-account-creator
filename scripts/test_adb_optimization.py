#!/usr/bin/env python3
"""
ADB Optimization Testing Script

This script tests the enhanced ADB communication optimizations including:
- Performance optimization techniques
- Command caching and fusion
- Device profiling
- Batch command optimization
- Performance analytics

Usage:
    python scripts/test_adb_optimization.py
"""

import asyncio
import time
import statistics
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.optimized_adb import OptimizedADBManager, ADBCommand, ADBCommandType
from core.adb_performance_optimizer import ADBPerformanceOptimizer, get_adb_optimizer
from core.logger import get_logger

logger = get_logger("ADBOptimizationTest")

class ADBOptimizationTester:
    """Comprehensive ADB optimization testing suite"""
    
    def __init__(self):
        self.adb_manager = None
        self.optimizer = None
        self.test_results = {}
    
    async def setup(self):
        """Setup test environment"""
        logger.info("🔧 Setting up ADB optimization test environment")
        
        # Initialize ADB manager
        self.adb_manager = OptimizedADBManager(max_workers=4)
        self.adb_manager.start()
        
        # Initialize optimizer
        self.optimizer = get_adb_optimizer(self.adb_manager)
        
        # Wait for devices to be detected
        await asyncio.sleep(2)
        
        devices = self.adb_manager.get_connected_devices()
        logger.info(f"📱 Detected {len(devices)} devices")
        
        if not devices:
            logger.warning("⚠️ No devices detected for testing")
        
        return len(devices) > 0
    
    async def cleanup(self):
        """Cleanup test environment"""
        if self.adb_manager:
            self.adb_manager.stop()
        logger.info("🧹 Test environment cleaned up")
    
    async def test_command_caching(self) -> Dict[str, Any]:
        """Test command caching functionality"""
        logger.info("🚀 Testing command caching optimization")
        
        devices = self.adb_manager.get_connected_devices()
        if not devices:
            return {'success': False, 'error': 'No devices available'}
        
        device_serial = devices[0].serial
        
        # Test cacheable command
        test_command = ADBCommand(
            command=["shell", "getprop ro.build.version.release"],
            device_serial=device_serial,
            command_type=ADBCommandType.SHELL
        )
        
        results = {
            'cache_hits': 0,
            'cache_misses': 0,
            'execution_times': [],
            'total_time_saved': 0.0
        }
        
        try:
            # First execution (cache miss)
            start_time = time.time()
            result1 = await self.optimizer.execute_optimized_command(test_command)
            first_exec_time = time.time() - start_time
            results['execution_times'].append(first_exec_time)
            
            if not result1.success:
                return {'success': False, 'error': 'Command execution failed'}
            
            # Multiple executions (should hit cache)
            cache_exec_times = []
            for i in range(5):
                start_time = time.time()
                result = await self.optimizer.execute_optimized_command(test_command)
                exec_time = time.time() - start_time
                cache_exec_times.append(exec_time)
                results['execution_times'].append(exec_time)
                
                if not result.success:
                    logger.warning(f"Cache execution {i+1} failed")
            
            # Analyze results
            avg_cache_time = statistics.mean(cache_exec_times)
            time_saved = max(0, first_exec_time - avg_cache_time)
            
            # Get optimizer stats
            perf_report = self.optimizer.get_performance_report()
            cache_stats = perf_report['statistics']
            
            results.update({
                'success': True,
                'first_execution_time': first_exec_time,
                'average_cache_time': avg_cache_time,
                'time_saved_per_command': time_saved,
                'cache_hit_rate': cache_stats.get('cache_hit_rate', 0),
                'total_cache_hits': cache_stats.get('cache_hits', 0),
                'total_cache_misses': cache_stats.get('cache_misses', 0)
            })
            
            logger.info(f"✅ Cache test - Hit rate: {results['cache_hit_rate']:.2%}")
            
        except Exception as e:
            logger.error(f"❌ Cache test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_device_profiling(self) -> Dict[str, Any]:
        """Test device profiling functionality"""
        logger.info("📊 Testing device profiling optimization")
        
        devices = self.adb_manager.get_connected_devices()
        if not devices:
            return {'success': False, 'error': 'No devices available'}
        
        results = {
            'profiled_devices': 0,
            'profiles': {},
            'profiling_times': []
        }
        
        try:
            # Profile all connected devices
            for device in devices[:2]:  # Limit to 2 devices for testing
                if device.state.value == 'connected':
                    start_time = time.time()
                    
                    profile = await self.optimizer.profiler.profile_device(device.serial)
                    
                    profiling_time = time.time() - start_time
                    results['profiling_times'].append(profiling_time)
                    
                    results['profiles'][device.serial] = {
                        'cpu_cores': len(profile.cpu_info),
                        'memory_info_keys': len(profile.memory_info),
                        'command_throughput': profile.command_throughput,
                        'network_latency': profile.network_latency,
                        'optimal_concurrency': profile.optimal_concurrency,
                        'profiling_time': profiling_time
                    }
                    
                    results['profiled_devices'] += 1
                    
                    logger.info(f"Device {device.serial[:8]}... profiled:")
                    logger.info(f"  Throughput: {profile.command_throughput:.2f} cmd/s")
                    logger.info(f"  Latency: {profile.network_latency*1000:.1f}ms")
                    logger.info(f"  Concurrency: {profile.optimal_concurrency}")
            
            results.update({
                'success': True,
                'average_profiling_time': statistics.mean(results['profiling_times']) if results['profiling_times'] else 0
            })
            
            logger.info(f"✅ Profiled {results['profiled_devices']} devices successfully")
            
        except Exception as e:
            logger.error(f"❌ Device profiling test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_batch_optimization(self) -> Dict[str, Any]:
        """Test batch command optimization"""
        logger.info("⚡ Testing batch command optimization")
        
        devices = self.adb_manager.get_connected_devices()
        if not devices:
            return {'success': False, 'error': 'No devices available'}
        
        device_serial = devices[0].serial
        
        # Create test commands
        test_commands = [
            ADBCommand(
                command=["shell", "getprop ro.build.version.sdk"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "getprop ro.product.model"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "getprop ro.product.brand"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "echo 'batch_test_1'"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "echo 'batch_test_2'"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            )
        ]
        
        results = {
            'individual_commands': len(test_commands),
            'individual_times': [],
            'batch_time': 0.0,
            'time_saved': 0.0
        }
        
        try:
            # Test individual command execution
            logger.info("Testing individual command execution...")
            individual_start = time.time()
            
            for cmd in test_commands:
                cmd_start = time.time()
                result = await self.optimizer.execute_optimized_command(cmd)
                cmd_time = time.time() - cmd_start
                results['individual_times'].append(cmd_time)
                
                if not result.success:
                    logger.warning(f"Individual command failed: {cmd.command}")
            
            total_individual_time = time.time() - individual_start
            
            # Test batch command execution
            logger.info("Testing batch command execution...")
            batch_start = time.time()
            
            batch_results = await self.optimizer.batch_optimize_commands(test_commands)
            
            batch_time = time.time() - batch_start
            results['batch_time'] = batch_time
            
            # Calculate optimization
            results.update({
                'success': True,
                'total_individual_time': total_individual_time,
                'batch_execution_time': batch_time,
                'time_saved': max(0, total_individual_time - batch_time),
                'optimization_percentage': (
                    (total_individual_time - batch_time) / total_individual_time * 100
                    if total_individual_time > 0 else 0
                ),
                'successful_batch_commands': sum(1 for r in batch_results if r.success),
                'total_batch_commands': len(batch_results)
            })
            
            logger.info(f"✅ Batch optimization saved {results['time_saved']:.3f}s ({results['optimization_percentage']:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Batch optimization test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_command_fusion(self) -> Dict[str, Any]:
        """Test command fusion optimization"""
        logger.info("🔧 Testing command fusion optimization")
        
        devices = self.adb_manager.get_connected_devices()
        if not devices:
            return {'success': False, 'error': 'No devices available'}
        
        device_serial = devices[0].serial
        
        # Create multiple getprop commands (should be fused)
        getprop_commands = [
            ADBCommand(
                command=["shell", "getprop ro.build.version.release"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "getprop ro.product.model"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            ),
            ADBCommand(
                command=["shell", "getprop ro.product.brand"],
                device_serial=device_serial,
                command_type=ADBCommandType.SHELL
            )
        ]
        
        results = {
            'original_commands': len(getprop_commands),
            'fused_commands': 0,
            'fusion_effective': False
        }
        
        try:
            # Test command fusion
            fused_commands = self.optimizer._fuse_compatible_commands(getprop_commands)
            results['fused_commands'] = len(fused_commands)
            results['fusion_effective'] = len(fused_commands) < len(getprop_commands)
            
            # Execute fused commands
            execution_results = []
            for cmd in fused_commands:
                result = await self.optimizer.execute_optimized_command(cmd)
                execution_results.append(result)
            
            results.update({
                'success': True,
                'successful_executions': sum(1 for r in execution_results if r.success),
                'fusion_ratio': len(fused_commands) / len(getprop_commands) if getprop_commands else 1
            })
            
            if results['fusion_effective']:
                logger.info(f"✅ Command fusion reduced {results['original_commands']} to {results['fused_commands']} commands")
            else:
                logger.info("ℹ️ Command fusion not applied (no compatible commands)")
            
        except Exception as e:
            logger.error(f"❌ Command fusion test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_performance_analytics(self) -> Dict[str, Any]:
        """Test performance analytics and reporting"""
        logger.info("📈 Testing performance analytics")
        
        results = {
            'analytics_available': False,
            'optimization_suggestions': 0,
            'performance_metrics': {}
        }
        
        try:
            # Get performance report
            perf_report = self.optimizer.get_performance_report()
            
            results.update({
                'success': True,
                'analytics_available': True,
                'performance_metrics': perf_report['statistics'],
                'optimization_suggestions': len(perf_report['optimization_suggestions']),
                'device_profiles_count': len(perf_report['device_profiles']),
                'cache_status': perf_report['cache_status']
            })
            
            # Test data persistence
            test_file = "profiling_results/optimization_test_data.json"
            Path("profiling_results").mkdir(exist_ok=True)
            
            self.optimizer.save_optimization_data(test_file)
            
            # Test loading
            new_optimizer = ADBPerformanceOptimizer(self.adb_manager)
            new_optimizer.load_optimization_data(test_file)
            
            results['data_persistence'] = True
            
            logger.info("✅ Performance analytics working correctly")
            logger.info(f"  Total commands: {results['performance_metrics'].get('total_commands', 0)}")
            logger.info(f"  Cache hit rate: {results['performance_metrics'].get('cache_hit_rate', 0):.2%}")
            logger.info(f"  Optimization suggestions: {results['optimization_suggestions']}")
            
        except Exception as e:
            logger.error(f"❌ Performance analytics test failed: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run all optimization tests"""
        logger.info("🚀 Starting comprehensive ADB optimization tests")
        
        all_results = {
            'test_suite': 'ADB Performance Optimization',
            'timestamp': time.time(),
            'tests': {}
        }
        
        # Setup test environment
        setup_success = await self.setup()
        if not setup_success:
            logger.error("❌ Failed to setup test environment")
            return {
                'success': False,
                'error': 'Test environment setup failed',
                **all_results
            }
        
        try:
            # Run individual tests
            test_methods = [
                ('caching', self.test_command_caching),
                ('device_profiling', self.test_device_profiling),
                ('batch_optimization', self.test_batch_optimization),
                ('command_fusion', self.test_command_fusion),
                ('performance_analytics', self.test_performance_analytics)
            ]
            
            for test_name, test_method in test_methods:
                logger.info(f"🔍 Running {test_name} test...")
                
                test_start = time.time()
                test_result = await test_method()
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
            await self.cleanup()
        
        return all_results
    
    def save_test_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to file"""
        if filename is None:
            filename = f"adb_optimization_test_results_{int(time.time())}.json"
        
        results_dir = Path("profiling_results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / filename
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"💾 Test results saved to {results_file}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")

async def main():
    """Main test function"""
    tester = ADBOptimizationTester()
    
    try:
        # Run comprehensive tests
        results = await tester.run_comprehensive_test()
        
        # Save results
        tester.save_test_results(results)
        
        # Print summary
        print("\n" + "="*80)
        print("🔧 ADB OPTIMIZATION TEST RESULTS")
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
    exit(asyncio.run(main())) 