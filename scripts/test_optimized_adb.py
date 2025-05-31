#!/usr/bin/env python3
"""
Optimized ADB Performance Testing Script

Test and benchmark the optimized ADB manager to validate performance improvements.
"""

import sys
import time
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.optimized_adb import (
    OptimizedADBManager, ADBCommandType, ADBDevice,
    create_adb_manager, get_adb_manager
)
from core.logger import get_logger

logger = get_logger("ADBTest")

class ADBPerformanceTest:
    """ADB performance testing suite"""
    
    def __init__(self):
        self.results = {}
        self.adb_manager = None
    
    def setup_adb_manager(self):
        """Setup ADB manager for testing"""
        self.adb_manager = create_adb_manager(max_workers=4)
        self.adb_manager.start()
        
        # Wait a moment for initialization
        time.sleep(1)
        
        logger.info("ADB manager initialized for testing")
    
    def cleanup_adb_manager(self):
        """Cleanup ADB manager"""
        if self.adb_manager:
            self.adb_manager.stop()
            self.adb_manager = None
        logger.info("ADB manager cleaned up")
    
    def test_device_scanning(self):
        """Test device scanning performance"""
        logger.info("🔍 Testing device scanning performance")
        
        scan_times = []
        device_counts = []
        
        # Run multiple scans to measure performance
        for i in range(5):
            start_time = time.perf_counter()
            devices = self.adb_manager.scan_devices()
            scan_time = time.perf_counter() - start_time
            
            scan_times.append(scan_time)
            device_counts.append(len(devices))
            
            logger.debug(f"Scan {i+1}: {len(devices)} devices in {scan_time*1000:.2f}ms")
        
        avg_scan_time = sum(scan_times) / len(scan_times)
        avg_device_count = sum(device_counts) / len(device_counts)
        
        self.results['device_scanning'] = {
            'average_scan_time': avg_scan_time,
            'scan_times': scan_times,
            'average_device_count': avg_device_count,
            'total_scans': len(scan_times)
        }
        
        logger.info(f"✅ Device scanning results:")
        logger.info(f"  Average scan time: {avg_scan_time*1000:.2f} ms")
        logger.info(f"  Average devices found: {avg_device_count:.1f}")
    
    def test_basic_commands(self):
        """Test basic ADB command execution"""
        logger.info("⚡ Testing basic ADB commands")
        
        # Test commands that should work even without devices
        test_commands = [
            (["version"], "Get ADB version"),
            (["help"], "Get ADB help"),
            (["devices"], "List devices"),
        ]
        
        command_results = []
        
        for command, description in test_commands:
            logger.debug(f"Testing: {description}")
            
            start_time = time.perf_counter()
            result = self.adb_manager.execute_command_sync(command)
            execution_time = time.perf_counter() - start_time
            
            command_results.append({
                'command': command,
                'description': description,
                'success': result.success,
                'execution_time': execution_time,
                'returncode': result.returncode,
                'stdout_length': len(result.stdout),
                'stderr_length': len(result.stderr)
            })
            
            logger.debug(f"  Result: {'✅' if result.success else '❌'} ({execution_time*1000:.2f}ms)")
        
        # Calculate statistics
        successful_commands = [r for r in command_results if r['success']]
        success_rate = len(successful_commands) / len(command_results) * 100
        avg_execution_time = sum(r['execution_time'] for r in successful_commands) / len(successful_commands) if successful_commands else 0
        
        self.results['basic_commands'] = {
            'command_results': command_results,
            'success_rate': success_rate,
            'average_execution_time': avg_execution_time,
            'total_commands': len(command_results)
        }
        
        logger.info(f"✅ Basic command results:")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Average execution time: {avg_execution_time*1000:.2f} ms")
    
    def test_command_queueing(self):
        """Test command queueing and priority handling"""
        logger.info("📋 Testing command queueing system")
        
        # Add multiple commands with different priorities
        command_ids = []
        priorities = [1, 3, 5, 2, 4]  # Mixed priorities
        
        start_time = time.time()
        
        for i, priority in enumerate(priorities):
            command_id = self.adb_manager.execute_command(
                ["version"],
                priority=priority
            )
            command_ids.append((command_id, priority))
        
        # Wait for all commands to complete
        time.sleep(2)
        
        total_queue_time = time.time() - start_time
        
        # Get queue statistics
        pending_count = self.adb_manager.command_queue.get_pending_count()
        
        self.results['command_queueing'] = {
            'commands_queued': len(command_ids),
            'total_queue_time': total_queue_time,
            'pending_commands': pending_count,
            'queue_processing_rate': len(command_ids) / total_queue_time
        }
        
        logger.info(f"✅ Command queueing results:")
        logger.info(f"  Commands processed: {len(command_ids)}")
        logger.info(f"  Total time: {total_queue_time:.2f} s")
        logger.info(f"  Processing rate: {len(command_ids) / total_queue_time:.1f} cmd/s")
        logger.info(f"  Pending commands: {pending_count}")
    
    def test_batch_processing(self):
        """Test batch command processing"""
        logger.info("📦 Testing batch command processing")
        
        # Create batch of commands
        batch_commands = [
            (["version"], None),
            (["help"], None),
            (["devices"], None),
            (["version"], None),
            (["help"], None)
        ]
        
        # Test sequential execution
        start_time = time.perf_counter()
        sequential_results = []
        for command, device_serial in batch_commands:
            result = self.adb_manager.execute_command_sync(command, device_serial)
            sequential_results.append(result)
        sequential_time = time.perf_counter() - start_time
        
        # Test batch execution
        start_time = time.perf_counter()
        batch_results = self.adb_manager.execute_batch_commands(batch_commands)
        batch_time = time.perf_counter() - start_time
        
        # Calculate improvement
        improvement = (sequential_time - batch_time) / sequential_time * 100 if sequential_time > 0 else 0
        
        self.results['batch_processing'] = {
            'sequential_time': sequential_time,
            'batch_time': batch_time,
            'speed_improvement_percent': improvement,
            'commands_processed': len(batch_commands),
            'sequential_rate': len(batch_commands) / sequential_time if sequential_time > 0 else 0,
            'batch_rate': len(batch_commands) / batch_time if batch_time > 0 else 0
        }
        
        logger.info(f"✅ Batch processing results:")
        logger.info(f"  Sequential time: {sequential_time:.2f} s")
        logger.info(f"  Batch time: {batch_time:.2f} s")
        logger.info(f"  Speed improvement: {improvement:.1f}%")
        logger.info(f"  Batch rate: {len(batch_commands) / batch_time:.1f} cmd/s")
    
    async def test_async_operations(self):
        """Test asynchronous command execution"""
        logger.info("🔄 Testing async command execution")
        
        # Test async commands
        async_commands = [
            ["version"],
            ["help"],
            ["devices"],
            ["version"],
            ["help"]
        ]
        
        # Test sequential async
        start_time = time.perf_counter()
        sequential_results = []
        for command in async_commands:
            result = await self.adb_manager.execute_command_async(command)
            sequential_results.append(result)
        sequential_async_time = time.perf_counter() - start_time
        
        # Test concurrent async
        start_time = time.perf_counter()
        tasks = [
            self.adb_manager.execute_command_async(command)
            for command in async_commands
        ]
        concurrent_results = await asyncio.gather(*tasks)
        concurrent_async_time = time.perf_counter() - start_time
        
        # Calculate improvement
        improvement = (sequential_async_time - concurrent_async_time) / sequential_async_time * 100 if sequential_async_time > 0 else 0
        
        self.results['async_operations'] = {
            'sequential_async_time': sequential_async_time,
            'concurrent_async_time': concurrent_async_time,
            'speed_improvement_percent': improvement,
            'commands_processed': len(async_commands),
            'sequential_rate': len(async_commands) / sequential_async_time if sequential_async_time > 0 else 0,
            'concurrent_rate': len(async_commands) / concurrent_async_time if concurrent_async_time > 0 else 0
        }
        
        logger.info(f"✅ Async operations results:")
        logger.info(f"  Sequential async time: {sequential_async_time:.2f} s")
        logger.info(f"  Concurrent async time: {concurrent_async_time:.2f} s")
        logger.info(f"  Speed improvement: {improvement:.1f}%")
        logger.info(f"  Concurrent rate: {len(async_commands) / concurrent_async_time:.1f} cmd/s")
    
    def test_performance_monitoring(self):
        """Test performance monitoring and statistics"""
        logger.info("📊 Testing performance monitoring")
        
        # Execute several commands to generate statistics
        for i in range(10):
            self.adb_manager.execute_command_sync(["version"])
        
        # Get performance statistics
        stats = self.adb_manager.get_performance_stats()
        
        # Perform health check
        health = self.adb_manager.health_check()
        
        self.results['performance_monitoring'] = {
            'stats': stats,
            'health': health,
            'monitoring_available': True
        }
        
        logger.info(f"✅ Performance monitoring results:")
        logger.info(f"  Commands executed: {stats['execution_stats']['commands_executed']}")
        logger.info(f"  Success rate: {stats['execution_stats']['success_rate']:.1f}%")
        logger.info(f"  Average execution time: {stats['execution_stats']['average_execution_time']*1000:.2f} ms")
        logger.info(f"  Overall health: {health['overall_health']}")
    
    async def run_all_tests(self):
        """Run all ADB performance tests"""
        logger.info("🚀 Starting comprehensive ADB performance tests")
        
        start_time = time.time()
        
        try:
            # Setup
            self.setup_adb_manager()
            
            # Run all tests
            self.test_device_scanning()
            self.test_basic_commands()
            self.test_command_queueing()
            self.test_batch_processing()
            await self.test_async_operations()
            self.test_performance_monitoring()
            
        finally:
            # Cleanup
            self.cleanup_adb_manager()
        
        total_time = time.time() - start_time
        
        # Generate summary
        self.results['summary'] = {
            'total_test_time': total_time,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_count': 6
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
        results_file = results_dir / f"adb_performance_test_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        logger.info(f"📄 Results saved to: {results_file}")
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("🔍 ADB PERFORMANCE TEST SUMMARY")
        print("="*80)
        
        if 'device_scanning' in self.results:
            scan_results = self.results['device_scanning']
            print(f"\n🔍 DEVICE SCANNING:")
            print(f"  Average scan time: {scan_results['average_scan_time']*1000:.2f} ms")
            print(f"  Average devices found: {scan_results['average_device_count']:.1f}")
        
        if 'basic_commands' in self.results:
            cmd_results = self.results['basic_commands']
            print(f"\n⚡ BASIC COMMANDS:")
            print(f"  Success rate: {cmd_results['success_rate']:.1f}%")
            print(f"  Average execution time: {cmd_results['average_execution_time']*1000:.2f} ms")
        
        if 'command_queueing' in self.results:
            queue_results = self.results['command_queueing']
            print(f"\n📋 COMMAND QUEUEING:")
            print(f"  Processing rate: {queue_results['queue_processing_rate']:.1f} cmd/s")
            print(f"  Pending commands: {queue_results['pending_commands']}")
        
        if 'batch_processing' in self.results:
            batch_results = self.results['batch_processing']
            print(f"\n📦 BATCH PROCESSING:")
            print(f"  Speed improvement: {batch_results['speed_improvement_percent']:.1f}%")
            print(f"  Processing rate: {batch_results['batch_rate']:.1f} cmd/s")
        
        if 'async_operations' in self.results:
            async_results = self.results['async_operations']
            print(f"\n🔄 ASYNC OPERATIONS:")
            print(f"  Speed improvement: {async_results['speed_improvement_percent']:.1f}%")
            print(f"  Concurrent rate: {async_results['concurrent_rate']:.1f} cmd/s")
        
        if 'performance_monitoring' in self.results:
            perf_results = self.results['performance_monitoring']
            stats = perf_results['stats']
            print(f"\n📊 PERFORMANCE MONITORING:")
            print(f"  Commands executed: {stats['execution_stats']['commands_executed']}")
            print(f"  Success rate: {stats['execution_stats']['success_rate']:.1f}%")
            print(f"  Health status: {perf_results['health']['overall_health']}")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Run tests
    test_suite = ADBPerformanceTest()
    
    # Run async tests
    asyncio.run(test_suite.run_all_tests())

if __name__ == "__main__":
    main() 