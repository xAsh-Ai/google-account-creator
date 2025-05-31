#!/usr/bin/env python3

"""
SMS Monitor - Real-time SMS monitoring and notification system

This module provides real-time monitoring of SMS verification processes,
including status tracking, notification systems, and automated response
handling for Google account creation automation.

Author: Google Account Creator Team
Version: 0.1.0
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from datetime import datetime, timedelta
import queue

from .sms_verifier import SMSVerifier, SMSConfig, PhoneNumber, ServiceType, SMSStatus
from .phone_verification import PhoneVerificationInterface, VerificationRequest, VerificationResponse

# Configure logging
logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    STATUS_UPDATE = "status_update"

class MonitoringStatus(Enum):
    """SMS monitoring status."""
    IDLE = "idle"
    MONITORING = "monitoring"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class SMSNotification:
    """Represents an SMS-related notification."""
    id: str
    type: NotificationType
    title: str
    message: str
    phone_number: Optional[str] = None
    verification_code: Optional[str] = None
    timestamp: float = 0.0
    data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

@dataclass
class MonitoringSession:
    """Represents an active monitoring session."""
    session_id: str
    phone_number: PhoneNumber
    start_time: float
    timeout: int
    status: SMSStatus = SMSStatus.PENDING
    last_check: float = 0.0
    check_count: int = 0
    notifications: List[SMSNotification] = None
    
    def __post_init__(self):
        if self.notifications is None:
            self.notifications = []

class SMSMonitor:
    """
    Real-time SMS monitoring and notification system.
    
    This class provides comprehensive monitoring of SMS verification processes,
    including real-time status updates, notification management, and automated
    response handling for account creation workflows.
    """
    
    def __init__(self, sms_verifier: SMSVerifier):
        """
        Initialize the SMS monitor.
        
        Args:
            sms_verifier: SMS verifier instance to monitor
        """
        self.sms_verifier = sms_verifier
        self.monitoring_sessions: Dict[str, MonitoringSession] = {}
        self.notification_queue: queue.Queue = queue.Queue()
        self.status = MonitoringStatus.IDLE
        
        # Monitoring configuration
        self.check_interval = 5  # Check every 5 seconds
        self.max_concurrent_sessions = 10
        self.notification_retention_hours = 24
        
        # Event handlers
        self.notification_handlers: List[Callable[[SMSNotification], None]] = []
        self.status_change_handlers: List[Callable[[str, SMSStatus, SMSStatus], None]] = []
        self.session_complete_handlers: List[Callable[[MonitoringSession], None]] = []
        
        # Background monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = False
        
        # Notification history
        self.notification_history: List[SMSNotification] = []
        
        logger.info("SMSMonitor initialized")

    async def start_monitoring(self) -> bool:
        """
        Start the SMS monitoring system.
        
        Returns:
            bool: True if monitoring started successfully
        """
        try:
            if self.status == MonitoringStatus.MONITORING:
                logger.warning("SMS monitoring is already running")
                return True
            
            logger.info("Starting SMS monitoring system...")
            
            self.status = MonitoringStatus.MONITORING
            self._stop_monitoring = False
            
            # Start background monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # Send startup notification
            await self._send_notification(
                NotificationType.INFO,
                "SMS Monitor Started",
                "SMS monitoring system is now active"
            )
            
            logger.info("SMS monitoring system started successfully")
            return True
            
        except Exception as e:
            self.status = MonitoringStatus.ERROR
            logger.error(f"Failed to start SMS monitoring: {e}")
            return False

    async def stop_monitoring(self) -> None:
        """Stop the SMS monitoring system."""
        try:
            logger.info("Stopping SMS monitoring system...")
            
            self._stop_monitoring = True
            self.status = MonitoringStatus.STOPPED
            
            # Cancel monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Send shutdown notification
            await self._send_notification(
                NotificationType.INFO,
                "SMS Monitor Stopped",
                "SMS monitoring system has been stopped"
            )
            
            logger.info("SMS monitoring system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping SMS monitoring: {e}")

    async def pause_monitoring(self) -> None:
        """Pause SMS monitoring temporarily."""
        if self.status == MonitoringStatus.MONITORING:
            self.status = MonitoringStatus.PAUSED
            await self._send_notification(
                NotificationType.WARNING,
                "SMS Monitor Paused",
                "SMS monitoring has been paused"
            )
            logger.info("SMS monitoring paused")

    async def resume_monitoring(self) -> None:
        """Resume SMS monitoring."""
        if self.status == MonitoringStatus.PAUSED:
            self.status = MonitoringStatus.MONITORING
            await self._send_notification(
                NotificationType.INFO,
                "SMS Monitor Resumed",
                "SMS monitoring has been resumed"
            )
            logger.info("SMS monitoring resumed")

    async def add_monitoring_session(self, phone_number: PhoneNumber, timeout: int = 300) -> str:
        """
        Add a phone number to monitoring.
        
        Args:
            phone_number: Phone number to monitor
            timeout: Monitoring timeout in seconds
            
        Returns:
            str: Session ID for the monitoring session
        """
        try:
            if len(self.monitoring_sessions) >= self.max_concurrent_sessions:
                raise Exception(f"Maximum concurrent sessions ({self.max_concurrent_sessions}) reached")
            
            session_id = f"monitor_{phone_number.id}_{int(time.time())}"
            
            session = MonitoringSession(
                session_id=session_id,
                phone_number=phone_number,
                start_time=time.time(),
                timeout=timeout
            )
            
            self.monitoring_sessions[session_id] = session
            
            await self._send_notification(
                NotificationType.INFO,
                "Monitoring Started",
                f"Started monitoring {phone_number.number} ({phone_number.country_name})",
                phone_number=phone_number.number,
                data={'session_id': session_id, 'timeout': timeout}
            )
            
            logger.info(f"Added monitoring session: {session_id} for {phone_number.number}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to add monitoring session: {e}")
            raise

    async def remove_monitoring_session(self, session_id: str) -> bool:
        """
        Remove a monitoring session.
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            bool: True if session was removed
        """
        try:
            if session_id in self.monitoring_sessions:
                session = self.monitoring_sessions[session_id]
                del self.monitoring_sessions[session_id]
                
                await self._send_notification(
                    NotificationType.INFO,
                    "Monitoring Stopped",
                    f"Stopped monitoring {session.phone_number.number}",
                    phone_number=session.phone_number.number,
                    data={'session_id': session_id}
                )
                
                logger.info(f"Removed monitoring session: {session_id}")
                return True
            else:
                logger.warning(f"Monitoring session not found: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove monitoring session: {e}")
            return False

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs in the background."""
        try:
            logger.debug("SMS monitoring loop started")
            
            while not self._stop_monitoring:
                try:
                    if self.status == MonitoringStatus.MONITORING:
                        await self._check_all_sessions()
                    
                    # Clean up completed/expired sessions
                    await self._cleanup_sessions()
                    
                    # Clean up old notifications
                    self._cleanup_notifications()
                    
                    # Wait before next check
                    await asyncio.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(self.check_interval)
            
            logger.debug("SMS monitoring loop stopped")
            
        except asyncio.CancelledError:
            logger.debug("SMS monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"SMS monitoring loop failed: {e}")
            self.status = MonitoringStatus.ERROR

    async def _check_all_sessions(self) -> None:
        """Check all active monitoring sessions."""
        current_time = time.time()
        
        for session_id, session in list(self.monitoring_sessions.items()):
            try:
                # Check if session has timed out
                if current_time - session.start_time > session.timeout:
                    await self._handle_session_timeout(session)
                    continue
                
                # Check SMS status
                await self._check_session_status(session)
                
            except Exception as e:
                logger.error(f"Error checking session {session_id}: {e}")

    async def _check_session_status(self, session: MonitoringSession) -> None:
        """Check the status of a specific monitoring session."""
        try:
            session.last_check = time.time()
            session.check_count += 1
            
            # Get current SMS status
            sms_data = await self.sms_verifier._check_sms_status(session.phone_number)
            
            old_status = session.status
            
            if sms_data:
                # SMS received
                session.status = SMSStatus.RECEIVED
                session.phone_number.status = SMSStatus.RECEIVED
                session.phone_number.sms_received_at = time.time()
                session.phone_number.full_message = sms_data.get('text', '')
                
                # Extract verification code
                verification_code = self.sms_verifier._extract_verification_code(
                    session.phone_number.full_message
                )
                
                if verification_code:
                    session.phone_number.verification_code = verification_code
                    
                    await self._send_notification(
                        NotificationType.SUCCESS,
                        "SMS Received",
                        f"Verification code received: {verification_code}",
                        phone_number=session.phone_number.number,
                        verification_code=verification_code,
                        data={
                            'session_id': session.session_id,
                            'full_message': session.phone_number.full_message,
                            'duration': time.time() - session.start_time
                        }
                    )
                    
                    # Notify status change handlers
                    for handler in self.status_change_handlers:
                        try:
                            handler(session.session_id, old_status, session.status)
                        except Exception as e:
                            logger.error(f"Status change handler error: {e}")
                    
                    # Mark session as complete
                    await self._complete_session(session)
                else:
                    await self._send_notification(
                        NotificationType.WARNING,
                        "SMS Received (No Code)",
                        f"SMS received but no verification code found: {session.phone_number.full_message}",
                        phone_number=session.phone_number.number,
                        data={'session_id': session.session_id}
                    )
            else:
                # Still waiting for SMS
                if session.check_count % 12 == 0:  # Every minute (12 * 5 seconds)
                    elapsed = time.time() - session.start_time
                    remaining = session.timeout - elapsed
                    
                    await self._send_notification(
                        NotificationType.STATUS_UPDATE,
                        "Waiting for SMS",
                        f"Still waiting for SMS on {session.phone_number.number} ({remaining:.0f}s remaining)",
                        phone_number=session.phone_number.number,
                        data={
                            'session_id': session.session_id,
                            'elapsed': elapsed,
                            'remaining': remaining,
                            'check_count': session.check_count
                        }
                    )
            
        except Exception as e:
            logger.error(f"Error checking session status: {e}")

    async def _handle_session_timeout(self, session: MonitoringSession) -> None:
        """Handle a session that has timed out."""
        try:
            session.status = SMSStatus.TIMEOUT
            session.phone_number.status = SMSStatus.TIMEOUT
            
            await self._send_notification(
                NotificationType.ERROR,
                "SMS Timeout",
                f"SMS verification timeout for {session.phone_number.number}",
                phone_number=session.phone_number.number,
                data={
                    'session_id': session.session_id,
                    'duration': time.time() - session.start_time,
                    'check_count': session.check_count
                }
            )
            
            # Complete the session
            await self._complete_session(session)
            
        except Exception as e:
            logger.error(f"Error handling session timeout: {e}")

    async def _complete_session(self, session: MonitoringSession) -> None:
        """Mark a session as complete and clean up."""
        try:
            # Notify completion handlers
            for handler in self.session_complete_handlers:
                try:
                    handler(session)
                except Exception as e:
                    logger.error(f"Session complete handler error: {e}")
            
            # Remove from active sessions
            if session.session_id in self.monitoring_sessions:
                del self.monitoring_sessions[session.session_id]
            
            logger.info(f"Completed monitoring session: {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error completing session: {e}")

    async def _cleanup_sessions(self) -> None:
        """Clean up expired or completed sessions."""
        current_time = time.time()
        sessions_to_remove = []
        
        for session_id, session in self.monitoring_sessions.items():
            # Remove sessions that are completed or have been running too long
            if (session.status in [SMSStatus.RECEIVED, SMSStatus.TIMEOUT, SMSStatus.ERROR] or
                current_time - session.start_time > session.timeout + 60):  # Grace period
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            await self.remove_monitoring_session(session_id)

    def _cleanup_notifications(self) -> None:
        """Clean up old notifications."""
        try:
            cutoff_time = time.time() - (self.notification_retention_hours * 3600)
            
            self.notification_history = [
                notification for notification in self.notification_history
                if notification.timestamp > cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Error cleaning up notifications: {e}")

    async def _send_notification(self, notification_type: NotificationType, title: str, 
                               message: str, phone_number: Optional[str] = None,
                               verification_code: Optional[str] = None,
                               data: Optional[Dict[str, Any]] = None) -> None:
        """Send a notification through the system."""
        try:
            notification = SMSNotification(
                id=f"notif_{int(time.time() * 1000)}_{len(self.notification_history)}",
                type=notification_type,
                title=title,
                message=message,
                phone_number=phone_number,
                verification_code=verification_code,
                data=data
            )
            
            # Add to history
            self.notification_history.append(notification)
            
            # Add to queue for external processing
            try:
                self.notification_queue.put_nowait(notification)
            except queue.Full:
                logger.warning("Notification queue is full, dropping notification")
            
            # Call notification handlers
            for handler in self.notification_handlers:
                try:
                    handler(notification)
                except Exception as e:
                    logger.error(f"Notification handler error: {e}")
            
            # Log the notification
            log_level = {
                NotificationType.INFO: logging.INFO,
                NotificationType.WARNING: logging.WARNING,
                NotificationType.ERROR: logging.ERROR,
                NotificationType.SUCCESS: logging.INFO,
                NotificationType.STATUS_UPDATE: logging.DEBUG
            }.get(notification_type, logging.INFO)
            
            logger.log(log_level, f"[{title}] {message}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    def add_notification_handler(self, handler: Callable[[SMSNotification], None]) -> None:
        """Add a notification handler function."""
        self.notification_handlers.append(handler)
        logger.debug("Notification handler added")

    def add_status_change_handler(self, handler: Callable[[str, SMSStatus, SMSStatus], None]) -> None:
        """Add a status change handler function."""
        self.status_change_handlers.append(handler)
        logger.debug("Status change handler added")

    def add_session_complete_handler(self, handler: Callable[[MonitoringSession], None]) -> None:
        """Add a session completion handler function."""
        self.session_complete_handlers.append(handler)
        logger.debug("Session complete handler added")

    def get_notifications(self, limit: int = 100, 
                         notification_type: Optional[NotificationType] = None) -> List[SMSNotification]:
        """
        Get recent notifications.
        
        Args:
            limit: Maximum number of notifications to return
            notification_type: Filter by notification type
            
        Returns:
            List[SMSNotification]: Recent notifications
        """
        try:
            notifications = self.notification_history
            
            if notification_type:
                notifications = [n for n in notifications if n.type == notification_type]
            
            # Sort by timestamp (newest first) and limit
            notifications.sort(key=lambda x: x.timestamp, reverse=True)
            return notifications[:limit]
            
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return []

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get information about active monitoring sessions."""
        try:
            return [
                {
                    'session_id': session.session_id,
                    'phone_number': session.phone_number.number,
                    'country': session.phone_number.country_name,
                    'status': session.status.value,
                    'start_time': session.start_time,
                    'elapsed': time.time() - session.start_time,
                    'timeout': session.timeout,
                    'check_count': session.check_count,
                    'last_check': session.last_check
                }
                for session in self.monitoring_sessions.values()
            ]
            
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring system statistics."""
        try:
            current_time = time.time()
            
            return {
                'status': self.status.value,
                'active_sessions': len(self.monitoring_sessions),
                'total_notifications': len(self.notification_history),
                'notification_types': {
                    nt.value: len([n for n in self.notification_history if n.type == nt])
                    for nt in NotificationType
                },
                'check_interval': self.check_interval,
                'max_concurrent_sessions': self.max_concurrent_sessions,
                'uptime': current_time - getattr(self, '_start_time', current_time)
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring stats: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the monitoring system.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            health_info = {
                'status': 'healthy',
                'monitoring_status': self.status.value,
                'active_sessions': len(self.monitoring_sessions),
                'notification_queue_size': self.notification_queue.qsize(),
                'issues': []
            }
            
            # Check if monitoring task is running
            if self.status == MonitoringStatus.MONITORING:
                if not self._monitoring_task or self._monitoring_task.done():
                    health_info['issues'].append("Monitoring task is not running")
                    health_info['status'] = 'degraded'
            
            # Check for stuck sessions
            current_time = time.time()
            stuck_sessions = [
                s for s in self.monitoring_sessions.values()
                if current_time - s.start_time > s.timeout + 300  # 5 minutes grace
            ]
            
            if stuck_sessions:
                health_info['issues'].append(f"{len(stuck_sessions)} stuck monitoring sessions")
                health_info['status'] = 'degraded'
            
            # Check notification queue
            if self.notification_queue.qsize() > 100:
                health_info['issues'].append("Notification queue is getting full")
                health_info['status'] = 'degraded'
            
            return health_info
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'issues': [f"Health check failed: {e}"]
            }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_monitoring()

# Utility functions for easy integration

def create_console_notification_handler() -> Callable[[SMSNotification], None]:
    """Create a simple console notification handler."""
    def handler(notification: SMSNotification) -> None:
        timestamp = datetime.fromtimestamp(notification.timestamp).strftime("%H:%M:%S")
        print(f"[{timestamp}] {notification.type.value.upper()}: {notification.title} - {notification.message}")
    
    return handler

def create_file_notification_handler(log_file: str) -> Callable[[SMSNotification], None]:
    """Create a file-based notification handler."""
    def handler(notification: SMSNotification) -> None:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.fromtimestamp(notification.timestamp).isoformat()
                log_entry = {
                    'timestamp': timestamp,
                    'type': notification.type.value,
                    'title': notification.title,
                    'message': notification.message,
                    'phone_number': notification.phone_number,
                    'verification_code': notification.verification_code,
                    'data': notification.data
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"File notification handler error: {e}")
    
    return handler 