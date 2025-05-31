#!/usr/bin/env python3

"""
Phone Verification - High-level interface for phone number verification

This module provides a simplified, high-level interface for phone number
verification using the SMS verification system. It handles the complete
verification workflow for automated Google account creation.

Author: Google Account Creator Team
Version: 0.1.0
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import json

from .sms_verifier import SMSVerifier, SMSConfig, PhoneNumber, ServiceType, SMSStatus

# Configure logging
logger = logging.getLogger(__name__)

class VerificationResult(Enum):
    """Phone verification result status."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    NO_NUMBERS_AVAILABLE = "no_numbers_available"

@dataclass
class VerificationRequest:
    """Represents a phone verification request."""
    service: ServiceType = ServiceType.GOOGLE
    preferred_country: Optional[str] = None
    timeout: int = 300  # 5 minutes
    max_retries: int = 3
    retry_delay: int = 30  # 30 seconds between retries
    
@dataclass
class VerificationResponse:
    """Represents the result of a phone verification."""
    result: VerificationResult
    phone_number: Optional[str] = None
    verification_code: Optional[str] = None
    country: Optional[str] = None
    cost: Optional[float] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0

class PhoneVerificationInterface:
    """
    High-level interface for phone number verification.
    
    This class provides a simplified API for requesting phone numbers,
    waiting for SMS verification codes, and handling the complete
    verification workflow for automated account creation.
    """
    
    def __init__(self, sms_config: SMSConfig):
        """
        Initialize the phone verification interface.
        
        Args:
            sms_config: SMS verification configuration
        """
        self.sms_verifier = SMSVerifier(sms_config)
        self.config = sms_config
        self.is_initialized = False
        
        # Callbacks for status updates
        self.on_number_requested: Optional[Callable[[str, str], None]] = None
        self.on_sms_waiting: Optional[Callable[[str], None]] = None
        self.on_sms_received: Optional[Callable[[str, str], None]] = None
        self.on_verification_complete: Optional[Callable[[str, str], None]] = None
        self.on_error: Optional[Callable[[str, str], None]] = None
        
        logger.info("PhoneVerificationInterface initialized")

    async def initialize(self) -> bool:
        """
        Initialize the verification interface.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            if not self.is_initialized:
                success = await self.sms_verifier.initialize()
                if success:
                    self.is_initialized = True
                    logger.info("Phone verification interface initialized successfully")
                else:
                    logger.error("Failed to initialize SMS verifier")
                return success
            return True
            
        except Exception as e:
            logger.error(f"Phone verification interface initialization failed: {e}")
            return False

    async def verify_phone_number(self, request: VerificationRequest) -> VerificationResponse:
        """
        Complete phone number verification workflow.
        
        Args:
            request: Verification request parameters
            
        Returns:
            VerificationResponse: Complete verification result
        """
        start_time = time.time()
        
        try:
            if not self.is_initialized:
                if not await self.initialize():
                    return VerificationResponse(
                        result=VerificationResult.ERROR,
                        error_message="Failed to initialize verification interface"
                    )
            
            logger.info(f"Starting phone verification for {request.service.value}")
            
            # Check account balance first
            balance = await self.sms_verifier.get_account_balance()
            if balance is None or balance < 0.5:  # Minimum balance check
                return VerificationResponse(
                    result=VerificationResult.INSUFFICIENT_BALANCE,
                    error_message=f"Insufficient balance: ${balance or 0}"
                )
            
            # Attempt verification with retries
            for attempt in range(request.max_retries):
                try:
                    logger.info(f"Verification attempt {attempt + 1}/{request.max_retries}")
                    
                    # Request phone number
                    phone_number = await self._request_phone_number(request)
                    if not phone_number:
                        if attempt < request.max_retries - 1:
                            logger.warning(f"Phone number request failed, retrying in {request.retry_delay}s...")
                            await asyncio.sleep(request.retry_delay)
                            continue
                        else:
                            return VerificationResponse(
                                result=VerificationResult.NO_NUMBERS_AVAILABLE,
                                error_message="No phone numbers available",
                                retry_count=attempt + 1
                            )
                    
                    # Wait for SMS
                    verification_code = await self._wait_for_verification(phone_number, request.timeout)
                    
                    if verification_code:
                        # Success - finish verification
                        await self.sms_verifier.finish_verification(phone_number)
                        
                        duration = time.time() - start_time
                        
                        if self.on_verification_complete:
                            self.on_verification_complete(phone_number.number, verification_code)
                        
                        return VerificationResponse(
                            result=VerificationResult.SUCCESS,
                            phone_number=phone_number.number,
                            verification_code=verification_code,
                            country=phone_number.country_name,
                            cost=phone_number.cost,
                            duration=duration,
                            retry_count=attempt
                        )
                    else:
                        # Timeout or error - cancel number and retry
                        await self.sms_verifier.cancel_phone_number(phone_number)
                        
                        if attempt < request.max_retries - 1:
                            logger.warning(f"SMS timeout, retrying in {request.retry_delay}s...")
                            await asyncio.sleep(request.retry_delay)
                        else:
                            return VerificationResponse(
                                result=VerificationResult.TIMEOUT,
                                error_message="SMS verification timeout after all retries",
                                retry_count=attempt + 1
                            )
                
                except Exception as e:
                    logger.error(f"Verification attempt {attempt + 1} failed: {e}")
                    
                    if attempt < request.max_retries - 1:
                        await asyncio.sleep(request.retry_delay)
                    else:
                        return VerificationResponse(
                            result=VerificationResult.ERROR,
                            error_message=str(e),
                            retry_count=attempt + 1
                        )
            
            # Should not reach here
            return VerificationResponse(
                result=VerificationResult.ERROR,
                error_message="Unexpected verification failure"
            )
            
        except Exception as e:
            logger.error(f"Phone verification failed: {e}")
            
            if self.on_error:
                self.on_error("verification_failed", str(e))
            
            return VerificationResponse(
                result=VerificationResult.ERROR,
                error_message=str(e),
                duration=time.time() - start_time
            )

    async def _request_phone_number(self, request: VerificationRequest) -> Optional[PhoneNumber]:
        """Request a phone number for verification."""
        try:
            logger.debug(f"Requesting phone number for {request.service.value}")
            
            phone_number = await self.sms_verifier.request_phone_number(
                service=request.service,
                preferred_country=request.preferred_country
            )
            
            if phone_number:
                logger.info(f"Phone number acquired: {phone_number.number} ({phone_number.country_name})")
                
                if self.on_number_requested:
                    self.on_number_requested(phone_number.number, phone_number.country_name)
                
                return phone_number
            else:
                logger.warning("Failed to acquire phone number")
                return None
                
        except Exception as e:
            logger.error(f"Phone number request failed: {e}")
            return None

    async def _wait_for_verification(self, phone_number: PhoneNumber, timeout: int) -> Optional[str]:
        """Wait for SMS verification code."""
        try:
            logger.info(f"Waiting for SMS on {phone_number.number} (timeout: {timeout}s)")
            
            if self.on_sms_waiting:
                self.on_sms_waiting(phone_number.number)
            
            verification_code = await self.sms_verifier.wait_for_sms(phone_number, timeout)
            
            if verification_code:
                logger.info(f"SMS verification code received: {verification_code}")
                
                if self.on_sms_received:
                    self.on_sms_received(phone_number.number, verification_code)
                
                return verification_code
            else:
                logger.warning(f"SMS timeout for {phone_number.number}")
                return None
                
        except Exception as e:
            logger.error(f"SMS waiting failed: {e}")
            return None

    async def get_available_countries(self, service: ServiceType = ServiceType.GOOGLE) -> List[Dict[str, Any]]:
        """
        Get list of available countries for phone verification.
        
        Args:
            service: Service type for verification
            
        Returns:
            List[Dict[str, Any]]: Available countries with pricing
        """
        try:
            if not self.is_initialized:
                await self.initialize()
            
            return await self.sms_verifier.get_available_countries(service)
            
        except Exception as e:
            logger.error(f"Failed to get available countries: {e}")
            return []

    async def check_account_balance(self) -> Optional[float]:
        """
        Check current account balance.
        
        Returns:
            Optional[float]: Account balance or None if failed
        """
        try:
            if not self.is_initialized:
                await self.initialize()
            
            return await self.sms_verifier.get_account_balance()
            
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return None

    def set_callbacks(self, 
                     on_number_requested: Optional[Callable[[str, str], None]] = None,
                     on_sms_waiting: Optional[Callable[[str], None]] = None,
                     on_sms_received: Optional[Callable[[str, str], None]] = None,
                     on_verification_complete: Optional[Callable[[str, str], None]] = None,
                     on_error: Optional[Callable[[str, str], None]] = None) -> None:
        """
        Set callback functions for verification events.
        
        Args:
            on_number_requested: Called when phone number is acquired (number, country)
            on_sms_waiting: Called when waiting for SMS (number)
            on_sms_received: Called when SMS is received (number, code)
            on_verification_complete: Called when verification is complete (number, code)
            on_error: Called on error (error_type, message)
        """
        self.on_number_requested = on_number_requested
        self.on_sms_waiting = on_sms_waiting
        self.on_sms_received = on_sms_received
        self.on_verification_complete = on_verification_complete
        self.on_error = on_error
        
        logger.debug("Verification callbacks configured")

    async def cancel_all_active_verifications(self) -> None:
        """Cancel all active phone number verifications."""
        try:
            await self.sms_verifier.cleanup_active_numbers()
            logger.info("All active verifications cancelled")
            
        except Exception as e:
            logger.error(f"Failed to cancel active verifications: {e}")

    def get_verification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get verification history.
        
        Args:
            limit: Maximum number of records
            
        Returns:
            List[Dict[str, Any]]: Verification history
        """
        try:
            return self.sms_verifier.get_verification_history(limit)
            
        except Exception as e:
            logger.error(f"Failed to get verification history: {e}")
            return []

    def get_metrics(self) -> Dict[str, Any]:
        """Get verification performance metrics."""
        try:
            return self.sms_verifier.get_metrics()
            
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the verification system.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            if not self.is_initialized:
                return {
                    'status': 'not_initialized',
                    'issues': ['Verification interface not initialized']
                }
            
            return await self.sms_verifier.health_check()
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'issues': [f"Health check failed: {e}"]
            }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cancel_all_active_verifications()

# Convenience functions for simple use cases

async def verify_phone_for_google(api_key: str, 
                                preferred_country: Optional[str] = None,
                                timeout: int = 300) -> VerificationResponse:
    """
    Convenience function for Google account phone verification.
    
    Args:
        api_key: 5sim.net API key
        preferred_country: Preferred country code
        timeout: Verification timeout in seconds
        
    Returns:
        VerificationResponse: Verification result
    """
    config = SMSConfig(api_key=api_key)
    interface = PhoneVerificationInterface(config)
    
    request = VerificationRequest(
        service=ServiceType.GOOGLE,
        preferred_country=preferred_country,
        timeout=timeout
    )
    
    try:
        return await interface.verify_phone_number(request)
    finally:
        await interface.cancel_all_active_verifications()

async def get_verification_countries(api_key: str, 
                                   service: ServiceType = ServiceType.GOOGLE) -> List[Dict[str, Any]]:
    """
    Convenience function to get available countries.
    
    Args:
        api_key: 5sim.net API key
        service: Service type
        
    Returns:
        List[Dict[str, Any]]: Available countries
    """
    config = SMSConfig(api_key=api_key)
    interface = PhoneVerificationInterface(config)
    
    try:
        return await interface.get_available_countries(service)
    finally:
        await interface.cancel_all_active_verifications()

async def check_sms_balance(api_key: str) -> Optional[float]:
    """
    Convenience function to check account balance.
    
    Args:
        api_key: 5sim.net API key
        
    Returns:
        Optional[float]: Account balance
    """
    config = SMSConfig(api_key=api_key)
    interface = PhoneVerificationInterface(config)
    
    try:
        return await interface.check_account_balance()
    finally:
        await interface.cancel_all_active_verifications() 