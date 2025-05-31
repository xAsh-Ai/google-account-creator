"""
System Profiler for Google Account Creator

Comprehensive performance profiling and monitoring system to identify
bottlenecks, analyze resource usage, and optimize system performance.

Features:
- CPU usage profiling with function-level analysis
- Memory usage tracking and leak detection
- I/O operations monitoring
- Network performance analysis
- Database query profiling
- Performance benchmarking
- Real-time monitoring capabilities
- Report generation with recommendations
"""

import time
import psutil
import threading
import functools
import cProfile
import pstats
import io
import tracemalloc
import sys
import os
import gc
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from contextlib import contextmanager
import json
import pickle
from concurrent.futures import ThreadPoolExecutor
import sqlite3

from core.logger import get_logger

# Initialize logger
logger = get_logger("SystemProfiler")

@dataclass
class ProfileMetrics:
    """Container for performance metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_usage: float = 0.0
    memory_percent: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    network_sent_bytes: int = 0
    network_recv_bytes: int = 0
    open_files: int = 0
    thread_count: int = 0
    process_count: int = 0
    function_calls: Dict[str, int] = field(default_factory=dict)
    execution_times: Dict[str, float] = field(default_factory=dict)
    memory_allocations: Dict[str, int] = field(default_factory=dict)

@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report"""
    start_time: datetime
    end_time: datetime
    duration: float
    total_cpu_time: float
    peak_memory_usage: float
    avg_memory_usage: float
    total_disk_io: int
    total_network_io: int
    hotspots: List[Dict[str, Any]] = field(default_factory=list)
    bottlenecks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    detailed_metrics: List[ProfileMetrics] = field(default_factory=list)

class FunctionProfiler:
    """Decorator-based function profiler"""
    
    def __init__(self):
        self.call_counts: Dict[str, int] = {}
        self.execution_times: Dict[str, List[float]] = {}
        self.memory_usage: Dict[str, List[int]] = {}
        self.lock = threading.Lock()
    
    def profile(self, func: Callable) -> Callable:
        """Decorator to profile function execution"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = f"{func.__module__}.{func.__qualname__}"
            
            # Start profiling
            start_time = time.perf_counter()
            start_memory = self._get_memory_usage()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # End profiling
                end_time = time.perf_counter()
                end_memory = self._get_memory_usage()
                
                execution_time = end_time - start_time
                memory_delta = end_memory - start_memory
                
                with self.lock:
                    # Update call counts
                    self.call_counts[func_name] = self.call_counts.get(func_name, 0) + 1
                    
                    # Update execution times
                    if func_name not in self.execution_times:
                        self.execution_times[func_name] = []
                    self.execution_times[func_name].append(execution_time)
                    
                    # Update memory usage
                    if func_name not in self.memory_usage:
                        self.memory_usage[func_name] = []
                    self.memory_usage[func_name].append(memory_delta)
        
        return wrapper
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        try:
            process = psutil.Process()
            return process.memory_info().rss
        except:
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get profiling statistics"""
        with self.lock:
            stats = {}
            
            for func_name in self.call_counts:
                call_count = self.call_counts[func_name]
                exec_times = self.execution_times.get(func_name, [])
                mem_usage = self.memory_usage.get(func_name, [])
                
                stats[func_name] = {
                    'call_count': call_count,
                    'total_time': sum(exec_times),
                    'avg_time': sum(exec_times) / len(exec_times) if exec_times else 0,
                    'max_time': max(exec_times) if exec_times else 0,
                    'min_time': min(exec_times) if exec_times else 0,
                    'total_memory_delta': sum(mem_usage),
                    'avg_memory_delta': sum(mem_usage) / len(mem_usage) if mem_usage else 0,
                    'max_memory_delta': max(mem_usage) if mem_usage else 0
                }
            
            return stats
    
    def reset(self):
        """Reset profiling data"""
        with self.lock:
            self.call_counts.clear()
            self.execution_times.clear()
            self.memory_usage.clear()

class MemoryProfiler:
    """Memory usage profiler with leak detection"""
    
    def __init__(self):
        self.snapshots: List[Any] = []
        self.tracking_enabled = False
        
    def start_tracking(self):
        """Start memory tracking"""
        tracemalloc.start()
        self.tracking_enabled = True
        self.take_snapshot()
    
    def stop_tracking(self):
        """Stop memory tracking"""
        if self.tracking_enabled:
            tracemalloc.stop()
            self.tracking_enabled = False
    
    def take_snapshot(self):
        """Take a memory snapshot"""
        if self.tracking_enabled:
            snapshot = tracemalloc.take_snapshot()
            self.snapshots.append({
                'timestamp': datetime.now(),
                'snapshot': snapshot
            })
    
    def analyze_leaks(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Analyze memory leaks between snapshots"""
        if len(self.snapshots) < 2:
            return []
        
        leaks = []
        
        for i in range(1, len(self.snapshots)):
            current = self.snapshots[i]['snapshot']
            previous = self.snapshots[i-1]['snapshot']
            
            top_stats = current.compare_to(previous, 'lineno')
            
            for stat in top_stats[:top_n]:
                if stat.size_diff > 0:  # Memory increase
                    leaks.append({
                        'filename': stat.traceback.format()[0],
                        'line': stat.traceback.format()[0].split(':')[1] if ':' in stat.traceback.format()[0] else 'unknown',
                        'size_diff': stat.size_diff,
                        'count_diff': stat.count_diff,
                        'timestamp': self.snapshots[i]['timestamp']
                    })
        
        return sorted(leaks, key=lambda x: x['size_diff'], reverse=True)
    
    def get_top_memory_consumers(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top memory consumers"""
        if not self.snapshots:
            return []
        
        latest_snapshot = self.snapshots[-1]['snapshot']
        top_stats = latest_snapshot.statistics('lineno')
        
        consumers = []
        for stat in top_stats[:top_n]:
            consumers.append({
                'filename': stat.traceback.format()[0],
                'size': stat.size,
                'count': stat.count,
                'average_size': stat.size / stat.count if stat.count > 0 else 0
            })
        
        return consumers

class SystemMonitor:
    """Real-time system resource monitor"""
    
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.monitoring = False
        self.metrics_history: List[ProfileMetrics] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
    def start_monitoring(self):
        """Start system monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        last_disk_io = psutil.disk_io_counters()
        last_network_io = psutil.net_io_counters()
        
        while self.monitoring:
            try:
                # Get current system metrics
                process = psutil.Process()
                current_disk_io = psutil.disk_io_counters()
                current_network_io = psutil.net_io_counters()
                
                metrics = ProfileMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=process.cpu_percent(),
                    memory_usage=process.memory_info().rss,
                    memory_percent=process.memory_percent(),
                    disk_read_bytes=current_disk_io.read_bytes - last_disk_io.read_bytes if last_disk_io else 0,
                    disk_write_bytes=current_disk_io.write_bytes - last_disk_io.write_bytes if last_disk_io else 0,
                    network_sent_bytes=current_network_io.bytes_sent - last_network_io.bytes_sent if last_network_io else 0,
                    network_recv_bytes=current_network_io.bytes_recv - last_network_io.bytes_recv if last_network_io else 0,
                    open_files=len(process.open_files()),
                    thread_count=process.num_threads(),
                    process_count=len(psutil.pids())
                )
                
                with self.lock:
                    self.metrics_history.append(metrics)
                    # Keep only last 1000 entries
                    if len(self.metrics_history) > 1000:
                        self.metrics_history.pop(0)
                
                last_disk_io = current_disk_io
                last_network_io = current_network_io
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.interval)
    
    def get_current_metrics(self) -> Optional[ProfileMetrics]:
        """Get the latest metrics"""
        with self.lock:
            return self.metrics_history[-1] if self.metrics_history else None
    
    def get_metrics_history(self, duration_minutes: int = 60) -> List[ProfileMetrics]:
        """Get metrics history for specified duration"""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        with self.lock:
            return [
                metrics for metrics in self.metrics_history
                if metrics.timestamp >= cutoff_time
            ]
    
    def get_average_metrics(self, duration_minutes: int = 60) -> Optional[ProfileMetrics]:
        """Get average metrics for specified duration"""
        history = self.get_metrics_history(duration_minutes)
        
        if not history:
            return None
        
        return ProfileMetrics(
            timestamp=datetime.now(),
            cpu_percent=sum(m.cpu_percent for m in history) / len(history),
            memory_usage=sum(m.memory_usage for m in history) / len(history),
            memory_percent=sum(m.memory_percent for m in history) / len(history),
            disk_read_bytes=sum(m.disk_read_bytes for m in history),
            disk_write_bytes=sum(m.disk_write_bytes for m in history),
            network_sent_bytes=sum(m.network_sent_bytes for m in history),
            network_recv_bytes=sum(m.network_recv_bytes for m in history),
            open_files=sum(m.open_files for m in history) / len(history),
            thread_count=sum(m.thread_count for m in history) / len(history),
            process_count=sum(m.process_count for m in history) / len(history)
        )

class DatabaseProfiler:
    """Database query profiler"""
    
    def __init__(self):
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self.slow_queries: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
    
    @contextmanager
    def profile_query(self, query: str, query_type: str = "unknown"):
        """Context manager to profile database queries"""
        start_time = time.perf_counter()
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            
            self._record_query(query, query_type, execution_time)
    
    def _record_query(self, query: str, query_type: str, execution_time: float):
        """Record query execution statistics"""
        with self.lock:
            # Update query statistics
            if query not in self.query_stats:
                self.query_stats[query] = {
                    'count': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0,
                    'query_type': query_type
                }
            
            stats = self.query_stats[query]
            stats['count'] += 1
            stats['total_time'] += execution_time
            stats['min_time'] = min(stats['min_time'], execution_time)
            stats['max_time'] = max(stats['max_time'], execution_time)
            stats['avg_time'] = stats['total_time'] / stats['count']
            
            # Track slow queries (> 1 second)
            if execution_time > 1.0:
                self.slow_queries.append({
                    'query': query,
                    'query_type': query_type,
                    'execution_time': execution_time,
                    'timestamp': datetime.now()
                })
                
                # Keep only last 100 slow queries
                if len(self.slow_queries) > 100:
                    self.slow_queries.pop(0)
    
    def get_query_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get query statistics"""
        with self.lock:
            return self.query_stats.copy()
    
    def get_slow_queries(self) -> List[Dict[str, Any]]:
        """Get slow queries list"""
        with self.lock:
            return self.slow_queries.copy()

class BenchmarkSuite:
    """Performance benchmarking suite"""
    
    def __init__(self):
        self.benchmark_results: Dict[str, List[float]] = {}
    
    def benchmark_function(self, func: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, float]:
        """Benchmark a function's performance"""
        func_name = f"{func.__module__}.{func.__qualname__}"
        execution_times = []
        
        # Warm-up run
        try:
            func(*args, **kwargs)
        except:
            pass
        
        # Benchmark runs
        for _ in range(iterations):
            start_time = time.perf_counter()
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Benchmark function failed: {e}")
                continue
            end_time = time.perf_counter()
            execution_times.append(end_time - start_time)
        
        if not execution_times:
            return {}
        
        # Calculate statistics
        results = {
            'iterations': len(execution_times),
            'total_time': sum(execution_times),
            'avg_time': sum(execution_times) / len(execution_times),
            'min_time': min(execution_times),
            'max_time': max(execution_times),
            'median_time': sorted(execution_times)[len(execution_times) // 2],
            'ops_per_second': len(execution_times) / sum(execution_times) if sum(execution_times) > 0 else 0
        }
        
        # Store results
        if func_name not in self.benchmark_results:
            self.benchmark_results[func_name] = []
        self.benchmark_results[func_name].append(results['avg_time'])
        
        return results
    
    def compare_performance(self, func1: Callable, func2: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, Any]:
        """Compare performance of two functions"""
        results1 = self.benchmark_function(func1, *args, iterations=iterations, **kwargs)
        results2 = self.benchmark_function(func2, *args, iterations=iterations, **kwargs)
        
        if not results1 or not results2:
            return {}
        
        speedup = results2['avg_time'] / results1['avg_time'] if results1['avg_time'] > 0 else 0
        
        return {
            'function1': f"{func1.__module__}.{func1.__qualname__}",
            'function2': f"{func2.__module__}.{func2.__qualname__}",
            'results1': results1,
            'results2': results2,
            'speedup': speedup,
            'faster_function': 'function1' if results1['avg_time'] < results2['avg_time'] else 'function2'
        }

class SystemProfiler:
    """Main system profiler orchestrating all profiling components"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Initialize profiling components
        self.function_profiler = FunctionProfiler()
        self.memory_profiler = MemoryProfiler()
        self.system_monitor = SystemMonitor(
            interval=self.config.get('monitor_interval', 1.0)
        )
        self.database_profiler = DatabaseProfiler()
        self.benchmark_suite = BenchmarkSuite()
        
        # Profiling state
        self.profiling_active = False
        self.start_time: Optional[datetime] = None
        self.cprofile_profiler: Optional[cProfile.Profile] = None
        
        # Results storage
        self.results_dir = Path(self.config.get('results_dir', 'profiling_results'))
        self.results_dir.mkdir(exist_ok=True)
    
    def start_profiling(self, enable_memory_tracking: bool = True, enable_cprofile: bool = True):
        """Start comprehensive system profiling"""
        if self.profiling_active:
            logger.warning("Profiling already active")
            return
        
        self.profiling_active = True
        self.start_time = datetime.now()
        
        # Start memory profiling
        if enable_memory_tracking:
            self.memory_profiler.start_tracking()
        
        # Start cProfile
        if enable_cprofile:
            self.cprofile_profiler = cProfile.Profile()
            self.cprofile_profiler.enable()
        
        # Start system monitoring
        self.system_monitor.start_monitoring()
        
        logger.info("System profiling started")
    
    def stop_profiling(self) -> PerformanceReport:
        """Stop profiling and generate report"""
        if not self.profiling_active:
            logger.warning("Profiling not active")
            return PerformanceReport(
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration=0.0,
                total_cpu_time=0.0,
                peak_memory_usage=0.0,
                avg_memory_usage=0.0,
                total_disk_io=0,
                total_network_io=0
            )
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Stop profiling components
        self.memory_profiler.stop_tracking()
        
        if self.cprofile_profiler:
            self.cprofile_profiler.disable()
        
        self.system_monitor.stop_monitoring()
        
        # Generate comprehensive report
        report = self._generate_report(end_time, duration)
        
        # Save report
        self._save_report(report)
        
        self.profiling_active = False
        logger.info(f"System profiling stopped. Duration: {duration:.2f}s")
        
        return report
    
    def _generate_report(self, end_time: datetime, duration: float) -> PerformanceReport:
        """Generate comprehensive performance report"""
        # Get system metrics
        metrics_history = self.system_monitor.get_metrics_history(duration_minutes=int(duration/60) + 1)
        avg_metrics = self.system_monitor.get_average_metrics(duration_minutes=int(duration/60) + 1)
        
        # Calculate totals and peaks
        peak_memory = max((m.memory_usage for m in metrics_history), default=0)
        avg_memory = avg_metrics.memory_usage if avg_metrics else 0
        total_disk_io = sum(m.disk_read_bytes + m.disk_write_bytes for m in metrics_history)
        total_network_io = sum(m.network_sent_bytes + m.network_recv_bytes for m in metrics_history)
        
        # Analyze function profiling
        function_stats = self.function_profiler.get_stats()
        hotspots = self._identify_hotspots(function_stats)
        
        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(metrics_history, function_stats)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics_history, function_stats)
        
        return PerformanceReport(
            start_time=self.start_time,
            end_time=end_time,
            duration=duration,
            total_cpu_time=sum(m.cpu_percent for m in metrics_history) * duration / 100 if metrics_history else 0,
            peak_memory_usage=peak_memory,
            avg_memory_usage=avg_memory,
            total_disk_io=total_disk_io,
            total_network_io=total_network_io,
            hotspots=hotspots,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            detailed_metrics=metrics_history
        )
    
    def _identify_hotspots(self, function_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance hotspots"""
        hotspots = []
        
        # Sort functions by total execution time
        sorted_functions = sorted(
            function_stats.items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )
        
        for func_name, stats in sorted_functions[:10]:  # Top 10 hotspots
            hotspots.append({
                'function': func_name,
                'total_time': stats['total_time'],
                'call_count': stats['call_count'],
                'avg_time': stats['avg_time'],
                'percentage_of_total': 0  # Will be calculated later
            })
        
        # Calculate percentages
        total_time = sum(stats['total_time'] for stats in function_stats.values())
        if total_time > 0:
            for hotspot in hotspots:
                hotspot['percentage_of_total'] = (hotspot['total_time'] / total_time) * 100
        
        return hotspots
    
    def _identify_bottlenecks(self, metrics_history: List[ProfileMetrics], function_stats: Dict[str, Any]) -> List[str]:
        """Identify system bottlenecks"""
        bottlenecks = []
        
        if not metrics_history:
            return bottlenecks
        
        # CPU bottlenecks
        avg_cpu = sum(m.cpu_percent for m in metrics_history) / len(metrics_history)
        if avg_cpu > 80:
            bottlenecks.append("High CPU usage detected - consider optimizing CPU-intensive operations")
        
        # Memory bottlenecks
        avg_memory_percent = sum(m.memory_percent for m in metrics_history) / len(metrics_history)
        if avg_memory_percent > 80:
            bottlenecks.append("High memory usage detected - investigate memory leaks and optimize memory allocation")
        
        # I/O bottlenecks
        total_disk_io = sum(m.disk_read_bytes + m.disk_write_bytes for m in metrics_history)
        if total_disk_io > 1024 * 1024 * 1024:  # > 1GB
            bottlenecks.append("High disk I/O detected - consider optimizing file operations and database queries")
        
        # Function-level bottlenecks
        for func_name, stats in function_stats.items():
            if stats['avg_time'] > 1.0:  # Functions taking > 1 second on average
                bottlenecks.append(f"Slow function detected: {func_name} (avg: {stats['avg_time']:.2f}s)")
        
        return bottlenecks
    
    def _generate_recommendations(self, metrics_history: List[ProfileMetrics], function_stats: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if not metrics_history:
            return recommendations
        
        # Memory recommendations
        memory_growth = self.memory_profiler.analyze_leaks()
        if memory_growth:
            recommendations.append("Memory leaks detected - review object lifecycle and implement proper cleanup")
        
        # Function optimization recommendations
        slow_functions = [
            func_name for func_name, stats in function_stats.items()
            if stats['avg_time'] > 0.1
        ]
        if slow_functions:
            recommendations.append(f"Optimize slow functions: {', '.join(slow_functions[:5])}")
        
        # I/O optimization
        avg_open_files = sum(m.open_files for m in metrics_history) / len(metrics_history)
        if avg_open_files > 100:
            recommendations.append("High number of open files - implement file handle pooling and proper cleanup")
        
        # General recommendations
        recommendations.extend([
            "Consider implementing caching for frequently accessed data",
            "Use connection pooling for database operations",
            "Implement async/await patterns for I/O-bound operations",
            "Profile individual components for targeted optimization"
        ])
        
        return recommendations
    
    def _save_report(self, report: PerformanceReport):
        """Save performance report to file"""
        timestamp = report.start_time.strftime("%Y%m%d_%H%M%S")
        
        # Save detailed report as JSON
        report_file = self.results_dir / f"performance_report_{timestamp}.json"
        report_data = {
            'start_time': report.start_time.isoformat(),
            'end_time': report.end_time.isoformat(),
            'duration': report.duration,
            'total_cpu_time': report.total_cpu_time,
            'peak_memory_usage': report.peak_memory_usage,
            'avg_memory_usage': report.avg_memory_usage,
            'total_disk_io': report.total_disk_io,
            'total_network_io': report.total_network_io,
            'hotspots': report.hotspots,
            'bottlenecks': report.bottlenecks,
            'recommendations': report.recommendations
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        # Save cProfile results
        if self.cprofile_profiler:
            cprofile_file = self.results_dir / f"cprofile_{timestamp}.prof"
            self.cprofile_profiler.dump_stats(str(cprofile_file))
        
        logger.info(f"Performance report saved to {report_file}")
    
    def get_function_profiler(self) -> FunctionProfiler:
        """Get function profiler for decorator usage"""
        return self.function_profiler
    
    def get_database_profiler(self) -> DatabaseProfiler:
        """Get database profiler"""
        return self.database_profiler
    
    def get_benchmark_suite(self) -> BenchmarkSuite:
        """Get benchmark suite"""
        return self.benchmark_suite

# Global profiler instance
_global_profiler: Optional[SystemProfiler] = None

def get_profiler() -> SystemProfiler:
    """Get or create global profiler instance"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = SystemProfiler()
    return _global_profiler

def profile_function(func: Callable) -> Callable:
    """Decorator to profile a function"""
    return get_profiler().get_function_profiler().profile(func)

@contextmanager
def profile_database_query(query: str, query_type: str = "unknown"):
    """Context manager to profile database queries"""
    with get_profiler().get_database_profiler().profile_query(query, query_type):
        yield

def benchmark_function(func: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, float]:
    """Benchmark a function's performance"""
    return get_profiler().get_benchmark_suite().benchmark_function(func, *args, iterations=iterations, **kwargs)

def start_system_profiling(**kwargs):
    """Start system profiling"""
    get_profiler().start_profiling(**kwargs)

def stop_system_profiling() -> PerformanceReport:
    """Stop system profiling and return report"""
    return get_profiler().stop_profiling()

if __name__ == "__main__":
    # Example usage
    profiler = SystemProfiler()
    
    # Start profiling
    profiler.start_profiling()
    
    # Simulate some work
    time.sleep(2)
    
    # Stop profiling and get report
    report = profiler.stop_profiling()
    
    print(f"Profiling completed. Duration: {report.duration:.2f}s")
    print(f"Peak memory usage: {report.peak_memory_usage / 1024 / 1024:.2f} MB")
    print(f"Bottlenecks found: {len(report.bottlenecks)}")
    print(f"Recommendations: {len(report.recommendations)}") 