#!/usr/bin/env python3
"""
Configuration Manager Demo Script

This script demonstrates the usage of the Configuration Management System
for the Google Account Creator project.

Features demonstrated:
- Basic configuration management
- Validation and error handling
- File and environment loading
- Encryption for sensitive values
- Configuration export/import
- Validation and integrity checks

Usage:
    python scripts/config_manager_demo.py
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config_manager import (
    ConfigManager, ConfigSource, ConfigFormat,
    ValidationError, ConfigurationError, EncryptionError,
    TypeValidationRule, RangeValidationRule, URLValidationRule
)
from core.logger import get_logger

logger = get_logger("ConfigDemo")

def demo_basic_configuration(config_file: str):
    """Demonstrate basic configuration operations"""
    logger.info("📝 Demo: Basic Configuration Management")
    
    # Initialize configuration manager
    config = ConfigManager(config_file, encryption_key="demo_encryption_key")
    
    # Set various configuration values
    config.set('sms.provider', '5sim')
    config.set('sms.api_key', 'sensitive_api_key_12345')  # This will be encrypted
    config.set('proxy.enabled', True)
    config.set('proxy.http_proxy', 'http://proxy.example.com:8080')
    config.set('account.batch_size', 10)
    config.set('account.max_daily_accounts', 100)
    
    # Retrieve values
    logger.info(f"SMS Provider: {config.get('sms.provider')}")
    logger.info(f"SMS API Key: {config.get('sms.api_key')}")
    logger.info(f"Proxy Enabled: {config.get('proxy.enabled')}")
    logger.info(f"Batch Size: {config.get('account.batch_size')}")
    
    # Show configuration summary
    summary = config.get_config_summary()
    logger.info(f"Configuration Summary: {summary}")
    
    logger.info("✅ Basic configuration demo completed")

def demo_encryption_features(config_file: str):
    """Demonstrate encryption features"""
    logger.info("🔐 Demo: Encryption Features")
    
    # Create config manager with encryption
    config = ConfigManager(config_file, encryption_key="demo_encryption_key")
    
    # Set sensitive values
    sensitive_values = {
        'sms.api_key': 'super_secret_sms_key',
        'database.password': 'ultra_secret_db_password',
        'slack.webhook': 'https://hooks.slack.com/services/SECRET/TOKEN/HERE'
    }
    
    for key, value in sensitive_values.items():
        config.set(key, value)
        logger.info(f"Set encrypted value for {key}")
    
    # Check encryption status
    encryption_status = config.get_encryption_status()
    logger.info(f"Encryption Status: {encryption_status}")
    
    # Validate encryption integrity
    integrity_check = config.validate_encryption_integrity()
    logger.info(f"Integrity Check: {integrity_check}")
    
    # Save configuration with encrypted values
    config.save_to_file(include_sensitive=True)
    
    # Load with new config manager instance to test decryption
    new_config = ConfigManager(config_file, encryption_key="demo_encryption_key")
    new_config.load_from_file()
    
    # Verify values can be retrieved
    for key, expected_value in sensitive_values.items():
        retrieved_value = new_config.get(key)
        if retrieved_value == expected_value:
            logger.info(f"✅ Successfully decrypted {key}")
        else:
            logger.error(f"❌ Failed to decrypt {key}")
    
    logger.info("✅ Encryption features demo completed")

def demo_validation_system(config_file: str):
    """Demonstrate configuration validation"""
    logger.info("🛡️ Demo: Validation System")
    
    config = ConfigManager(config_file, encryption_key="demo_encryption_key")
    
    # Test valid values
    try:
        config.set('account.batch_size', 5)  # Valid integer
        config.set('proxy.enabled', True)   # Valid boolean
        logger.info("✅ Valid values accepted")
    except ValidationError as e:
        logger.error(f"❌ Unexpected validation error: {e}")
    
    # Test invalid values
    try:
        config.set('account.batch_size', "not_a_number")  # Invalid type
        logger.error("❌ Invalid value should have been rejected")
    except ValidationError as e:
        logger.info(f"✅ Invalid value correctly rejected: {e}")
    
    # Check validation status
    is_valid = config.is_configuration_valid()
    logger.info(f"Configuration is valid: {is_valid}")
    
    # Get validation errors
    validation_errors = config.get_validation_errors()
    if validation_errors:
        logger.info(f"Validation errors: {validation_errors}")
    
    logger.info("✅ Validation system demo completed")

def demo_file_operations(config_file: str, temp_dir: str):
    """Demonstrate file loading and saving"""
    logger.info("📁 Demo: File Operations")
    
    config = ConfigManager(config_file, encryption_key="demo_encryption_key")
    
    # Set some test data
    config.set('demo.string_value', 'Hello World')
    config.set('demo.number_value', 42)
    config.set('demo.boolean_value', True)
    config.set('demo.secret_value', 'this_is_secret')
    
    # Test different file formats
    formats = [
        (ConfigFormat.YAML, 'demo_config.yaml'),
        (ConfigFormat.JSON, 'demo_config.json'),
        (ConfigFormat.INI, 'demo_config.ini')
    ]
    
    for file_format, filename in formats:
        file_path = os.path.join(temp_dir, filename)
        
        # Save in this format
        success = config.save_to_file(file_path, file_format, include_sensitive=True)
        if success:
            logger.info(f"✅ Saved configuration as {file_format.value}")
            
            # Create new config and load
            new_config = ConfigManager(file_path, encryption_key="demo_encryption_key")
            load_success = new_config.load_from_file()
            
            if load_success:
                # Verify data integrity
                if new_config.get('demo.string_value') == 'Hello World':
                    logger.info(f"✅ Successfully loaded and verified {file_format.value}")
                else:
                    logger.error(f"❌ Data integrity issue with {file_format.value}")
            else:
                logger.error(f"❌ Failed to load {file_format.value}")
        else:
            logger.error(f"❌ Failed to save {file_format.value}")
    
    # Test encrypted export/import
    export_file = os.path.join(temp_dir, "encrypted_export.json")
    
    # Export encrypted configuration
    export_success = config.export_encrypted_config(export_file)
    if export_success:
        logger.info("✅ Exported encrypted configuration")
        
        # Import into new config manager
        import_config = ConfigManager(encryption_key="demo_encryption_key")
        import_success = import_config.import_encrypted_config(export_file)
        
        if import_success:
            logger.info("✅ Successfully imported encrypted configuration")
            
            # Verify data
            if import_config.get('demo.secret_value') == 'this_is_secret':
                logger.info("✅ Encrypted data correctly imported and decrypted")
            else:
                logger.error("❌ Encrypted data import failed")
        else:
            logger.error("❌ Failed to import encrypted configuration")
    else:
        logger.error("❌ Failed to export encrypted configuration")
    
    logger.info("✅ File operations demo completed")

def main():
    """Run all configuration manager demos"""
    logger.info("🚀 Starting ConfigManager Demo")
    
    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp(prefix="config_demo_")
    config_file = os.path.join(temp_dir, "demo_config.yaml")
    
    try:
        demo_basic_configuration(config_file)
        demo_encryption_features(config_file)
        demo_validation_system(config_file)
        demo_file_operations(config_file, temp_dir)
        
        logger.info("✅ All demos completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"🧹 Cleaned up temporary directory: {temp_dir}")

if __name__ == "__main__":
    main() 