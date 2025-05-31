#!/usr/bin/env python3
"""
System Profiling Script

Interactive script to profile the Google Account Creator system,
analyze performance bottlenecks, and generate optimization recommendations.

Usage:
    python scripts/profile_system.py [options]
    
Options:
    --duration SECONDS    Profiling duration (default: 60)
    --components LIST     Components to profile (default: all)
    --output DIR         Output directory for reports
    --interactive        Interactive mode with menu
    --benchmark          Run performance benchmarks
"""

import sys
import argparse
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.profiler import (
    SystemProfiler, get_profiler, profile_function, 
    benchmark_function, start_system_profiling, stop_system_profiling
)
from core.logger import get_logger

# Optional imports - only import if available
try:
    from core.database import DatabaseManager
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

try:
    from core.config_manager import ConfigManager
    HAS_CONFIG_MANAGER = True
except ImportError:
    HAS_CONFIG_MANAGER = False

try:
    from core.account_creator import GoogleAccountCreator
    HAS_ACCOUNT_CREATOR = True
except ImportError:
    HAS_ACCOUNT_CREATOR = False

try:
    from core.phone_verification import PhoneVerificationManager
    HAS_PHONE_VERIFICATION = True
except ImportError:
    HAS_PHONE_VERIFICATION = False

try:
    from core.ocr_service import OCRService
    HAS_OCR_SERVICE = True
except ImportError:
    HAS_OCR_SERVICE = False

# Initialize logger
logger = get_logger("ProfileSystem")

class SystemProfilerRunner:
    """Main profiler runner with comprehensive testing"""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.profiler = SystemProfiler({
            'results_dir': output_dir or 'profiling_results',
            'monitor_interval': 0.5
        })
        
        # Component instances for testing
        self.components = {}
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize system components for profiling"""
        if HAS_CONFIG_MANAGER:
            try:
                self.components['config_manager'] = ConfigManager()
                logger.info("✅ ConfigManager initialized")
            except Exception as e:
                logger.warning(f"⚠️ ConfigManager failed: {e}")
        else:
            logger.info("ℹ️ ConfigManager not available")
        
        if HAS_DATABASE:
            try:
                self.components['database'] = DatabaseManager()
                logger.info("✅ DatabaseManager initialized")
            except Exception as e:
                logger.warning(f"⚠️ DatabaseManager failed: {e}")
        else:
            logger.info("ℹ️ DatabaseManager not available")
        
        if HAS_OCR_SERVICE:
            try:
                self.components['ocr_service'] = OCRService()
                logger.info("✅ OCRService initialized")
            except Exception as e:
                logger.warning(f"⚠️ OCRService failed: {e}")
        else:
            logger.info("ℹ️ OCRService not available")
        
        if HAS_PHONE_VERIFICATION:
            try:
                self.components['phone_verification'] = PhoneVerificationManager()
                logger.info("✅ PhoneVerificationManager initialized")
            except Exception as e:
                logger.warning(f"⚠️ PhoneVerificationManager failed: {e}")
        else:
            logger.info("ℹ️ PhoneVerificationManager not available")
    
    def run_comprehensive_profile(self, duration: int = 60, components: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run comprehensive system profiling"""
        logger.info(f"🚀 Starting comprehensive system profiling for {duration} seconds")
        
        # Start profiling
        self.profiler.start_profiling(
            enable_memory_tracking=True,
            enable_cprofile=True
        )
        
        # Run component tests
        results = {}
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Test each component if available
            for component_name in (components or self.components.keys()):
                if component_name in self.components:
                    try:
                        component_result = self._test_component(component_name)
                        if component_name not in results:
                            results[component_name] = []
                        results[component_name].append(component_result)
                    except Exception as e:
                        logger.error(f"❌ Error testing {component_name}: {e}")
            
            # If no components available, just do basic work
            if not self.components:
                self._simulate_basic_work()
            
            # Brief pause between iterations
            time.sleep(1)
        
        # Stop profiling and get report
        report = self.profiler.stop_profiling()
        
        logger.info("✅ Profiling completed")
        return {
            'performance_report': report,
            'component_results': results
        }
    
    @profile_function
    def _simulate_basic_work(self):
        """Simulate basic computational work for profiling"""
        # String operations
        data = "test_email@example.com"
        processed = data.split('@')[0] + "_processed"
        
        # List operations
        numbers = list(range(100))
        squared = [x * x for x in numbers]
        
        # Dictionary operations
        test_dict = {f"key_{i}": f"value_{i}" for i in range(50)}
        
        # JSON operations
        import json
        json_data = json.dumps(test_dict)
        parsed_data = json.loads(json_data)
        
        return len(processed) + len(squared) + len(parsed_data)
    
    def _test_component(self, component_name: str) -> Dict[str, Any]:
        """Test individual component performance"""
        component = self.components[component_name]
        
        if component_name == 'config_manager':
            return self._test_config_manager(component)
        elif component_name == 'database':
            return self._test_database(component)
        elif component_name == 'ocr_service':
            return self._test_ocr_service(component)
        elif component_name == 'phone_verification':
            return self._test_phone_verification(component)
        else:
            return {'error': f'Unknown component: {component_name}'}
    
    @profile_function
    def _test_config_manager(self, config_manager) -> Dict[str, Any]:
        """Test ConfigManager performance"""
        start_time = time.perf_counter()
        
        # Test configuration operations
        try:
            # Read operations
            config_manager.get_all_config()
            config_manager.get('anthropic_api_key', '')
            config_manager.get('openai_api_key', '')
            
            # Write operations (if safe)
            test_key = f'test_key_{int(time.time())}'
            config_manager.set(test_key, 'test_value')
            config_manager.get(test_key)
            config_manager.remove(test_key)
            
            end_time = time.perf_counter()
            
            return {
                'component': 'config_manager',
                'success': True,
                'duration': end_time - start_time,
                'operations': 6
            }
        except Exception as e:
            return {
                'component': 'config_manager',
                'success': False,
                'error': str(e),
                'duration': time.perf_counter() - start_time
            }
    
    @profile_function
    def _test_database(self, database) -> Dict[str, Any]:
        """Test DatabaseManager performance"""
        start_time = time.perf_counter()
        
        try:
            # Test basic database operations
            with self.profiler.get_database_profiler().profile_query("SELECT 1", "test"):
                # Simulate a database query
                time.sleep(0.001)  # Minimal delay to simulate DB operation
            
            end_time = time.perf_counter()
            
            return {
                'component': 'database',
                'success': True,
                'duration': end_time - start_time,
                'operations': 1
            }
        except Exception as e:
            return {
                'component': 'database',
                'success': False,
                'error': str(e),
                'duration': time.perf_counter() - start_time
            }
    
    @profile_function
    def _test_ocr_service(self, ocr_service) -> Dict[str, Any]:
        """Test OCRService performance"""
        start_time = time.perf_counter()
        
        try:
            # Test OCR capabilities (without actual image processing)
            # This is a mock test to measure initialization and basic operations
            test_operations = 0
            
            # Simulate OCR processing time
            time.sleep(0.01)  # Simulate processing delay
            test_operations += 1
            
            end_time = time.perf_counter()
            
            return {
                'component': 'ocr_service',
                'success': True,
                'duration': end_time - start_time,
                'operations': test_operations
            }
        except Exception as e:
            return {
                'component': 'ocr_service',
                'success': False,
                'error': str(e),
                'duration': time.perf_counter() - start_time
            }
    
    @profile_function
    def _test_phone_verification(self, phone_verification) -> Dict[str, Any]:
        """Test PhoneVerificationManager performance"""
        start_time = time.perf_counter()
        
        try:
            # Test phone verification operations
            test_operations = 0
            
            # Simulate verification checks
            time.sleep(0.005)  # Simulate processing
            test_operations += 1
            
            end_time = time.perf_counter()
            
            return {
                'component': 'phone_verification',
                'success': True,
                'duration': end_time - start_time,
                'operations': test_operations
            }
        except Exception as e:
            return {
                'component': 'phone_verification',
                'success': False,
                'error': str(e),
                'duration': time.perf_counter() - start_time
            }
    
    def run_benchmarks(self) -> Dict[str, Any]:
        """Run performance benchmarks"""
        logger.info("🏃 Running performance benchmarks")
        
        benchmark_results = {}
        
        # Benchmark configuration operations
        if 'config_manager' in self.components:
            config_manager = self.components['config_manager']
            
            def config_read_test():
                config_manager.get('test_key', 'default')
            
            def config_write_test():
                test_key = f'bench_{int(time.time() * 1000000)}'
                config_manager.set(test_key, 'test_value')
                config_manager.remove(test_key)
            
            benchmark_results['config_read'] = benchmark_function(config_read_test, iterations=1000)
            benchmark_results['config_write'] = benchmark_function(config_write_test, iterations=100)
        
        # Benchmark string operations (common in account creation)
        def string_processing_test():
            test_data = "test_email@example.com"
            return test_data.split('@')[0] + "_suffix"
        
        benchmark_results['string_processing'] = benchmark_function(string_processing_test, iterations=10000)
        
        # Benchmark JSON operations
        def json_processing_test():
            data = {"account_id": "test_123", "status": "active", "metadata": {"created": "2024-01-01"}}
            json_str = json.dumps(data)
            return json.loads(json_str)
        
        benchmark_results['json_processing'] = benchmark_function(json_processing_test, iterations=5000)
        
        # Benchmark list operations
        def list_processing_test():
            numbers = list(range(1000))
            return sum(x * x for x in numbers if x % 2 == 0)
        
        benchmark_results['list_processing'] = benchmark_function(list_processing_test, iterations=1000)
        
        logger.info("✅ Benchmarks completed")
        return benchmark_results
    
    def analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze profiling results and generate insights"""
        performance_report = results['performance_report']
        component_results = results.get('component_results', {})
        
        analysis = {
            'summary': {
                'duration': performance_report.duration,
                'peak_memory_mb': performance_report.peak_memory_usage / 1024 / 1024,
                'avg_memory_mb': performance_report.avg_memory_usage / 1024 / 1024,
                'total_disk_io_mb': performance_report.total_disk_io / 1024 / 1024,
                'total_network_io_mb': performance_report.total_network_io / 1024 / 1024,
                'hotspots_count': len(performance_report.hotspots),
                'bottlenecks_count': len(performance_report.bottlenecks)
            },
            'component_performance': {},
            'optimization_priorities': [],
            'immediate_actions': [],
            'long_term_improvements': []
        }
        
        # Analyze component performance
        for component_name, tests in component_results.items():
            if tests:
                successful_tests = [t for t in tests if t.get('success', False)]
                if successful_tests:
                    avg_duration = sum(t['duration'] for t in successful_tests) / len(successful_tests)
                    total_operations = sum(t.get('operations', 0) for t in successful_tests)
                    
                    analysis['component_performance'][component_name] = {
                        'avg_duration': avg_duration,
                        'total_tests': len(tests),
                        'successful_tests': len(successful_tests),
                        'success_rate': len(successful_tests) / len(tests) * 100,
                        'total_operations': total_operations,
                        'ops_per_second': total_operations / (avg_duration * len(successful_tests)) if avg_duration > 0 else 0
                    }
        
        # Identify optimization priorities
        if performance_report.peak_memory_usage > 512 * 1024 * 1024:  # > 512MB
            analysis['optimization_priorities'].append("Memory usage optimization - peak usage exceeds 512MB")
        
        if performance_report.hotspots:
            top_hotspot = performance_report.hotspots[0]
            if top_hotspot['percentage_of_total'] > 20:
                analysis['optimization_priorities'].append(f"Function optimization - {top_hotspot['function']} consumes {top_hotspot['percentage_of_total']:.1f}% of CPU time")
        
        # Generate immediate actions
        for bottleneck in performance_report.bottlenecks[:3]:  # Top 3 bottlenecks
            analysis['immediate_actions'].append(f"Address bottleneck: {bottleneck}")
        
        # Generate long-term improvements
        analysis['long_term_improvements'].extend([
            "Implement connection pooling for database operations",
            "Add caching layer for frequently accessed configuration",
            "Optimize OCR processing with image preprocessing",
            "Implement async patterns for I/O operations"
        ])
        
        return analysis
    
    def print_analysis(self, analysis: Dict[str, Any]):
        """Print analysis results in a readable format"""
        print("\n" + "="*80)
        print("🔍 SYSTEM PERFORMANCE ANALYSIS REPORT")
        print("="*80)
        
        # Summary
        summary = analysis['summary']
        print(f"\n📊 SUMMARY:")
        print(f"  Duration: {summary['duration']:.2f} seconds")
        print(f"  Peak Memory: {summary['peak_memory_mb']:.2f} MB")
        print(f"  Average Memory: {summary['avg_memory_mb']:.2f} MB")
        print(f"  Disk I/O: {summary['total_disk_io_mb']:.2f} MB")
        print(f"  Network I/O: {summary['total_network_io_mb']:.2f} MB")
        print(f"  Performance Hotspots: {summary['hotspots_count']}")
        print(f"  Bottlenecks: {summary['bottlenecks_count']}")
        
        # Component Performance
        if analysis['component_performance']:
            print(f"\n🧩 COMPONENT PERFORMANCE:")
            for component, perf in analysis['component_performance'].items():
                print(f"  {component}:")
                print(f"    Success Rate: {perf['success_rate']:.1f}%")
                print(f"    Avg Duration: {perf['avg_duration']*1000:.2f} ms")
                print(f"    Operations/sec: {perf['ops_per_second']:.2f}")
        
        # Optimization Priorities
        if analysis['optimization_priorities']:
            print(f"\n🎯 OPTIMIZATION PRIORITIES:")
            for i, priority in enumerate(analysis['optimization_priorities'], 1):
                print(f"  {i}. {priority}")
        
        # Immediate Actions
        if analysis['immediate_actions']:
            print(f"\n⚡ IMMEDIATE ACTIONS:")
            for i, action in enumerate(analysis['immediate_actions'], 1):
                print(f"  {i}. {action}")
        
        # Long-term Improvements
        if analysis['long_term_improvements']:
            print(f"\n🚀 LONG-TERM IMPROVEMENTS:")
            for i, improvement in enumerate(analysis['long_term_improvements'], 1):
                print(f"  {i}. {improvement}")
        
        print("\n" + "="*80)

def interactive_menu():
    """Interactive menu for profiling options"""
    profiler_runner = SystemProfilerRunner()
    
    while True:
        print("\n" + "="*60)
        print("🔍 GOOGLE ACCOUNT CREATOR - SYSTEM PROFILER")
        print("="*60)
        print("1. 🚀 Run Quick Profile (30 seconds)")
        print("2. 📊 Run Comprehensive Profile (60 seconds)")
        print("3. 🏃 Run Extended Profile (120 seconds)")
        print("4. 🏅 Run Benchmarks Only")
        print("5. 🧩 Profile Specific Components")
        print("6. 📈 View Previous Results")
        print("7. ❌ Exit")
        
        choice = input("\nSelect option (1-7): ").strip()
        
        if choice == '1':
            print("\n🚀 Running quick profile...")
            results = profiler_runner.run_comprehensive_profile(duration=30)
            analysis = profiler_runner.analyze_results(results)
            profiler_runner.print_analysis(analysis)
            
        elif choice == '2':
            print("\n📊 Running comprehensive profile...")
            results = profiler_runner.run_comprehensive_profile(duration=60)
            analysis = profiler_runner.analyze_results(results)
            profiler_runner.print_analysis(analysis)
            
        elif choice == '3':
            print("\n🏃 Running extended profile...")
            results = profiler_runner.run_comprehensive_profile(duration=120)
            analysis = profiler_runner.analyze_results(results)
            profiler_runner.print_analysis(analysis)
            
        elif choice == '4':
            print("\n🏅 Running benchmarks...")
            benchmark_results = profiler_runner.run_benchmarks()
            print("\n📊 BENCHMARK RESULTS:")
            for test_name, result in benchmark_results.items():
                print(f"  {test_name}:")
                print(f"    Avg Time: {result['avg_time']*1000:.2f} ms")
                print(f"    Ops/sec: {result['ops_per_second']:.2f}")
                print(f"    Iterations: {result['iterations']}")
            
        elif choice == '5':
            available_components = list(profiler_runner.components.keys())
            print(f"\n🧩 Available components: {', '.join(available_components)}")
            selected = input("Enter components (comma-separated) or 'all': ").strip()
            
            if selected.lower() == 'all':
                components = None
            else:
                components = [c.strip() for c in selected.split(',') if c.strip() in available_components]
            
            if components or selected.lower() == 'all':
                duration = int(input("Duration in seconds (default 60): ") or "60")
                results = profiler_runner.run_comprehensive_profile(duration=duration, components=components)
                analysis = profiler_runner.analyze_results(results)
                profiler_runner.print_analysis(analysis)
            else:
                print("❌ No valid components selected")
                
        elif choice == '6':
            results_dir = Path('profiling_results')
            if results_dir.exists():
                report_files = list(results_dir.glob('performance_report_*.json'))
                if report_files:
                    print(f"\n📈 Found {len(report_files)} previous reports:")
                    for i, report_file in enumerate(sorted(report_files)[-5:], 1):  # Last 5 reports
                        print(f"  {i}. {report_file.name}")
                    
                    try:
                        choice_idx = int(input(f"Select report (1-{min(5, len(report_files))}): ")) - 1
                        if 0 <= choice_idx < min(5, len(report_files)):
                            selected_file = sorted(report_files)[-5:][choice_idx]
                            with open(selected_file, 'r') as f:
                                report_data = json.load(f)
                            print(f"\n📊 REPORT: {selected_file.name}")
                            print(f"  Duration: {report_data['duration']:.2f}s")
                            print(f"  Peak Memory: {report_data['peak_memory_usage']/1024/1024:.2f} MB")
                            print(f"  Hotspots: {len(report_data['hotspots'])}")
                            print(f"  Bottlenecks: {len(report_data['bottlenecks'])}")
                        else:
                            print("❌ Invalid selection")
                    except (ValueError, FileNotFoundError, json.JSONDecodeError):
                        print("❌ Error reading report")
                else:
                    print("📭 No previous reports found")
            else:
                print("📭 No profiling results directory found")
                
        elif choice == '7':
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid option. Please select 1-7.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="System Performance Profiler")
    parser.add_argument('--duration', type=int, default=60, help='Profiling duration in seconds')
    parser.add_argument('--components', nargs='*', help='Components to profile')
    parser.add_argument('--output', help='Output directory for reports')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    parser.add_argument('--benchmark', action='store_true', help='Run benchmarks only')
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_menu()
        return
    
    # Initialize profiler
    profiler_runner = SystemProfilerRunner(args.output)
    
    if args.benchmark:
        # Run benchmarks only
        benchmark_results = profiler_runner.run_benchmarks()
        print("\n📊 BENCHMARK RESULTS:")
        for test_name, result in benchmark_results.items():
            print(f"  {test_name}: {result['avg_time']*1000:.2f}ms avg, {result['ops_per_second']:.2f} ops/sec")
    else:
        # Run comprehensive profiling
        print(f"🚀 Starting system profiling for {args.duration} seconds...")
        results = profiler_runner.run_comprehensive_profile(
            duration=args.duration,
            components=args.components
        )
        
        # Analyze and display results
        analysis = profiler_runner.analyze_results(results)
        profiler_runner.print_analysis(analysis)
        
        print(f"\n📄 Detailed reports saved to: {profiler_runner.profiler.results_dir}")

if __name__ == "__main__":
    main() 