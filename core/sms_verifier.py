#!/usr/bin/env python3

"""
SMS Verifier - SMS verification module for Google Account Creation

This module provides comprehensive SMS verification functionality using 5sim.net API,
including phone number acquisition, SMS reception, and verification code extraction
for automated Google account creation.

Author: Google Account Creator Team
Version: 0.1.0
"""

import asyncio
import logging
import time
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import random

import requests
import aiohttp

# Configure logging
logger = logging.getLogger(__name__)

class SMSStatus(Enum):
    """SMS verification status."""
    PENDING = "pending"
    RECEIVED = "received"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"

class ServiceType(Enum):
    """Supported services for SMS verification."""
    GOOGLE = "google"
    GMAIL = "gmail"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    DISCORD = "discord"

@dataclass
class PhoneNumber:
    """Represents a phone number for SMS verification."""
    id: str
    number: str
    country_code: str
    country_name: str
    service: ServiceType
    cost: float
    status: SMSStatus = SMSStatus.PENDING
    created_at: float = 0.0
    sms_received_at: Optional[float] = None
    verification_code: Optional[str] = None
    full_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

@dataclass
class SMSConfig:
    """SMS verification configuration."""
    api_key: str
    api_endpoint: str = "https://5sim.net/v1"
    default_timeout: int = 300  # 5 minutes
    check_interval: int = 10    # Check SMS every 10 seconds
    max_retries: int = 3
    retry_delay: int = 5
    preferred_countries: List[str] = None
    
    def __post_init__(self):
        if self.preferred_countries is None:
            self.preferred_countries = ["russia", "poland", "estonia", "lithuania"]

class SMSError(Exception):
    """Custom exception for SMS verification operations."""
    pass

class SMSVerifier:
    """
    Comprehensive SMS verifier for 5sim.net integration.
    
    Handles phone number acquisition, SMS reception monitoring,
    and verification code extraction for account creation automation.
    """
    
    def __init__(self, config: SMSConfig):
        """
        Initialize the SMS verifier.
        
        Args:
            config: SMS verification configuration
        """
        self.config = config
        self.active_numbers: Dict[str, PhoneNumber] = {}
        self.verification_history: List[PhoneNumber] = []
        
        # Session for API calls
        self.api_session = requests.Session()
        self.api_session.headers.update({
            'Authorization': f'Bearer {config.api_key}',
            'Accept': 'application/json',
            'User-Agent': 'GoogleAccountCreator/1.0'
        })
        
        # Performance metrics
        self.metrics = {
            'total_numbers_requested': 0,
            'successful_verifications': 0,
            'failed_verifications': 0,
            'timeout_count': 0,
            'avg_verification_time': 0.0,
            'success_rate': 0.0
        }
        
        # Cache for country/service availability
        self._availability_cache = {}
        self._cache_expiry = 0
        
        logger.info("SMSVerifier initialized")

    async def initialize(self) -> bool:
        """
        Initialize the SMS verifier and verify API connectivity.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing SMS verifier...")
            
            # Verify API connectivity and balance
            if not await self._verify_api_connection():
                raise SMSError("Failed to verify API connection")
            
            # Load available countries and services
            await self._update_availability_cache()
            
            logger.info("SMS verifier initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"SMS verifier initialization failed: {e}")
            return False

    async def _verify_api_connection(self) -> bool:
        """Verify connectivity to the 5sim.net API."""
        try:
            logger.debug("Verifying API connection...")
            
            response = self.api_session.get(
                f"{self.config.api_endpoint}/user/profile",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                profile_info = response.json()
                balance = profile_info.get('balance', 0)
                email = profile_info.get('email', 'unknown')
                
                logger.info(f"API connection verified for user: {email} (Balance: ${balance})")
                
                if balance < 1.0:
                    logger.warning(f"Low balance: ${balance} - consider adding funds")
                
                return True
            else:
                logger.error(f"API verification failed with status: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"API connection verification failed: {e}")
            return False

    async def _update_availability_cache(self) -> None:
        """Update the cache of available countries and services."""
        try:
            current_time = time.time()
            
            # Cache expires after 1 hour
            if current_time - self._cache_expiry > 3600:
                logger.debug("Updating availability cache...")
                
                response = self.api_session.get(
                    f"{self.config.api_endpoint}/guest/countries",
                    timeout=self.config.default_timeout
                )
                
                if response.status_code == 200:
                    countries_data = response.json()
                    
                    # Get service prices for each country
                    for country, country_info in countries_data.items():
                        if country in self.config.preferred_countries:
                            self._availability_cache[country] = country_info
                    
                    self._cache_expiry = current_time
                    logger.debug(f"Availability cache updated with {len(self._availability_cache)} countries")
                else:
                    logger.warning(f"Failed to update availability cache: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Availability cache update failed: {e}")

    async def get_available_countries(self, service: ServiceType = ServiceType.GOOGLE) -> List[Dict[str, Any]]:
        """
        Get list of available countries for SMS verification.
        
        Args:
            service: Service type for verification
            
        Returns:
            List[Dict[str, Any]]: Available countries with pricing info
        """
        try:
            await self._update_availability_cache()
            
            available_countries = []
            
            for country, country_info in self._availability_cache.items():
                services = country_info.get('services', {})
                service_name = service.value
                
                if service_name in services:
                    service_info = services[service_name]
                    
                    available_countries.append({
                        'country': country,
                        'country_name': country_info.get('name', country),
                        'service': service_name,
                        'cost': service_info.get('cost', 0),
                        'count': service_info.get('count', 0)
                    })
            
            # Sort by cost (cheapest first)
            available_countries.sort(key=lambda x: x['cost'])
            
            logger.debug(f"Found {len(available_countries)} available countries for {service.value}")
            return available_countries
            
        except Exception as e:
            logger.error(f"Failed to get available countries: {e}")
            return []

    async def request_phone_number(self, service: ServiceType = ServiceType.GOOGLE, 
                                 preferred_country: Optional[str] = None) -> Optional[PhoneNumber]:
        """
        Request a phone number for SMS verification.
        
        Args:
            service: Service type for verification
            preferred_country: Preferred country code (optional)
            
        Returns:
            PhoneNumber: Requested phone number or None if failed
        """
        try:
            logger.info(f"Requesting phone number for {service.value}")
            
            # Get available countries
            available_countries = await self.get_available_countries(service)
            
            if not available_countries:
                raise SMSError("No available countries for the specified service")
            
            # Select country
            selected_country = None
            if preferred_country:
                selected_country = next(
                    (c for c in available_countries if c['country'] == preferred_country), 
                    None
                )
            
            if not selected_country:
                # Choose cheapest available country
                selected_country = available_countries[0]
            
            logger.info(f"Selected country: {selected_country['country_name']} (${selected_country['cost']})")
            
            # Request phone number
            request_data = {
                'country': selected_country['country'],
                'service': service.value
            }
            
            response = self.api_session.post(
                f"{self.config.api_endpoint}/user/buy/activation/{selected_country['country']}/{service.value}",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                activation_data = response.json()
                
                phone_number = PhoneNumber(
                    id=str(activation_data['id']),
                    number=activation_data['phone'],
                    country_code=selected_country['country'],
                    country_name=selected_country['country_name'],
                    service=service,
                    cost=selected_country['cost'],
                    status=SMSStatus.PENDING
                )
                
                self.active_numbers[phone_number.id] = phone_number
                self.metrics['total_numbers_requested'] += 1
                
                logger.info(f"Phone number acquired: {phone_number.number} (ID: {phone_number.id})")
                return phone_number
            else:
                error_text = response.text
                logger.error(f"Phone number request failed: {response.status_code} - {error_text}")
                return None
                
        except Exception as e:
            logger.error(f"Phone number request failed: {e}")
            return None

    async def wait_for_sms(self, phone_number: PhoneNumber, 
                          timeout: Optional[int] = None) -> Optional[str]:
        """
        Wait for SMS and extract verification code.
        
        Args:
            phone_number: Phone number to monitor
            timeout: Timeout in seconds (uses config default if None)
            
        Returns:
            Optional[str]: Verification code or None if timeout/error
        """
        try:
            if timeout is None:
                timeout = self.config.default_timeout
            
            logger.info(f"Waiting for SMS on {phone_number.number} (timeout: {timeout}s)")
            
            start_time = time.time()
            end_time = start_time + timeout
            
            while time.time() < end_time:
                # Check for SMS
                sms_data = await self._check_sms_status(phone_number)
                
                if sms_data:
                    phone_number.sms_received_at = time.time()
                    phone_number.full_message = sms_data.get('text', '')
                    phone_number.status = SMSStatus.RECEIVED
                    
                    # Extract verification code
                    verification_code = self._extract_verification_code(phone_number.full_message)
                    
                    if verification_code:
                        phone_number.verification_code = verification_code
                        
                        verification_time = phone_number.sms_received_at - phone_number.created_at
                        self._update_verification_metrics(verification_time, True)
                        
                        logger.info(f"SMS received with code: {verification_code}")
                        return verification_code
                    else:
                        logger.warning(f"SMS received but no code found: {phone_number.full_message}")
                
                # Wait before next check
                await asyncio.sleep(self.config.check_interval)
            
            # Timeout reached
            phone_number.status = SMSStatus.TIMEOUT
            self.metrics['timeout_count'] += 1
            self._update_verification_metrics(timeout, False)
            
            logger.warning(f"SMS timeout for {phone_number.number}")
            return None
            
        except Exception as e:
            phone_number.status = SMSStatus.ERROR
            self._update_verification_metrics(0, False)
            logger.error(f"SMS waiting failed: {e}")
            return None

    async def _check_sms_status(self, phone_number: PhoneNumber) -> Optional[Dict[str, Any]]:
        """Check SMS status for a phone number."""
        try:
            response = self.api_session.get(
                f"{self.config.api_endpoint}/user/check/{phone_number.id}",
                timeout=10
            )
            
            if response.status_code == 200:
                activation_data = response.json()
                
                if activation_data.get('sms'):
                    # SMS received
                    return activation_data['sms'][0] if activation_data['sms'] else None
                else:
                    # No SMS yet
                    return None
            else:
                logger.debug(f"SMS check returned: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"SMS status check failed: {e}")
            return None

    def _extract_verification_code(self, sms_text: str) -> Optional[str]:
        """
        Extract verification code from SMS text.
        
        Args:
            sms_text: SMS message text
            
        Returns:
            Optional[str]: Extracted verification code
        """
        try:
            if not sms_text:
                return None
            
            # Common patterns for verification codes
            patterns = [
                r'(?:code|verification|verify)[\s:]+(\d{4,8})',  # "code: 123456"
                r'(\d{6})',  # 6-digit number
                r'(\d{4})',  # 4-digit number
                r'(\d{5})',  # 5-digit number
                r'(\d{7})',  # 7-digit number
                r'(\d{8})',  # 8-digit number
                r'G-(\d{6})',  # Google format "G-123456"
                r'Your\s+code\s+is\s+(\d+)',  # "Your code is 123456"
                r'(\d+)\s+is\s+your',  # "123456 is your verification code"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, sms_text, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    logger.debug(f"Extracted code '{code}' using pattern: {pattern}")
                    return code
            
            # If no pattern matches, try to find any sequence of 4-8 digits
            digit_matches = re.findall(r'\d{4,8}', sms_text)
            if digit_matches:
                code = digit_matches[0]  # Take the first match
                logger.debug(f"Extracted code '{code}' from digit sequence")
                return code
            
            logger.warning(f"No verification code found in SMS: {sms_text}")
            return None
            
        except Exception as e:
            logger.error(f"Code extraction failed: {e}")
            return None

    async def cancel_phone_number(self, phone_number: PhoneNumber) -> bool:
        """
        Cancel a phone number request.
        
        Args:
            phone_number: Phone number to cancel
            
        Returns:
            bool: True if cancellation successful
        """
        try:
            logger.info(f"Cancelling phone number: {phone_number.number}")
            
            response = self.api_session.get(
                f"{self.config.api_endpoint}/user/cancel/{phone_number.id}",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                phone_number.status = SMSStatus.CANCELLED
                
                # Remove from active numbers
                if phone_number.id in self.active_numbers:
                    del self.active_numbers[phone_number.id]
                
                # Add to history
                self.verification_history.append(phone_number)
                
                logger.info(f"Phone number cancelled: {phone_number.number}")
                return True
            else:
                logger.error(f"Phone number cancellation failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Phone number cancellation failed: {e}")
            return False

    async def finish_verification(self, phone_number: PhoneNumber) -> bool:
        """
        Mark verification as complete.
        
        Args:
            phone_number: Phone number to finish
            
        Returns:
            bool: True if completion successful
        """
        try:
            logger.info(f"Finishing verification for: {phone_number.number}")
            
            response = self.api_session.get(
                f"{self.config.api_endpoint}/user/finish/{phone_number.id}",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                # Remove from active numbers
                if phone_number.id in self.active_numbers:
                    del self.active_numbers[phone_number.id]
                
                # Add to history
                self.verification_history.append(phone_number)
                
                logger.info(f"Verification finished: {phone_number.number}")
                return True
            else:
                logger.warning(f"Verification finish failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Verification finish failed: {e}")
            return False

    def _update_verification_metrics(self, verification_time: float, success: bool) -> None:
        """Update verification performance metrics."""
        if success:
            self.metrics['successful_verifications'] += 1
            
            # Update average verification time
            current_avg = self.metrics['avg_verification_time']
            total_success = self.metrics['successful_verifications']
            
            if total_success > 1:
                self.metrics['avg_verification_time'] = (
                    current_avg * (total_success - 1) + verification_time
                ) / total_success
            else:
                self.metrics['avg_verification_time'] = verification_time
        else:
            self.metrics['failed_verifications'] += 1
        
        # Update success rate
        total_attempts = self.metrics['successful_verifications'] + self.metrics['failed_verifications']
        if total_attempts > 0:
            self.metrics['success_rate'] = self.metrics['successful_verifications'] / total_attempts

    async def get_account_balance(self) -> Optional[float]:
        """
        Get current account balance.
        
        Returns:
            Optional[float]: Account balance or None if failed
        """
        try:
            response = self.api_session.get(
                f"{self.config.api_endpoint}/user/profile",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                profile_data = response.json()
                balance = float(profile_data.get('balance', 0))
                logger.debug(f"Account balance: ${balance}")
                return balance
            else:
                logger.error(f"Balance check failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return None

    def get_verification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get verification history.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List[Dict[str, Any]]: Verification history
        """
        try:
            # Combine active and historical numbers
            all_numbers = list(self.active_numbers.values()) + self.verification_history
            
            # Sort by creation time (newest first)
            all_numbers.sort(key=lambda x: x.created_at, reverse=True)
            
            # Limit results
            limited_numbers = all_numbers[:limit]
            
            return [asdict(phone_number) for phone_number in limited_numbers]
            
        except Exception as e:
            logger.error(f"Failed to get verification history: {e}")
            return []

    def get_metrics(self) -> Dict[str, Any]:
        """Get SMS verification performance metrics."""
        return self.metrics.copy()

    async def cleanup_active_numbers(self) -> None:
        """Cancel all active phone numbers."""
        try:
            logger.info("Cleaning up active phone numbers...")
            
            cancel_tasks = []
            for phone_number in list(self.active_numbers.values()):
                if phone_number.status == SMSStatus.PENDING:
                    cancel_tasks.append(self.cancel_phone_number(phone_number))
            
            if cancel_tasks:
                await asyncio.gather(*cancel_tasks, return_exceptions=True)
            
            logger.info("Active phone numbers cleaned up")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the SMS verifier.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            health_info = {
                'status': 'healthy',
                'active_numbers': len(self.active_numbers),
                'api_connectivity': False,
                'account_balance': 0.0,
                'average_response_time': 0.0,
                'issues': []
            }
            
            # Test API connectivity and get balance
            start_time = time.time()
            try:
                balance = await self.get_account_balance()
                health_info['api_connectivity'] = balance is not None
                health_info['account_balance'] = balance or 0.0
                health_info['average_response_time'] = time.time() - start_time
                
                if balance and balance < 1.0:
                    health_info['issues'].append(f"Low account balance: ${balance}")
                    health_info['status'] = 'degraded'
                    
            except Exception as e:
                health_info['issues'].append(f"API connectivity issue: {e}")
                health_info['status'] = 'degraded'
            
            # Check for stuck numbers
            current_time = time.time()
            stuck_numbers = [
                pn for pn in self.active_numbers.values()
                if current_time - pn.created_at > self.config.default_timeout * 2
            ]
            
            if stuck_numbers:
                health_info['issues'].append(f"{len(stuck_numbers)} numbers stuck in pending state")
                health_info['status'] = 'degraded'
            
            return health_info
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'issues': [f"Health check failed: {e}"]
            }

    def __del__(self):
        """Cleanup on destruction."""
        try:
            # Try to cancel active numbers synchronously
            for phone_number in self.active_numbers.values():
                if phone_number.status == SMSStatus.PENDING:
                    try:
                        self.api_session.get(
                            f"{self.config.api_endpoint}/user/cancel/{phone_number.id}",
                            timeout=5
                        )
                    except Exception:
                        pass  # Ignore errors during cleanup
        except Exception:
            pass  # Ignore all errors in destructor 