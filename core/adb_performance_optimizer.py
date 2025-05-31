"""
ADB Performance Optimizer

Advanced optimization techniques for ADB communication:
- Adaptive command routing
- Predictive caching
- Network compression
- Command fusion and consolidation  
- Smart retry strategies
- Performance analytics and tuning
"""

import asyncio
import time
import statistics
import threading
import pickle
import zlib
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
import re

from core.optimized_adb import OptimizedADBManager, ADBCommand, ADBResult, ADBCommandType, ADBDevice
from core.profiler import profile_function
from core.logger import get_logger

logger = get_logger(__name__)

@dataclass
class CommandPattern:
    """Command pattern for optimization"""
    pattern: str
    frequency: int = 0
    average_execution_time: float = 0.0
    success_rate: float = 1.0
    optimal_batch_size: int = 1
    cache_ttl: float = 0.0  # Cache time-to-live in seconds
    
@dataclass
class DeviceProfile:
    """Device performance profile"""
    serial: str
    cpu_info: Dict[str, Any] = field(default_factory=dict)
    memory_info: Dict[str, Any] = field(default_factory=dict)
    storage_info: Dict[str, Any] = field(default_factory=dict)
    network_latency: float = 0.0
    command_throughput: float = 0.0  # Commands per second
    optimal_concurrency: int = 1
    preferred_command_types: List[ADBCommandType] = field(default_factory=list)
    last_profiled: float = field(default_factory=time.time)

@dataclass 
class CacheEntry:
    """Cache entry for command results"""
    result: ADBResult
    created_at: float
    ttl: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

class CommandCache:
    """Intelligent caching for ADB command results"""
    
    def __init__(self, max_size: int = 10000, default_ttl: float = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
    
    def _generate_cache_key(self, command: ADBCommand) -> str:
        """Generate cache key for command"""
        # Create deterministic key from command components
        key_components = [
            str(command.command),
            command.device_serial or "default",
            command.command_type.value
        ]
        
        key_string = "|".join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, command: ADBCommand) -> Optional[ADBResult]:
        """Get cached result for command"""
        cache_key = self._generate_cache_key(command)
        
        with self._lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                
                # Check if entry is still valid
                if time.time() - entry.created_at <= entry.ttl:
                    entry.access_count += 1
                    entry.last_accessed = time.time()
                    logger.debug(f"Cache hit for command: {command.command[:2]}")
                    return entry.result
                else:
                    # Entry expired
                    del self.cache[cache_key]
                    logger.debug(f"Cache expired for command: {command.command[:2]}")
            
            return None
    
    def put(self, command: ADBCommand, result: ADBResult, ttl: Optional[float] = None):
        """Cache command result"""
        cache_key = self._generate_cache_key(command)
        effective_ttl = ttl or self.default_ttl
        
        # Only cache successful results
        if not result.success:
            return
        
        with self._lock:
            # Evict oldest entries if at capacity
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            self.cache[cache_key] = CacheEntry(
                result=result,
                created_at=time.time(),
                ttl=effective_ttl
            )
            
            logger.debug(f"Cached result for command: {command.command[:2]}")
    
    def _evict_oldest(self):
        """Evict least recently used entries"""
        if not self.cache:
            return
        
        # Sort by last accessed time and remove oldest 10%
        entries_by_access = sorted(
            self.cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        evict_count = max(1, len(entries_by_access) // 10)
        
        for i in range(evict_count):
            cache_key, _ = entries_by_access[i]
            del self.cache[cache_key]
        
        logger.debug(f"Evicted {evict_count} cache entries")
    
    def _cleanup_worker(self):
        """Background thread to clean up expired entries"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def _cleanup_expired(self):
        """Remove expired cache entries"""
        current_time = time.time()
        
        with self._lock:
            expired_keys = [
                key for key, entry in self.cache.items()
                if current_time - entry.created_at > entry.ttl
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

class CommandAnalyzer:
    """Analyze command patterns and performance"""
    
    def __init__(self):
        self.patterns: Dict[str, CommandPattern] = {}
        self.execution_history: deque = deque(maxlen=10000)
        self._lock = threading.Lock()
    
    def analyze_command(self, command: ADBCommand, result: ADBResult):
        """Analyze command execution"""
        pattern_key = self._extract_pattern(command)
        
        with self._lock:
            if pattern_key not in self.patterns:
                self.patterns[pattern_key] = CommandPattern(pattern=pattern_key)
            
            pattern = self.patterns[pattern_key]
            pattern.frequency += 1
            
            # Update success rate
            if result.success:
                pattern.success_rate = (pattern.success_rate * (pattern.frequency - 1) + 1.0) / pattern.frequency
            else:
                pattern.success_rate = (pattern.success_rate * (pattern.frequency - 1) + 0.0) / pattern.frequency
            
            # Update average execution time
            pattern.average_execution_time = (
                pattern.average_execution_time * (pattern.frequency - 1) + result.execution_time
            ) / pattern.frequency
            
            # Store execution record
            self.execution_history.append({
                'pattern': pattern_key,
                'execution_time': result.execution_time,
                'success': result.success,
                'timestamp': time.time(),
                'device': command.device_serial
            })
    
    def _extract_pattern(self, command: ADBCommand) -> str:
        """Extract pattern from command"""
        # Normalize command for pattern matching
        cmd_str = " ".join(command.command)
        
        # Replace device-specific values with placeholders
        patterns = [
            (r'/data/data/[^/]+', '/data/data/APP'),
            (r'/sdcard/[^/]+', '/sdcard/FILE'),
            (r'\d+\.\d+\.\d+\.\d+', 'IP_ADDRESS'),
            (r'\d{4,}', 'NUMBER'),
            (r'"[^"]*"', 'STRING'),
            (r"'[^']*'", 'STRING')
        ]
        
        normalized = cmd_str
        for pattern, replacement in patterns:
            normalized = re.sub(pattern, replacement, normalized)
        
        return f"{command.command_type.value}:{normalized}"
    
    def get_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Get optimization suggestions based on analysis"""
        suggestions = []
        
        with self._lock:
            # Find frequently used commands
            frequent_patterns = sorted(
                self.patterns.items(),
                key=lambda x: x[1].frequency,
                reverse=True
            )[:10]
            
            for pattern_key, pattern in frequent_patterns:
                if pattern.frequency > 10:
                    # Suggest caching for slow commands
                    if pattern.average_execution_time > 1.0:
                        suggestions.append({
                            'type': 'caching',
                            'pattern': pattern_key,
                            'reason': f'Slow command ({pattern.average_execution_time:.2f}s avg)',
                            'suggested_ttl': min(300, pattern.average_execution_time * 10)
                        })
                    
                    # Suggest batching for frequent commands
                    if pattern.frequency > 50:
                        suggestions.append({
                            'type': 'batching',
                            'pattern': pattern_key,
                            'reason': f'Frequent command ({pattern.frequency} executions)',
                            'suggested_batch_size': min(10, max(2, pattern.frequency // 20))
                        })
        
        return suggestions

class DeviceProfiler:
    """Profile device capabilities and optimize accordingly"""
    
    def __init__(self, adb_manager: OptimizedADBManager):
        self.adb_manager = adb_manager
        self.profiles: Dict[str, DeviceProfile] = {}
        self._lock = threading.Lock()
    
    async def profile_device(self, device_serial: str) -> DeviceProfile:
        """Profile device performance characteristics"""
        logger.info(f"🔍 Profiling device: {device_serial}")
        
        profile = DeviceProfile(serial=device_serial)
        
        try:
            # Get CPU information
            cpu_result = await self.adb_manager.execute_command_async([
                "shell", "cat /proc/cpuinfo"
            ], device_serial)
            
            if cpu_result.success:
                profile.cpu_info = self._parse_cpu_info(cpu_result.stdout)
            
            # Get memory information
            mem_result = await self.adb_manager.execute_command_async([
                "shell", "cat /proc/meminfo"
            ], device_serial)
            
            if mem_result.success:
                profile.memory_info = self._parse_memory_info(mem_result.stdout)
            
            # Test command throughput
            profile.command_throughput = await self._test_command_throughput(device_serial)
            
            # Test network latency
            profile.network_latency = await self._test_network_latency(device_serial)
            
            # Determine optimal concurrency
            profile.optimal_concurrency = await self._test_optimal_concurrency(device_serial)
            
            with self._lock:
                self.profiles[device_serial] = profile
            
            logger.info(f"✅ Device profiling completed for {device_serial}")
            
        except Exception as e:
            logger.error(f"❌ Device profiling failed for {device_serial}: {e}")
        
        return profile
    
    def _parse_cpu_info(self, cpu_info: str) -> Dict[str, Any]:
        """Parse CPU information from /proc/cpuinfo"""
        info = {}
        
        lines = cpu_info.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                if key in ['processor', 'cpu_cores', 'siblings']:
                    try:
                        info[key] = int(value)
                    except ValueError:
                        info[key] = value
                elif key in ['bogomips', 'cpu_mhz']:
                    try:
                        info[key] = float(value)
                    except ValueError:
                        info[key] = value
                else:
                    info[key] = value
        
        return info
    
    def _parse_memory_info(self, mem_info: str) -> Dict[str, Any]:
        """Parse memory information from /proc/meminfo"""
        info = {}
        
        lines = mem_info.strip().split('\n')
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                # Extract numeric value and unit
                parts = value.split()
                if parts:
                    try:
                        numeric_value = int(parts[0])
                        unit = parts[1] if len(parts) > 1 else 'bytes'
                        
                        # Convert to bytes
                        if unit.lower() == 'kb':
                            numeric_value *= 1024
                        elif unit.lower() == 'mb':
                            numeric_value *= 1024 * 1024
                        
                        info[key] = numeric_value
                    except ValueError:
                        info[key] = value
        
        return info
    
    async def _test_command_throughput(self, device_serial: str) -> float:
        """Test command execution throughput"""
        try:
            start_time = time.time()
            commands_count = 10
            
            # Execute simple commands to measure throughput
            tasks = []
            for _ in range(commands_count):
                task = self.adb_manager.execute_command_async([
                    "shell", "echo test"
                ], device_serial)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            elapsed_time = time.time() - start_time
            throughput = commands_count / elapsed_time
            
            logger.debug(f"Device {device_serial} throughput: {throughput:.2f} cmd/s")
            return throughput
            
        except Exception as e:
            logger.warning(f"Throughput test failed for {device_serial}: {e}")
            return 1.0
    
    async def _test_network_latency(self, device_serial: str) -> float:
        """Test network latency to device"""
        try:
            latencies = []
            
            for _ in range(5):
                start_time = time.time()
                
                result = await self.adb_manager.execute_command_async([
                    "shell", "echo latency_test"
                ], device_serial)
                
                if result.success:
                    latency = time.time() - start_time
                    latencies.append(latency)
            
            if latencies:
                avg_latency = statistics.mean(latencies)
                logger.debug(f"Device {device_serial} latency: {avg_latency*1000:.1f}ms")
                return avg_latency
            
        except Exception as e:
            logger.warning(f"Latency test failed for {device_serial}: {e}")
        
        return 0.1  # Default latency
    
    async def _test_optimal_concurrency(self, device_serial: str) -> int:
        """Test optimal concurrency level for device"""
        try:
            # Test different concurrency levels
            best_concurrency = 1
            best_throughput = 0
            
            for concurrency in [1, 2, 4, 8]:
                start_time = time.time()
                
                # Create concurrent tasks
                tasks = []
                for _ in range(concurrency * 5):  # 5 commands per worker
                    task = self.adb_manager.execute_command_async([
                        "shell", "sleep 0.1"
                    ], device_serial)
                    tasks.append(task)
                
                await asyncio.gather(*tasks)
                
                elapsed_time = time.time() - start_time
                throughput = len(tasks) / elapsed_time
                
                if throughput > best_throughput:
                    best_throughput = throughput
                    best_concurrency = concurrency
                
                logger.debug(f"Concurrency {concurrency}: {throughput:.2f} cmd/s")
            
            logger.debug(f"Optimal concurrency for {device_serial}: {best_concurrency}")
            return best_concurrency
            
        except Exception as e:
            logger.warning(f"Concurrency test failed for {device_serial}: {e}")
            return 2  # Safe default
    
    def get_device_profile(self, device_serial: str) -> Optional[DeviceProfile]:
        """Get device profile"""
        with self._lock:
            return self.profiles.get(device_serial)

class ADBPerformanceOptimizer:
    """Main performance optimizer for ADB operations"""
    
    def __init__(self, adb_manager: OptimizedADBManager):
        self.adb_manager = adb_manager
        self.cache = CommandCache()
        self.analyzer = CommandAnalyzer()
        self.profiler = DeviceProfiler(adb_manager)
        
        # Performance statistics
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'optimized_commands': 0,
            'total_commands': 0,
            'time_saved': 0.0
        }
        self._stats_lock = threading.Lock()
        
        # Command fusion patterns
        self.fusion_patterns = {
            'property_batch': {
                'pattern': r'shell getprop (.+)',
                'fusion_command': 'shell "getprop {props}"',
                'max_batch_size': 10
            },
            'file_operations': {
                'pattern': r'shell (ls|cat|test) (.+)',
                'fusion_command': 'shell "{commands}"',
                'max_batch_size': 5
            }
        }
    
    @profile_function
    async def execute_optimized_command(self, 
                                      command: ADBCommand) -> ADBResult:
        """Execute command with all optimizations applied"""
        
        with self._stats_lock:
            self.stats['total_commands'] += 1
        
        # Try cache first
        cached_result = self.cache.get(command)
        if cached_result:
            with self._stats_lock:
                self.stats['cache_hits'] += 1
                self.stats['time_saved'] += cached_result.execution_time
            
            logger.debug(f"🚀 Cache hit - saved {cached_result.execution_time:.3f}s")
            return cached_result
        
        with self._stats_lock:
            self.stats['cache_misses'] += 1
        
        # Get device profile for optimization
        device_profile = self.profiler.get_device_profile(command.device_serial)
        
        # Apply device-specific optimizations
        if device_profile:
            command = self._apply_device_optimizations(command, device_profile)
        
        # Execute command
        start_time = time.time()
        result = await self.adb_manager.execute_command_async(
            command.command,
            command.device_serial,
            command.command_type,
            command.timeout
        )
        
        # Analyze execution
        self.analyzer.analyze_command(command, result)
        
        # Cache successful results if appropriate
        if result.success and self._should_cache_command(command):
            cache_ttl = self._determine_cache_ttl(command)
            self.cache.put(command, result, cache_ttl)
        
        with self._stats_lock:
            self.stats['optimized_commands'] += 1
        
        return result
    
    def _apply_device_optimizations(self, 
                                  command: ADBCommand, 
                                  profile: DeviceProfile) -> ADBCommand:
        """Apply device-specific optimizations"""
        
        # Adjust timeout based on device performance
        if profile.network_latency > 0.5:  # High latency device
            command.timeout *= 2
        elif profile.command_throughput > 10:  # Fast device
            command.timeout *= 0.7
        
        # Adjust retry count based on device reliability
        device_stats = self.adb_manager.get_device_info(command.device_serial)
        if device_stats and device_stats.connection_quality < 0.8:
            command.retry_count = min(5, command.retry_count + 2)
        
        return command
    
    def _should_cache_command(self, command: ADBCommand) -> bool:
        """Determine if command result should be cached"""
        
        # Don't cache commands that modify state
        modifying_commands = [
            'install', 'uninstall', 'push', 'rm', 'mkdir', 
            'mv', 'cp', 'chmod', 'chown', 'input'
        ]
        
        cmd_str = " ".join(command.command).lower()
        
        for mod_cmd in modifying_commands:
            if mod_cmd in cmd_str:
                return False
        
        # Cache read-only commands
        readonly_commands = [
            'getprop', 'cat', 'ls', 'ps', 'netstat', 'dumpsys'
        ]
        
        for readonly_cmd in readonly_commands:
            if readonly_cmd in cmd_str:
                return True
        
        return False
    
    def _determine_cache_ttl(self, command: ADBCommand) -> float:
        """Determine appropriate cache TTL for command"""
        
        cmd_str = " ".join(command.command).lower()
        
        # Short TTL for dynamic data
        if any(keyword in cmd_str for keyword in ['ps', 'netstat', 'top']):
            return 30.0
        
        # Medium TTL for semi-static data
        if any(keyword in cmd_str for keyword in ['dumpsys', 'getprop']):
            return 300.0
        
        # Long TTL for static data
        if any(keyword in cmd_str for keyword in ['cat /system', 'ls /system']):
            return 3600.0
        
        return 60.0  # Default TTL
    
    async def batch_optimize_commands(self, 
                                    commands: List[ADBCommand]) -> List[ADBResult]:
        """Optimize and execute batch of commands"""
        
        if not commands:
            return []
        
        logger.info(f"🔧 Optimizing batch of {len(commands)} commands")
        
        # Group by device
        device_groups = defaultdict(list)
        for cmd in commands:
            device_groups[cmd.device_serial or 'default'].append(cmd)
        
        # Execute by device groups
        all_results = []
        
        for device_serial, device_commands in device_groups.items():
            # Try to fuse compatible commands
            fused_commands = self._fuse_compatible_commands(device_commands)
            
            # Execute optimized commands
            device_results = []
            for cmd in fused_commands:
                result = await self.execute_optimized_command(cmd)
                device_results.append(result)
            
            all_results.extend(device_results)
        
        return all_results
    
    def _fuse_compatible_commands(self, commands: List[ADBCommand]) -> List[ADBCommand]:
        """Fuse compatible commands for better performance"""
        
        if len(commands) <= 1:
            return commands
        
        fused_commands = []
        remaining_commands = commands.copy()
        
        # Try to fuse getprop commands
        prop_commands = [
            cmd for cmd in remaining_commands 
            if 'getprop' in " ".join(cmd.command)
        ]
        
        if len(prop_commands) > 1:
            # Extract property names
            props = []
            for cmd in prop_commands:
                cmd_str = " ".join(cmd.command)
                match = re.search(r'getprop\s+([^\s]+)', cmd_str)
                if match:
                    props.append(match.group(1))
            
            if props:
                # Create fused command
                fused_cmd = ADBCommand(
                    command=["shell", f"getprop | grep -E '({'|'.join(props)})'"],
                    device_serial=prop_commands[0].device_serial,
                    command_type=ADBCommandType.SHELL
                )
                fused_commands.append(fused_cmd)
                
                # Remove fused commands from remaining
                for cmd in prop_commands:
                    remaining_commands.remove(cmd)
        
        # Add remaining commands
        fused_commands.extend(remaining_commands)
        
        return fused_commands
    
    async def profile_all_devices(self):
        """Profile all connected devices"""
        devices = self.adb_manager.get_connected_devices()
        
        logger.info(f"📊 Profiling {len(devices)} devices")
        
        tasks = []
        for device in devices:
            if device.state.value == 'connected':
                task = self.profiler.profile_device(device.serial)
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks)
        
        logger.info("✅ Device profiling completed")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        
        # Get basic stats
        with self._stats_lock:
            stats = self.stats.copy()
        
        # Calculate cache hit rate
        total_cache_requests = stats['cache_hits'] + stats['cache_misses']
        cache_hit_rate = (
            stats['cache_hits'] / total_cache_requests 
            if total_cache_requests > 0 else 0
        )
        
        # Get optimization suggestions
        suggestions = self.analyzer.get_optimization_suggestions()
        
        # Get device profiles
        device_profiles = {}
        with self.profiler._lock:
            for serial, profile in self.profiler.profiles.items():
                device_profiles[serial] = {
                    'throughput': profile.command_throughput,
                    'latency': profile.network_latency,
                    'concurrency': profile.optimal_concurrency,
                    'last_profiled': profile.last_profiled
                }
        
        return {
            'statistics': {
                **stats,
                'cache_hit_rate': cache_hit_rate,
                'optimization_rate': (
                    stats['optimized_commands'] / stats['total_commands']
                    if stats['total_commands'] > 0 else 0
                )
            },
            'optimization_suggestions': suggestions,
            'device_profiles': device_profiles,
            'cache_status': {
                'size': len(self.cache.cache),
                'max_size': self.cache.max_size
            }
        }
    
    def save_optimization_data(self, file_path: str):
        """Save optimization data for persistence"""
        data = {
            'patterns': {k: {
                'pattern': v.pattern,
                'frequency': v.frequency,
                'average_execution_time': v.average_execution_time,
                'success_rate': v.success_rate,
                'optimal_batch_size': v.optimal_batch_size,
                'cache_ttl': v.cache_ttl
            } for k, v in self.analyzer.patterns.items()},
            'device_profiles': {k: {
                'serial': v.serial,
                'cpu_info': v.cpu_info,
                'memory_info': v.memory_info,
                'network_latency': v.network_latency,
                'command_throughput': v.command_throughput,
                'optimal_concurrency': v.optimal_concurrency,
                'last_profiled': v.last_profiled
            } for k, v in self.profiler.profiles.items()},
            'statistics': self.stats
        }
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Optimization data saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save optimization data: {e}")
    
    def load_optimization_data(self, file_path: str):
        """Load optimization data from file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load patterns
            for k, v in data.get('patterns', {}).items():
                pattern = CommandPattern(
                    pattern=v['pattern'],
                    frequency=v['frequency'],
                    average_execution_time=v['average_execution_time'],
                    success_rate=v['success_rate'],
                    optimal_batch_size=v['optimal_batch_size'],
                    cache_ttl=v['cache_ttl']
                )
                self.analyzer.patterns[k] = pattern
            
            # Load device profiles
            for k, v in data.get('device_profiles', {}).items():
                profile = DeviceProfile(
                    serial=v['serial'],
                    cpu_info=v['cpu_info'],
                    memory_info=v['memory_info'],
                    network_latency=v['network_latency'],
                    command_throughput=v['command_throughput'],
                    optimal_concurrency=v['optimal_concurrency'],
                    last_profiled=v['last_profiled']
                )
                self.profiler.profiles[k] = profile
            
            # Load statistics
            self.stats.update(data.get('statistics', {}))
            
            logger.info(f"📂 Optimization data loaded from {file_path}")
            
        except Exception as e:
            logger.warning(f"Failed to load optimization data: {e}")

# Global optimizer instance
_optimizer_instance: Optional[ADBPerformanceOptimizer] = None

def get_adb_optimizer(adb_manager: OptimizedADBManager = None) -> ADBPerformanceOptimizer:
    """Get or create global ADB optimizer instance"""
    global _optimizer_instance
    
    if _optimizer_instance is None:
        if adb_manager is None:
            from core.optimized_adb import get_adb_manager
            adb_manager = get_adb_manager()
        
        _optimizer_instance = ADBPerformanceOptimizer(adb_manager)
    
    return _optimizer_instance

def shutdown_adb_optimizer():
    """Shutdown global optimizer instance"""
    global _optimizer_instance
    _optimizer_instance = None 