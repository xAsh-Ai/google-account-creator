#!/usr/bin/env python3
"""
Comprehensive Logging System Demo

This script demonstrates all features of the custom logging system including:
- Custom logger configuration
- Different log levels and formats
- Context-based logging
- Sensitive data masking
- Log rotation and archiving
- Performance tracking
- Log shipping
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.logger import (
    CustomLogger, LoggerConfig, LogLevel, LogFormat,
    LoggingContext, PerformanceTimer, LogArchiver,
    get_logger, configure_default_logger
)

def demo_basic_logging():
    """Demonstrate basic logging functionality"""
    print("\n" + "="*60)
    print("DEMO 1: Basic Logging Functionality")
    print("="*60)
    
    # Create logger with basic configuration
    config = LoggerConfig(
        name="BasicDemo",
        level=LogLevel.DEBUG,
        format_type=LogFormat.TEXT,
        file_path="logs/basic_demo.log",
        console_output=True
    )
    
    logger = CustomLogger(config)
    
    print("\n1. Testing different log levels:")
    logger.trace("This is a trace message")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    logger.fatal("This is a fatal message")
    
    print("\n2. Testing exception logging:")
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("An error occurred during division")
    
    logger.shutdown()

def demo_log_formats():
    """Demonstrate different log formats"""
    print("\n" + "="*60)
    print("DEMO 2: Different Log Formats")
    print("="*60)
    
    formats = [LogFormat.TEXT, LogFormat.JSON, LogFormat.STRUCTURED]
    
    for fmt in formats:
        print(f"\n--- {fmt.value.upper()} Format ---")
        
        config = LoggerConfig(
            name=f"{fmt.value}Demo",
            level=LogLevel.INFO,
            format_type=fmt,
            file_path=f"logs/{fmt.value}_demo.log",
            console_output=True
        )
        
        logger = CustomLogger(config)
        logger.info(f"This is a sample message in {fmt.value} format")
        logger.warning("This is a warning with some data", extra={"user_id": 12345, "action": "login"})
        logger.shutdown()

def demo_context_logging():
    """Demonstrate context-based logging"""
    print("\n" + "="*60)
    print("DEMO 3: Context-Based Logging")
    print("="*60)
    
    config = LoggerConfig(
        name="ContextDemo",
        level=LogLevel.INFO,
        format_type=LogFormat.JSON,
        file_path="logs/context_demo.log",
        console_output=True,
        enable_context=True
    )
    
    logger = CustomLogger(config)
    
    print("\n1. Request-based context:")
    request_id = logger.start_request(user_id="user123", session_id="sess456")
    logger.info(f"Started processing request {request_id}")
    
    # Simulate some processing
    time.sleep(0.1)
    logger.info("Processing step 1 completed")
    logger.info("Processing step 2 completed")
    
    duration = logger.end_request()
    logger.info(f"Request completed in {duration:.3f} seconds")
    
    print("\n2. Custom context:")
    with LoggingContext(logger, operation="account_creation", batch_id="batch789"):
        logger.info("Starting account creation batch")
        logger.info("Creating account 1")
        logger.info("Creating account 2")
        logger.info("Batch creation completed")
    
    logger.shutdown()

def demo_sensitive_data_masking():
    """Demonstrate sensitive data masking"""
    print("\n" + "="*60)
    print("DEMO 4: Sensitive Data Masking")
    print("="*60)
    
    config = LoggerConfig(
        name="MaskingDemo",
        level=LogLevel.INFO,
        format_type=LogFormat.TEXT,
        file_path="logs/masking_demo.log",
        console_output=True,
        enable_masking=True
    )
    
    logger = CustomLogger(config)
    
    print("\n1. Default masking patterns:")
    logger.info("User email: john.doe@example.com")
    logger.info("Password: password=secret123")
    logger.info("API Key: api_key=sk-1234567890abcdef1234567890abcdef")
    logger.info("Phone: Call me at (555) 123-4567")
    logger.info("Credit Card: 4111-1111-1111-1111")
    logger.info("IP Address: Connecting from 192.168.1.100")
    logger.info("URL with auth: https://user:pass@api.example.com/data")
    
    print("\n2. Custom masking pattern:")
    import re
    # Add custom pattern for order IDs
    order_pattern = re.compile(r'ORDER-\d{8}')
    def mask_order_id(match):
        order_id = match.group()
        return f"ORDER-****{order_id[-4:]}"
    
    logger.add_masking_pattern("order_id", order_pattern, mask_order_id)
    logger.info("Processing order ORDER-12345678")
    
    logger.shutdown()

def demo_performance_tracking():
    """Demonstrate performance tracking"""
    print("\n" + "="*60)
    print("DEMO 5: Performance Tracking")
    print("="*60)
    
    config = LoggerConfig(
        name="PerformanceDemo",
        level=LogLevel.DEBUG,
        format_type=LogFormat.TEXT,
        file_path="logs/performance_demo.log",
        console_output=True
    )
    
    logger = CustomLogger(config)
    
    print("\n1. Using PerformanceTimer context manager:")
    with PerformanceTimer(logger, "database_query", threshold=0.1):
        time.sleep(0.05)  # Simulate fast query
    
    with PerformanceTimer(logger, "database_query", threshold=0.1):
        time.sleep(0.15)  # Simulate slow query (will trigger warning)
    
    print("\n2. Manual performance tracking:")
    start_time = time.time()
    time.sleep(0.08)
    duration = time.time() - start_time
    logger.log_performance("api_call", duration, threshold=0.1)
    
    # Track multiple operations
    for i in range(5):
        start_time = time.time()
        time.sleep(0.02 + i * 0.01)  # Varying durations
        duration = time.time() - start_time
        logger.track_performance("file_processing", duration)
    
    # Get performance statistics
    stats = logger.get_performance_stats("file_processing")
    logger.info(f"File processing stats: {stats}")
    
    logger.shutdown()

def demo_log_rotation():
    """Demonstrate log rotation"""
    print("\n" + "="*60)
    print("DEMO 6: Log Rotation")
    print("="*60)
    
    config = LoggerConfig(
        name="RotationDemo",
        level=LogLevel.INFO,
        format_type=LogFormat.TEXT,
        file_path="logs/rotation_demo.log",
        console_output=True,
        max_file_size=1024,  # 1KB for quick rotation
        backup_count=3
    )
    
    logger = CustomLogger(config)
    
    print("\n1. Configuring rotation:")
    logger.configure_rotation(
        max_age_days=1,
        max_total_size_mb=1,
        keep_latest_count=5,
        compression_enabled=True
    )
    
    # Add rotation callback
    def rotation_callback(old_file, new_file):
        print(f"Log rotated: {old_file} -> {new_file}")
    
    logger.add_rotation_callback(rotation_callback)
    
    print("\n2. Generating logs to trigger rotation:")
    for i in range(50):
        logger.info(f"This is log message number {i+1} with some additional content to increase file size")
    
    print("\n3. Rotation status:")
    status = logger.get_rotation_status()
    if status:
        print(f"Current size: {status['current_size_mb']:.3f} MB")
        print(f"Max size: {status['max_size_mb']:.3f} MB")
        print(f"Archived files: {len(status['archived_files'])}")
        
        for archived in status['archived_files'][:3]:  # Show first 3
            print(f"  - {archived['name']} ({archived['size_mb']:.3f} MB)")
    
    print("\n4. Force rotation:")
    if logger.force_rotation():
        print("Forced rotation successful")
    else:
        print("Forced rotation failed or not needed")
    
    logger.shutdown()

def demo_log_archiving():
    """Demonstrate log archiving"""
    print("\n" + "="*60)
    print("DEMO 7: Log Archiving")
    print("="*60)
    
    # Create some sample log files to archive
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    sample_files = []
    for i in range(3):
        file_path = logs_dir / f"sample_{i}.log"
        with open(file_path, 'w') as f:
            f.write(f"Sample log content {i}\n" * 100)
        sample_files.append(file_path)
    
    # Create archiver
    archiver = LogArchiver("logs/archived")
    
    print("\n1. Archiving log files:")
    for file_path in sample_files:
        if archiver.archive_log(file_path):
            print(f"Archived: {file_path}")
    
    print("\n2. Archive statistics:")
    stats = archiver.get_archive_statistics()
    print(f"Total files: {stats['total_files']}")
    print(f"Total size: {stats['total_size_mb']:.3f} MB")
    print(f"Compressed files: {stats['compressed_files']}")
    print(f"Uncompressed files: {stats['uncompressed_files']}")
    
    print("\n3. Compressing old archives:")
    compressed_count = archiver.compress_archived_logs(older_than_days=0)  # Compress all
    print(f"Compressed {compressed_count} files")
    
    print("\n4. Searching archives:")
    results = archiver.search_logs(
        start_date=datetime.now() - timedelta(hours=1),
        end_date=datetime.now()
    )
    print(f"Found {len(results)} matching archives")
    for result in results:
        print(f"  - {result['name']} ({result['size_bytes']} bytes)")

def demo_concurrent_logging():
    """Demonstrate thread-safe concurrent logging"""
    print("\n" + "="*60)
    print("DEMO 8: Concurrent Logging")
    print("="*60)
    
    config = LoggerConfig(
        name="ConcurrentDemo",
        level=LogLevel.INFO,
        format_type=LogFormat.JSON,
        file_path="logs/concurrent_demo.log",
        console_output=True,
        enable_context=True
    )
    
    logger = CustomLogger(config)
    
    def worker_thread(worker_id, logger):
        """Worker function for threading demo"""
        with LoggingContext(logger, worker_id=worker_id, thread_name=f"worker-{worker_id}"):
            for i in range(5):
                logger.info(f"Worker {worker_id} processing item {i+1}")
                time.sleep(0.01)  # Simulate work
    
    print("\n1. Starting concurrent logging with multiple threads:")
    threads = []
    for i in range(3):
        thread = threading.Thread(target=worker_thread, args=(i+1, logger))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print("All worker threads completed")
    logger.shutdown()

def demo_default_logger():
    """Demonstrate default logger usage"""
    print("\n" + "="*60)
    print("DEMO 9: Default Logger Usage")
    print("="*60)
    
    # Configure default logger
    config = LoggerConfig(
        name="DefaultLogger",
        level=LogLevel.INFO,
        format_type=LogFormat.TEXT,
        file_path="logs/default.log",
        console_output=True
    )
    
    configure_default_logger(config)
    
    print("\n1. Using convenience functions:")
    from core.logger import info, warning, error, debug
    
    info("This is an info message using convenience function")
    warning("This is a warning message")
    error("This is an error message")
    debug("This debug message won't show (level is INFO)")
    
    print("\n2. Using get_logger():")
    logger = get_logger()
    logger.info("Using the default logger instance")
    logger.set_context(module="demo", operation="test")
    logger.info("Message with context")
    
    # Clean up
    from core.logger import shutdown_logging
    shutdown_logging()

def main():
    """Run all demos"""
    print("Starting Comprehensive Logging System Demo")
    print("This demo will create log files in the 'logs' directory")
    
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    try:
        demo_basic_logging()
        demo_log_formats()
        demo_context_logging()
        demo_sensitive_data_masking()
        demo_performance_tracking()
        demo_log_rotation()
        demo_log_archiving()
        demo_concurrent_logging()
        demo_default_logger()
        
        print("\n" + "="*60)
        print("ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"\nCheck the 'logs' directory for generated log files:")
        print(f"Log directory: {logs_dir.absolute()}")
        
        # List generated files
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            archived_logs = list(logs_dir.glob("**/archived_logs/*"))
            
            print(f"\nGenerated files:")
            for log_file in sorted(log_files):
                size = log_file.stat().st_size if log_file.exists() else 0
                print(f"  - {log_file.name} ({size} bytes)")
            
            if archived_logs:
                print(f"\nArchived files:")
                for archived in sorted(archived_logs)[:5]:  # Show first 5
                    size = archived.stat().st_size if archived.exists() else 0
                    print(f"  - {archived.name} ({size} bytes)")
    
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 