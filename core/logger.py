"""
Comprehensive Logging System for Google Account Creator

This module provides a centralized, configurable logging system with advanced features
including context tracking, sensitive data masking, and log shipping capabilities.

Features:
- Custom logger with configurable levels and formatting
- Context-based logging with session/request tracking
- Sensitive data masking for security
- Log rotation and archiving
- Log shipping to centralized services
- Performance logging for key operations
"""

import logging
import logging.handlers
import json
import re
import time
import threading
import uuid
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import contextvars
from queue import Queue, Empty
import gzip
import shutil
import os

# Context variables for thread-safe logging context
log_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar('log_context', default={})

class LogLevel(Enum):
    """Custom log levels with numeric values"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    FATAL = 60

class LogFormat(Enum):
    """Available log output formats"""
    TEXT = "text"
    JSON = "json"
    STRUCTURED = "structured"

@dataclass
class LogEntry:
    """Represents a single log entry with all metadata"""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    context: Dict[str, Any] = field(default_factory=dict)
    extra_data: Dict[str, Any] = field(default_factory=dict)
    exception_info: Optional[str] = None
    stack_trace: Optional[str] = None

@dataclass
class LoggerConfig:
    """Configuration for the custom logger"""
    name: str = "GoogleAccountCreator"
    level: LogLevel = LogLevel.INFO
    format_type: LogFormat = LogFormat.TEXT
    file_path: Optional[str] = "logs/application.log"
    console_output: bool = True
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    rotation_interval: Optional[str] = None  # 'daily', 'weekly', 'monthly'
    enable_context: bool = True
    enable_masking: bool = True
    enable_shipping: bool = False
    shipping_endpoint: Optional[str] = None
    shipping_api_key: Optional[str] = None
    custom_format: Optional[str] = None

class SensitiveDataMasker:
    """Handles masking of sensitive information in log messages"""
    
    def __init__(self):
        # Patterns for sensitive data detection
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'password': re.compile(r'(?i)(password|pwd|pass)\s*[:=]\s*[\'"]?([^\s\'"]+)[\'"]?'),
            'api_key': re.compile(r'(?i)(api[_-]?key|token|secret)\s*[:=]\s*[\'"]?([A-Za-z0-9\-_]{20,})[\'"]?'),
            'phone': re.compile(r'\b(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'url_with_auth': re.compile(r'https?://[^:]+:[^@]+@[^\s]+'),
        }
        
        # Custom masking functions
        self.mask_functions: Dict[str, Callable[[str], str]] = {
            'email': lambda m: f"{m.group()[:2]}***@{m.group().split('@')[1]}",
            'password': lambda m: f"{m.group(1)}={self._mask_value(m.group(2))}",
            'api_key': lambda m: f"{m.group(1)}={self._mask_value(m.group(2))}",
            'phone': lambda m: f"***-***-{m.group(4)}",
            'credit_card': lambda m: f"****-****-****-{m.group()[-4:]}",
            'ssn': lambda m: "***-**-****",
            'ip_address': lambda m: f"{m.group().split('.')[0]}.***.***.***",
            'url_with_auth': lambda m: re.sub(r'://[^:]+:[^@]+@', '://***:***@', m.group()),
        }
    
    def _mask_value(self, value: str) -> str:
        """Mask a value by showing only first and last characters"""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
    
    def mask_message(self, message: str) -> str:
        """Apply masking to a log message"""
        masked_message = message
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in self.mask_functions:
                masked_message = pattern.sub(self.mask_functions[pattern_name], masked_message)
        
        return masked_message
    
    def add_pattern(self, name: str, pattern: re.Pattern, mask_function: Callable[[str], str]) -> None:
        """Add a custom masking pattern"""
        self.patterns[name] = pattern
        self.mask_functions[name] = mask_function
    
    def remove_pattern(self, name: str) -> None:
        """Remove a masking pattern"""
        self.patterns.pop(name, None)
        self.mask_functions.pop(name, None)

class ContextManager:
    """Manages logging context for request/session tracking"""
    
    def __init__(self):
        self.global_context: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def set_global_context(self, **kwargs) -> None:
        """Set global context values"""
        with self._lock:
            self.global_context.update(kwargs)
    
    def clear_global_context(self) -> None:
        """Clear global context"""
        with self._lock:
            self.global_context.clear()
    
    def set_request_context(self, **kwargs) -> None:
        """Set context for current request/thread"""
        current_context = log_context.get({})
        current_context.update(kwargs)
        log_context.set(current_context)
    
    def clear_request_context(self) -> None:
        """Clear request context"""
        log_context.set({})
    
    def get_context(self) -> Dict[str, Any]:
        """Get combined context (global + request)"""
        context = {}
        with self._lock:
            context.update(self.global_context)
        context.update(log_context.get({}))
        return context
    
    def generate_request_id(self) -> str:
        """Generate a unique request ID"""
        return str(uuid.uuid4())
    
    def start_request(self, request_id: Optional[str] = None, **kwargs) -> str:
        """Start a new request context"""
        if request_id is None:
            request_id = self.generate_request_id()
        
        self.set_request_context(
            request_id=request_id,
            start_time=time.time(),
            **kwargs
        )
        return request_id
    
    def end_request(self) -> Optional[float]:
        """End request context and return duration"""
        context = log_context.get({})
        start_time = context.get('start_time')
        
        if start_time:
            duration = time.time() - start_time
            self.clear_request_context()
            return duration
        
        self.clear_request_context()
        return None

class CustomFormatter(logging.Formatter):
    """Custom formatter that supports multiple output formats"""
    
    def __init__(self, format_type: LogFormat, enable_context: bool = True, 
                 enable_masking: bool = True, masker: Optional[SensitiveDataMasker] = None):
        super().__init__()
        self.format_type = format_type
        self.enable_context = enable_context
        self.enable_masking = enable_masking
        self.masker = masker or SensitiveDataMasker()
        
        # Default format templates
        self.text_format = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
        self.json_format = True  # Will be handled in format method
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record according to specified format type"""
        # Apply sensitive data masking
        if self.enable_masking:
            record.msg = self.masker.mask_message(str(record.msg))
            if record.args:
                masked_args = []
                for arg in record.args:
                    if isinstance(arg, str):
                        masked_args.append(self.masker.mask_message(arg))
                    else:
                        masked_args.append(arg)
                record.args = tuple(masked_args)
        
        if self.format_type == LogFormat.JSON:
            return self._format_json(record)
        elif self.format_type == LogFormat.STRUCTURED:
            return self._format_structured(record)
        else:  # TEXT format
            return self._format_text(record)
    
    def _format_text(self, record: logging.LogRecord) -> str:
        """Format as human-readable text"""
        self._style._fmt = self.text_format
        
        formatted = super().format(record)
        
        # Add context if enabled
        if self.enable_context:
            context = log_context.get({})
            if context:
                context_str = " | ".join(f"{k}={v}" for k, v in context.items())
                formatted += f" | Context: {context_str}"
        
        return formatted
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """Format as JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "thread_id": record.thread,
            "process_id": record.process,
        }
        
        # Add context if enabled
        if self.enable_context:
            context = log_context.get({})
            if context:
                log_entry["context"] = context
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", "msecs",
                          "relativeCreated", "thread", "threadName", "processName", 
                          "process", "getMessage", "exc_info", "exc_text", "stack_info"]:
                log_entry[f"extra_{key}"] = value
        
        return json.dumps(log_entry, ensure_ascii=False)
    
    def _format_structured(self, record: logging.LogRecord) -> str:
        """Format as structured text (key=value pairs)"""
        parts = [
            f"time={datetime.fromtimestamp(record.created).isoformat()}",
            f"level={record.levelname}",
            f"logger={record.name}",
            f"module={record.module}",
            f"function={record.funcName}",
            f"line={record.lineno}",
            f"thread={record.thread}",
            f"message={record.getMessage()}"
        ]
        
        # Add context if enabled
        if self.enable_context:
            context = log_context.get({})
            for key, value in context.items():
                parts.append(f"ctx_{key}={value}")
        
        return " ".join(parts)

class LogShipper:
    """Handles shipping logs to centralized services"""
    
    def __init__(self, endpoint: str, api_key: Optional[str] = None, 
                 batch_size: int = 100, flush_interval: int = 30):
        self.endpoint = endpoint
        self.api_key = api_key
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        self.log_queue = Queue()
        self.batch_buffer: List[Dict[str, Any]] = []
        self.last_flush = time.time()
        self.shipping_thread = None
        self.stop_event = threading.Event()
        
        self._start_shipping_thread()
    
    def _start_shipping_thread(self) -> None:
        """Start the background thread for log shipping"""
        self.shipping_thread = threading.Thread(target=self._ship_logs_worker, daemon=True)
        self.shipping_thread.start()
    
    def _ship_logs_worker(self) -> None:
        """Background worker for shipping logs"""
        while not self.stop_event.is_set():
            try:
                # Process queue items
                while not self.log_queue.empty():
                    try:
                        log_entry = self.log_queue.get_nowait()
                        self.batch_buffer.append(log_entry)
                        
                        if len(self.batch_buffer) >= self.batch_size:
                            self._flush_batch()
                    except Empty:
                        break
                
                # Time-based flush
                if (time.time() - self.last_flush) >= self.flush_interval:
                    if self.batch_buffer:
                        self._flush_batch()
                
                time.sleep(1)  # Prevent busy waiting
                
            except Exception as e:
                # Log shipping errors should not crash the application
                print(f"Log shipping error: {e}")
    
    def _flush_batch(self) -> None:
        """Flush current batch to the endpoint"""
        if not self.batch_buffer:
            return
        
        try:
            import requests
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            payload = {
                "logs": self.batch_buffer,
                "timestamp": datetime.now().isoformat(),
                "source": "GoogleAccountCreator"
            }
            
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.batch_buffer.clear()
                self.last_flush = time.time()
            else:
                print(f"Log shipping failed: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Error shipping logs: {e}")
    
    def ship_log(self, log_entry: Dict[str, Any]) -> None:
        """Add a log entry to the shipping queue"""
        try:
            self.log_queue.put_nowait(log_entry)
        except Exception:
            # If queue is full, drop the log entry
            pass
    
    def stop(self) -> None:
        """Stop the log shipper"""
        self.stop_event.set()
        if self.batch_buffer:
            self._flush_batch()
        if self.shipping_thread:
            self.shipping_thread.join(timeout=5)

class LogRotationManager:
    """
    Advanced log rotation manager with compression and archiving
    
    Features:
    - Size-based and time-based rotation
    - Automatic compression of old logs
    - Archiving to different storage locations
    - Cleanup policies
    - Rotation callbacks for external integrations
    """
    
    def __init__(self, config: LoggerConfig):
        self.config = config
        self.log_file = Path(config.file_path) if config.file_path else None
        self.compression_enabled = True
        self.archive_location: Optional[Path] = None
        self.cleanup_policy = {
            'max_age_days': 30,
            'max_total_size_mb': 1000,
            'keep_latest_count': 10
        }
        self.rotation_callbacks: List[Callable[[str, str], None]] = []
        
        # Rotation tracking
        self.last_rotation_time = time.time()
        self.current_file_size = 0
        self._lock = threading.Lock()
        
        if self.log_file:
            self._initialize_rotation()
    
    def _initialize_rotation(self) -> None:
        """Initialize rotation system"""
        try:
            if self.log_file and self.log_file.exists():
                self.current_file_size = self.log_file.stat().st_size
            
            # Create archive directory if needed
            if self.archive_location is None:
                self.archive_location = self.log_file.parent / "archived_logs"
            
            self.archive_location.mkdir(parents=True, exist_ok=True)
            
        except Exception as e:
            print(f"Error initializing log rotation: {e}")
    
    def set_compression_enabled(self, enabled: bool) -> None:
        """Enable or disable compression of rotated logs"""
        self.compression_enabled = enabled
    
    def set_archive_location(self, location: Union[str, Path]) -> None:
        """Set custom archive location for rotated logs"""
        self.archive_location = Path(location)
        self.archive_location.mkdir(parents=True, exist_ok=True)
    
    def set_cleanup_policy(self, max_age_days: int = 30, 
                          max_total_size_mb: int = 1000,
                          keep_latest_count: int = 10) -> None:
        """Configure cleanup policy for archived logs"""
        self.cleanup_policy = {
            'max_age_days': max_age_days,
            'max_total_size_mb': max_total_size_mb,
            'keep_latest_count': keep_latest_count
        }
    
    def add_rotation_callback(self, callback: Callable[[str, str], None]) -> None:
        """Add callback to be called when rotation occurs"""
        self.rotation_callbacks.append(callback)
    
    def remove_rotation_callback(self, callback: Callable[[str, str], None]) -> None:
        """Remove rotation callback"""
        if callback in self.rotation_callbacks:
            self.rotation_callbacks.remove(callback)
    
    def should_rotate_by_size(self) -> bool:
        """Check if rotation is needed based on file size"""
        if not self.log_file or not self.log_file.exists():
            return False
        
        current_size = self.log_file.stat().st_size
        return current_size >= self.config.max_file_size
    
    def should_rotate_by_time(self) -> bool:
        """Check if rotation is needed based on time interval"""
        if not self.config.rotation_interval:
            return False
        
        current_time = time.time()
        
        if self.config.rotation_interval == 'daily':
            # Check if it's a new day
            last_date = datetime.fromtimestamp(self.last_rotation_time).date()
            current_date = datetime.fromtimestamp(current_time).date()
            return current_date > last_date
        
        elif self.config.rotation_interval == 'weekly':
            # Check if a week has passed
            week_seconds = 7 * 24 * 3600
            return (current_time - self.last_rotation_time) >= week_seconds
        
        elif self.config.rotation_interval == 'monthly':
            # Check if a month has passed (approximate)
            month_seconds = 30 * 24 * 3600
            return (current_time - self.last_rotation_time) >= month_seconds
        
        return False
    
    def rotate_log(self, force: bool = False) -> bool:
        """
        Perform log rotation
        
        Args:
            force: Force rotation even if conditions are not met
            
        Returns:
            True if rotation was performed
        """
        with self._lock:
            try:
                if not self.log_file or not self.log_file.exists():
                    return False
                
                # Check if rotation is needed
                if not force and not self.should_rotate_by_size() and not self.should_rotate_by_time():
                    return False
                
                # Generate rotation filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                rotation_filename = f"{self.log_file.stem}_{timestamp}.log"
                
                if self.compression_enabled:
                    rotation_filename += ".gz"
                
                rotation_path = self.archive_location / rotation_filename
                
                # Perform the rotation
                if self.compression_enabled:
                    self._compress_and_move(self.log_file, rotation_path)
                else:
                    shutil.move(str(self.log_file), str(rotation_path))
                
                # Update tracking
                self.last_rotation_time = time.time()
                self.current_file_size = 0
                
                # Call rotation callbacks
                for callback in self.rotation_callbacks:
                    try:
                        callback(str(self.log_file), str(rotation_path))
                    except Exception as e:
                        print(f"Rotation callback error: {e}")
                
                # Perform cleanup
                self._cleanup_old_logs()
                
                return True
                
            except Exception as e:
                print(f"Error during log rotation: {e}")
                return False
    
    def _compress_and_move(self, source: Path, destination: Path) -> None:
        """Compress log file and move to destination"""
        try:
            with open(source, 'rb') as f_in:
                with gzip.open(destination, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove original file after successful compression
            source.unlink()
            
        except Exception as e:
            raise Exception(f"Failed to compress and move log file: {e}")
    
    def _cleanup_old_logs(self) -> None:
        """Clean up old log files based on cleanup policy"""
        try:
            if not self.archive_location or not self.archive_location.exists():
                return
            
            # Get all archived log files
            log_files = []
            for pattern in ["*.log", "*.log.gz"]:
                log_files.extend(self.archive_location.glob(pattern))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            current_time = time.time()
            total_size = 0
            files_to_delete = []
            
            for i, log_file in enumerate(log_files):
                file_stat = log_file.stat()
                file_age_days = (current_time - file_stat.st_mtime) / (24 * 3600)
                file_size_mb = file_stat.st_size / (1024 * 1024)
                
                # Check cleanup conditions
                should_delete = False
                
                # Age-based cleanup
                if file_age_days > self.cleanup_policy['max_age_days']:
                    should_delete = True
                
                # Count-based cleanup (keep only latest N files)
                if i >= self.cleanup_policy['keep_latest_count']:
                    should_delete = True
                
                # Size-based cleanup
                total_size += file_size_mb
                if total_size > self.cleanup_policy['max_total_size_mb']:
                    should_delete = True
                
                if should_delete:
                    files_to_delete.append(log_file)
            
            # Delete files
            for file_to_delete in files_to_delete:
                try:
                    file_to_delete.unlink()
                except Exception as e:
                    print(f"Error deleting old log file {file_to_delete}: {e}")
                    
        except Exception as e:
            print(f"Error during log cleanup: {e}")
    
    def get_rotation_status(self) -> Dict[str, Any]:
        """Get current rotation status and statistics"""
        status = {
            'log_file': str(self.log_file) if self.log_file else None,
            'current_size_mb': 0,
            'max_size_mb': self.config.max_file_size / (1024 * 1024),
            'last_rotation': datetime.fromtimestamp(self.last_rotation_time).isoformat(),
            'rotation_interval': self.config.rotation_interval,
            'compression_enabled': self.compression_enabled,
            'archive_location': str(self.archive_location) if self.archive_location else None,
            'cleanup_policy': self.cleanup_policy.copy(),
            'should_rotate_by_size': False,
            'should_rotate_by_time': False,
            'archived_files': []
        }
        
        try:
            if self.log_file and self.log_file.exists():
                current_size = self.log_file.stat().st_size
                status['current_size_mb'] = current_size / (1024 * 1024)
                status['should_rotate_by_size'] = self.should_rotate_by_size()
                status['should_rotate_by_time'] = self.should_rotate_by_time()
            
            # Get archived files info
            if self.archive_location and self.archive_location.exists():
                archived_files = []
                for pattern in ["*.log", "*.log.gz"]:
                    for log_file in self.archive_location.glob(pattern):
                        file_stat = log_file.stat()
                        archived_files.append({
                            'name': log_file.name,
                            'size_mb': file_stat.st_size / (1024 * 1024),
                            'created': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                            'compressed': log_file.suffix == '.gz'
                        })
                
                # Sort by creation time (newest first)
                archived_files.sort(key=lambda x: x['created'], reverse=True)
                status['archived_files'] = archived_files
                
        except Exception as e:
            status['error'] = str(e)
        
        return status
    
    def force_rotation(self) -> bool:
        """Force immediate log rotation"""
        return self.rotate_log(force=True)
    
    def estimate_rotation_time(self) -> Optional[datetime]:
        """Estimate when the next rotation will occur"""
        try:
            if not self.log_file or not self.log_file.exists():
                return None
            
            # Time-based estimation
            if self.config.rotation_interval:
                if self.config.rotation_interval == 'daily':
                    # Next midnight
                    tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    return tomorrow
                elif self.config.rotation_interval == 'weekly':
                    # Next Monday
                    days_ahead = 6 - datetime.now().weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    next_week = datetime.now() + timedelta(days=days_ahead)
                    return next_week.replace(hour=0, minute=0, second=0, microsecond=0)
                elif self.config.rotation_interval == 'monthly':
                    # Next month (approximate)
                    next_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if next_month.month == 12:
                        next_month = next_month.replace(year=next_month.year + 1, month=1)
                    else:
                        next_month = next_month.replace(month=next_month.month + 1)
                    return next_month
            
            # Size-based estimation (rough)
            if self.config.max_file_size > 0:
                current_size = self.log_file.stat().st_size
                remaining_size = self.config.max_file_size - current_size
                
                if remaining_size > 0:
                    # Estimate based on recent growth rate
                    # This is a very rough estimation
                    estimated_hours = remaining_size / (1024 * 100)  # Assume 100KB/hour growth
                    return datetime.now() + timedelta(hours=estimated_hours)
            
            return None
            
        except Exception:
            return None

class LogArchiver:
    """
    Advanced log archiving system for long-term storage
    
    Features:
    - Multiple storage backends (local, cloud)
    - Automatic archiving policies
    - Metadata tracking
    - Search and retrieval capabilities
    """
    
    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.base_path / "archive_metadata.json"
        self.metadata = self._load_metadata()
        
        # Archiving policies
        self.policies = {
            'compress_after_days': 7,
            'move_to_cold_storage_after_days': 30,
            'delete_after_days': 365
        }
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load archive metadata"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}
    
    def _save_metadata(self) -> None:
        """Save archive metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving archive metadata: {e}")
    
    def archive_log(self, log_file: Path, preserve_original: bool = False) -> bool:
        """Archive a log file with metadata"""
        try:
            if not log_file.exists():
                return False
            
            # Generate archive filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{log_file.stem}_{timestamp}.log"
            
            # Create date-based subdirectory
            date_dir = self.base_path / datetime.now().strftime("%Y/%m")
            date_dir.mkdir(parents=True, exist_ok=True)
            
            archive_path = date_dir / archive_name
            
            # Copy or move the file
            if preserve_original:
                shutil.copy2(log_file, archive_path)
            else:
                shutil.move(str(log_file), str(archive_path))
            
            # Update metadata
            file_info = {
                'original_path': str(log_file),
                'archive_path': str(archive_path),
                'archived_at': datetime.now().isoformat(),
                'size_bytes': archive_path.stat().st_size,
                'compressed': False,
                'tags': []
            }
            
            self.metadata[archive_name] = file_info
            self._save_metadata()
            
            return True
            
        except Exception as e:
            print(f"Error archiving log file: {e}")
            return False
    
    def compress_archived_logs(self, older_than_days: int = 7) -> int:
        """Compress archived logs older than specified days"""
        compressed_count = 0
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        try:
            for archive_name, info in self.metadata.items():
                if info.get('compressed', False):
                    continue
                
                archived_at = datetime.fromisoformat(info['archived_at'])
                if archived_at < cutoff_date:
                    archive_path = Path(info['archive_path'])
                    
                    if archive_path.exists():
                        compressed_path = archive_path.with_suffix('.log.gz')
                        
                        try:
                            with open(archive_path, 'rb') as f_in:
                                with gzip.open(compressed_path, 'wb') as f_out:
                                    shutil.copyfileobj(f_in, f_out)
                            
                            # Remove original and update metadata
                            archive_path.unlink()
                            info['archive_path'] = str(compressed_path)
                            info['compressed'] = True
                            info['size_bytes'] = compressed_path.stat().st_size
                            
                            compressed_count += 1
                            
                        except Exception as e:
                            print(f"Error compressing {archive_path}: {e}")
            
            if compressed_count > 0:
                self._save_metadata()
                
        except Exception as e:
            print(f"Error during compression: {e}")
        
        return compressed_count
    
    def search_logs(self, start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   tags: Optional[List[str]] = None,
                   min_size: Optional[int] = None,
                   max_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search archived logs based on criteria"""
        results = []
        
        try:
            for archive_name, info in self.metadata.items():
                archived_at = datetime.fromisoformat(info['archived_at'])
                
                # Date filtering
                if start_date and archived_at < start_date:
                    continue
                if end_date and archived_at > end_date:
                    continue
                
                # Size filtering
                size_bytes = info.get('size_bytes', 0)
                if min_size and size_bytes < min_size:
                    continue
                if max_size and size_bytes > max_size:
                    continue
                
                # Tag filtering
                if tags:
                    info_tags = info.get('tags', [])
                    if not any(tag in info_tags for tag in tags):
                        continue
                
                results.append({
                    'name': archive_name,
                    **info
                })
            
            # Sort by archived date (newest first)
            results.sort(key=lambda x: x['archived_at'], reverse=True)
            
        except Exception as e:
            print(f"Error searching logs: {e}")
        
        return results
    
    def get_archive_statistics(self) -> Dict[str, Any]:
        """Get archive statistics"""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'compressed_files': 0,
            'uncompressed_files': 0,
            'oldest_archive': None,
            'newest_archive': None,
            'size_by_month': {},
            'compression_ratio': 0.0
        }
        
        try:
            total_original_size = 0
            total_compressed_size = 0
            archive_dates = []
            
            for archive_name, info in self.metadata.items():
                stats['total_files'] += 1
                size_mb = info.get('size_bytes', 0) / (1024 * 1024)
                stats['total_size_mb'] += size_mb
                
                if info.get('compressed', False):
                    stats['compressed_files'] += 1
                    total_compressed_size += info.get('size_bytes', 0)
                else:
                    stats['uncompressed_files'] += 1
                
                # Track by month
                archived_at = datetime.fromisoformat(info['archived_at'])
                month_key = archived_at.strftime("%Y-%m")
                if month_key not in stats['size_by_month']:
                    stats['size_by_month'][month_key] = 0
                stats['size_by_month'][month_key] += size_mb
                
                archive_dates.append(archived_at)
            
            # Date range
            if archive_dates:
                stats['oldest_archive'] = min(archive_dates).isoformat()
                stats['newest_archive'] = max(archive_dates).isoformat()
            
            # Compression ratio (rough estimate)
            if total_compressed_size > 0:
                # Assume original files were 3x larger before compression
                estimated_original_size = total_compressed_size * 3
                stats['compression_ratio'] = (estimated_original_size - total_compressed_size) / estimated_original_size
            
        except Exception as e:
            stats['error'] = str(e)
        
        return stats

class CustomLogger:
    """
    Main custom logger class with advanced features
    
    Features:
    - Configurable log levels and formatting
    - Context-based logging
    - Sensitive data masking
    - Log rotation and archiving
    - Log shipping to centralized services
    - Performance tracking
    """
    
    def __init__(self, config: LoggerConfig):
        self.config = config
        self.logger = logging.getLogger(config.name)
        self.logger.setLevel(config.level.value)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Initialize components
        self.masker = SensitiveDataMasker()
        self.context_manager = ContextManager()
        self.log_shipper = None
        self.rotation_manager = None
        
        # Setup handlers
        self._setup_handlers()
        
        # Setup log rotation
        if config.file_path:
            self.rotation_manager = LogRotationManager(config)
        
        # Setup log shipping if enabled
        if config.enable_shipping and config.shipping_endpoint:
            self.log_shipper = LogShipper(
                config.shipping_endpoint,
                config.shipping_api_key
            )
        
        # Performance tracking
        self.performance_metrics: Dict[str, List[float]] = {}
        self._metrics_lock = threading.Lock()
    
    def _setup_handlers(self) -> None:
        """Setup log handlers based on configuration"""
        formatter = CustomFormatter(
            format_type=self.config.format_type,
            enable_context=self.config.enable_context,
            enable_masking=self.config.enable_masking,
            masker=self.masker
        )
        
        # Console handler
        if self.config.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler with custom rotation handler
        if self.config.file_path:
            # Ensure log directory exists
            log_dir = Path(self.config.file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Use a simple file handler since we manage rotation manually
            file_handler = logging.FileHandler(self.config.file_path)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _log_with_context(self, level: int, message: str, *args, **kwargs) -> None:
        """Internal method to log with context, shipping, and rotation check"""
        # Check for rotation before logging
        if self.rotation_manager:
            try:
                if self.rotation_manager.should_rotate_by_size() or self.rotation_manager.should_rotate_by_time():
                    # Close current file handlers
                    file_handlers = [h for h in self.logger.handlers if isinstance(h, logging.FileHandler)]
                    for handler in file_handlers:
                        handler.close()
                        self.logger.removeHandler(handler)
                    
                    # Perform rotation
                    self.rotation_manager.rotate_log()
                    
                    # Re-add file handler
                    formatter = CustomFormatter(
                        format_type=self.config.format_type,
                        enable_context=self.config.enable_context,
                        enable_masking=self.config.enable_masking,
                        masker=self.masker
                    )
                    file_handler = logging.FileHandler(self.config.file_path)
                    file_handler.setFormatter(formatter)
                    self.logger.addHandler(file_handler)
                    
            except Exception as e:
                # Log rotation should not prevent logging
                print(f"Error during log rotation: {e}")
        
        # Create log record
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, args, None, **kwargs
        )
        
        # Handle the record
        self.logger.handle(record)
        
        # Ship to centralized service if enabled
        if self.log_shipper:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "context": self.context_manager.get_context()
            }
            self.log_shipper.ship_log(log_entry)
    
    # Standard logging methods
    def trace(self, message: str, *args, **kwargs) -> None:
        """Log trace level message"""
        self._log_with_context(LogLevel.TRACE.value, message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug level message"""
        self._log_with_context(LogLevel.DEBUG.value, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """Log info level message"""
        self._log_with_context(LogLevel.INFO.value, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning level message"""
        self._log_with_context(LogLevel.WARNING.value, message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """Log error level message"""
        self._log_with_context(LogLevel.ERROR.value, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical level message"""
        self._log_with_context(LogLevel.CRITICAL.value, message, *args, **kwargs)
    
    def fatal(self, message: str, *args, **kwargs) -> None:
        """Log fatal level message"""
        self._log_with_context(LogLevel.FATAL.value, message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with traceback"""
        kwargs['exc_info'] = True
        self.error(message, *args, **kwargs)
    
    # Context management methods
    def set_context(self, **kwargs) -> None:
        """Set logging context for current request/thread"""
        self.context_manager.set_request_context(**kwargs)
    
    def clear_context(self) -> None:
        """Clear current request context"""
        self.context_manager.clear_request_context()
    
    def start_request(self, request_id: Optional[str] = None, **kwargs) -> str:
        """Start a new request context"""
        return self.context_manager.start_request(request_id, **kwargs)
    
    def end_request(self) -> Optional[float]:
        """End request context and return duration"""
        return self.context_manager.end_request()
    
    # Performance tracking methods
    def track_performance(self, operation: str, duration: float) -> None:
        """Track performance metrics for an operation"""
        with self._metrics_lock:
            if operation not in self.performance_metrics:
                self.performance_metrics[operation] = []
            self.performance_metrics[operation].append(duration)
    
    def get_performance_stats(self, operation: str) -> Dict[str, float]:
        """Get performance statistics for an operation"""
        with self._metrics_lock:
            durations = self.performance_metrics.get(operation, [])
            
            if not durations:
                return {}
            
            return {
                "count": len(durations),
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "total": sum(durations)
            }
    
    def log_performance(self, operation: str, duration: float, 
                       threshold: Optional[float] = None) -> None:
        """Log performance information"""
        self.track_performance(operation, duration)
        
        if threshold and duration > threshold:
            self.warning(f"Performance alert: {operation} took {duration:.3f}s (threshold: {threshold:.3f}s)")
        else:
            self.debug(f"Performance: {operation} completed in {duration:.3f}s")
    
    # Utility methods
    def add_masking_pattern(self, name: str, pattern: re.Pattern, 
                           mask_function: Callable[[str], str]) -> None:
        """Add custom sensitive data masking pattern"""
        self.masker.add_pattern(name, pattern, mask_function)
    
    def set_level(self, level: LogLevel) -> None:
        """Change the logging level"""
        self.logger.setLevel(level.value)
        self.config.level = level
    
    def get_config(self) -> LoggerConfig:
        """Get current logger configuration"""
        return self.config
    
    # Log rotation methods
    def configure_rotation(self, max_age_days: int = 30, 
                          max_total_size_mb: int = 1000,
                          keep_latest_count: int = 10,
                          compression_enabled: bool = True,
                          archive_location: Optional[str] = None) -> None:
        """Configure log rotation settings"""
        if self.rotation_manager:
            self.rotation_manager.set_cleanup_policy(
                max_age_days, max_total_size_mb, keep_latest_count
            )
            self.rotation_manager.set_compression_enabled(compression_enabled)
            
            if archive_location:
                self.rotation_manager.set_archive_location(archive_location)
    
    def add_rotation_callback(self, callback: Callable[[str, str], None]) -> None:
        """Add callback to be called when log rotation occurs"""
        if self.rotation_manager:
            self.rotation_manager.add_rotation_callback(callback)
    
    def remove_rotation_callback(self, callback: Callable[[str, str], None]) -> None:
        """Remove log rotation callback"""
        if self.rotation_manager:
            self.rotation_manager.remove_rotation_callback(callback)
    
    def force_rotation(self) -> bool:
        """Force immediate log rotation"""
        if self.rotation_manager:
            return self.rotation_manager.force_rotation()
        return False
    
    def get_rotation_status(self) -> Optional[Dict[str, Any]]:
        """Get current log rotation status"""
        if self.rotation_manager:
            return self.rotation_manager.get_rotation_status()
        return None
    
    def estimate_next_rotation(self) -> Optional[datetime]:
        """Estimate when the next log rotation will occur"""
        if self.rotation_manager:
            return self.rotation_manager.estimate_rotation_time()
        return None
    
    def cleanup_old_logs(self) -> None:
        """Manually trigger cleanup of old log files"""
        if self.rotation_manager:
            self.rotation_manager._cleanup_old_logs()
    
    def shutdown(self) -> None:
        """Shutdown the logger and clean up resources"""
        if self.log_shipper:
            self.log_shipper.stop()
        
        # Close all handlers
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

# Context managers for convenient usage
class LoggingContext:
    """Context manager for setting temporary logging context"""
    
    def __init__(self, logger: CustomLogger, **context):
        self.logger = logger
        self.context = context
        self.old_context = None
    
    def __enter__(self):
        self.old_context = log_context.get({})
        new_context = self.old_context.copy()
        new_context.update(self.context)
        log_context.set(new_context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        log_context.set(self.old_context)

class PerformanceTimer:
    """Context manager for tracking operation performance"""
    
    def __init__(self, logger: CustomLogger, operation: str, 
                 threshold: Optional[float] = None):
        self.logger = logger
        self.operation = operation
        self.threshold = threshold
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.logger.log_performance(self.operation, duration, self.threshold)

# Default logger instance
_default_logger: Optional[CustomLogger] = None

def get_logger(name: Optional[str] = None, config: Optional[LoggerConfig] = None) -> CustomLogger:
    """Get a logger instance (singleton pattern for default logger)"""
    global _default_logger
    
    if name is None and config is None:
        # Return default logger
        if _default_logger is None:
            default_config = LoggerConfig()
            _default_logger = CustomLogger(default_config)
        return _default_logger
    
    # Return new logger instance
    if config is None:
        config = LoggerConfig(name=name or "GoogleAccountCreator")
    return CustomLogger(config)

def configure_default_logger(config: LoggerConfig) -> CustomLogger:
    """Configure the default logger with custom settings"""
    global _default_logger
    
    if _default_logger:
        _default_logger.shutdown()
    
    _default_logger = CustomLogger(config)
    return _default_logger

def shutdown_logging() -> None:
    """Shutdown all logging and clean up resources"""
    global _default_logger
    
    if _default_logger:
        _default_logger.shutdown()
        _default_logger = None

# Convenience functions for quick logging
def trace(message: str, *args, **kwargs) -> None:
    """Quick trace logging"""
    get_logger().trace(message, *args, **kwargs)

def debug(message: str, *args, **kwargs) -> None:
    """Quick debug logging"""
    get_logger().debug(message, *args, **kwargs)

def info(message: str, *args, **kwargs) -> None:
    """Quick info logging"""
    get_logger().info(message, *args, **kwargs)

def warning(message: str, *args, **kwargs) -> None:
    """Quick warning logging"""
    get_logger().warning(message, *args, **kwargs)

def error(message: str, *args, **kwargs) -> None:
    """Quick error logging"""
    get_logger().error(message, *args, **kwargs)

def critical(message: str, *args, **kwargs) -> None:
    """Quick critical logging"""
    get_logger().critical(message, *args, **kwargs)

def exception(message: str, *args, **kwargs) -> None:
    """Quick exception logging with traceback"""
    get_logger().exception(message, *args, **kwargs) 