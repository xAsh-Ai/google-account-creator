"""
Memory Optimization Module

Advanced memory management and optimization techniques for the Google Account Creator:
- Memory leak detection and prevention
- Efficient data structures and caching
- Automatic garbage collection optimization
- Memory pool management
- Memory usage monitoring and alerts
- Object lifecycle management
"""

import gc
import sys
import threading
import time
import weakref
import psutil
import tracemalloc
from typing import Dict, List, Any, Optional, Set, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from collections import defaultdict, deque
from pathlib import Path
import logging
from contextlib import contextmanager
from functools import wraps
import pickle
import json

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: float = field(default_factory=time.time)
    total_memory: int = 0  # bytes
    available_memory: int = 0  # bytes
    used_memory: int = 0  # bytes
    memory_percent: float = 0.0
    
    # Python-specific metrics
    python_memory: int = 0  # bytes
    objects_count: int = 0
    gc_collections: List[int] = field(default_factory=list)
    
    # Application-specific metrics
    active_objects: Dict[str, int] = field(default_factory=dict)
    cache_memory: int = 0
    temp_memory: int = 0

@dataclass
class MemoryLeak:
    """Memory leak detection result"""
    object_type: str
    object_count: int
    memory_size: int
    growth_rate: float  # objects per second
    stack_trace: Optional[str] = None
    first_detected: float = field(default_factory=time.time)
    severity: str = "medium"  # low, medium, high, critical

class MemoryPool(Generic[T]):
    """Memory pool for efficient object reuse"""
    
    def __init__(self, 
                 factory: Callable[[], T],
                 max_size: int = 1000,
                 cleanup_interval: float = 300.0):
        self.factory = factory
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        
        self._pool: deque = deque()
        self._lock = threading.Lock()
        self._total_created = 0
        self._total_reused = 0
        self._last_cleanup = time.time()
    
    def acquire(self) -> T:
        """Acquire object from pool"""
        with self._lock:
            if self._pool:
                obj = self._pool.popleft()
                self._total_reused += 1
                return obj
            else:
                obj = self.factory()
                self._total_created += 1
                return obj
    
    def release(self, obj: T):
        """Return object to pool"""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Reset object if it has a reset method
                if hasattr(obj, 'reset') and callable(getattr(obj, 'reset')):
                    obj.reset()
                self._pool.append(obj)
            
            # Periodic cleanup
            now = time.time()
            if now - self._last_cleanup > self.cleanup_interval:
                self._cleanup()
                self._last_cleanup = now
    
    def _cleanup(self):
        """Clean up excess objects in pool"""
        target_size = self.max_size // 2
        while len(self._pool) > target_size:
            self._pool.pop()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        with self._lock:
            return {
                'pool_size': len(self._pool),
                'max_size': self.max_size,
                'total_created': self._total_created,
                'total_reused': self._total_reused,
                'reuse_rate': self._total_reused / max(1, self._total_created + self._total_reused)
            }

class SmartCache:
    """Memory-efficient cache with automatic cleanup"""
    
    def __init__(self, 
                 max_size: int = 10000,
                 max_memory: int = 100 * 1024 * 1024,  # 100MB
                 ttl: float = 3600.0):
        self.max_size = max_size
        self.max_memory = max_memory
        self.ttl = ttl
        
        self._cache: Dict[str, Any] = {}
        self._access_times: Dict[str, float] = {}
        self._creation_times: Dict[str, float] = {}
        self._sizes: Dict[str, int] = {}
        self._lock = threading.RLock()
        
        self._current_memory = 0
        self._hits = 0
        self._misses = 0
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        with self._lock:
            if key in self._cache:
                # Check TTL
                if time.time() - self._creation_times[key] > self.ttl:
                    self._remove_item(key)
                    self._misses += 1
                    return None
                
                self._access_times[key] = time.time()
                self._hits += 1
                return self._cache[key]
            else:
                self._misses += 1
                return None
    
    def put(self, key: str, value: Any):
        """Put item in cache"""
        with self._lock:
            # Calculate size
            try:
                size = sys.getsizeof(value)
                if hasattr(value, '__dict__'):
                    size += sys.getsizeof(value.__dict__)
            except Exception:
                size = 1024  # Default estimate
            
            # Remove existing item if present
            if key in self._cache:
                self._remove_item(key)
            
            # Check memory limit
            if self._current_memory + size > self.max_memory:
                self._evict_lru()
            
            # Check size limit
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            # Add new item
            self._cache[key] = value
            self._access_times[key] = time.time()
            self._creation_times[key] = time.time()
            self._sizes[key] = size
            self._current_memory += size
    
    def _remove_item(self, key: str):
        """Remove item from cache"""
        if key in self._cache:
            self._current_memory -= self._sizes.get(key, 0)
            del self._cache[key]
            del self._access_times[key]
            del self._creation_times[key]
            del self._sizes[key]
    
    def _evict_lru(self):
        """Evict least recently used items"""
        if not self._cache:
            return
        
        # Sort by access time and remove oldest 10%
        items_by_access = sorted(
            self._access_times.items(),
            key=lambda x: x[1]
        )
        
        evict_count = max(1, len(items_by_access) // 10)
        
        for i in range(evict_count):
            key, _ = items_by_access[i]
            self._remove_item(key)
    
    def _cleanup_worker(self):
        """Background cleanup worker"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self):
        """Clean up expired items"""
        current_time = time.time()
        
        with self._lock:
            expired_keys = [
                key for key, creation_time in self._creation_times.items()
                if current_time - creation_time > self.ttl
            ]
            
            for key in expired_keys:
                self._remove_item(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache items")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'memory_usage': self._current_memory,
                'max_memory': self.max_memory,
                'hit_rate': hit_rate,
                'hits': self._hits,
                'misses': self._misses
            }

class MemoryTracker:
    """Track object creation and memory usage"""
    
    def __init__(self):
        self.tracked_objects: Dict[int, weakref.ref] = {}
        self.object_counts: defaultdict = defaultdict(int)
        self.object_sizes: defaultdict = defaultdict(int)
        self.creation_times: Dict[int, float] = {}
        self._lock = threading.Lock()
        
        # Enable tracemalloc for detailed tracking
        if not tracemalloc.is_tracing():
            tracemalloc.start(10)  # Keep 10 frames
    
    def track_object(self, obj: Any, category: str = "default"):
        """Track an object for memory monitoring"""
        obj_id = id(obj)
        obj_type = type(obj).__name__
        
        try:
            obj_size = sys.getsizeof(obj)
            if hasattr(obj, '__dict__'):
                obj_size += sys.getsizeof(obj.__dict__)
        except Exception:
            obj_size = 0
        
        with self._lock:
            # Create weak reference with cleanup callback
            def cleanup_callback(ref):
                with self._lock:
                    if obj_id in self.tracked_objects:
                        del self.tracked_objects[obj_id]
                    if obj_id in self.creation_times:
                        del self.creation_times[obj_id]
                    self.object_counts[f"{category}:{obj_type}"] -= 1
                    self.object_sizes[f"{category}:{obj_type}"] -= obj_size
            
            self.tracked_objects[obj_id] = weakref.ref(obj, cleanup_callback)
            self.object_counts[f"{category}:{obj_type}"] += 1
            self.object_sizes[f"{category}:{obj_type}"] += obj_size
            self.creation_times[obj_id] = time.time()
    
    def get_object_stats(self) -> Dict[str, Any]:
        """Get object tracking statistics"""
        with self._lock:
            return {
                'object_counts': dict(self.object_counts),
                'object_sizes': dict(self.object_sizes),
                'total_tracked': len(self.tracked_objects)
            }

class MemoryMonitor:
    """System-wide memory monitoring and alerting"""
    
    def __init__(self, 
                 alert_threshold: float = 0.8,
                 critical_threshold: float = 0.9,
                 monitoring_interval: float = 30.0):
        self.alert_threshold = alert_threshold
        self.critical_threshold = critical_threshold
        self.monitoring_interval = monitoring_interval
        
        self.snapshots: deque = deque(maxlen=1000)
        self.alerts: List[Dict[str, Any]] = []
        self.leak_detector = MemoryLeakDetector()
        self.tracker = MemoryTracker()
        
        self._monitoring = False
        self._monitor_thread = None
        self._callbacks: List[Callable[[MemorySnapshot], None]] = []
    
    def start_monitoring(self):
        """Start memory monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Memory monitoring started")
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        logger.info("Memory monitoring stopped")
    
    def add_callback(self, callback: Callable[[MemorySnapshot], None]):
        """Add callback for memory updates"""
        self._callbacks.append(callback)
    
    def _monitor_worker(self):
        """Background monitoring worker"""
        while self._monitoring:
            try:
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)
                
                # Check for alerts
                self._check_alerts(snapshot)
                
                # Check for memory leaks
                leaks = self.leak_detector.detect_leaks()
                if leaks:
                    self._handle_leaks(leaks)
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(snapshot)
                    except Exception as e:
                        logger.warning(f"Memory callback error: {e}")
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Memory monitoring error: {e}")
                time.sleep(self.monitoring_interval)
    
    def _take_snapshot(self) -> MemorySnapshot:
        """Take memory usage snapshot"""
        # System memory
        memory_info = psutil.virtual_memory()
        
        # Python memory
        process = psutil.Process()
        process_memory = process.memory_info()
        
        # GC statistics
        gc_stats = gc.get_stats()
        gc_collections = [stat['collections'] for stat in gc_stats]
        
        # Object tracking
        object_stats = self.tracker.get_object_stats()
        
        return MemorySnapshot(
            total_memory=memory_info.total,
            available_memory=memory_info.available,
            used_memory=memory_info.used,
            memory_percent=memory_info.percent,
            python_memory=process_memory.rss,
            objects_count=len(gc.get_objects()),
            gc_collections=gc_collections,
            active_objects=object_stats['object_counts']
        )
    
    def _check_alerts(self, snapshot: MemorySnapshot):
        """Check for memory alerts"""
        memory_percent = snapshot.memory_percent / 100.0
        
        if memory_percent >= self.critical_threshold:
            alert = {
                'level': 'critical',
                'message': f'Critical memory usage: {memory_percent:.1%}',
                'timestamp': snapshot.timestamp,
                'memory_percent': memory_percent
            }
            self.alerts.append(alert)
            logger.critical(alert['message'])
            
        elif memory_percent >= self.alert_threshold:
            alert = {
                'level': 'warning',
                'message': f'High memory usage: {memory_percent:.1%}',
                'timestamp': snapshot.timestamp,
                'memory_percent': memory_percent
            }
            self.alerts.append(alert)
            logger.warning(alert['message'])
    
    def _handle_leaks(self, leaks: List[MemoryLeak]):
        """Handle detected memory leaks"""
        for leak in leaks:
            alert = {
                'level': leak.severity,
                'message': f'Memory leak detected: {leak.object_type} ({leak.object_count} objects)',
                'timestamp': time.time(),
                'leak_info': {
                    'object_type': leak.object_type,
                    'object_count': leak.object_count,
                    'memory_size': leak.memory_size,
                    'growth_rate': leak.growth_rate
                }
            }
            self.alerts.append(alert)
            
            if leak.severity in ['high', 'critical']:
                logger.error(alert['message'])
            else:
                logger.warning(alert['message'])
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics"""
        if not self.snapshots:
            return {}
        
        current = self.snapshots[-1]
        
        # Calculate trends
        if len(self.snapshots) > 1:
            previous = self.snapshots[-2]
            memory_trend = current.memory_percent - previous.memory_percent
            python_trend = current.python_memory - previous.python_memory
        else:
            memory_trend = 0.0
            python_trend = 0
        
        return {
            'current_snapshot': current,
            'memory_trend': memory_trend,
            'python_memory_trend': python_trend,
            'total_alerts': len(self.alerts),
            'recent_alerts': [a for a in self.alerts if time.time() - a['timestamp'] < 3600],
            'object_stats': self.tracker.get_object_stats()
        }

class MemoryLeakDetector:
    """Detect potential memory leaks"""
    
    def __init__(self, detection_window: float = 300.0):
        self.detection_window = detection_window
        self.object_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.size_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    
    def detect_leaks(self) -> List[MemoryLeak]:
        """Detect memory leaks"""
        leaks = []
        current_time = time.time()
        
        # Get current object counts
        current_objects = {}
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            current_objects[obj_type] = current_objects.get(obj_type, 0) + 1
        
        # Record history
        for obj_type, count in current_objects.items():
            self.object_history[obj_type].append((current_time, count))
            
            try:
                size = sys.getsizeof(obj)
                self.size_history[obj_type].append((current_time, size))
            except Exception:
                pass
        
        # Analyze trends
        for obj_type, history in self.object_history.items():
            if len(history) < 10:  # Need enough data points
                continue
            
            # Calculate growth rate
            recent_entries = [entry for entry in history if current_time - entry[0] <= self.detection_window]
            
            if len(recent_entries) < 5:
                continue
            
            times = [entry[0] for entry in recent_entries]
            counts = [entry[1] for entry in recent_entries]
            
            # Simple linear regression for growth rate
            if len(set(counts)) > 1:  # Check if counts are changing
                time_range = max(times) - min(times)
                count_range = max(counts) - min(counts)
                
                if time_range > 0:
                    growth_rate = count_range / time_range
                    
                    # Check if growth rate is suspicious
                    if growth_rate > 1.0:  # More than 1 object per second
                        current_count = counts[-1]
                        total_size = sum(entry[1] for entry in self.size_history[obj_type][-10:])
                        
                        severity = "low"
                        if growth_rate > 10.0:
                            severity = "critical"
                        elif growth_rate > 5.0:
                            severity = "high"
                        elif growth_rate > 2.0:
                            severity = "medium"
                        
                        leak = MemoryLeak(
                            object_type=obj_type,
                            object_count=current_count,
                            memory_size=total_size,
                            growth_rate=growth_rate,
                            severity=severity
                        )
                        
                        leaks.append(leak)
        
        return leaks

class MemoryOptimizer:
    """Main memory optimization coordinator"""
    
    def __init__(self):
        self.monitor = MemoryMonitor()
        self.caches: Dict[str, SmartCache] = {}
        self.pools: Dict[str, MemoryPool] = {}
        
        # Global settings
        self.gc_optimization_enabled = True
        self.automatic_cleanup_enabled = True
        
        # Statistics
        self.optimization_stats = {
            'gc_forced_collections': 0,
            'cache_cleanups': 0,
            'pool_cleanups': 0,
            'memory_freed': 0
        }
    
    def start(self):
        """Start memory optimization"""
        self.monitor.start_monitoring()
        self.monitor.add_callback(self._memory_callback)
        
        # Configure garbage collection
        if self.gc_optimization_enabled:
            self._optimize_gc()
        
        logger.info("Memory optimizer started")
    
    def stop(self):
        """Stop memory optimization"""
        self.monitor.stop_monitoring()
        logger.info("Memory optimizer stopped")
    
    def create_cache(self, name: str, **kwargs) -> SmartCache:
        """Create optimized cache"""
        cache = SmartCache(**kwargs)
        self.caches[name] = cache
        return cache
    
    def create_pool(self, name: str, factory: Callable, **kwargs) -> MemoryPool:
        """Create memory pool"""
        pool = MemoryPool(factory, **kwargs)
        self.pools[name] = pool
        return pool
    
    def _memory_callback(self, snapshot: MemorySnapshot):
        """Handle memory updates"""
        memory_percent = snapshot.memory_percent / 100.0
        
        # Automatic cleanup when memory usage is high
        if self.automatic_cleanup_enabled and memory_percent > 0.8:
            self._emergency_cleanup()
    
    def _emergency_cleanup(self):
        """Emergency memory cleanup"""
        logger.warning("Performing emergency memory cleanup")
        
        # Force garbage collection
        collected = gc.collect()
        self.optimization_stats['gc_forced_collections'] += 1
        
        # Clean up caches
        for cache in self.caches.values():
            cache._cleanup_expired()
            cache._evict_lru()
        self.optimization_stats['cache_cleanups'] += 1
        
        # Clean up pools
        for pool in self.pools.values():
            pool._cleanup()
        self.optimization_stats['pool_cleanups'] += 1
        
        logger.info(f"Emergency cleanup completed, collected {collected} objects")
    
    def _optimize_gc(self):
        """Optimize garbage collection settings"""
        # Adjust GC thresholds for better performance
        # Default: (700, 10, 10)
        # Optimized: More aggressive collection for generation 0
        gc.set_threshold(500, 15, 15)
        
        # Enable automatic GC
        gc.enable()
        
        logger.debug("Garbage collection optimized")
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """Get comprehensive optimization report"""
        memory_stats = self.monitor.get_memory_stats()
        
        cache_stats = {}
        for name, cache in self.caches.items():
            cache_stats[name] = cache.get_stats()
        
        pool_stats = {}
        for name, pool in self.pools.items():
            pool_stats[name] = pool.get_stats()
        
        return {
            'memory_stats': memory_stats,
            'cache_stats': cache_stats,
            'pool_stats': pool_stats,
            'optimization_stats': self.optimization_stats,
            'gc_stats': {
                'collections': gc.get_stats(),
                'threshold': gc.get_threshold(),
                'count': gc.get_count()
            }
        }
    
    def force_optimization(self):
        """Force immediate optimization"""
        logger.info("Forcing memory optimization")
        
        # Force garbage collection
        before_objects = len(gc.get_objects())
        collected = gc.collect()
        after_objects = len(gc.get_objects())
        
        # Clean all caches
        for cache in self.caches.values():
            cache._cleanup_expired()
        
        # Clean all pools
        for pool in self.pools.values():
            pool._cleanup()
        
        self.optimization_stats['gc_forced_collections'] += 1
        
        logger.info(f"Optimization complete: {collected} objects collected, "
                   f"{before_objects - after_objects} objects freed")

# Decorators for memory optimization

def memory_efficient(func):
    """Decorator to make function memory efficient"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Take snapshot before
        gc_before = len(gc.get_objects())
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Force cleanup after execution
            gc.collect()
            gc_after = len(gc.get_objects())
            
            if gc_after > gc_before * 1.1:  # 10% growth threshold
                logger.debug(f"Function {func.__name__} increased object count from {gc_before} to {gc_after}")
    
    return wrapper

@contextmanager
def memory_scope():
    """Context manager for memory-efficient operations"""
    gc_before = len(gc.get_objects())
    
    try:
        yield
    finally:
        gc.collect()
        gc_after = len(gc.get_objects())
        
        logger.debug(f"Memory scope: {gc_before} -> {gc_after} objects ({gc_after - gc_before:+d})")

# Global memory optimizer instance
_memory_optimizer: Optional[MemoryOptimizer] = None

def get_memory_optimizer() -> MemoryOptimizer:
    """Get global memory optimizer instance"""
    global _memory_optimizer
    
    if _memory_optimizer is None:
        _memory_optimizer = MemoryOptimizer()
    
    return _memory_optimizer

def start_memory_optimization():
    """Start global memory optimization"""
    optimizer = get_memory_optimizer()
    optimizer.start()

def stop_memory_optimization():
    """Stop global memory optimization"""
    global _memory_optimizer
    
    if _memory_optimizer:
        _memory_optimizer.stop()
        _memory_optimizer = None 