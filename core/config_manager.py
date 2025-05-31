"""
Configuration Management System for Google Account Creator

This module provides a comprehensive configuration management system that handles
loading, validation, encryption, and management of all system settings.

Features:
- Type-safe configuration management with validation
- Support for multiple configuration sources (files, environment variables)
- Encryption for sensitive values
- Default configuration generation
- Hierarchical configuration structure
"""

import os
import json
import yaml
import configparser
from typing import Any, Dict, List, Optional, Union, Type, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging
from enum import Enum
import re
from urllib.parse import urlparse
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from datetime import datetime

# Type definitions
T = TypeVar('T')
ConfigValue = Union[str, int, float, bool, List[Any], Dict[str, Any]]

class ConfigSource(Enum):
    """Configuration source types"""
    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    OVERRIDE = "override"

class ConfigFormat(Enum):
    """Supported configuration file formats"""
    JSON = "json"
    YAML = "yaml"
    INI = "ini"

@dataclass
class ConfigItem:
    """Represents a single configuration item with metadata"""
    key: str
    value: Any
    default_value: Any
    description: str
    data_type: Type
    is_sensitive: bool = False
    is_required: bool = False
    source: ConfigSource = ConfigSource.DEFAULT
    validation_rules: Optional[Dict[str, Any]] = None

@dataclass
class ProxyConfig:
    """Proxy configuration settings"""
    enabled: bool = False
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    socks_proxy: Optional[str] = None
    proxy_list_file: Optional[str] = None
    rotation_interval: int = 300  # seconds
    max_retries: int = 3
    timeout: int = 30

@dataclass
class SMSConfig:
    """SMS verification configuration"""
    provider: str = "5sim"
    api_key: Optional[str] = None
    country_code: str = "US"
    max_wait_time: int = 300  # seconds
    retry_attempts: int = 3
    backup_providers: List[str] = field(default_factory=lambda: ["sms-activate", "textverified"])

@dataclass
class AccountConfig:
    """Account creation configuration"""
    batch_size: int = 5
    creation_delay: int = 30  # seconds between accounts
    max_daily_accounts: int = 50
    use_real_names: bool = False
    name_database_file: str = "data/names.json"
    profile_image_dir: str = "data/profile_images"
    recovery_email_enabled: bool = True

@dataclass
class SecurityConfig:
    """Security and privacy settings"""
    encryption_enabled: bool = True
    log_sensitive_data: bool = False
    secure_delete: bool = True
    session_timeout: int = 3600  # seconds
    max_login_attempts: int = 3
    lockout_duration: int = 900  # seconds

@dataclass
class HealthCheckConfig:
    """Health checker configuration"""
    enabled: bool = True
    check_interval: int = 3600  # seconds
    batch_size: int = 10
    timeout: int = 30
    notification_threshold: float = 0.8  # survival rate threshold
    slack_webhook: Optional[str] = None
    discord_webhook: Optional[str] = None

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "logs/google_account_creator.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_output: bool = True

@dataclass
class SystemConfig:
    """Main system configuration container"""
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    account: AccountConfig = field(default_factory=AccountConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

class ConfigurationError(Exception):
    """Custom exception for configuration-related errors"""
    pass

class ValidationError(ConfigurationError):
    """Exception raised when configuration validation fails"""
    pass

class EncryptionError(ConfigurationError):
    """Exception raised when encryption/decryption fails"""
    pass

class ValidationRule:
    """Base class for validation rules"""
    
    def validate(self, value: Any) -> bool:
        """Validate a value. Should be overridden by subclasses."""
        raise NotImplementedError
    
    def get_error_message(self) -> str:
        """Get error message for validation failure"""
        return "Validation failed"

class TypeValidationRule(ValidationRule):
    """Validates data type"""
    
    def __init__(self, expected_type: Type):
        self.expected_type = expected_type
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True  # None is valid for optional fields
        return isinstance(value, self.expected_type)
    
    def get_error_message(self) -> str:
        return f"Value must be of type {self.expected_type.__name__}"

class RangeValidationRule(ValidationRule):
    """Validates numeric ranges"""
    
    def __init__(self, min_value: Optional[Union[int, float]] = None, 
                 max_value: Optional[Union[int, float]] = None):
        self.min_value = min_value
        self.max_value = max_value
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        if not isinstance(value, (int, float)):
            return False
        
        if self.min_value is not None and value < self.min_value:
            return False
        
        if self.max_value is not None and value > self.max_value:
            return False
        
        return True
    
    def get_error_message(self) -> str:
        if self.min_value is not None and self.max_value is not None:
            return f"Value must be between {self.min_value} and {self.max_value}"
        elif self.min_value is not None:
            return f"Value must be at least {self.min_value}"
        elif self.max_value is not None:
            return f"Value must be at most {self.max_value}"
        return "Value out of range"

class RegexValidationRule(ValidationRule):
    """Validates string patterns using regex"""
    
    def __init__(self, pattern: str, description: str = ""):
        self.pattern = re.compile(pattern)
        self.description = description
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        if not isinstance(value, str):
            return False
        
        return bool(self.pattern.match(value))
    
    def get_error_message(self) -> str:
        return f"Value must match pattern: {self.description or self.pattern.pattern}"

class ChoiceValidationRule(ValidationRule):
    """Validates that value is one of allowed choices"""
    
    def __init__(self, choices: List[Any]):
        self.choices = choices
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        return value in self.choices
    
    def get_error_message(self) -> str:
        return f"Value must be one of: {', '.join(map(str, self.choices))}"

class URLValidationRule(ValidationRule):
    """Validates URL format"""
    
    def __init__(self, schemes: Optional[List[str]] = None):
        self.schemes = schemes or ['http', 'https']
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        if not isinstance(value, str):
            return False
        
        try:
            parsed = urlparse(value)
            return parsed.scheme in self.schemes and bool(parsed.netloc)
        except Exception:
            return False
    
    def get_error_message(self) -> str:
        return f"Value must be a valid URL with scheme: {', '.join(self.schemes)}"

class FilePathValidationRule(ValidationRule):
    """Validates file path format and existence"""
    
    def __init__(self, must_exist: bool = False, must_be_file: bool = True):
        self.must_exist = must_exist
        self.must_be_file = must_be_file
    
    def validate(self, value: Any) -> bool:
        if value is None:
            return True
        
        if not isinstance(value, str):
            return False
        
        path = Path(value)
        
        if self.must_exist:
            if not path.exists():
                return False
            
            if self.must_be_file and not path.is_file():
                return False
        
        return True
    
    def get_error_message(self) -> str:
        if self.must_exist:
            if self.must_be_file:
                return "Path must exist and be a file"
            else:
                return "Path must exist"
        return "Invalid file path format"

class ConfigValidator:
    """Configuration validator that applies validation rules"""
    
    def __init__(self):
        self.rules: Dict[str, List[ValidationRule]] = {}
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default validation rules for known configuration keys"""
        
        # Proxy settings
        self.add_rule("proxy.enabled", TypeValidationRule(bool))
        self.add_rule("proxy.http_proxy", URLValidationRule(['http', 'https']))
        self.add_rule("proxy.https_proxy", URLValidationRule(['http', 'https']))
        self.add_rule("proxy.socks_proxy", URLValidationRule(['socks4', 'socks5']))
        self.add_rule("proxy.rotation_interval", TypeValidationRule(int))
        self.add_rule("proxy.rotation_interval", RangeValidationRule(min_value=1, max_value=86400))
        self.add_rule("proxy.max_retries", TypeValidationRule(int))
        self.add_rule("proxy.max_retries", RangeValidationRule(min_value=1, max_value=10))
        self.add_rule("proxy.timeout", TypeValidationRule(int))
        self.add_rule("proxy.timeout", RangeValidationRule(min_value=1, max_value=300))
        
        # SMS settings
        self.add_rule("sms.provider", TypeValidationRule(str))
        self.add_rule("sms.provider", ChoiceValidationRule(["5sim", "sms-activate", "textverified"]))
        self.add_rule("sms.api_key", TypeValidationRule(str))
        self.add_rule("sms.country_code", TypeValidationRule(str))
        self.add_rule("sms.country_code", RegexValidationRule(r'^[A-Z]{2}$', "Two-letter country code"))
        self.add_rule("sms.max_wait_time", TypeValidationRule(int))
        self.add_rule("sms.max_wait_time", RangeValidationRule(min_value=30, max_value=1800))
        self.add_rule("sms.retry_attempts", TypeValidationRule(int))
        self.add_rule("sms.retry_attempts", RangeValidationRule(min_value=1, max_value=10))
        
        # Account settings
        self.add_rule("account.batch_size", TypeValidationRule(int))
        self.add_rule("account.batch_size", RangeValidationRule(min_value=1, max_value=100))
        self.add_rule("account.creation_delay", TypeValidationRule(int))
        self.add_rule("account.creation_delay", RangeValidationRule(min_value=1, max_value=3600))
        self.add_rule("account.max_daily_accounts", TypeValidationRule(int))
        self.add_rule("account.max_daily_accounts", RangeValidationRule(min_value=1, max_value=1000))
        self.add_rule("account.use_real_names", TypeValidationRule(bool))
        self.add_rule("account.name_database_file", TypeValidationRule(str))
        self.add_rule("account.profile_image_dir", TypeValidationRule(str))
        self.add_rule("account.recovery_email_enabled", TypeValidationRule(bool))
        
        # Security settings
        self.add_rule("security.encryption_enabled", TypeValidationRule(bool))
        self.add_rule("security.log_sensitive_data", TypeValidationRule(bool))
        self.add_rule("security.secure_delete", TypeValidationRule(bool))
        self.add_rule("security.session_timeout", TypeValidationRule(int))
        self.add_rule("security.session_timeout", RangeValidationRule(min_value=300, max_value=86400))
        self.add_rule("security.max_login_attempts", TypeValidationRule(int))
        self.add_rule("security.max_login_attempts", RangeValidationRule(min_value=1, max_value=10))
        self.add_rule("security.lockout_duration", TypeValidationRule(int))
        self.add_rule("security.lockout_duration", RangeValidationRule(min_value=60, max_value=3600))
        
        # Health check settings
        self.add_rule("health_check.enabled", TypeValidationRule(bool))
        self.add_rule("health_check.check_interval", TypeValidationRule(int))
        self.add_rule("health_check.check_interval", RangeValidationRule(min_value=60, max_value=86400))
        self.add_rule("health_check.batch_size", TypeValidationRule(int))
        self.add_rule("health_check.batch_size", RangeValidationRule(min_value=1, max_value=100))
        self.add_rule("health_check.timeout", TypeValidationRule(int))
        self.add_rule("health_check.timeout", RangeValidationRule(min_value=5, max_value=300))
        self.add_rule("health_check.notification_threshold", TypeValidationRule(float))
        self.add_rule("health_check.notification_threshold", RangeValidationRule(min_value=0.0, max_value=1.0))
        self.add_rule("health_check.slack_webhook", URLValidationRule(['https']))
        self.add_rule("health_check.discord_webhook", URLValidationRule(['https']))
        
        # Logging settings
        self.add_rule("logging.level", TypeValidationRule(str))
        self.add_rule("logging.level", ChoiceValidationRule(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]))
        self.add_rule("logging.file_path", TypeValidationRule(str))
        self.add_rule("logging.max_file_size", TypeValidationRule(int))
        self.add_rule("logging.max_file_size", RangeValidationRule(min_value=1024, max_value=1073741824))  # 1KB to 1GB
        self.add_rule("logging.backup_count", TypeValidationRule(int))
        self.add_rule("logging.backup_count", RangeValidationRule(min_value=1, max_value=100))
        self.add_rule("logging.console_output", TypeValidationRule(bool))
    
    def add_rule(self, key: str, rule: ValidationRule) -> None:
        """Add a validation rule for a configuration key"""
        if key not in self.rules:
            self.rules[key] = []
        self.rules[key].append(rule)
    
    def remove_rule(self, key: str, rule_type: Type[ValidationRule] = None) -> None:
        """Remove validation rules for a key"""
        if key in self.rules:
            if rule_type:
                self.rules[key] = [r for r in self.rules[key] if not isinstance(r, rule_type)]
            else:
                del self.rules[key]
    
    def validate(self, key: str, value: Any) -> tuple[bool, List[str]]:
        """
        Validate a configuration value.
        
        Args:
            key: Configuration key
            value: Value to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        if key not in self.rules:
            return True, []
        
        errors = []
        for rule in self.rules[key]:
            try:
                if not rule.validate(value):
                    errors.append(rule.get_error_message())
            except Exception as e:
                errors.append(f"Validation error: {e}")
        
        return len(errors) == 0, errors
    
    def validate_all(self, config_items: Dict[str, ConfigItem]) -> Dict[str, List[str]]:
        """
        Validate all configuration items.
        
        Args:
            config_items: Dictionary of configuration items
            
        Returns:
            Dictionary of validation errors by key
        """
        all_errors = {}
        
        for key, item in config_items.items():
            is_valid, errors = self.validate(key, item.value)
            if not is_valid:
                all_errors[key] = errors
        
        return all_errors
    
    def get_validation_info(self, key: str) -> Dict[str, Any]:
        """Get validation information for a configuration key"""
        if key not in self.rules:
            return {"rules": [], "description": "No validation rules defined"}
        
        info = {
            "rules": [],
            "description": f"Validation rules for {key}"
        }
        
        for rule in self.rules[key]:
            rule_info = {
                "type": rule.__class__.__name__,
                "description": rule.get_error_message()
            }
            
            # Add specific rule details
            if isinstance(rule, RangeValidationRule):
                rule_info["min_value"] = rule.min_value
                rule_info["max_value"] = rule.max_value
            elif isinstance(rule, ChoiceValidationRule):
                rule_info["choices"] = rule.choices
            elif isinstance(rule, RegexValidationRule):
                rule_info["pattern"] = rule.pattern.pattern
            
            info["rules"].append(rule_info)
        
        return info

class EncryptionManager:
    """
    Advanced encryption manager for sensitive configuration values.
    
    Features:
    - Multiple encryption algorithms
    - Key derivation and rotation
    - Secure key storage
    - Salt management
    """
    
    def __init__(self, master_password: Optional[str] = None):
        """
        Initialize encryption manager.
        
        Args:
            master_password: Master password for key derivation
        """
        self.logger = logging.getLogger(__name__)
        self._master_password = master_password
        self._salt = None
        self._cipher_suite = None
        self._key_version = 1
        
        if master_password:
            self._initialize_encryption(master_password)
    
    def _initialize_encryption(self, master_password: str) -> None:
        """Initialize encryption with master password"""
        try:
            # Generate or load salt
            self._salt = self._get_or_create_salt()
            
            # Derive encryption key
            key = self._derive_key(master_password, self._salt)
            
            # Initialize cipher suite
            self._cipher_suite = Fernet(key)
            
            self.logger.info("Encryption initialized successfully")
            
        except Exception as e:
            raise EncryptionError(f"Failed to initialize encryption: {e}")
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one"""
        salt_file = Path("config/.salt")
        
        try:
            if salt_file.exists():
                with open(salt_file, 'rb') as f:
                    return f.read()
            else:
                # Create new salt
                salt = secrets.token_bytes(32)
                
                # Ensure directory exists
                salt_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Save salt securely
                with open(salt_file, 'wb') as f:
                    f.write(salt)
                
                # Set restrictive permissions
                salt_file.chmod(0o600)
                
                return salt
                
        except Exception as e:
            self.logger.warning(f"Could not manage salt file: {e}")
            # Fallback to generated salt (not persistent)
            return secrets.token_bytes(32)
    
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Encrypted string with version prefix
        """
        if not self._cipher_suite:
            raise EncryptionError("Encryption not initialized")
        
        try:
            # Add version prefix for future key rotation support
            encrypted = self._cipher_suite.encrypt(plaintext.encode())
            versioned_encrypted = f"v{self._key_version}:{base64.urlsafe_b64encode(encrypted).decode()}"
            return versioned_encrypted
            
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            encrypted_text: Encrypted string to decrypt
            
        Returns:
            Decrypted plaintext string
        """
        if not self._cipher_suite:
            raise EncryptionError("Encryption not initialized")
        
        try:
            # Handle versioned encryption
            if ':' in encrypted_text and encrypted_text.startswith('v'):
                version_part, encrypted_part = encrypted_text.split(':', 1)
                version = int(version_part[1:])  # Remove 'v' prefix
                
                if version != self._key_version:
                    self.logger.warning(f"Decrypting with different key version: {version}")
                
                encrypted_bytes = base64.urlsafe_b64decode(encrypted_part.encode())
            else:
                # Legacy format (no version)
                encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            
            decrypted = self._cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode()
            
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")
    
    def is_encrypted(self, text: str) -> bool:
        """Check if a string appears to be encrypted"""
        try:
            # Check for version prefix
            if text.startswith('v') and ':' in text:
                return True
            
            # Try to decode as base64 (legacy format)
            base64.urlsafe_b64decode(text.encode())
            return len(text) > 50  # Encrypted strings are typically longer
            
        except Exception:
            return False
    
    def rotate_key(self, new_password: str) -> bool:
        """
        Rotate encryption key (for future use).
        
        Args:
            new_password: New master password
            
        Returns:
            True if rotation successful
        """
        try:
            # This would require re-encrypting all sensitive values
            # For now, just update the key
            old_cipher = self._cipher_suite
            
            # Initialize with new password
            self._key_version += 1
            self._initialize_encryption(new_password)
            
            self.logger.info(f"Key rotated to version {self._key_version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Key rotation failed: {e}")
            return False
    
    def get_key_info(self) -> Dict[str, Any]:
        """Get information about the current encryption key"""
        return {
            "version": self._key_version,
            "algorithm": "Fernet (AES 128)",
            "key_derivation": "PBKDF2-HMAC-SHA256",
            "iterations": 100000,
            "salt_length": len(self._salt) if self._salt else 0,
            "initialized": self._cipher_suite is not None
        }

class ConfigManager:
    """
    Main configuration manager class that handles all configuration operations.
    
    Features:
    - Type-safe configuration management
    - Multiple configuration sources with priority
    - Validation and encryption
    - Default configuration generation
    """
    
    def __init__(self, config_file: Optional[str] = None, encryption_key: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_file: Path to the configuration file
            encryption_key: Key for encrypting sensitive values
        """
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file or "config/system_config.yaml"
        self.config_items: Dict[str, ConfigItem] = {}
        self.system_config = SystemConfig()
        
        # Initialize validation
        self.validator = ConfigValidator()
        
        # Initialize advanced encryption
        self.encryption_manager = EncryptionManager(encryption_key)
        
        # Legacy encryption support
        self._encryption_key = encryption_key
        self._cipher_suite = None
        if encryption_key:
            self._setup_encryption(encryption_key)
        
        # Configuration sources priority (highest to lowest)
        self.source_priority = [
            ConfigSource.OVERRIDE,
            ConfigSource.ENVIRONMENT,
            ConfigSource.FILE,
            ConfigSource.DEFAULT
        ]
        
        # Initialize default configuration
        self._initialize_defaults()
    
    def _setup_encryption(self, key: str) -> None:
        """Setup encryption cipher suite"""
        try:
            # Derive key from password
            password = key.encode()
            salt = b'salt_'  # In production, use a random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key_bytes = base64.urlsafe_b64encode(kdf.derive(password))
            self._cipher_suite = Fernet(key_bytes)
        except Exception as e:
            raise EncryptionError(f"Failed to setup encryption: {e}")
    
    def _initialize_defaults(self) -> None:
        """Initialize default configuration items"""
        defaults = [
            # Proxy settings
            ConfigItem("proxy.enabled", False, False, "Enable proxy usage", bool),
            ConfigItem("proxy.http_proxy", None, None, "HTTP proxy URL", str),
            ConfigItem("proxy.https_proxy", None, None, "HTTPS proxy URL", str),
            ConfigItem("proxy.rotation_interval", 300, 300, "Proxy rotation interval in seconds", int),
            
            # SMS settings
            ConfigItem("sms.provider", "5sim", "5sim", "SMS provider name", str, is_required=True),
            ConfigItem("sms.api_key", None, None, "SMS provider API key", str, is_sensitive=True, is_required=True),
            ConfigItem("sms.country_code", "US", "US", "Country code for SMS", str),
            ConfigItem("sms.max_wait_time", 300, 300, "Maximum wait time for SMS", int),
            
            # Account settings
            ConfigItem("account.batch_size", 5, 5, "Number of accounts to create in batch", int),
            ConfigItem("account.creation_delay", 30, 30, "Delay between account creations", int),
            ConfigItem("account.max_daily_accounts", 50, 50, "Maximum accounts per day", int),
            ConfigItem("account.use_real_names", False, False, "Use real names for accounts", bool),
            
            # Security settings
            ConfigItem("security.encryption_enabled", True, True, "Enable encryption for sensitive data", bool),
            ConfigItem("security.log_sensitive_data", False, False, "Log sensitive data", bool),
            ConfigItem("security.session_timeout", 3600, 3600, "Session timeout in seconds", int),
            
            # Health check settings
            ConfigItem("health_check.enabled", True, True, "Enable health checking", bool),
            ConfigItem("health_check.check_interval", 3600, 3600, "Health check interval", int),
            ConfigItem("health_check.notification_threshold", 0.8, 0.8, "Notification threshold", float),
            ConfigItem("health_check.slack_webhook", None, None, "Slack webhook URL", str, is_sensitive=True),
            
            # Logging settings
            ConfigItem("logging.level", "INFO", "INFO", "Logging level", str),
            ConfigItem("logging.file_path", "logs/google_account_creator.log", "logs/google_account_creator.log", "Log file path", str),
            ConfigItem("logging.max_file_size", 10485760, 10485760, "Maximum log file size", int),
        ]
        
        for item in defaults:
            self.config_items[item.key] = item
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.
        
        Args:
            key: Configuration key (dot notation supported)
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        try:
            if key in self.config_items:
                item = self.config_items[key]
                value = item.value
                
                # Decrypt if sensitive and encryption is enabled
                if item.is_sensitive and self.encryption_manager and isinstance(value, str):
                    try:
                        if self.encryption_manager.is_encrypted(value):
                            value = self._decrypt_value(value)
                    except Exception as e:
                        self.logger.warning(f"Failed to decrypt value for {key}: {e}")
                        # If decryption fails, assume it's not encrypted
                        pass
                
                return value
            
            # Try to get from nested structure
            return self._get_nested_value(key, default)
            
        except Exception as e:
            self.logger.error(f"Error getting config value for key '{key}': {e}")
            return default
    
    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.OVERRIDE, 
            validate: bool = True) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
            source: Source of the configuration
            validate: Whether to validate the value
        """
        try:
            # Validate if requested
            if validate:
                is_valid, errors = self.validator.validate(key, value)
                if not is_valid:
                    error_msg = f"Validation failed for '{key}': {'; '.join(errors)}"
                    raise ValidationError(error_msg)
            
            if key in self.config_items:
                item = self.config_items[key]
                
                # Encrypt if sensitive and we have encryption enabled, but only if not already encrypted
                if item.is_sensitive and self.encryption_manager and isinstance(value, str):
                    # Check if value is already encrypted
                    if not self.encryption_manager.is_encrypted(value):
                        encrypted_value = self._encrypt_value(str(value))
                        item.value = encrypted_value
                    else:
                        # Value is already encrypted, store as-is
                        item.value = value
                else:
                    item.value = value
                    
                item.source = source
            else:
                # Create new config item
                # Determine if this is a sensitive key based on key name
                is_sensitive = any(sensitive_keyword in key.lower() 
                                 for sensitive_keyword in ['api_key', 'password', 'token', 'secret', 'webhook'])
                
                stored_value = value
                if is_sensitive and self.encryption_manager and isinstance(value, str):
                    # Check if value is already encrypted
                    if not self.encryption_manager.is_encrypted(value):
                        stored_value = self._encrypt_value(str(value))
                
                self.config_items[key] = ConfigItem(
                    key=key,
                    value=stored_value,
                    default_value=value,
                    description=f"Custom configuration for {key}",
                    data_type=type(value),
                    source=source,
                    is_sensitive=is_sensitive
                )
            
            # Update nested structure
            self._set_nested_value(key, value)
            
        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"Error setting config value for key '{key}': {e}")
            raise ConfigurationError(f"Failed to set configuration: {e}")
    
    def delete(self, key: str) -> bool:
        """
        Delete a configuration value.
        
        Args:
            key: Configuration key to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            if key in self.config_items:
                del self.config_items[key]
                self._delete_nested_value(key)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting config key '{key}': {e}")
            return False
    
    def has(self, key: str) -> bool:
        """Check if a configuration key exists"""
        return key in self.config_items or self._has_nested_value(key)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        result = {}
        for key, item in self.config_items.items():
            result[key] = self.get(key)
        return result
    
    def get_system_config(self) -> SystemConfig:
        """Get the complete system configuration object"""
        return self.system_config
    
    def _get_nested_value(self, key: str, default: Any = None) -> Any:
        """Get value from nested configuration structure"""
        try:
            parts = key.split('.')
            obj = self.system_config
            
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return default
            
            return obj
        except Exception:
            return default
    
    def _set_nested_value(self, key: str, value: Any) -> None:
        """Set value in nested configuration structure"""
        try:
            parts = key.split('.')
            obj = self.system_config
            
            # Navigate to parent object
            for part in parts[:-1]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return
            
            # Set the final value
            if hasattr(obj, parts[-1]):
                setattr(obj, parts[-1], value)
                
        except Exception as e:
            self.logger.error(f"Error setting nested value for '{key}': {e}")
    
    def _delete_nested_value(self, key: str) -> None:
        """Delete value from nested configuration structure"""
        try:
            parts = key.split('.')
            obj = self.system_config
            
            # Navigate to parent object
            for part in parts[:-1]:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return
            
            # Reset to default value
            if hasattr(obj, parts[-1]):
                # Get default from config item
                if key in self.config_items:
                    default_value = self.config_items[key].default_value
                    setattr(obj, parts[-1], default_value)
                
        except Exception as e:
            self.logger.error(f"Error deleting nested value for '{key}': {e}")
    
    def _has_nested_value(self, key: str) -> bool:
        """Check if nested value exists"""
        try:
            parts = key.split('.')
            obj = self.system_config
            
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                else:
                    return False
            
            return True
        except Exception:
            return False
    
    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value using the advanced encryption manager"""
        try:
            return self.encryption_manager.encrypt(value)
        except EncryptionError:
            # Fallback to legacy encryption
            if self._cipher_suite:
                try:
                    encrypted = self._cipher_suite.encrypt(value.encode())
                    return base64.urlsafe_b64encode(encrypted).decode()
                except Exception as e:
                    raise EncryptionError(f"Failed to encrypt value: {e}")
            else:
                return value
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a sensitive value using the advanced encryption manager"""
        try:
            return self.encryption_manager.decrypt(encrypted_value)
        except EncryptionError:
            # Fallback to legacy decryption
            if self._cipher_suite:
                try:
                    encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
                    decrypted = self._cipher_suite.decrypt(encrypted_bytes)
                    return decrypted.decode()
                except Exception as e:
                    raise EncryptionError(f"Failed to decrypt value: {e}")
            else:
                return encrypted_value
    
    def reset_to_defaults(self) -> None:
        """Reset all configuration to default values"""
        for key, item in self.config_items.items():
            item.value = item.default_value
            item.source = ConfigSource.DEFAULT
        
        # Reset system config
        self.system_config = SystemConfig()
        self.logger.info("Configuration reset to defaults")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        summary = {
            "total_items": len(self.config_items),
            "sensitive_items": sum(1 for item in self.config_items.values() if item.is_sensitive),
            "required_items": sum(1 for item in self.config_items.values() if item.is_required),
            "sources": {},
            "encryption_enabled": self._cipher_suite is not None
        }
        
        # Count by source
        for source in ConfigSource:
            summary["sources"][source.value] = sum(
                1 for item in self.config_items.values() if item.source == source
            )
        
        return summary
    
    def validate_configuration(self) -> Dict[str, List[str]]:
        """
        Validate all configuration items.
        
        Returns:
            Dictionary of validation errors by key
        """
        return self.validator.validate_all(self.config_items)
    
    def is_configuration_valid(self) -> bool:
        """Check if the entire configuration is valid"""
        errors = self.validate_configuration()
        return len(errors) == 0
    
    def get_validation_errors(self) -> List[str]:
        """Get all validation errors as a flat list"""
        errors = self.validate_configuration()
        all_errors = []
        for key, key_errors in errors.items():
            for error in key_errors:
                all_errors.append(f"{key}: {error}")
        return all_errors
    
    def validate_required_fields(self) -> List[str]:
        """Check for missing required configuration fields"""
        missing = []
        for key, item in self.config_items.items():
            if item.is_required and (item.value is None or item.value == ""):
                missing.append(key)
        return missing
    
    def add_validation_rule(self, key: str, rule: ValidationRule) -> None:
        """Add a custom validation rule for a configuration key"""
        self.validator.add_rule(key, rule)
    
    def remove_validation_rule(self, key: str, rule_type: Type[ValidationRule] = None) -> None:
        """Remove validation rules for a configuration key"""
        self.validator.remove_rule(key, rule_type)
    
    def get_validation_info(self, key: str) -> Dict[str, Any]:
        """Get validation information for a configuration key"""
        return self.validator.get_validation_info(key)
    
    def validate_and_set(self, key: str, value: Any, source: ConfigSource = ConfigSource.OVERRIDE) -> bool:
        """
        Validate and set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
            source: Source of the configuration
            
        Returns:
            True if validation passed and value was set, False otherwise
        """
        try:
            self.set(key, value, source, validate=True)
            return True
        except ValidationError as e:
            self.logger.warning(f"Validation failed for '{key}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error setting validated config for '{key}': {e}")
            return False
    
    def load_from_file(self, file_path: Optional[str] = None, 
                      file_format: Optional[ConfigFormat] = None) -> bool:
        """
        Load configuration from a file.
        
        Args:
            file_path: Path to the configuration file
            file_format: Format of the configuration file (auto-detected if None)
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            config_path = file_path or self.config_file
            if not os.path.exists(config_path):
                self.logger.warning(f"Configuration file not found: {config_path}")
                return False
            
            # Auto-detect format if not specified
            if file_format is None:
                file_format = self._detect_file_format(config_path)
            
            # Load configuration data
            config_data = self._load_file_data(config_path, file_format)
            if config_data is None:
                return False
            
            # Apply configuration with FILE source
            self._apply_config_data(config_data, ConfigSource.FILE)
            
            self.logger.info(f"Configuration loaded from {config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading configuration from file: {e}")
            return False
    
    def load_from_environment(self, prefix: str = "GAC_") -> int:
        """
        Load configuration from environment variables.
        
        Args:
            prefix: Prefix for environment variables (e.g., GAC_PROXY_ENABLED)
            
        Returns:
            Number of configuration items loaded from environment
        """
        try:
            loaded_count = 0
            
            for env_key, env_value in os.environ.items():
                if not env_key.startswith(prefix):
                    continue
                
                # Convert environment variable name to config key
                config_key = self._env_key_to_config_key(env_key, prefix)
                
                # Convert string value to appropriate type
                converted_value = self._convert_env_value(config_key, env_value)
                
                # Set configuration with ENVIRONMENT source
                self.set(config_key, converted_value, ConfigSource.ENVIRONMENT, validate=False)
                loaded_count += 1
                
                self.logger.debug(f"Loaded from environment: {config_key} = {converted_value}")
            
            self.logger.info(f"Loaded {loaded_count} configuration items from environment variables")
            return loaded_count
            
        except Exception as e:
            self.logger.error(f"Error loading configuration from environment: {e}")
            return 0
    
    def load_from_dict(self, config_dict: Dict[str, Any], 
                      source: ConfigSource = ConfigSource.OVERRIDE) -> int:
        """
        Load configuration from a dictionary.
        
        Args:
            config_dict: Dictionary containing configuration data
            source: Source of the configuration
            
        Returns:
            Number of configuration items loaded
        """
        try:
            loaded_count = 0
            flattened = self._flatten_dict(config_dict)
            
            for key, value in flattened.items():
                self.set(key, value, source, validate=False)
                loaded_count += 1
            
            self.logger.info(f"Loaded {loaded_count} configuration items from dictionary")
            return loaded_count
            
        except Exception as e:
            self.logger.error(f"Error loading configuration from dictionary: {e}")
            return 0
    
    def save_to_file(self, file_path: Optional[str] = None, 
                    file_format: Optional[ConfigFormat] = None,
                    include_sensitive: bool = False) -> bool:
        """
        Save current configuration to a file.
        
        Args:
            file_path: Path to save the configuration file
            file_format: Format for the configuration file
            include_sensitive: Whether to include sensitive values
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            save_path = file_path or self.config_file
            
            # Auto-detect format if not specified
            if file_format is None:
                file_format = self._detect_file_format(save_path)
            
            # Prepare configuration data
            config_data = self._prepare_save_data(include_sensitive)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save based on format
            success = self._save_file_data(save_path, config_data, file_format)
            
            if success:
                self.logger.info(f"Configuration saved to {save_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error saving configuration to file: {e}")
            return False
    
    def generate_default_config_file(self, file_path: Optional[str] = None,
                                   file_format: ConfigFormat = ConfigFormat.YAML) -> bool:
        """
        Generate a default configuration file with all settings and their defaults.
        
        Args:
            file_path: Path for the configuration file
            file_format: Format for the configuration file
            
        Returns:
            True if generated successfully, False otherwise
        """
        try:
            save_path = file_path or self.config_file
            
            # Create configuration with defaults and descriptions
            config_data = self._generate_default_config_structure()
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save the default configuration
            success = self._save_file_data(save_path, config_data, file_format)
            
            if success:
                self.logger.info(f"Default configuration file generated: {save_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error generating default configuration file: {e}")
            return False
    
    def reload_configuration(self) -> bool:
        """
        Reload configuration from all sources in priority order.
        
        Returns:
            True if reloaded successfully, False otherwise
        """
        try:
            # Reset to defaults first
            self.reset_to_defaults()
            
            # Load from file
            self.load_from_file()
            
            # Load from environment (higher priority)
            self.load_from_environment()
            
            # Validate the final configuration
            if not self.is_configuration_valid():
                self.logger.warning("Configuration validation failed after reload")
                errors = self.get_validation_errors()
                for error in errors:
                    self.logger.warning(f"Validation error: {error}")
            
            self.logger.info("Configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")
            return False
    
    def _detect_file_format(self, file_path: str) -> ConfigFormat:
        """Detect configuration file format from extension"""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.yaml', '.yml']:
            return ConfigFormat.YAML
        elif ext == '.json':
            return ConfigFormat.JSON
        elif ext in ['.ini', '.cfg']:
            return ConfigFormat.INI
        else:
            # Default to YAML
            return ConfigFormat.YAML
    
    def _load_file_data(self, file_path: str, file_format: ConfigFormat) -> Optional[Dict[str, Any]]:
        """Load data from configuration file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_format == ConfigFormat.YAML:
                    return yaml.safe_load(f) or {}
                elif file_format == ConfigFormat.JSON:
                    return json.load(f) or {}
                elif file_format == ConfigFormat.INI:
                    parser = configparser.ConfigParser()
                    parser.read_file(f)
                    return self._configparser_to_dict(parser)
                else:
                    raise ValueError(f"Unsupported file format: {file_format}")
                    
        except Exception as e:
            self.logger.error(f"Error loading file data from {file_path}: {e}")
            return None
    
    def _save_file_data(self, file_path: str, data: Dict[str, Any], 
                       file_format: ConfigFormat) -> bool:
        """Save data to configuration file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_format == ConfigFormat.YAML:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
                elif file_format == ConfigFormat.JSON:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                elif file_format == ConfigFormat.INI:
                    parser = self._dict_to_configparser(data)
                    parser.write(f)
                else:
                    raise ValueError(f"Unsupported file format: {file_format}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving file data to {file_path}: {e}")
            return False
    
    def _apply_config_data(self, config_data: Dict[str, Any], source: ConfigSource) -> None:
        """Apply configuration data from any source"""
        flattened = self._flatten_dict(config_data)
        
        for key, value in flattened.items():
            # Skip validation during loading to allow fixing invalid configs
            self.set(key, value, source, validate=False)
    
    def _env_key_to_config_key(self, env_key: str, prefix: str) -> str:
        """Convert environment variable name to configuration key"""
        # Remove prefix and convert to lowercase with dots
        config_key = env_key[len(prefix):].lower().replace('_', '.')
        return config_key
    
    def _convert_env_value(self, config_key: str, env_value: str) -> Any:
        """Convert environment variable string value to appropriate type"""
        # Get expected type from config item if it exists
        if config_key in self.config_items:
            expected_type = self.config_items[config_key].data_type
        else:
            # Try to infer type from value
            return self._infer_type_from_string(env_value)
        
        try:
            if expected_type == bool:
                return env_value.lower() in ('true', '1', 'yes', 'on')
            elif expected_type == int:
                return int(env_value)
            elif expected_type == float:
                return float(env_value)
            elif expected_type == list:
                # Assume comma-separated values
                return [item.strip() for item in env_value.split(',') if item.strip()]
            else:
                return env_value
                
        except (ValueError, TypeError):
            self.logger.warning(f"Could not convert environment value '{env_value}' for key '{config_key}'")
            return env_value
    
    def _infer_type_from_string(self, value: str) -> Any:
        """Infer the appropriate type for a string value"""
        # Try boolean
        if value.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', '1', '0'):
            return value.lower() in ('true', 'yes', 'on', '1')
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Default to string
        return value
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """Flatten a nested dictionary using dot notation"""
        items = []
        
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def _unflatten_dict(self, d: Dict[str, Any], sep: str = '.') -> Dict[str, Any]:
        """Convert a flattened dictionary back to nested structure"""
        result = {}
        
        for key, value in d.items():
            parts = key.split(sep)
            current = result
            
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        
        return result
    
    def _configparser_to_dict(self, parser: configparser.ConfigParser) -> Dict[str, Any]:
        """Convert ConfigParser to dictionary"""
        result = {}
        
        for section_name in parser.sections():
            section = {}
            for key, value in parser.items(section_name):
                section[key] = self._infer_type_from_string(value)
            result[section_name] = section
        
        return result
    
    def _dict_to_configparser(self, data: Dict[str, Any]) -> configparser.ConfigParser:
        """Convert dictionary to ConfigParser"""
        parser = configparser.ConfigParser()
        
        # Convert flat keys to sections
        nested_data = self._unflatten_dict(data)
        
        for section_name, section_data in nested_data.items():
            if isinstance(section_data, dict):
                parser.add_section(section_name)
                for key, value in section_data.items():
                    parser.set(section_name, key, str(value))
        
        return parser
    
    def _prepare_save_data(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Prepare configuration data for saving"""
        save_data = {}
        
        for key, item in self.config_items.items():
            # Skip sensitive values if not requested
            if item.is_sensitive and not include_sensitive:
                continue
            
            # For sensitive values that should be included, save the raw (encrypted) value
            if item.is_sensitive and include_sensitive:
                # Save the raw encrypted value, not decrypted
                save_data[key] = item.value
            else:
                # Get the actual value (decrypted if needed)
                value = self.get(key)
                save_data[key] = value
        
        # Convert to nested structure
        return self._unflatten_dict(save_data)
    
    def _generate_default_config_structure(self) -> Dict[str, Any]:
        """Generate a structured default configuration with comments"""
        config = {
            "proxy": {
                "enabled": False,
                "http_proxy": None,
                "https_proxy": None,
                "socks_proxy": None,
                "proxy_list_file": None,
                "rotation_interval": 300,
                "max_retries": 3,
                "timeout": 30
            },
            "sms": {
                "provider": "5sim",
                "api_key": None,
                "country_code": "US",
                "max_wait_time": 300,
                "retry_attempts": 3,
                "backup_providers": ["sms-activate", "textverified"]
            },
            "account": {
                "batch_size": 5,
                "creation_delay": 30,
                "max_daily_accounts": 50,
                "use_real_names": False,
                "name_database_file": "data/names.json",
                "profile_image_dir": "data/profile_images",
                "recovery_email_enabled": True
            },
            "security": {
                "encryption_enabled": True,
                "log_sensitive_data": False,
                "secure_delete": True,
                "session_timeout": 3600,
                "max_login_attempts": 3,
                "lockout_duration": 900
            },
            "health_check": {
                "enabled": True,
                "check_interval": 3600,
                "batch_size": 10,
                "timeout": 30,
                "notification_threshold": 0.8,
                "slack_webhook": None,
                "discord_webhook": None
            },
            "logging": {
                "level": "INFO",
                "file_path": "logs/google_account_creator.log",
                "max_file_size": 10485760,
                "backup_count": 5,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "console_output": True
            }
        }
        
        return config
    
    def get_config_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration items grouped by their source"""
        sources = {}
        
        for source in ConfigSource:
            sources[source.value] = {}
        
        for key, item in self.config_items.items():
            source_key = item.source.value
            sources[source_key][key] = {
                "value": self.get(key),
                "description": item.description,
                "is_sensitive": item.is_sensitive,
                "is_required": item.is_required
            }
        
        return sources
    
    def merge_configurations(self, other_config: 'ConfigManager', 
                           override_conflicts: bool = True) -> int:
        """
        Merge another configuration into this one.
        
        Args:
            other_config: Another ConfigManager instance to merge from
            override_conflicts: Whether to override conflicting values
            
        Returns:
            Number of items merged
        """
        try:
            merged_count = 0
            
            for key, other_item in other_config.config_items.items():
                if key in self.config_items and not override_conflicts:
                    continue
                
                # Copy the configuration item
                self.config_items[key] = ConfigItem(
                    key=other_item.key,
                    value=other_item.value,
                    default_value=other_item.default_value,
                    description=other_item.description,
                    data_type=other_item.data_type,
                    is_sensitive=other_item.is_sensitive,
                    is_required=other_item.is_required,
                    source=ConfigSource.OVERRIDE,
                    validation_rules=other_item.validation_rules
                )
                
                # Update nested structure
                self._set_nested_value(key, other_item.value)
                merged_count += 1
            
            self.logger.info(f"Merged {merged_count} configuration items")
            return merged_count
            
        except Exception as e:
            self.logger.error(f"Error merging configurations: {e}")
            return 0
    
    def setup_encryption(self, master_password: str) -> bool:
        """
        Setup or update encryption with a master password.
        
        Args:
            master_password: Master password for encryption
            
        Returns:
            True if setup successful
        """
        try:
            self.encryption_manager = EncryptionManager(master_password)
            
            # Re-encrypt all sensitive values with new encryption
            self._re_encrypt_sensitive_values()
            
            self.logger.info("Encryption setup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Encryption setup failed: {e}")
            return False
    
    def _re_encrypt_sensitive_values(self) -> None:
        """Re-encrypt all sensitive values with current encryption"""
        for key, item in self.config_items.items():
            if item.is_sensitive and item.value:
                try:
                    # Decrypt with old method if needed
                    if isinstance(item.value, str) and self.encryption_manager.is_encrypted(item.value):
                        decrypted = self._decrypt_value(item.value)
                        # Re-encrypt with new method
                        item.value = self._encrypt_value(decrypted)
                except Exception as e:
                    self.logger.warning(f"Could not re-encrypt value for {key}: {e}")
    
    def export_encrypted_config(self, file_path: str, 
                              include_all_sensitive: bool = True) -> bool:
        """
        Export configuration with encrypted sensitive values.
        
        Args:
            file_path: Path to save encrypted configuration
            include_all_sensitive: Whether to include all sensitive values
            
        Returns:
            True if export successful
        """
        try:
            export_data = {}
            
            for key, item in self.config_items.items():
                if item.is_sensitive:
                    if include_all_sensitive:
                        # Include encrypted value
                        export_data[key] = {
                            "value": item.value,  # Already encrypted
                            "encrypted": True,
                            "description": item.description
                        }
                else:
                    export_data[key] = {
                        "value": item.value,
                        "encrypted": False,
                        "description": item.description
                    }
            
            # Convert to nested structure
            nested_data = self._unflatten_dict(export_data)
            
            # Save as JSON with metadata
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "export_time": str(datetime.now()),
                        "encryption_info": self.encryption_manager.get_key_info(),
                        "total_items": len(export_data),
                        "sensitive_items": sum(1 for item in self.config_items.values() if item.is_sensitive)
                    },
                    "configuration": nested_data
                }, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Encrypted configuration exported to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False
    
    def import_encrypted_config(self, file_path: str) -> bool:
        """
        Import configuration with encrypted sensitive values.
        
        Args:
            file_path: Path to encrypted configuration file
            
        Returns:
            True if import successful
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "configuration" not in data:
                raise ValueError("Invalid encrypted configuration file format")
            
            config_data = data["configuration"]
            metadata = data.get("metadata", {})
            
            self.logger.info(f"Importing configuration from {metadata.get('export_time', 'unknown time')}")
            
            # Flatten and apply configuration
            flattened = self._flatten_dict(config_data)
            
            for key, item_data in flattened.items():
                if isinstance(item_data, dict) and "value" in item_data:
                    value = item_data["value"]
                    is_encrypted = item_data.get("encrypted", False)
                    
                    # Set the value (will be handled appropriately based on sensitivity)
                    self.set(key, value, ConfigSource.FILE, validate=False)
                else:
                    # Simple value
                    self.set(key, item_data, ConfigSource.FILE, validate=False)
            
            self.logger.info("Encrypted configuration imported successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            return False
    
    def get_encryption_status(self) -> Dict[str, Any]:
        """Get status of encryption for all sensitive values"""
        status = {
            "encryption_enabled": self.encryption_manager is not None and hasattr(self.encryption_manager, '_cipher'),
            "key_info": self.encryption_manager.get_key_info() if self.encryption_manager else {},
            "sensitive_items": {},
            "total_sensitive": 0,
            "encrypted_count": 0
        }
        
        for key, item in self.config_items.items():
            if item.is_sensitive:
                status["total_sensitive"] += 1
                
                is_encrypted = False
                if item.value and isinstance(item.value, str) and self.encryption_manager:
                    is_encrypted = self.encryption_manager.is_encrypted(item.value)
                
                if is_encrypted:
                    status["encrypted_count"] += 1
                
                status["sensitive_items"][key] = {
                    "encrypted": is_encrypted,
                    "has_value": item.value is not None and item.value != "",
                    "description": item.description
                }
        
        return status
    
    def validate_encryption_integrity(self) -> Dict[str, Any]:
        """Validate that all encrypted values can be decrypted"""
        results = {
            "total_checked": 0,
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for key, item in self.config_items.items():
            if item.is_sensitive and item.value:
                results["total_checked"] += 1
                
                try:
                    if self.encryption_manager and self.encryption_manager.is_encrypted(item.value):
                        # Try to decrypt
                        decrypted = self._decrypt_value(item.value)
                        if decrypted:
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"{key}: Decryption returned empty value")
                    else:
                        # Not encrypted (might be plain text)
                        results["successful"] += 1
                        
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"{key}: {str(e)}")
        
        # Add overall status
        if results["total_checked"] == 0:
            results["overall_status"] = "no_data"
        elif results["failed"] == 0:
            results["overall_status"] = "valid"
        else:
            results["overall_status"] = "invalid"
        
        return results 