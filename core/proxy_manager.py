#!/usr/bin/env python3

"""
Proxy Manager - VPN and Proxy Management module for Google Account Creation

This module provides comprehensive proxy/VPN functionality using BrightProxy services,
including session management, IP rotation, and WebRTC leak prevention for automated
Google account creation with enhanced anonymity.

Author: Google Account Creator Team
Version: 0.1.0
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import random

import requests
import aiohttp
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)

class ProxyType(Enum):
    """Supported proxy types."""
    HTTP = "http"
    HTTPS = "https" 
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"

class ProxyStatus(Enum):
    """Proxy connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ROTATING = "rotating"
    ERROR = "error"

@dataclass
class ProxySession:
    """Represents a proxy session configuration."""
    session_id: str
    endpoint: str
    port: int
    username: str
    password: str
    proxy_type: ProxyType
    country: Optional[str] = None
    city: Optional[str] = None
    current_ip: Optional[str] = None
    status: ProxyStatus = ProxyStatus.DISCONNECTED
    created_at: float = 0.0
    last_rotation: float = 0.0
    rotation_count: int = 0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

@dataclass
class ProxyConfig:
    """Proxy configuration settings."""
    api_key: str
    api_endpoint: str = "https://api.brightdata.com"
    max_concurrent_sessions: int = 5
    default_timeout: int = 30
    rotation_interval: int = 300  # 5 minutes
    max_retries: int = 3
    retry_delay: int = 5
    enable_webrtc_protection: bool = True
    preferred_countries: List[str] = None
    
    def __post_init__(self):
        if self.preferred_countries is None:
            self.preferred_countries = ["US", "CA", "GB", "DE", "FR"]

class ProxyError(Exception):
    """Custom exception for proxy operations."""
    pass

class ProxyManager:
    """
    Comprehensive proxy manager for BrightProxy integration.
    
    Handles session management, IP rotation, WebRTC leak prevention,
    and provides high-level proxy operations for account creation automation.
    """
    
    def __init__(self, config: ProxyConfig):
        """
        Initialize the proxy manager.
        
        Args:
            config: Proxy configuration settings
        """
        self.config = config
        self.sessions: Dict[str, ProxySession] = {}
        self.session_pool: List[str] = []
        self.active_session_id: Optional[str] = None
        self.webrtc_blocked_domains = set()
        
        # Session for API calls
        self.api_session = requests.Session()
        self.api_session.headers.update({
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'GoogleAccountCreator/1.0'
        })
        
        # Performance metrics
        self.metrics = {
            'total_sessions_created': 0,
            'total_rotations': 0,
            'total_errors': 0,
            'avg_connection_time': 0.0,
            'success_rate': 0.0
        }
        
        logger.info("ProxyManager initialized")

    async def initialize(self) -> bool:
        """
        Initialize the proxy manager and verify API connectivity.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing proxy manager...")
            
            # Verify API connectivity
            if not await self._verify_api_connection():
                raise ProxyError("Failed to verify API connection")
            
            # Load WebRTC blocked domains
            self._load_webrtc_blocked_domains()
            
            # Initialize session pool
            await self._initialize_session_pool()
            
            logger.info("Proxy manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Proxy manager initialization failed: {e}")
            return False

    async def _verify_api_connection(self) -> bool:
        """Verify connectivity to the BrightProxy API."""
        try:
            logger.debug("Verifying API connection...")
            
            # Test endpoint to verify API connectivity
            response = self.api_session.get(
                f"{self.config.api_endpoint}/api/v1/status",
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                api_info = response.json()
                logger.info(f"API connection verified: {api_info.get('service', 'BrightProxy')}")
                return True
            else:
                logger.error(f"API verification failed with status: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"API connection verification failed: {e}")
            return False

    def _load_webrtc_blocked_domains(self) -> None:
        """Load domains known to cause WebRTC leaks."""
        # Common WebRTC leak sources
        webrtc_domains = {
            'stun.l.google.com',
            'stun1.l.google.com', 
            'stun2.l.google.com',
            'stun3.l.google.com',
            'stun4.l.google.com',
            'stun.services.mozilla.com',
            'stun.sipgate.net',
            'stun.12connect.com',
            'stun.12voip.com',
            'stun.1und1.de'
        }
        
        self.webrtc_blocked_domains.update(webrtc_domains)
        logger.debug(f"Loaded {len(self.webrtc_blocked_domains)} WebRTC blocked domains")

    async def _initialize_session_pool(self) -> None:
        """Initialize a pool of proxy sessions for rotation."""
        try:
            logger.info(f"Initializing session pool with {self.config.max_concurrent_sessions} sessions")
            
            for i in range(self.config.max_concurrent_sessions):
                session_id = f"session_{int(time.time())}_{i}"
                session = await self._create_new_session(session_id)
                
                if session:
                    self.sessions[session_id] = session
                    self.session_pool.append(session_id)
                    logger.debug(f"Created session: {session_id}")
                else:
                    logger.warning(f"Failed to create session {i+1}")
            
            logger.info(f"Session pool initialized with {len(self.session_pool)} sessions")
            
        except Exception as e:
            logger.error(f"Session pool initialization failed: {e}")

    async def _create_new_session(self, session_id: str) -> Optional[ProxySession]:
        """Create a new proxy session."""
        try:
            # Get available countries and select one
            country = random.choice(self.config.preferred_countries)
            
            # API call to create session
            session_data = {
                'session_id': session_id,
                'country': country,
                'session_type': 'rotating_residential',
                'format': 'username_password'
            }
            
            response = self.api_session.post(
                f"{self.config.api_endpoint}/api/v1/sessions",
                json=session_data,
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 201:
                session_info = response.json()
                
                session = ProxySession(
                    session_id=session_id,
                    endpoint=session_info['endpoint'],
                    port=session_info['port'],
                    username=session_info['username'],
                    password=session_info['password'],
                    proxy_type=ProxyType.HTTP,
                    country=country,
                    status=ProxyStatus.DISCONNECTED
                )
                
                self.metrics['total_sessions_created'] += 1
                logger.debug(f"Session created: {session_id} ({country})")
                return session
            else:
                logger.error(f"Failed to create session: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Session creation failed for {session_id}: {e}")
            return None

    async def get_proxy_session(self, preferred_country: Optional[str] = None) -> Optional[ProxySession]:
        """
        Get an available proxy session.
        
        Args:
            preferred_country: Preferred country code (optional)
            
        Returns:
            ProxySession: Available session or None
        """
        try:
            # Find available session
            available_sessions = [
                sid for sid in self.session_pool 
                if self.sessions[sid].status in [ProxyStatus.DISCONNECTED, ProxyStatus.CONNECTED]
            ]
            
            if not available_sessions:
                logger.warning("No available sessions, creating new one")
                new_session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"
                new_session = await self._create_new_session(new_session_id)
                
                if new_session:
                    self.sessions[new_session_id] = new_session
                    self.session_pool.append(new_session_id)
                    available_sessions = [new_session_id]
            
            # Filter by preferred country if specified
            if preferred_country:
                country_sessions = [
                    sid for sid in available_sessions
                    if self.sessions[sid].country == preferred_country
                ]
                if country_sessions:
                    available_sessions = country_sessions
            
            if available_sessions:
                session_id = random.choice(available_sessions)
                session = self.sessions[session_id]
                self.active_session_id = session_id
                return session
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get proxy session: {e}")
            return None

    async def connect_session(self, session: ProxySession) -> bool:
        """
        Connect to a proxy session.
        
        Args:
            session: Proxy session to connect
            
        Returns:
            bool: True if connection successful
        """
        try:
            logger.info(f"Connecting to session: {session.session_id}")
            start_time = time.time()
            
            session.status = ProxyStatus.CONNECTING
            
            # Test connection by making a request through the proxy
            proxy_url = f"{session.proxy_type.value}://{session.username}:{session.password}@{session.endpoint}:{session.port}"
            
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            async with aiohttp.ClientSession() as client_session:
                try:
                    async with client_session.get(
                        'https://api.ipify.org?format=json',
                        proxy=proxy_url,
                        timeout=aiohttp.ClientTimeout(total=self.config.default_timeout)
                    ) as response:
                        if response.status == 200:
                            ip_info = await response.json()
                            session.current_ip = ip_info.get('ip')
                            session.status = ProxyStatus.CONNECTED
                            
                            connection_time = time.time() - start_time
                            self._update_connection_metrics(connection_time)
                            
                            logger.info(f"Session connected: {session.session_id} (IP: {session.current_ip})")
                            return True
                        else:
                            raise ProxyError(f"Connection test failed: {response.status}")
                            
                except asyncio.TimeoutError:
                    raise ProxyError("Connection timeout")
                    
        except Exception as e:
            session.status = ProxyStatus.ERROR
            self.metrics['total_errors'] += 1
            logger.error(f"Session connection failed: {e}")
            return False

    async def rotate_ip(self, session: ProxySession) -> bool:
        """
        Rotate IP address for the given session.
        
        Args:
            session: Session to rotate IP for
            
        Returns:
            bool: True if rotation successful
        """
        try:
            logger.info(f"Rotating IP for session: {session.session_id}")
            
            session.status = ProxyStatus.ROTATING
            old_ip = session.current_ip
            
            # API call to rotate IP
            rotation_data = {
                'session_id': session.session_id,
                'action': 'rotate_ip'
            }
            
            response = self.api_session.post(
                f"{self.config.api_endpoint}/api/v1/sessions/{session.session_id}/rotate",
                json=rotation_data,
                timeout=self.config.default_timeout
            )
            
            if response.status_code == 200:
                # Verify new IP
                await asyncio.sleep(2)  # Wait for rotation to take effect
                
                if await self._verify_ip_change(session, old_ip):
                    session.last_rotation = time.time()
                    session.rotation_count += 1
                    session.status = ProxyStatus.CONNECTED
                    self.metrics['total_rotations'] += 1
                    
                    logger.info(f"IP rotated successfully: {old_ip} -> {session.current_ip}")
                    return True
                else:
                    raise ProxyError("IP rotation verification failed")
            else:
                raise ProxyError(f"Rotation API call failed: {response.status_code}")
                
        except Exception as e:
            session.status = ProxyStatus.ERROR
            self.metrics['total_errors'] += 1
            logger.error(f"IP rotation failed for {session.session_id}: {e}")
            return False

    async def _verify_ip_change(self, session: ProxySession, old_ip: str) -> bool:
        """Verify that IP address has changed after rotation."""
        try:
            proxy_url = f"{session.proxy_type.value}://{session.username}:{session.password}@{session.endpoint}:{session.port}"
            
            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(
                    'https://api.ipify.org?format=json',
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        ip_info = await response.json()
                        new_ip = ip_info.get('ip')
                        
                        if new_ip and new_ip != old_ip:
                            session.current_ip = new_ip
                            return True
                        else:
                            logger.warning(f"IP did not change: {old_ip} -> {new_ip}")
                            return False
                    return False
                    
        except Exception as e:
            logger.error(f"IP verification failed: {e}")
            return False

    def get_proxy_config_for_requests(self, session: ProxySession) -> Dict[str, str]:
        """
        Get proxy configuration for use with requests library.
        
        Args:
            session: Proxy session
            
        Returns:
            Dict[str, str]: Proxy configuration for requests
        """
        proxy_url = f"{session.proxy_type.value}://{session.username}:{session.password}@{session.endpoint}:{session.port}"
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def get_proxy_config_for_selenium(self, session: ProxySession) -> Dict[str, Any]:
        """
        Get proxy configuration for use with Selenium WebDriver.
        
        Args:
            session: Proxy session
            
        Returns:
            Dict[str, Any]: Proxy configuration for Selenium
        """
        return {
            'proxy_type': session.proxy_type.value,
            'http_proxy': f"{session.endpoint}:{session.port}",
            'ssl_proxy': f"{session.endpoint}:{session.port}",
            'proxy_auth': f"{session.username}:{session.password}"
        }

    def _update_connection_metrics(self, connection_time: float) -> None:
        """Update connection performance metrics."""
        current_avg = self.metrics['avg_connection_time']
        total_connections = self.metrics['total_sessions_created']
        
        # Calculate new average
        if total_connections > 1:
            self.metrics['avg_connection_time'] = (current_avg * (total_connections - 1) + connection_time) / total_connections
        else:
            self.metrics['avg_connection_time'] = connection_time
        
        # Update success rate
        total_operations = self.metrics['total_sessions_created'] + self.metrics['total_rotations']
        if total_operations > 0:
            self.metrics['success_rate'] = 1 - (self.metrics['total_errors'] / total_operations)

    async def disconnect_session(self, session: ProxySession) -> bool:
        """
        Disconnect from a proxy session.
        
        Args:
            session: Session to disconnect
            
        Returns:
            bool: True if disconnection successful
        """
        try:
            logger.info(f"Disconnecting session: {session.session_id}")
            
            # API call to close session
            response = self.api_session.delete(
                f"{self.config.api_endpoint}/api/v1/sessions/{session.session_id}",
                timeout=self.config.default_timeout
            )
            
            session.status = ProxyStatus.DISCONNECTED
            session.current_ip = None
            
            if response.status_code in [200, 204]:
                logger.info(f"Session disconnected: {session.session_id}")
                return True
            else:
                logger.warning(f"Session disconnect API call failed: {response.status_code}")
                return False  # Still mark as disconnected locally
                
        except Exception as e:
            logger.error(f"Session disconnection failed: {e}")
            session.status = ProxyStatus.ERROR
            return False

    async def cleanup_all_sessions(self) -> None:
        """Disconnect and cleanup all active sessions."""
        try:
            logger.info("Cleaning up all proxy sessions...")
            
            disconnect_tasks = []
            for session in self.sessions.values():
                if session.status != ProxyStatus.DISCONNECTED:
                    disconnect_tasks.append(self.disconnect_session(session))
            
            if disconnect_tasks:
                await asyncio.gather(*disconnect_tasks, return_exceptions=True)
            
            self.sessions.clear()
            self.session_pool.clear()
            self.active_session_id = None
            
            logger.info("All sessions cleaned up")
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")

    def get_webrtc_protection_config(self) -> Dict[str, Any]:
        """
        Get WebRTC protection configuration for browsers.
        
        Returns:
            Dict[str, Any]: WebRTC protection settings
        """
        return {
            'webrtc_ip_handling_policy': 'disable_non_proxied_udp',
            'webrtc_multiple_routes': False,
            'webrtc_non_proxied_udp': False,
            'blocked_domains': list(self.webrtc_blocked_domains),
            'disable_webrtc': True
        }

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Optional[Dict[str, Any]]: Session information or None
        """
        session = self.sessions.get(session_id)
        if session:
            return asdict(session)
        return None

    def get_all_sessions_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all sessions."""
        return {sid: asdict(session) for sid, session in self.sessions.items()}

    def get_metrics(self) -> Dict[str, Any]:
        """Get proxy manager performance metrics."""
        return self.metrics.copy()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the proxy manager.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            health_info = {
                'status': 'healthy',
                'total_sessions': len(self.sessions),
                'active_sessions': len([s for s in self.sessions.values() if s.status == ProxyStatus.CONNECTED]),
                'api_connectivity': False,
                'average_response_time': 0.0,
                'issues': []
            }
            
            # Test API connectivity
            start_time = time.time()
            try:
                response = self.api_session.get(
                    f"{self.config.api_endpoint}/api/v1/status",
                    timeout=5
                )
                health_info['api_connectivity'] = response.status_code == 200
                health_info['average_response_time'] = time.time() - start_time
            except Exception as e:
                health_info['issues'].append(f"API connectivity issue: {e}")
                health_info['status'] = 'degraded'
            
            # Check session health
            error_sessions = [s for s in self.sessions.values() if s.status == ProxyStatus.ERROR]
            if error_sessions:
                health_info['issues'].append(f"{len(error_sessions)} sessions in error state")
                health_info['status'] = 'degraded'
            
            # Check if we have enough sessions
            if len(self.sessions) < self.config.max_concurrent_sessions // 2:
                health_info['issues'].append("Low number of available sessions")
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
            # Try to cleanup sessions synchronously
            for session in self.sessions.values():
                if session.status != ProxyStatus.DISCONNECTED:
                    try:
                        self.api_session.delete(
                            f"{self.config.api_endpoint}/api/v1/sessions/{session.session_id}",
                            timeout=5
                        )
                    except Exception:
                        pass  # Ignore errors during cleanup
        except Exception:
            pass  # Ignore all errors in destructor 