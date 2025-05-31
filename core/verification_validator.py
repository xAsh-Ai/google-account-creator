#!/usr/bin/env python3

"""
Verification Validator - Validation utilities for phone verification

This module provides comprehensive validation utilities for phone number
verification processes, including verification code validation, phone number
format validation, and verification result validation for automated Google
account creation.

Author: Google Account Creator Team
Version: 0.1.0
"""

import re
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

# Configure logging
logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    """Validation result status."""
    VALID = "valid"
    INVALID = "invalid"
    SUSPICIOUS = "suspicious"
    EXPIRED = "expired"
    MALFORMED = "malformed"

class CodeType(Enum):
    """Types of verification codes."""
    GOOGLE = "google"
    SMS_GENERIC = "sms_generic"
    NUMERIC = "numeric"
    ALPHANUMERIC = "alphanumeric"
    UNKNOWN = "unknown"

@dataclass
class ValidationError:
    """Represents a validation error."""
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "error"  # error, warning, info

@dataclass
class CodeValidationResult:
    """Result of verification code validation."""
    is_valid: bool
    code_type: CodeType
    normalized_code: Optional[str] = None
    confidence: float = 0.0
    errors: List[ValidationError] = None
    warnings: List[ValidationError] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

@dataclass
class PhoneValidationResult:
    """Result of phone number validation."""
    is_valid: bool
    formatted_number: Optional[str] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    carrier: Optional[str] = None
    line_type: Optional[str] = None
    errors: List[ValidationError] = None
    warnings: List[ValidationError] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

class VerificationValidator:
    """
    Comprehensive validation utilities for phone verification.
    
    This class provides validation for verification codes, phone numbers,
    and verification results to ensure data integrity and security in
    automated account creation processes.
    """
    
    # Common verification code patterns
    CODE_PATTERNS = {
        CodeType.GOOGLE: [
            r'G-(\d{6})',  # G-123456
            r'Google.*?(\d{6})',  # Google verification code: 123456
            r'(\d{6}).*?Google',  # 123456 is your Google verification code
            r'verification.*?code.*?(\d{6})',  # Your verification code is 123456
            r'(\d{6})',  # Simple 6-digit code
        ],
        CodeType.NUMERIC: [
            r'(\d{4,8})',  # 4-8 digit codes
        ],
        CodeType.ALPHANUMERIC: [
            r'([A-Z0-9]{4,8})',  # 4-8 character alphanumeric codes
        ]
    }
    
    # Suspicious patterns that might indicate spam or invalid messages
    SUSPICIOUS_PATTERNS = [
        r'spam',
        r'advertisement',
        r'promotion',
        r'click.*?link',
        r'download.*?app',
        r'congratulations',
        r'winner',
        r'prize',
        r'free.*?gift'
    ]
    
    def __init__(self):
        """Initialize the verification validator."""
        self.validation_history: List[Dict[str, Any]] = []
        logger.info("VerificationValidator initialized")

    def validate_verification_code(self, 
                                 message: str, 
                                 expected_service: str = "google",
                                 strict_mode: bool = True) -> CodeValidationResult:
        """
        Validate and extract verification code from SMS message.
        
        Args:
            message: SMS message text
            expected_service: Expected service type (google, etc.)
            strict_mode: Whether to use strict validation
            
        Returns:
            CodeValidationResult: Validation result with extracted code
        """
        try:
            if not message or not isinstance(message, str):
                return CodeValidationResult(
                    is_valid=False,
                    code_type=CodeType.UNKNOWN,
                    errors=[ValidationError("invalid_message", "Message is empty or invalid")]
                )
            
            # Clean and normalize message
            normalized_message = self._normalize_message(message)
            
            # Check for suspicious content
            if self._is_suspicious_message(normalized_message):
                return CodeValidationResult(
                    is_valid=False,
                    code_type=CodeType.UNKNOWN,
                    errors=[ValidationError("suspicious_content", "Message contains suspicious content")],
                    warnings=[ValidationError("spam_detected", "Message may be spam", severity="warning")]
                )
            
            # Extract verification code based on expected service
            if expected_service.lower() == "google":
                result = self._extract_google_code(normalized_message, strict_mode)
            else:
                result = self._extract_generic_code(normalized_message, strict_mode)
            
            # Additional validation
            if result.is_valid and result.normalized_code:
                result = self._validate_code_format(result, expected_service, strict_mode)
            
            # Log validation attempt
            self._log_validation_attempt(message, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Verification code validation failed: {e}")
            return CodeValidationResult(
                is_valid=False,
                code_type=CodeType.UNKNOWN,
                errors=[ValidationError("validation_error", f"Validation failed: {str(e)}")]
            )

    def validate_phone_number(self, 
                            phone_number: str, 
                            country_hint: Optional[str] = None) -> PhoneValidationResult:
        """
        Validate phone number format and extract information.
        
        Args:
            phone_number: Phone number to validate
            country_hint: Country code hint for parsing
            
        Returns:
            PhoneValidationResult: Validation result with phone info
        """
        try:
            if not phone_number or not isinstance(phone_number, str):
                return PhoneValidationResult(
                    is_valid=False,
                    errors=[ValidationError("invalid_phone", "Phone number is empty or invalid")]
                )
            
            # Clean phone number
            cleaned_number = self._clean_phone_number(phone_number)
            
            try:
                # Parse phone number
                parsed_number = phonenumbers.parse(cleaned_number, country_hint)
                
                # Validate number
                if not phonenumbers.is_valid_number(parsed_number):
                    return PhoneValidationResult(
                        is_valid=False,
                        errors=[ValidationError("invalid_format", "Phone number format is invalid")]
                    )
                
                # Extract information
                country_code = phonenumbers.region_code_for_number(parsed_number)
                formatted_number = phonenumbers.format_number(parsed_number, PhoneNumberFormat.E164)
                
                # Get additional info
                carrier = None
                line_type = None
                try:
                    from phonenumbers import carrier as phone_carrier
                    from phonenumbers import geocoder
                    
                    carrier = phone_carrier.name_for_number(parsed_number, "en")
                    line_type = phonenumbers.number_type(parsed_number).name
                except ImportError:
                    logger.debug("Phone number carrier/geocoder not available")
                
                result = PhoneValidationResult(
                    is_valid=True,
                    formatted_number=formatted_number,
                    country_code=country_code,
                    country_name=self._get_country_name(country_code),
                    carrier=carrier,
                    line_type=line_type
                )
                
                # Add warnings for potential issues
                if line_type and line_type in ['VOIP', 'TOLL_FREE']:
                    result.warnings.append(
                        ValidationError("line_type_warning", f"Phone line type is {line_type}", severity="warning")
                    )
                
                return result
                
            except NumberParseException as e:
                return PhoneValidationResult(
                    is_valid=False,
                    errors=[ValidationError("parse_error", f"Failed to parse phone number: {e.error_type.name}")]
                )
                
        except Exception as e:
            logger.error(f"Phone number validation failed: {e}")
            return PhoneValidationResult(
                is_valid=False,
                errors=[ValidationError("validation_error", f"Validation failed: {str(e)}")]
            )

    def validate_verification_timing(self, 
                                   request_time: float, 
                                   received_time: float,
                                   max_delay: int = 600) -> ValidationResult:
        """
        Validate verification timing to detect potential issues.
        
        Args:
            request_time: When verification was requested (timestamp)
            received_time: When verification was received (timestamp)
            max_delay: Maximum acceptable delay in seconds
            
        Returns:
            ValidationResult: Timing validation result
        """
        try:
            if request_time <= 0 or received_time <= 0:
                return ValidationResult.INVALID
            
            delay = received_time - request_time
            
            if delay < 0:
                # Received before requested - suspicious
                return ValidationResult.SUSPICIOUS
            elif delay > max_delay:
                # Too long delay - might be expired
                return ValidationResult.EXPIRED
            elif delay < 5:
                # Very fast - might be suspicious
                return ValidationResult.SUSPICIOUS
            else:
                return ValidationResult.VALID
                
        except Exception as e:
            logger.error(f"Timing validation failed: {e}")
            return ValidationResult.INVALID

    def _normalize_message(self, message: str) -> str:
        """Normalize SMS message for processing."""
        # Remove extra whitespace and normalize
        normalized = ' '.join(message.split())
        
        # Remove common SMS artifacts
        normalized = re.sub(r'[\r\n\t]+', ' ', normalized)
        normalized = re.sub(r'[^\w\s\-\.\:\(\)]+', ' ', normalized)
        
        return normalized.strip()

    def _is_suspicious_message(self, message: str) -> bool:
        """Check if message contains suspicious content."""
        message_lower = message.lower()
        
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        
        return False

    def _extract_google_code(self, message: str, strict_mode: bool) -> CodeValidationResult:
        """Extract Google verification code from message."""
        for pattern in self.CODE_PATTERNS[CodeType.GOOGLE]:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                code = match.group(1) if match.groups() else match.group(0)
                
                # Validate Google code format (6 digits)
                if re.match(r'^\d{6}$', code):
                    return CodeValidationResult(
                        is_valid=True,
                        code_type=CodeType.GOOGLE,
                        normalized_code=code,
                        confidence=0.9
                    )
        
        # Fallback to generic extraction if not strict
        if not strict_mode:
            return self._extract_generic_code(message, strict_mode)
        
        return CodeValidationResult(
            is_valid=False,
            code_type=CodeType.UNKNOWN,
            errors=[ValidationError("no_code_found", "No valid Google verification code found")]
        )

    def _extract_generic_code(self, message: str, strict_mode: bool) -> CodeValidationResult:
        """Extract generic verification code from message."""
        # Try numeric codes first
        for pattern in self.CODE_PATTERNS[CodeType.NUMERIC]:
            matches = re.findall(pattern, message)
            for code in matches:
                if 4 <= len(code) <= 8:  # Reasonable code length
                    return CodeValidationResult(
                        is_valid=True,
                        code_type=CodeType.NUMERIC,
                        normalized_code=code,
                        confidence=0.7
                    )
        
        # Try alphanumeric if not strict
        if not strict_mode:
            for pattern in self.CODE_PATTERNS[CodeType.ALPHANUMERIC]:
                matches = re.findall(pattern, message, re.IGNORECASE)
                for code in matches:
                    if 4 <= len(code) <= 8:
                        return CodeValidationResult(
                            is_valid=True,
                            code_type=CodeType.ALPHANUMERIC,
                            normalized_code=code.upper(),
                            confidence=0.5
                        )
        
        return CodeValidationResult(
            is_valid=False,
            code_type=CodeType.UNKNOWN,
            errors=[ValidationError("no_code_found", "No valid verification code found")]
        )

    def _validate_code_format(self, 
                            result: CodeValidationResult, 
                            expected_service: str, 
                            strict_mode: bool) -> CodeValidationResult:
        """Additional validation of extracted code format."""
        if not result.normalized_code:
            return result
        
        code = result.normalized_code
        
        # Service-specific validation
        if expected_service.lower() == "google":
            if not re.match(r'^\d{6}$', code):
                result.errors.append(
                    ValidationError("invalid_google_format", "Google codes must be 6 digits")
                )
                result.is_valid = False
        
        # General format checks
        if len(code) < 4:
            result.errors.append(
                ValidationError("code_too_short", "Verification code is too short")
            )
            result.is_valid = False
        elif len(code) > 8:
            result.errors.append(
                ValidationError("code_too_long", "Verification code is too long")
            )
            result.is_valid = False
        
        # Check for obviously invalid codes
        if code in ['0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999']:
            result.warnings.append(
                ValidationError("suspicious_pattern", "Code has suspicious pattern", severity="warning")
            )
            result.confidence *= 0.5
        
        return result

    def _clean_phone_number(self, phone_number: str) -> str:
        """Clean phone number for parsing."""
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.\+]+', '', phone_number)
        
        # Add + prefix if missing and starts with country code
        if not cleaned.startswith('+') and len(cleaned) > 10:
            cleaned = '+' + cleaned
        
        return cleaned

    def _get_country_name(self, country_code: str) -> Optional[str]:
        """Get country name from country code."""
        country_names = {
            'US': 'United States',
            'CA': 'Canada',
            'GB': 'United Kingdom',
            'DE': 'Germany',
            'FR': 'France',
            'IT': 'Italy',
            'ES': 'Spain',
            'RU': 'Russia',
            'CN': 'China',
            'JP': 'Japan',
            'KR': 'South Korea',
            'IN': 'India',
            'BR': 'Brazil',
            'AU': 'Australia',
            'NL': 'Netherlands',
            'SE': 'Sweden',
            'NO': 'Norway',
            'DK': 'Denmark',
            'FI': 'Finland',
            'PL': 'Poland',
            'CZ': 'Czech Republic',
            'HU': 'Hungary',
            'RO': 'Romania',
            'BG': 'Bulgaria',
            'HR': 'Croatia',
            'SI': 'Slovenia',
            'SK': 'Slovakia',
            'LT': 'Lithuania',
            'LV': 'Latvia',
            'EE': 'Estonia'
        }
        return country_names.get(country_code, country_code)

    def _log_validation_attempt(self, message: str, result: CodeValidationResult) -> None:
        """Log validation attempt for analysis."""
        try:
            log_entry = {
                'timestamp': time.time(),
                'message_length': len(message),
                'is_valid': result.is_valid,
                'code_type': result.code_type.value,
                'confidence': result.confidence,
                'error_count': len(result.errors),
                'warning_count': len(result.warnings)
            }
            
            self.validation_history.append(log_entry)
            
            # Keep only recent history
            if len(self.validation_history) > 1000:
                self.validation_history = self.validation_history[-500:]
                
        except Exception as e:
            logger.error(f"Failed to log validation attempt: {e}")

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        try:
            if not self.validation_history:
                return {'total_validations': 0}
            
            total = len(self.validation_history)
            valid = sum(1 for entry in self.validation_history if entry['is_valid'])
            
            code_types = {}
            for entry in self.validation_history:
                code_type = entry['code_type']
                code_types[code_type] = code_types.get(code_type, 0) + 1
            
            avg_confidence = sum(entry['confidence'] for entry in self.validation_history) / total
            
            return {
                'total_validations': total,
                'valid_validations': valid,
                'success_rate': valid / total if total > 0 else 0,
                'code_type_distribution': code_types,
                'average_confidence': avg_confidence,
                'recent_validations': self.validation_history[-10:]
            }
            
        except Exception as e:
            logger.error(f"Failed to get validation stats: {e}")
            return {'error': str(e)}

# Utility functions for common validation tasks

def validate_google_code(message: str, strict: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Quick validation for Google verification codes.
    
    Args:
        message: SMS message
        strict: Whether to use strict validation
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, extracted_code)
    """
    validator = VerificationValidator()
    result = validator.validate_verification_code(message, "google", strict)
    return result.is_valid, result.normalized_code

def validate_phone_format(phone_number: str, country: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Quick phone number format validation.
    
    Args:
        phone_number: Phone number to validate
        country: Country hint
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, formatted_number)
    """
    validator = VerificationValidator()
    result = validator.validate_phone_number(phone_number, country)
    return result.is_valid, result.formatted_number

def is_verification_code_valid(code: str, code_type: str = "google") -> bool:
    """
    Simple verification code format check.
    
    Args:
        code: Verification code
        code_type: Type of code (google, numeric, etc.)
        
    Returns:
        bool: True if code format is valid
    """
    if not code or not isinstance(code, str):
        return False
    
    if code_type.lower() == "google":
        return bool(re.match(r'^\d{6}$', code))
    elif code_type.lower() == "numeric":
        return bool(re.match(r'^\d{4,8}$', code))
    elif code_type.lower() == "alphanumeric":
        return bool(re.match(r'^[A-Z0-9]{4,8}$', code.upper()))
    
    return False 