"""
Timing and Synchronization Optimization Module

Advanced timing and synchronization optimization for the Google Account Creator:
- High-precision timing mechanisms
- Thread scheduling optimization
- Lock contention reduction
- Efficient synchronization primitives
- Latency monitoring and optimization
- Adaptive timing strategies
"""

import time
import threading
import asyncio
import queue
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
import logging
import statistics
import weakref
from concurrent.futures import ThreadPoolExecutor, Future
import psutil
import json
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)

@dataclass
class TimingMeasurement:
    """Single timing measurement"""
    operation: str
    start_time: float
    end_time: float
    duration: float
    thread_id: int
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SynchronizationStats:
    """Synchronization performance statistics"""
    operation: str
    total_operations: int = 0
    total_wait_time: float = 0.0
    max_wait_time: float = 0.0
    min_wait_time: float = float('inf')
    contention_events: int = 0
    lock_acquisitions: int = 0
    lock_releases: int = 0
    
    @property
    def average_wait_time(self) -> float:
        return self.total_wait_time / max(1, self.total_operations)
    
    @property
    def contention_rate(self) -> float:
        return self.contention_events / max(1, self.lock_acquisitions)

class HighPrecisionTimer:
    """High-precision timing utilities"""
    
    def __init__(self):
        # Choose the best available timer
        self.timer_func = self._select_best_timer()
        self.resolution = self._measure_resolution()
        self.overhead = self._measure_overhead()
    
    def _select_best_timer(self) -> Callable[[], float]:
        """Select the highest precision timer available"""
        # Try different timer functions and select the best one
        timers = [
            ('time.perf_counter', time.perf_counter),
            ('time.time_ns', lambda: time.time_ns() / 1_000_000_000),
            ('time.time', time.time)
        ]
        
        best_timer = None
        best_resolution = float('inf')
        
        for name, timer_func in timers:
            try:
                # Test resolution
                start = timer_func()
                time.sleep(0.001)  # 1ms
                end = timer_func()
                
                if end > start:  # Valid timer
                    resolution = end - start
                    if resolution < best_resolution:
                        best_resolution = resolution
                        best_timer = timer_func
                        logger.debug(f"Selected timer: {name} (resolution: {resolution:.9f}s)")
            except Exception:
                continue
        
        return best_timer or time.time
    
    def _measure_resolution(self) -> float:
        """Measure timer resolution"""
        measurements = []
        
        for _ in range(1000):
            start = self.timer_func()
            while True:
                current = self.timer_func()
                if current > start:
                    measurements.append(current - start)
                    break
        
        return min(measurements) if measurements else 1e-6
    
    def _measure_overhead(self) -> float:
        """Measure timing overhead"""
        measurements = []
        
        for _ in range(10000):
            start = self.timer_func()
            end = self.timer_func()
            measurements.append(end - start)
        
        return statistics.median(measurements)
    
    def now(self) -> float:
        """Get current high-precision time"""
        return self.timer_func()
    
    @contextmanager
    def measure(self, operation: str = "operation"):
        """Context manager for measuring operation duration"""
        start = self.now()
        measurement = TimingMeasurement(
            operation=operation,
            start_time=start,
            end_time=0.0,
            duration=0.0,
            thread_id=threading.get_ident()
        )
        
        try:
            yield measurement
            measurement.success = True
        except Exception as e:
            measurement.success = False
            measurement.metadata['error'] = str(e)
            raise
        finally:
            end = self.now()
            measurement.end_time = end
            measurement.duration = end - start

class AdaptiveDelay:
    """Adaptive delay system that learns optimal timing"""
    
    def __init__(self, 
                 initial_delay: float = 0.1,
                 min_delay: float = 0.01,
                 max_delay: float = 5.0,
                 adaptation_rate: float = 0.1):
        self.current_delay = initial_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.adaptation_rate = adaptation_rate
        
        self.success_history: deque = deque(maxlen=100)
        self.delay_history: deque = deque(maxlen=100)
        self.performance_history: deque = deque(maxlen=100)
        
        self._lock = threading.Lock()
    
    def get_delay(self) -> float:
        """Get current optimal delay"""
        with self._lock:
            return self.current_delay
    
    def record_result(self, success: bool, performance_metric: float = 1.0):
        """Record operation result and adapt delay"""
        with self._lock:
            self.success_history.append(success)
            self.delay_history.append(self.current_delay)
            self.performance_history.append(performance_metric)
            
            # Adapt delay based on recent results
            if len(self.success_history) >= 10:
                recent_success_rate = sum(self.success_history[-10:]) / 10
                recent_performance = statistics.mean(self.performance_history[-10:])
                
                # Increase delay if success rate is low or performance is poor
                if recent_success_rate < 0.8 or recent_performance < 0.5:
                    adjustment = 1.0 + self.adaptation_rate
                # Decrease delay if success rate is high and performance is good
                elif recent_success_rate > 0.95 and recent_performance > 0.8:
                    adjustment = 1.0 - self.adaptation_rate
                else:
                    adjustment = 1.0
                
                new_delay = self.current_delay * adjustment
                self.current_delay = max(self.min_delay, min(self.max_delay, new_delay))
    
    def reset(self):
        """Reset adaptive delay to initial state"""
        with self._lock:
            self.current_delay = (self.min_delay + self.max_delay) / 2
            self.success_history.clear()
            self.delay_history.clear()
            self.performance_history.clear()

class SmartLock:
    """Lock with contention monitoring and optimization"""
    
    def __init__(self, name: str = "unnamed_lock"):
        self.name = name
        self._lock = threading.RLock()
        self.stats = SynchronizationStats(operation=name)
        self._timer = HighPrecisionTimer()
        
        self.waiting_threads: Set[int] = set()
        self.holder_thread: Optional[int] = None
        self.acquisition_count = 0
        
        self._stats_lock = threading.Lock()
    
    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquire lock with timing measurements"""
        thread_id = threading.get_ident()
        start_time = self._timer.now()
        
        with self._stats_lock:
            self.waiting_threads.add(thread_id)
            if len(self.waiting_threads) > 1:
                self.stats.contention_events += 1
        
        try:
            # Attempt to acquire the lock
            acquired = self._lock.acquire(blocking, timeout)
            
            if acquired:
                end_time = self._timer.now()
                wait_time = end_time - start_time
                
                with self._stats_lock:
                    self.holder_thread = thread_id
                    self.acquisition_count += 1
                    self.stats.lock_acquisitions += 1
                    self.stats.total_operations += 1
                    self.stats.total_wait_time += wait_time
                    self.stats.max_wait_time = max(self.stats.max_wait_time, wait_time)
                    self.stats.min_wait_time = min(self.stats.min_wait_time, wait_time)
            
            return acquired
            
        finally:
            with self._stats_lock:
                self.waiting_threads.discard(thread_id)
    
    def release(self):
        """Release lock with timing measurements"""
        thread_id = threading.get_ident()
        
        try:
            self._lock.release()
            
            with self._stats_lock:
                if self.holder_thread == thread_id:
                    self.holder_thread = None
                self.stats.lock_releases += 1
                
        except Exception:
            # Lock might not be held by this thread
            pass
    
    @contextmanager
    def acquire_context(self, timeout: float = -1):
        """Context manager for lock acquisition"""
        acquired = self.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock '{self.name}' within {timeout}s")
        
        try:
            yield
        finally:
            self.release()
    
    def get_stats(self) -> SynchronizationStats:
        """Get lock statistics"""
        with self._stats_lock:
            return SynchronizationStats(
                operation=self.stats.operation,
                total_operations=self.stats.total_operations,
                total_wait_time=self.stats.total_wait_time,
                max_wait_time=self.stats.max_wait_time,
                min_wait_time=self.stats.min_wait_time,
                contention_events=self.stats.contention_events,
                lock_acquisitions=self.stats.lock_acquisitions,
                lock_releases=self.stats.lock_releases
            )

class ThreadPoolOptimizer:
    """Optimized thread pool with dynamic sizing"""
    
    def __init__(self, 
                 initial_workers: int = 4,
                 max_workers: int = 32,
                 min_workers: int = 2,
                 optimization_interval: float = 30.0):
        self.max_workers = max_workers
        self.min_workers = min_workers
        self.optimization_interval = optimization_interval
        
        self.executor = ThreadPoolExecutor(max_workers=initial_workers)
        self.current_workers = initial_workers
        
        self.task_queue_sizes: deque = deque(maxlen=100)
        self.completion_times: deque = deque(maxlen=1000)
        self.cpu_usage_history: deque = deque(maxlen=100)
        
        self._optimization_thread = None
        self._optimizing = False
        self._stats_lock = threading.Lock()
        
        self.start_optimization()
    
    def start_optimization(self):
        """Start automatic optimization"""
        if self._optimizing:
            return
        
        self._optimizing = True
        self._optimization_thread = threading.Thread(
            target=self._optimization_worker,
            daemon=True
        )
        self._optimization_thread.start()
    
    def stop_optimization(self):
        """Stop automatic optimization"""
        self._optimizing = False
        if self._optimization_thread:
            self._optimization_thread.join(timeout=5)
    
    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Submit task with timing measurement"""
        start_time = time.time()
        
        def timed_wrapper():
            try:
                result = fn(*args, **kwargs)
                end_time = time.time()
                
                with self._stats_lock:
                    self.completion_times.append(end_time - start_time)
                
                return result
            except Exception as e:
                end_time = time.time()
                
                with self._stats_lock:
                    self.completion_times.append(end_time - start_time)
                
                raise
        
        # Record queue size
        with self._stats_lock:
            queue_size = self.executor._work_queue.qsize()
            self.task_queue_sizes.append(queue_size)
        
        return self.executor.submit(timed_wrapper)
    
    def _optimization_worker(self):
        """Background optimization worker"""
        while self._optimizing:
            try:
                time.sleep(self.optimization_interval)
                self._optimize_workers()
            except Exception as e:
                logger.error(f"Thread pool optimization error: {e}")
    
    def _optimize_workers(self):
        """Optimize number of workers"""
        with self._stats_lock:
            if not self.task_queue_sizes or not self.completion_times:
                return
            
            # Get recent metrics
            avg_queue_size = statistics.mean(list(self.task_queue_sizes)[-10:])
            avg_completion_time = statistics.mean(list(self.completion_times)[-50:])
            
            # Get CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            self.cpu_usage_history.append(cpu_usage)
            avg_cpu_usage = statistics.mean(list(self.cpu_usage_history)[-10:])
        
        # Decision logic
        should_increase = (
            avg_queue_size > 5 and  # High queue backlog
            avg_cpu_usage < 80 and  # CPU not saturated
            self.current_workers < self.max_workers
        )
        
        should_decrease = (
            avg_queue_size < 1 and  # Low queue
            avg_completion_time < 0.1 and  # Fast completions
            self.current_workers > self.min_workers
        )
        
        if should_increase:
            new_workers = min(self.max_workers, self.current_workers + 2)
            self._resize_pool(new_workers)
            logger.info(f"Increased thread pool to {new_workers} workers")
            
        elif should_decrease:
            new_workers = max(self.min_workers, self.current_workers - 1)
            self._resize_pool(new_workers)
            logger.info(f"Decreased thread pool to {new_workers} workers")
    
    def _resize_pool(self, new_size: int):
        """Resize thread pool"""
        if new_size == self.current_workers:
            return
        
        # Create new executor with desired size
        old_executor = self.executor
        self.executor = ThreadPoolExecutor(max_workers=new_size)
        self.current_workers = new_size
        
        # Shutdown old executor gracefully
        old_executor.shutdown(wait=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get thread pool statistics"""
        with self._stats_lock:
            return {
                'current_workers': self.current_workers,
                'max_workers': self.max_workers,
                'min_workers': self.min_workers,
                'avg_queue_size': (
                    statistics.mean(self.task_queue_sizes) 
                    if self.task_queue_sizes else 0
                ),
                'avg_completion_time': (
                    statistics.mean(self.completion_times)
                    if self.completion_times else 0
                ),
                'avg_cpu_usage': (
                    statistics.mean(self.cpu_usage_history)
                    if self.cpu_usage_history else 0
                ),
                'total_tasks_completed': len(self.completion_times)
            }
    
    def shutdown(self):
        """Shutdown thread pool"""
        self.stop_optimization()
        self.executor.shutdown(wait=True)

class TimingCoordinator:
    """Coordinates timing across multiple operations"""
    
    def __init__(self):
        self.timer = HighPrecisionTimer()
        self.locks: Dict[str, SmartLock] = {}
        self.delays: Dict[str, AdaptiveDelay] = {}
        self.measurements: List[TimingMeasurement] = []
        
        self.thread_pools: Dict[str, ThreadPoolOptimizer] = {}
        
        self._global_lock = SmartLock("global_coordinator")
        self._measurement_lock = threading.Lock()
    
    def get_lock(self, name: str) -> SmartLock:
        """Get or create named lock"""
        with self._global_lock.acquire_context():
            if name not in self.locks:
                self.locks[name] = SmartLock(name)
            return self.locks[name]
    
    def get_delay(self, name: str, **kwargs) -> AdaptiveDelay:
        """Get or create named adaptive delay"""
        with self._global_lock.acquire_context():
            if name not in self.delays:
                self.delays[name] = AdaptiveDelay(**kwargs)
            return self.delays[name]
    
    def get_thread_pool(self, name: str, **kwargs) -> ThreadPoolOptimizer:
        """Get or create named thread pool"""
        with self._global_lock.acquire_context():
            if name not in self.thread_pools:
                self.thread_pools[name] = ThreadPoolOptimizer(**kwargs)
            return self.thread_pools[name]
    
    @contextmanager
    def measure_operation(self, operation: str, **metadata):
        """Measure operation timing"""
        with self.timer.measure(operation) as measurement:
            measurement.metadata.update(metadata)
            yield measurement
        
        with self._measurement_lock:
            self.measurements.append(measurement)
            
            # Keep only recent measurements
            if len(self.measurements) > 10000:
                self.measurements = self.measurements[-5000:]
    
    def wait_adaptive(self, delay_name: str, success: bool = True, performance: float = 1.0):
        """Adaptive wait with learning"""
        delay_manager = self.get_delay(delay_name)
        
        delay_time = delay_manager.get_delay()
        time.sleep(delay_time)
        
        delay_manager.record_result(success, performance)
    
    def batch_operations(self, 
                        operations: List[Callable],
                        pool_name: str = "default",
                        max_concurrent: int = 10) -> List[Future]:
        """Execute operations in optimized batches"""
        thread_pool = self.get_thread_pool(pool_name, max_workers=max_concurrent)
        
        futures = []
        for operation in operations:
            future = thread_pool.submit(operation)
            futures.append(future)
        
        return futures
    
    def get_timing_stats(self) -> Dict[str, Any]:
        """Get comprehensive timing statistics"""
        with self._measurement_lock:
            measurements = self.measurements.copy()
        
        if not measurements:
            return {}
        
        # Group by operation
        by_operation = defaultdict(list)
        for measurement in measurements:
            by_operation[measurement.operation].append(measurement)
        
        stats = {}
        for operation, op_measurements in by_operation.items():
            durations = [m.duration for m in op_measurements]
            success_count = sum(1 for m in op_measurements if m.success)
            
            stats[operation] = {
                'count': len(op_measurements),
                'success_rate': success_count / len(op_measurements),
                'avg_duration': statistics.mean(durations),
                'median_duration': statistics.median(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'std_duration': statistics.stdev(durations) if len(durations) > 1 else 0,
                'total_time': sum(durations)
            }
        
        return stats
    
    def get_synchronization_stats(self) -> Dict[str, SynchronizationStats]:
        """Get synchronization statistics"""
        return {name: lock.get_stats() for name, lock in self.locks.items()}
    
    def get_thread_pool_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get thread pool statistics"""
        return {name: pool.get_stats() for name, pool in self.thread_pools.items()}
    
    def cleanup(self):
        """Cleanup resources"""
        # Shutdown thread pools
        for pool in self.thread_pools.values():
            pool.shutdown()
        
        self.thread_pools.clear()
        self.locks.clear()
        self.delays.clear()
        
        with self._measurement_lock:
            self.measurements.clear()

# Decorators for timing optimization

def timed_operation(operation_name: str = None, coordinator: TimingCoordinator = None):
    """Decorator for automatic timing measurement"""
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            coord = coordinator or get_timing_coordinator()
            
            with coord.measure_operation(operation_name) as measurement:
                result = func(*args, **kwargs)
                return result
        
        return wrapper
    return decorator

def synchronized(lock_name: str = None, coordinator: TimingCoordinator = None):
    """Decorator for automatic synchronization"""
    def decorator(func):
        nonlocal lock_name
        if lock_name is None:
            lock_name = f"{func.__module__}.{func.__name__}_lock"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            coord = coordinator or get_timing_coordinator()
            lock = coord.get_lock(lock_name)
            
            with lock.acquire_context():
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

def adaptive_retry(delay_name: str = None, 
                  max_retries: int = 3,
                  coordinator: TimingCoordinator = None):
    """Decorator for adaptive retry with timing optimization"""
    def decorator(func):
        nonlocal delay_name
        if delay_name is None:
            delay_name = f"{func.__module__}.{func.__name__}_retry"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            coord = coordinator or get_timing_coordinator()
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Record success
                    if attempt > 0:
                        coord.wait_adaptive(delay_name, success=True, performance=1.0)
                    
                    return result
                    
                except Exception as e:
                    if attempt >= max_retries:
                        # Final failure
                        coord.wait_adaptive(delay_name, success=False, performance=0.0)
                        raise
                    
                    # Wait before retry
                    coord.wait_adaptive(delay_name, success=False, performance=0.5)
        
        return wrapper
    return decorator

# Global timing coordinator
_timing_coordinator: Optional[TimingCoordinator] = None

def get_timing_coordinator() -> TimingCoordinator:
    """Get global timing coordinator"""
    global _timing_coordinator
    
    if _timing_coordinator is None:
        _timing_coordinator = TimingCoordinator()
    
    return _timing_coordinator

def cleanup_timing_coordinator():
    """Cleanup global timing coordinator"""
    global _timing_coordinator
    
    if _timing_coordinator:
        _timing_coordinator.cleanup()
        _timing_coordinator = None 