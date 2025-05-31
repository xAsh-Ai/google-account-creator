#!/usr/bin/env python3
"""
에러 복구 및 복원력 시스템

이 모듈은 Google Account Creator의 포괄적인 에러 복구 및 시스템 복원력을 제공합니다.
- 공통 에러 핸들러 및 자동 복구
- 지수 백오프 재시도 메커니즘
- 수동 개입 시스템
- 워치독 프로세스
- 시스템 일시정지/재개 기능
"""

import asyncio
import logging
import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Set, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import traceback
import signal
import subprocess
import psutil
from collections import defaultdict, deque
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import aiofiles
import socket
import random

# 로깅 설정
logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """에러 타입 분류"""
    ADB_CONNECTION_LOST = "adb_connection_lost"
    VPN_FAILURE = "vpn_failure" 
    PROXY_FAILURE = "proxy_failure"
    SMS_TIMEOUT = "sms_timeout"
    GOOGLE_SECURITY_CHALLENGE = "google_security_challenge"
    DEVICE_OFFLINE = "device_offline"
    NETWORK_ERROR = "network_error"
    MEMORY_ERROR = "memory_error"
    CAPTCHA_CHALLENGE = "captcha_challenge"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    WORKER_CRASHED = "worker_crashed"
    SYSTEM_OVERLOAD = "system_overload"

class RecoveryStrategy(Enum):
    """복구 전략"""
    SIMPLE_RETRY = "simple_retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    DEVICE_RESTART = "device_restart"
    SERVICE_RESTART = "service_restart"
    MANUAL_INTERVENTION = "manual_intervention"
    SKIP_AND_CONTINUE = "skip_and_continue"
    SYSTEM_PAUSE = "system_pause"
    ESCALATE = "escalate"

class SystemState(Enum):
    """시스템 상태"""
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class ErrorEvent:
    """에러 이벤트 정보"""
    id: str
    error_type: ErrorType
    timestamp: datetime
    component: str  # 에러가 발생한 컴포넌트
    device_id: Optional[str] = None
    worker_id: Optional[str] = None
    error_message: str = ""
    stack_trace: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempts: int = 0
    max_retry_attempts: int = 3
    recovery_strategy: Optional[RecoveryStrategy] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None

@dataclass
class RecoveryConfig:
    """복구 설정"""
    max_retry_attempts: int = 3
    initial_retry_delay: float = 1.0
    max_retry_delay: float = 60.0
    backoff_multiplier: float = 2.0
    enable_auto_recovery: bool = True
    enable_manual_intervention: bool = True
    enable_notifications: bool = True
    notification_threshold: int = 5  # 연속 실패 시 알림
    
class ErrorRecoverySystem:
    """에러 복구 시스템 메인 클래스"""
    
    def __init__(self, config: RecoveryConfig = None):
        """
        에러 복구 시스템 초기화
        
        Args:
            config: 복구 설정
        """
        self.config = config or RecoveryConfig()
        
        # 시스템 상태
        self.system_state = SystemState.RUNNING
        self.is_active = False
        
        # 에러 추적
        self.error_events: Dict[str, ErrorEvent] = {}
        self.error_history: deque = deque(maxlen=1000)
        self.error_stats: Dict[ErrorType, int] = defaultdict(int)
        
        # 복구 핸들러 등록
        self.error_handlers: Dict[ErrorType, Callable] = {}
        self.recovery_strategies: Dict[ErrorType, RecoveryStrategy] = {}
        
        # 수동 개입 큐
        self.manual_intervention_queue: List[ErrorEvent] = []
        self.intervention_callbacks: List[Callable] = []
        
        # 시스템 참조
        self.device_manager = None
        self.worker_manager = None
        self.resource_manager = None
        
        # 워치독
        self.watchdog_active = False
        self.watchdog_task = None
        
        # 이벤트
        self.pause_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        
        # 기본 핸들러 등록
        self._register_default_handlers()
        
        logger.info("에러 복구 시스템이 초기화되었습니다.")
    
    def _register_default_handlers(self):
        """기본 에러 핸들러들을 등록합니다."""
        
        # ADB 연결 실패
        self.register_error_handler(
            ErrorType.ADB_CONNECTION_LOST,
            self._handle_adb_connection_lost,
            RecoveryStrategy.DEVICE_RESTART
        )
        
        # VPN 실패
        self.register_error_handler(
            ErrorType.VPN_FAILURE,
            self._handle_vpn_failure,
            RecoveryStrategy.SERVICE_RESTART
        )
        
        # 프록시 실패
        self.register_error_handler(
            ErrorType.PROXY_FAILURE,
            self._handle_proxy_failure,
            RecoveryStrategy.SIMPLE_RETRY
        )
        
        # SMS 타임아웃
        self.register_error_handler(
            ErrorType.SMS_TIMEOUT,
            self._handle_sms_timeout,
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # Google 보안 챌린지
        self.register_error_handler(
            ErrorType.GOOGLE_SECURITY_CHALLENGE,
            self._handle_google_security_challenge,
            RecoveryStrategy.MANUAL_INTERVENTION
        )
        
        # 디바이스 오프라인
        self.register_error_handler(
            ErrorType.DEVICE_OFFLINE,
            self._handle_device_offline,
            RecoveryStrategy.DEVICE_RESTART
        )
        
        # 네트워크 에러
        self.register_error_handler(
            ErrorType.NETWORK_ERROR,
            self._handle_network_error,
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # 메모리 에러
        self.register_error_handler(
            ErrorType.MEMORY_ERROR,
            self._handle_memory_error,
            RecoveryStrategy.SYSTEM_PAUSE
        )
        
        # 캡챠 챌린지
        self.register_error_handler(
            ErrorType.CAPTCHA_CHALLENGE,
            self._handle_captcha_challenge,
            RecoveryStrategy.MANUAL_INTERVENTION
        )
        
        # 속도 제한 초과
        self.register_error_handler(
            ErrorType.RATE_LIMIT_EXCEEDED,
            self._handle_rate_limit_exceeded,
            RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # 워커 크래시
        self.register_error_handler(
            ErrorType.WORKER_CRASHED,
            self._handle_worker_crashed,
            RecoveryStrategy.SERVICE_RESTART
        )
        
        # 시스템 과부하
        self.register_error_handler(
            ErrorType.SYSTEM_OVERLOAD,
            self._handle_system_overload,
            RecoveryStrategy.SYSTEM_PAUSE
        )
    
    def register_error_handler(self, error_type: ErrorType, 
                             handler: Callable, 
                             strategy: RecoveryStrategy):
        """
        에러 핸들러를 등록합니다.
        
        Args:
            error_type: 에러 타입
            handler: 핸들러 함수
            strategy: 복구 전략
        """
        self.error_handlers[error_type] = handler
        self.recovery_strategies[error_type] = strategy
        logger.debug(f"에러 핸들러 등록: {error_type.value} -> {strategy.value}")
    
    async def handle_error(self, error_type: ErrorType, 
                          error_message: str,
                          component: str,
                          context: Dict[str, Any] = None,
                          device_id: str = None,
                          worker_id: str = None) -> bool:
        """
        에러를 처리합니다.
        
        Args:
            error_type: 에러 타입
            error_message: 에러 메시지
            component: 발생 컴포넌트
            context: 컨텍스트 정보
            device_id: 디바이스 ID
            worker_id: 워커 ID
            
        Returns:
            복구 성공 여부
        """
        # 에러 이벤트 생성
        error_event = ErrorEvent(
            id=f"error_{int(time.time())}_{len(self.error_events)}",
            error_type=error_type,
            timestamp=datetime.now(),
            component=component,
            device_id=device_id,
            worker_id=worker_id,
            error_message=error_message,
            stack_trace=traceback.format_exc(),
            context=context or {},
            recovery_strategy=self.recovery_strategies.get(error_type)
        )
        
        # 에러 기록
        self.error_events[error_event.id] = error_event
        self.error_history.append(error_event)
        self.error_stats[error_type] += 1
        
        logger.error(f"에러 발생: {error_type.value} in {component} - {error_message}")
        
        # 에러 처리 시도
        return await self._process_error_event(error_event)
    
    async def _process_error_event(self, error_event: ErrorEvent) -> bool:
        """
        에러 이벤트를 처리합니다.
        
        Args:
            error_event: 에러 이벤트
            
        Returns:
            처리 성공 여부
        """
        try:
            # 복구 시도 증가
            error_event.recovery_attempts += 1
            
            # 최대 재시도 횟수 확인
            if error_event.recovery_attempts > error_event.max_retry_attempts:
                logger.warning(f"에러 {error_event.id}: 최대 재시도 횟수 초과")
                return await self._escalate_error(error_event)
            
            # 에러 핸들러 실행
            handler = self.error_handlers.get(error_event.error_type)
            if handler:
                success = await handler(error_event)
                
                if success:
                    error_event.resolved = True
                    error_event.resolution_time = datetime.now()
                    logger.info(f"에러 {error_event.id} 복구 성공")
                    return True
                else:
                    logger.warning(f"에러 {error_event.id} 복구 실패, 재시도 대기 중...")
                    # 지수 백오프 적용
                    await self._apply_backoff(error_event)
                    return False
            else:
                logger.error(f"에러 타입 {error_event.error_type.value}에 대한 핸들러가 없습니다.")
                return await self._escalate_error(error_event)
                
        except Exception as e:
            logger.error(f"에러 처리 중 예외 발생: {e}")
            return False
    
    async def _apply_backoff(self, error_event: ErrorEvent):
        """지수 백오프를 적용합니다."""
        delay = min(
            self.config.initial_retry_delay * (self.config.backoff_multiplier ** (error_event.recovery_attempts - 1)),
            self.config.max_retry_delay
        )
        
        logger.info(f"에러 {error_event.id}: {delay:.1f}초 후 재시도")
        await asyncio.sleep(delay)
    
    async def _escalate_error(self, error_event: ErrorEvent) -> bool:
        """에러를 에스컬레이션합니다."""
        logger.critical(f"에러 {error_event.id} 에스컬레이션")
        
        # 수동 개입 큐에 추가
        if self.config.enable_manual_intervention:
            self.manual_intervention_queue.append(error_event)
            await self._notify_manual_intervention_required(error_event)
        
        # 시스템 일시정지 고려
        if error_event.error_type in [ErrorType.SYSTEM_OVERLOAD, ErrorType.MEMORY_ERROR]:
            await self.pause_system("Critical error escalation")
        
        return False
    
    # === 공통 에러 핸들러들 ===
    
    async def _handle_adb_connection_lost(self, error_event: ErrorEvent) -> bool:
        """ADB 연결 실패 처리"""
        device_id = error_event.device_id
        logger.info(f"ADB 연결 실패 복구 시도: {device_id}")
        
        try:
            if not device_id:
                return False
            
            # ADB 서버 재시작
            await self._restart_adb_server()
            
            # 디바이스 재연결 시도
            result = await asyncio.create_subprocess_exec(
                'adb', 'connect', device_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                logger.info(f"ADB 연결 복구 성공: {device_id}")
                return True
            else:
                logger.error(f"ADB 연결 복구 실패: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"ADB 연결 복구 중 오류: {e}")
            return False
    
    async def _restart_adb_server(self):
        """ADB 서버를 재시작합니다."""
        try:
            # ADB 서버 종료
            await asyncio.create_subprocess_exec('adb', 'kill-server')
            await asyncio.sleep(2)
            
            # ADB 서버 시작
            await asyncio.create_subprocess_exec('adb', 'start-server')
            await asyncio.sleep(3)
            
            logger.info("ADB 서버 재시작 완료")
            
        except Exception as e:
            logger.error(f"ADB 서버 재시작 실패: {e}")
    
    async def _handle_vpn_failure(self, error_event: ErrorEvent) -> bool:
        """VPN 실패 처리"""
        logger.info("VPN 연결 실패 복구 시도")
        
        try:
            # VPN 서비스 재시작 (예시)
            # 실제 구현에서는 사용하는 VPN 서비스에 따라 다름
            await asyncio.sleep(5)  # VPN 재연결 시뮬레이션
            
            # 연결 상태 확인
            if await self._check_internet_connectivity():
                logger.info("VPN 연결 복구 성공")
                return True
            else:
                logger.warning("VPN 연결 복구 실패")
                return False
                
        except Exception as e:
            logger.error(f"VPN 복구 중 오류: {e}")
            return False
    
    async def _handle_proxy_failure(self, error_event: ErrorEvent) -> bool:
        """프록시 실패 처리"""
        logger.info("프록시 연결 실패 복구 시도")
        
        try:
            # 프록시 로테이션 또는 재연결
            await asyncio.sleep(2)  # 프록시 변경 시뮬레이션
            
            # 연결 테스트
            if await self._check_internet_connectivity():
                logger.info("프록시 연결 복구 성공")
                return True
            else:
                logger.warning("프록시 연결 복구 실패")
                return False
                
        except Exception as e:
            logger.error(f"프록시 복구 중 오류: {e}")
            return False
    
    async def _handle_sms_timeout(self, error_event: ErrorEvent) -> bool:
        """SMS 타임아웃 처리"""
        logger.info("SMS 타임아웃 복구 시도")
        
        try:
            # SMS 서비스 상태 확인
            # 다른 SMS 제공업체 시도
            await asyncio.sleep(10)  # SMS 대기 시간 연장
            
            logger.info("SMS 타임아웃 복구 처리 완료")
            return True
            
        except Exception as e:
            logger.error(f"SMS 타임아웃 복구 중 오류: {e}")
            return False
    
    async def _handle_google_security_challenge(self, error_event: ErrorEvent) -> bool:
        """Google 보안 챌린지 처리"""
        logger.warning("Google 보안 챌린지 감지 - 수동 개입 필요")
        
        # 수동 개입 요청
        await self._request_manual_intervention(
            error_event, 
            "Google 보안 챌린지 해결이 필요합니다."
        )
        
        return False  # 수동 개입 필요
    
    async def _handle_device_offline(self, error_event: ErrorEvent) -> bool:
        """디바이스 오프라인 처리"""
        device_id = error_event.device_id
        logger.info(f"디바이스 오프라인 복구 시도: {device_id}")
        
        try:
            if not device_id:
                return False
            
            # 디바이스 재부팅 시도
            if "emulator" in device_id:
                # 에뮬레이터 재시작
                await self._restart_emulator(device_id)
            else:
                # 물리적 디바이스 재연결 시도
                await self._reconnect_physical_device(device_id)
            
            # 연결 상태 확인
            await asyncio.sleep(10)  # 재시작 대기
            
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device_id, 'shell', 'echo', 'test',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                logger.info(f"디바이스 복구 성공: {device_id}")
                return True
            else:
                logger.error(f"디바이스 복구 실패: {device_id}")
                return False
                
        except Exception as e:
            logger.error(f"디바이스 복구 중 오류: {e}")
            return False
    
    async def _handle_network_error(self, error_event: ErrorEvent) -> bool:
        """네트워크 에러 처리"""
        logger.info("네트워크 에러 복구 시도")
        
        try:
            # 네트워크 연결 상태 확인
            if await self._check_internet_connectivity():
                logger.info("네트워크 연결 정상")
                return True
            
            # DNS 갱신
            await self._flush_dns()
            
            # 재연결 대기
            await asyncio.sleep(5)
            
            # 재확인
            if await self._check_internet_connectivity():
                logger.info("네트워크 복구 성공")
                return True
            else:
                logger.warning("네트워크 복구 실패")
                return False
                
        except Exception as e:
            logger.error(f"네트워크 복구 중 오류: {e}")
            return False
    
    async def _handle_memory_error(self, error_event: ErrorEvent) -> bool:
        """메모리 에러 처리"""
        logger.warning("메모리 부족 상황 처리")
        
        try:
            # 메모리 정리
            await self._cleanup_memory()
            
            # 시스템 일시정지
            await self.pause_system("Memory pressure relief")
            
            # 5분 대기
            await asyncio.sleep(300)
            
            # 시스템 재개
            await self.resume_system()
            
            logger.info("메모리 에러 복구 처리 완료")
            return True
            
        except Exception as e:
            logger.error(f"메모리 에러 복구 중 오류: {e}")
            return False
    
    async def _handle_captcha_challenge(self, error_event: ErrorEvent) -> bool:
        """캡챠 챌린지 처리"""
        logger.warning("캡챠 챌린지 감지 - 수동 개입 필요")
        
        # 수동 개입 요청
        await self._request_manual_intervention(
            error_event,
            "캡챠 해결이 필요합니다."
        )
        
        return False  # 수동 개입 필요
    
    async def _handle_rate_limit_exceeded(self, error_event: ErrorEvent) -> bool:
        """속도 제한 초과 처리"""
        logger.info("속도 제한 초과 - 대기 중")
        
        try:
            # 1시간 대기
            await asyncio.sleep(3600)
            
            logger.info("속도 제한 대기 완료")
            return True
            
        except Exception as e:
            logger.error(f"속도 제한 처리 중 오류: {e}")
            return False
    
    async def _handle_worker_crashed(self, error_event: ErrorEvent) -> bool:
        """워커 크래시 처리"""
        worker_id = error_event.worker_id
        logger.info(f"워커 크래시 복구 시도: {worker_id}")
        
        try:
            if self.worker_manager and worker_id:
                # 워커 재시작
                success = await self.worker_manager._restart_worker(worker_id)
                
                if success:
                    logger.info(f"워커 복구 성공: {worker_id}")
                    return True
                else:
                    logger.error(f"워커 복구 실패: {worker_id}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"워커 복구 중 오류: {e}")
            return False
    
    async def _handle_system_overload(self, error_event: ErrorEvent) -> bool:
        """시스템 과부하 처리"""
        logger.warning("시스템 과부하 감지 - 부하 감소 조치")
        
        try:
            # 시스템 일시정지
            await self.pause_system("System overload protection")
            
            # 리소스 정리
            await self._cleanup_resources()
            
            # 10분 대기
            await asyncio.sleep(600)
            
            # 시스템 재개
            await self.resume_system()
            
            logger.info("시스템 과부하 복구 완료")
            return True
            
        except Exception as e:
            logger.error(f"시스템 과부하 복구 중 오류: {e}")
            return False
    
    # === 유틸리티 메서드들 ===
    
    async def _check_internet_connectivity(self) -> bool:
        """인터넷 연결 상태를 확인합니다."""
        try:
            result = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '8.8.8.8',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await result.communicate()
            return result.returncode == 0
            
        except Exception:
            return False
    
    async def _flush_dns(self):
        """DNS 캐시를 갱신합니다."""
        try:
            # macOS/Linux DNS 갱신
            await asyncio.create_subprocess_exec('sudo', 'dscacheutil', '-flushcache')
        except Exception as e:
            logger.debug(f"DNS 갱신 실패: {e}")
    
    async def _cleanup_memory(self):
        """메모리를 정리합니다."""
        try:
            import gc
            gc.collect()
            
            # 시스템 메모리 정리
            if hasattr(psutil, 'virtual_memory'):
                memory_info = psutil.virtual_memory()
                logger.info(f"메모리 사용률: {memory_info.percent:.1f}%")
            
        except Exception as e:
            logger.error(f"메모리 정리 중 오류: {e}")
    
    async def _cleanup_resources(self):
        """시스템 리소스를 정리합니다."""
        try:
            await self._cleanup_memory()
            
            # 임시 파일 정리
            import tempfile
            import shutil
            
            temp_dir = Path(tempfile.gettempdir())
            for temp_file in temp_dir.glob("google_account_creator_*"):
                try:
                    if temp_file.is_file():
                        temp_file.unlink()
                    elif temp_file.is_dir():
                        shutil.rmtree(temp_file)
                except Exception:
                    pass
                    
            logger.info("리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"리소스 정리 중 오류: {e}")
    
    async def _restart_emulator(self, device_id: str):
        """에뮬레이터를 재시작합니다."""
        try:
            # 에뮬레이터 종료
            await asyncio.create_subprocess_exec('adb', '-s', device_id, 'emu', 'kill')
            await asyncio.sleep(5)
            
            # 에뮬레이터 재시작 (AVD 이름 필요)
            avd_name = device_id.replace("emulator-", "")
            await asyncio.create_subprocess_exec('emulator', '-avd', avd_name, '-no-window')
            
            logger.info(f"에뮬레이터 재시작: {device_id}")
            
        except Exception as e:
            logger.error(f"에뮬레이터 재시작 실패: {e}")
    
    async def _reconnect_physical_device(self, device_id: str):
        """물리적 디바이스를 재연결합니다."""
        try:
            # USB 연결 재설정
            await asyncio.create_subprocess_exec('adb', 'disconnect', device_id)
            await asyncio.sleep(2)
            await asyncio.create_subprocess_exec('adb', 'connect', device_id)
            
            logger.info(f"물리적 디바이스 재연결: {device_id}")
            
        except Exception as e:
            logger.error(f"디바이스 재연결 실패: {e}")
    
    # === 수동 개입 시스템 ===
    
    async def _request_manual_intervention(self, error_event: ErrorEvent, message: str):
        """수동 개입을 요청합니다."""
        self.manual_intervention_queue.append(error_event)
        
        # 알림 전송
        await self._send_notification(
            f"수동 개입 필요: {error_event.error_type.value}",
            message,
            error_event
        )
        
        # 콜백 실행
        for callback in self.intervention_callbacks:
            try:
                await callback(error_event, message)
            except Exception as e:
                logger.error(f"개입 콜백 실행 오류: {e}")
    
    async def _notify_manual_intervention_required(self, error_event: ErrorEvent):
        """수동 개입 필요 알림을 보냅니다."""
        message = f"""
        에러 ID: {error_event.id}
        에러 타입: {error_event.error_type.value}
        컴포넌트: {error_event.component}
        디바이스: {error_event.device_id or 'N/A'}
        워커: {error_event.worker_id or 'N/A'}
        메시지: {error_event.error_message}
        시간: {error_event.timestamp}
        """
        
        await self._send_notification(
            "Google Account Creator - 수동 개입 필요",
            message,
            error_event
        )
    
    async def _send_notification(self, subject: str, message: str, error_event: ErrorEvent):
        """알림을 전송합니다."""
        try:
            # 로그 기록
            logger.critical(f"알림: {subject}")
            logger.critical(f"내용: {message}")
            
            # 실제 구현에서는 이메일, Slack, 텔레그램 등으로 알림 전송
            # 여기서는 파일로 저장
            notification_file = Path("notifications") / f"notification_{int(time.time())}.txt"
            notification_file.parent.mkdir(exist_ok=True)
            
            with open(notification_file, 'w', encoding='utf-8') as f:
                f.write(f"Subject: {subject}\n")
                f.write(f"Time: {datetime.now()}\n")
                f.write(f"Message: {message}\n")
                f.write(f"Error Event: {json.dumps(error_event.__dict__, default=str, indent=2)}")
            
            logger.info(f"알림 저장됨: {notification_file}")
            
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}")
    
    # === 시스템 제어 ===
    
    async def pause_system(self, reason: str = "Manual pause"):
        """시스템을 일시정지합니다."""
        logger.warning(f"시스템 일시정지: {reason}")
        
        self.system_state = SystemState.PAUSED
        self.pause_event.set()
        self.resume_event.clear()
        
        # 알림 전송
        await self._send_notification(
            "시스템 일시정지",
            f"Google Account Creator가 일시정지되었습니다.\n이유: {reason}",
            None
        )
    
    async def resume_system(self):
        """시스템을 재개합니다."""
        logger.info("시스템 재개")
        
        self.system_state = SystemState.RUNNING
        self.pause_event.clear()
        self.resume_event.set()
        
        # 알림 전송
        await self._send_notification(
            "시스템 재개",
            "Google Account Creator가 재개되었습니다.",
            None
        )
    
    async def emergency_stop(self, reason: str = "Emergency stop"):
        """비상 정지합니다."""
        logger.critical(f"비상 정지: {reason}")
        
        self.system_state = SystemState.EMERGENCY_STOP
        self.shutdown_event.set()
        
        # 알림 전송
        await self._send_notification(
            "비상 정지",
            f"Google Account Creator가 비상 정지되었습니다.\n이유: {reason}",
            None
        )
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태를 반환합니다."""
        return {
            "system_state": self.system_state.value,
            "is_active": self.is_active,
            "total_errors": len(self.error_events),
            "unresolved_errors": len([e for e in self.error_events.values() if not e.resolved]),
            "manual_intervention_queue": len(self.manual_intervention_queue),
            "error_stats": {k.value: v for k, v in self.error_stats.items()},
            "recent_errors": [
                {
                    "id": e.id,
                    "type": e.error_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "component": e.component,
                    "resolved": e.resolved
                }
                for e in list(self.error_history)[-10:]
            ]
        }

# 편의 함수들
def create_error_recovery_system(config: RecoveryConfig = None) -> ErrorRecoverySystem:
    """에러 복구 시스템을 생성합니다."""
    return ErrorRecoverySystem(config)

if __name__ == "__main__":
    # 테스트 코드
    async def test_error_recovery():
        recovery_system = create_error_recovery_system()
        
        # 테스트 에러 발생
        await recovery_system.handle_error(
            ErrorType.ADB_CONNECTION_LOST,
            "Test ADB connection lost",
            "test_component",
            device_id="test_device"
        )
        
        # 상태 확인
        status = recovery_system.get_system_status()
        print("시스템 상태:", json.dumps(status, indent=2))
    
    # 테스트 실행
    asyncio.run(test_error_recovery())

class GlobalExceptionHandler:
    """전역 예외 처리기"""
    
    def __init__(self, error_recovery_system: ErrorRecoverySystem):
        """
        전역 예외 처리기 초기화
        
        Args:
            error_recovery_system: 에러 복구 시스템 인스턴스
        """
        self.error_recovery_system = error_recovery_system
        self.exception_count = 0
        self.critical_exception_count = 0
        
        # 예외 통계
        self.exception_stats: Dict[str, int] = defaultdict(int)
        self.exception_history: deque = deque(maxlen=100)
        
        # 처리되지 않은 예외 로그
        self.unhandled_exceptions: List[Dict[str, Any]] = []
        
        # 예외 필터
        self.ignored_exceptions: Set[type] = {
            KeyboardInterrupt,  # 사용자 중단
            SystemExit         # 시스템 종료
        }
        
        # 예외 매핑 (Python 예외 -> ErrorType)
        self.exception_mapping = {
            ConnectionError: ErrorType.NETWORK_ERROR,
            TimeoutError: ErrorType.NETWORK_ERROR,
            MemoryError: ErrorType.MEMORY_ERROR,
            OSError: ErrorType.SYSTEM_OVERLOAD,
            subprocess.SubprocessError: ErrorType.WORKER_CRASHED,
            FileNotFoundError: ErrorType.SYSTEM_OVERLOAD,
            PermissionError: ErrorType.SYSTEM_OVERLOAD,
        }
        
        logger.info("전역 예외 처리기가 초기화되었습니다.")
    
    def install_exception_handler(self):
        """전역 예외 처리기를 설치합니다."""
        import sys
        import threading
        
        # 메인 스레드 예외 처리기
        sys.excepthook = self.handle_exception
        
        # 스레드 예외 처리기
        threading.excepthook = self.handle_thread_exception
        
        # asyncio 예외 처리기
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.set_exception_handler(self.handle_asyncio_exception)
        except RuntimeError:
            # 이벤트 루프가 실행 중이 아닌 경우
            pass
        
        logger.info("전역 예외 처리기가 설치되었습니다.")
    
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        메인 스레드 예외를 처리합니다.
        
        Args:
            exc_type: 예외 타입
            exc_value: 예외 값
            exc_traceback: 트레이스백
        """
        if exc_type in self.ignored_exceptions:
            return
        
        # 예외 정보 수집
        exception_info = self._collect_exception_info(
            exc_type, exc_value, exc_traceback, "main_thread"
        )
        
        # 동기 처리 (별도 스레드에서 비동기 처리)
        threading.Thread(
            target=self._handle_exception_async,
            args=(exception_info,),
            daemon=True
        ).start()
        
        # 치명적 예외인 경우 기본 처리도 수행
        if self._is_critical_exception(exc_type, exc_value):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def handle_thread_exception(self, args):
        """
        스레드 예외를 처리합니다.
        
        Args:
            args: 스레드 예외 정보
        """
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread
        
        if exc_type in self.ignored_exceptions:
            return
        
        # 예외 정보 수집
        exception_info = self._collect_exception_info(
            exc_type, exc_value, exc_traceback, f"thread_{thread.name}"
        )
        
        # 비동기 처리
        threading.Thread(
            target=self._handle_exception_async,
            args=(exception_info,),
            daemon=True
        ).start()
    
    def handle_asyncio_exception(self, loop, context):
        """
        asyncio 예외를 처리합니다.
        
        Args:
            loop: 이벤트 루프
            context: 예외 컨텍스트
        """
        exception = context.get('exception')
        
        if exception and type(exception) not in self.ignored_exceptions:
            # 예외 정보 수집
            exception_info = {
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'context': context,
                'component': 'asyncio_loop',
                'timestamp': datetime.now(),
                'stack_trace': traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                ) if hasattr(exception, '__traceback__') else []
            }
            
            # 비동기 태스크로 처리
            asyncio.create_task(self._handle_exception_info_async(exception_info))
        
        # 원래 예외 처리기 호출
        if hasattr(loop, '_original_exception_handler'):
            loop._original_exception_handler(loop, context)
    
    def _collect_exception_info(self, exc_type, exc_value, exc_traceback, component: str) -> Dict[str, Any]:
        """예외 정보를 수집합니다."""
        return {
            'exception_type': exc_type.__name__,
            'exception_message': str(exc_value),
            'component': component,
            'timestamp': datetime.now(),
            'stack_trace': traceback.format_exception(exc_type, exc_value, exc_traceback),
            'process_id': os.getpid(),
            'thread_name': threading.current_thread().name,
            'memory_usage': self._get_memory_usage(),
            'system_load': self._get_system_load()
        }
    
    def _handle_exception_async(self, exception_info: Dict[str, Any]):
        """예외를 비동기적으로 처리합니다."""
        try:
            # 새 이벤트 루프 생성 (스레드에서 실행)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 비동기 처리 실행
            loop.run_until_complete(self._handle_exception_info_async(exception_info))
            
        except Exception as e:
            logger.error(f"예외 처리 중 오류: {e}")
        finally:
            try:
                loop.close()
            except:
                pass
    
    async def _handle_exception_info_async(self, exception_info: Dict[str, Any]):
        """예외 정보를 비동기적으로 처리합니다."""
        try:
            self.exception_count += 1
            exception_type = exception_info['exception_type']
            
            # 통계 업데이트
            self.exception_stats[exception_type] += 1
            self.exception_history.append(exception_info)
            
            # 에러 타입 매핑
            python_exc_type = globals().get(exception_type)
            error_type = self.exception_mapping.get(python_exc_type, ErrorType.SYSTEM_OVERLOAD)
            
            # 에러 복구 시스템에 전달
            await self.error_recovery_system.handle_error(
                error_type=error_type,
                error_message=exception_info['exception_message'],
                component=exception_info['component'],
                context={
                    'exception_info': exception_info,
                    'is_global_exception': True
                }
            )
            
            # 로그 기록
            logger.error(f"전역 예외 처리: {exception_type} in {exception_info['component']}")
            logger.error(f"메시지: {exception_info['exception_message']}")
            
            # 치명적 예외 처리
            if self._is_critical_exception_by_name(exception_type, exception_info['exception_message']):
                self.critical_exception_count += 1
                await self._handle_critical_exception(exception_info)
            
            # 예외 패턴 분석
            await self._analyze_exception_patterns()
            
        except Exception as e:
            logger.critical(f"전역 예외 처리기 내부 오류: {e}")
            self.unhandled_exceptions.append(exception_info)
    
    def _is_critical_exception(self, exc_type, exc_value) -> bool:
        """예외가 치명적인지 판단합니다."""
        critical_exceptions = {
            MemoryError,
            SystemError,
            OSError,
        }
        
        if exc_type in critical_exceptions:
            return True
        
        # 에러 메시지 기반 판단
        error_message = str(exc_value).lower()
        critical_keywords = [
            'out of memory',
            'disk full',
            'cannot allocate',
            'system overload',
            'critical error'
        ]
        
        return any(keyword in error_message for keyword in critical_keywords)
    
    def _is_critical_exception_by_name(self, exception_type: str, exception_message: str) -> bool:
        """예외 이름과 메시지로 치명도를 판단합니다."""
        critical_types = [
            'MemoryError',
            'SystemError', 
            'OSError'
        ]
        
        if exception_type in critical_types:
            return True
        
        critical_keywords = [
            'out of memory',
            'disk full', 
            'cannot allocate',
            'system overload',
            'critical error'
        ]
        
        return any(keyword in exception_message.lower() for keyword in critical_keywords)
    
    async def _handle_critical_exception(self, exception_info: Dict[str, Any]):
        """치명적 예외를 처리합니다."""
        logger.critical(f"치명적 예외 감지: {exception_info['exception_type']}")
        
        # 시스템 상태 확인
        system_status = self.error_recovery_system.get_system_status()
        
        # 연속된 치명적 예외 확인
        if self.critical_exception_count >= 3:
            logger.critical("연속된 치명적 예외 발생 - 비상 정지")
            await self.error_recovery_system.emergency_stop(
                f"연속 치명적 예외: {exception_info['exception_type']}"
            )
        else:
            # 시스템 일시정지
            await self.error_recovery_system.pause_system(
                f"치명적 예외 처리: {exception_info['exception_type']}"
            )
    
    async def _analyze_exception_patterns(self):
        """예외 패턴을 분석합니다."""
        if len(self.exception_history) < 5:
            return
        
        # 최근 예외들 분석
        recent_exceptions = list(self.exception_history)[-5:]
        
        # 같은 타입의 예외가 연속으로 발생하는지 확인
        exception_types = [exc['exception_type'] for exc in recent_exceptions]
        
        if len(set(exception_types)) == 1:  # 모두 같은 타입
            exception_type = exception_types[0]
            logger.warning(f"연속된 동일 예외 패턴 감지: {exception_type}")
            
            # 패턴에 따른 조치
            if exception_type in ['ConnectionError', 'TimeoutError']:
                # 네트워크 문제 패턴
                await self.error_recovery_system.pause_system("반복 네트워크 오류")
            elif exception_type in ['MemoryError']:
                # 메모리 문제 패턴
                await self.error_recovery_system._cleanup_memory()
        
        # 예외 빈도 분석
        time_window = datetime.now() - timedelta(minutes=5)
        recent_count = sum(
            1 for exc in recent_exceptions 
            if exc['timestamp'] > time_window
        )
        
        if recent_count >= 10:  # 5분 내 10개 이상 예외
            logger.warning("높은 예외 발생 빈도 감지")
            await self.error_recovery_system.pause_system("높은 예외 발생 빈도")
    
    def _get_memory_usage(self) -> float:
        """현재 메모리 사용량을 반환합니다."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return memory_info.rss / 1024 / 1024  # MB
        except:
            return 0.0
    
    def _get_system_load(self) -> float:
        """시스템 로드를 반환합니다."""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except:
            return 0.0
    
    def get_exception_statistics(self) -> Dict[str, Any]:
        """예외 통계를 반환합니다."""
        return {
            'total_exceptions': self.exception_count,
            'critical_exceptions': self.critical_exception_count,
            'exception_types': dict(self.exception_stats),
            'recent_exceptions': [
                {
                    'type': exc['exception_type'],
                    'component': exc['component'],
                    'timestamp': exc['timestamp'].isoformat(),
                    'message': exc['exception_message'][:100] + '...' if len(exc['exception_message']) > 100 else exc['exception_message']
                }
                for exc in list(self.exception_history)[-10:]
            ],
            'unhandled_count': len(self.unhandled_exceptions)
        }
    
    def reset_statistics(self):
        """통계를 초기화합니다."""
        self.exception_count = 0
        self.critical_exception_count = 0
        self.exception_stats.clear()
        self.exception_history.clear()
        self.unhandled_exceptions.clear()
        
        logger.info("예외 통계가 초기화되었습니다.")

class ExceptionLogger:
    """예외 로깅 전용 클래스"""
    
    def __init__(self, log_file: str = "logs/exceptions.log"):
        """
        예외 로거 초기화
        
        Args:
            log_file: 예외 로그 파일 경로
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 전용 로거 설정
        self.logger = logging.getLogger('exception_logger')
        self.logger.setLevel(logging.ERROR)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.ERROR)
        
        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        logger.info(f"예외 로거가 초기화되었습니다: {self.log_file}")
    
    def log_exception(self, exception_info: Dict[str, Any]):
        """예외를 로그에 기록합니다."""
        try:
            log_entry = {
                'timestamp': exception_info['timestamp'].isoformat(),
                'type': exception_info['exception_type'],
                'message': exception_info['exception_message'],
                'component': exception_info['component'],
                'process_id': exception_info.get('process_id'),
                'thread_name': exception_info.get('thread_name'),
                'memory_usage_mb': exception_info.get('memory_usage', 0),
                'system_load': exception_info.get('system_load', 0),
                'stack_trace': exception_info.get('stack_trace', [])
            }
            
            # JSON 형태로 로그 기록
            self.logger.error(json.dumps(log_entry, ensure_ascii=False, indent=2))
            
        except Exception as e:
            logger.error(f"예외 로깅 중 오류: {e}")
    
    def get_log_summary(self, hours: int = 24) -> Dict[str, Any]:
        """로그 요약을 반환합니다."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 로그 파일 읽기
            if not self.log_file.exists():
                return {'error': 'Log file not found'}
            
            exception_counts = defaultdict(int)
            total_exceptions = 0
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        if line.strip():
                            log_entry = json.loads(line)
                            entry_time = datetime.fromisoformat(log_entry['timestamp'])
                            
                            if entry_time > cutoff_time:
                                exception_counts[log_entry['type']] += 1
                                total_exceptions += 1
                    except:
                        continue
            
            return {
                'total_exceptions': total_exceptions,
                'exception_types': dict(exception_counts),
                'time_period_hours': hours
            }
            
        except Exception as e:
            logger.error(f"로그 요약 생성 중 오류: {e}")
            return {'error': str(e)}

# 전역 인스턴스들
_global_exception_handler: Optional[GlobalExceptionHandler] = None
_exception_logger: Optional[ExceptionLogger] = None

def setup_global_exception_handling(error_recovery_system: ErrorRecoverySystem,
                                   log_file: str = "logs/exceptions.log") -> GlobalExceptionHandler:
    """
    전역 예외 처리를 설정합니다.
    
    Args:
        error_recovery_system: 에러 복구 시스템
        log_file: 예외 로그 파일 경로
        
    Returns:
        전역 예외 처리기
    """
    global _global_exception_handler, _exception_logger
    
    # 예외 로거 설정
    _exception_logger = ExceptionLogger(log_file)
    
    # 전역 예외 처리기 설정
    _global_exception_handler = GlobalExceptionHandler(error_recovery_system)
    _global_exception_handler.install_exception_handler()
    
    logger.info("전역 예외 처리 시스템이 설정되었습니다.")
    return _global_exception_handler

def get_global_exception_handler() -> Optional[GlobalExceptionHandler]:
    """전역 예외 처리기를 반환합니다."""
    return _global_exception_handler

def get_exception_logger() -> Optional[ExceptionLogger]:
    """예외 로거를 반환합니다."""
    return _exception_logger

class RetryManager:
    """재시도 관리 클래스"""
    
    def __init__(self, 
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_factor: float = 2.0,
                 jitter: bool = True):
        """
        재시도 관리자 초기화
        
        Args:
            max_attempts: 최대 재시도 횟수
            base_delay: 기본 지연 시간 (초)
            max_delay: 최대 지연 시간 (초)
            backoff_factor: 백오프 배수
            jitter: 지터(무작위 지연) 사용 여부
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        
        # 재시도 통계
        self.retry_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'total_attempts': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'average_attempts': 0.0,
            'last_attempt': None
        })
        
        logger.info("재시도 관리자가 초기화되었습니다.")
    
    async def retry_async(self, 
                         func: Callable,
                         *args,
                         operation_name: str = "unknown",
                         exceptions: Tuple[type, ...] = (Exception,),
                         **kwargs) -> Any:
        """
        비동기 함수를 재시도합니다.
        
        Args:
            func: 실행할 비동기 함수
            *args: 함수 인수
            operation_name: 작업 이름 (통계용)
            exceptions: 재시도할 예외 타입들
            **kwargs: 함수 키워드 인수
            
        Returns:
            함수 실행 결과
            
        Raises:
            마지막 발생한 예외
        """
        last_exception = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                # 통계 업데이트
                self._update_retry_stats(operation_name, 'attempt')
                
                # 함수 실행
                result = await func(*args, **kwargs)
                
                # 성공 시 통계 업데이트
                if attempt > 1:
                    self._update_retry_stats(operation_name, 'success', attempt)
                
                logger.info(f"재시도 성공: {operation_name} (시도 {attempt}/{self.max_attempts})")
                return result
                
            except exceptions as e:
                last_exception = e
                
                logger.warning(f"재시도 실패: {operation_name} (시도 {attempt}/{self.max_attempts}) - {e}")
                
                # 마지막 시도가 아닌 경우 지연
                if attempt < self.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"다음 재시도까지 {delay:.1f}초 대기...")
                    await asyncio.sleep(delay)
                else:
                    # 최종 실패 통계 업데이트
                    self._update_retry_stats(operation_name, 'final_failure', attempt)
        
        # 모든 재시도 실패
        logger.error(f"재시도 최종 실패: {operation_name} ({self.max_attempts}회 시도)")
        raise last_exception
    
    def retry_sync(self,
                   func: Callable,
                   *args,
                   operation_name: str = "unknown",
                   exceptions: Tuple[type, ...] = (Exception,),
                   **kwargs) -> Any:
        """
        동기 함수를 재시도합니다.
        
        Args:
            func: 실행할 동기 함수
            *args: 함수 인수
            operation_name: 작업 이름 (통계용)
            exceptions: 재시도할 예외 타입들
            **kwargs: 함수 키워드 인수
            
        Returns:
            함수 실행 결과
            
        Raises:
            마지막 발생한 예외
        """
        last_exception = None
        
        for attempt in range(1, self.max_attempts + 1):
            try:
                # 통계 업데이트
                self._update_retry_stats(operation_name, 'attempt')
                
                # 함수 실행
                result = func(*args, **kwargs)
                
                # 성공 시 통계 업데이트
                if attempt > 1:
                    self._update_retry_stats(operation_name, 'success', attempt)
                
                logger.info(f"재시도 성공: {operation_name} (시도 {attempt}/{self.max_attempts})")
                return result
                
            except exceptions as e:
                last_exception = e
                
                logger.warning(f"재시도 실패: {operation_name} (시도 {attempt}/{self.max_attempts}) - {e}")
                
                # 마지막 시도가 아닌 경우 지연
                if attempt < self.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"다음 재시도까지 {delay:.1f}초 대기...")
                    time.sleep(delay)
                else:
                    # 최종 실패 통계 업데이트
                    self._update_retry_stats(operation_name, 'final_failure', attempt)
        
        # 모든 재시도 실패
        logger.error(f"재시도 최종 실패: {operation_name} ({self.max_attempts}회 시도)")
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """재시도 지연 시간을 계산합니다."""
        # 지수 백오프 계산
        delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        
        # 최대 지연시간 제한
        delay = min(delay, self.max_delay)
        
        # 지터 적용 (무작위성 추가)
        if self.jitter:
            import random
            jitter_range = delay * 0.1  # 10% 지터
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)  # 음수 방지
        
        return delay
    
    def _update_retry_stats(self, operation_name: str, event_type: str, attempt: int = 1):
        """재시도 통계를 업데이트합니다."""
        stats = self.retry_stats[operation_name]
        
        if event_type == 'attempt':
            stats['total_attempts'] += 1
            stats['last_attempt'] = datetime.now()
        elif event_type == 'success':
            stats['successful_retries'] += 1
            # 평균 시도 횟수 업데이트
            total_operations = stats['successful_retries'] + stats['failed_retries']
            if total_operations > 0:
                stats['average_attempts'] = stats['total_attempts'] / total_operations
        elif event_type == 'final_failure':
            stats['failed_retries'] += 1
            # 평균 시도 횟수 업데이트
            total_operations = stats['successful_retries'] + stats['failed_retries']
            if total_operations > 0:
                stats['average_attempts'] = stats['total_attempts'] / total_operations
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """재시도 통계를 반환합니다."""
        return {
            'operations': dict(self.retry_stats),
            'total_operations': len(self.retry_stats),
            'configuration': {
                'max_attempts': self.max_attempts,
                'base_delay': self.base_delay,
                'max_delay': self.max_delay,
                'backoff_factor': self.backoff_factor,
                'jitter': self.jitter
            }
        }
    
    def reset_statistics(self):
        """통계를 초기화합니다."""
        self.retry_stats.clear()
        logger.info("재시도 통계가 초기화되었습니다.")

class CircuitBreaker:
    """서킷 브레이커 패턴 구현"""
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: type = Exception):
        """
        서킷 브레이커 초기화
        
        Args:
            failure_threshold: 실패 임계값
            recovery_timeout: 복구 타임아웃 (초)
            expected_exception: 예상 예외 타입
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # 서킷 상태
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        
        logger.info("서킷 브레이커가 초기화되었습니다.")
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        비동기 함수를 서킷 브레이커로 보호하여 호출합니다.
        
        Args:
            func: 호출할 함수
            *args: 함수 인수
            **kwargs: 함수 키워드 인수
            
        Returns:
            함수 실행 결과
            
        Raises:
            CircuitBreakerOpenError: 서킷이 열려있는 경우
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info("서킷 브레이커 HALF_OPEN 상태로 전환")
            else:
                raise CircuitBreakerOpenError("서킷 브레이커가 열려있습니다.")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        동기 함수를 서킷 브레이커로 보호하여 호출합니다.
        
        Args:
            func: 호출할 함수
            *args: 함수 인수
            **kwargs: 함수 키워드 인수
            
        Returns:
            함수 실행 결과
            
        Raises:
            CircuitBreakerOpenError: 서킷이 열려있는 경우
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info("서킷 브레이커 HALF_OPEN 상태로 전환")
            else:
                raise CircuitBreakerOpenError("서킷 브레이커가 열려있습니다.")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """서킷 리셋을 시도해야 하는지 확인합니다."""
        if self.last_failure_time is None:
            return False
        
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """성공 시 호출됩니다."""
        self.failure_count = 0
        self.state = 'CLOSED'
        logger.debug("서킷 브레이커 CLOSED 상태로 전환")
    
    def _on_failure(self):
        """실패 시 호출됩니다."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"서킷 브레이커 OPEN 상태로 전환 (실패 {self.failure_count}회)")
    
    def get_state(self) -> Dict[str, Any]:
        """서킷 브레이커 상태를 반환합니다."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'last_failure_time': self.last_failure_time,
            'recovery_timeout': self.recovery_timeout
        }

class RetryableOperation:
    """재시도 가능한 작업을 나타내는 클래스"""
    
    def __init__(self,
                 operation_func: Callable,
                 operation_name: str,
                 max_retries: int = 3,
                 retry_delays: List[float] = None,
                 retryable_exceptions: Tuple[type, ...] = None):
        """
        재시도 가능한 작업 초기화
        
        Args:
            operation_func: 실행할 함수
            operation_name: 작업 이름
            max_retries: 최대 재시도 횟수
            retry_delays: 사용자 정의 지연 시간 리스트
            retryable_exceptions: 재시도 가능한 예외 타입들
        """
        self.operation_func = operation_func
        self.operation_name = operation_name
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [1, 2, 4, 8, 16]
        self.retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            TimeoutError,
            OSError,
            subprocess.SubprocessError
        )
        
        # 실행 상태
        self.attempt_count = 0
        self.last_exception = None
        self.start_time = None
        self.end_time = None
        
        logger.debug(f"재시도 가능한 작업 생성: {operation_name}")
    
    async def execute_async(self, *args, **kwargs) -> Any:
        """비동기 작업을 실행합니다."""
        self.start_time = time.time()
        self.attempt_count = 0
        
        for attempt in range(self.max_retries + 1):
            self.attempt_count = attempt + 1
            
            try:
                logger.debug(f"{self.operation_name} 실행 시도 {self.attempt_count}/{self.max_retries + 1}")
                
                result = await self.operation_func(*args, **kwargs)
                
                self.end_time = time.time()
                logger.info(f"{self.operation_name} 성공 (시도 {self.attempt_count}, "
                          f"실행시간: {self.end_time - self.start_time:.2f}초)")
                
                return result
                
            except self.retryable_exceptions as e:
                self.last_exception = e
                
                logger.warning(f"{self.operation_name} 실패 (시도 {self.attempt_count}): {e}")
                
                # 마지막 시도가 아닌 경우 지연
                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    logger.info(f"{self.operation_name} {delay}초 후 재시도...")
                    await asyncio.sleep(delay)
                else:
                    self.end_time = time.time()
                    logger.error(f"{self.operation_name} 최종 실패 "
                               f"(총 {self.attempt_count}회 시도, "
                               f"실행시간: {self.end_time - self.start_time:.2f}초)")
                    raise
            
            except Exception as e:
                # 재시도 불가능한 예외
                self.last_exception = e
                self.end_time = time.time()
                
                logger.error(f"{self.operation_name} 재시도 불가능한 오류: {e}")
                raise
    
    def execute_sync(self, *args, **kwargs) -> Any:
        """동기 작업을 실행합니다."""
        self.start_time = time.time()
        self.attempt_count = 0
        
        for attempt in range(self.max_retries + 1):
            self.attempt_count = attempt + 1
            
            try:
                logger.debug(f"{self.operation_name} 실행 시도 {self.attempt_count}/{self.max_retries + 1}")
                
                result = self.operation_func(*args, **kwargs)
                
                self.end_time = time.time()
                logger.info(f"{self.operation_name} 성공 (시도 {self.attempt_count}, "
                          f"실행시간: {self.end_time - self.start_time:.2f}초)")
                
                return result
                
            except self.retryable_exceptions as e:
                self.last_exception = e
                
                logger.warning(f"{self.operation_name} 실패 (시도 {self.attempt_count}): {e}")
                
                # 마지막 시도가 아닌 경우 지연
                if attempt < self.max_retries:
                    delay = self._get_retry_delay(attempt)
                    logger.info(f"{self.operation_name} {delay}초 후 재시도...")
                    time.sleep(delay)
                else:
                    self.end_time = time.time()
                    logger.error(f"{self.operation_name} 최종 실패 "
                               f"(총 {self.attempt_count}회 시도, "
                               f"실행시간: {self.end_time - self.start_time:.2f}초)")
                    raise
            
            except Exception as e:
                # 재시도 불가능한 예외
                self.last_exception = e
                self.end_time = time.time()
                
                logger.error(f"{self.operation_name} 재시도 불가능한 오류: {e}")
                raise
    
    def _get_retry_delay(self, attempt_index: int) -> float:
        """재시도 지연 시간을 반환합니다."""
        if attempt_index < len(self.retry_delays):
            return self.retry_delays[attempt_index]
        else:
            # 기본 지수 백오프
            return min(2 ** attempt_index, 60)
    
    def get_execution_info(self) -> Dict[str, Any]:
        """실행 정보를 반환합니다."""
        return {
            'operation_name': self.operation_name,
            'attempt_count': self.attempt_count,
            'max_retries': self.max_retries,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'execution_duration': (self.end_time - self.start_time) if self.end_time and self.start_time else None,
            'last_exception': str(self.last_exception) if self.last_exception else None,
            'succeeded': self.end_time is not None and self.last_exception is None
        }

class CircuitBreakerOpenError(Exception):
    """서킷 브레이커가 열려있을 때 발생하는 예외"""
    pass

# 재시도 데코레이터들
def retry_async(max_attempts: int = 3,
                base_delay: float = 1.0,
                max_delay: float = 60.0,
                backoff_factor: float = 2.0,
                exceptions: Tuple[type, ...] = (Exception,),
                operation_name: str = None):
    """비동기 함수용 재시도 데코레이터"""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retry_manager = RetryManager(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor
            )
            
            name = operation_name or func.__name__
            
            return await retry_manager.retry_async(
                func, *args,
                operation_name=name,
                exceptions=exceptions,
                **kwargs
            )
        
        return wrapper
    return decorator

def retry_sync(max_attempts: int = 3,
               base_delay: float = 1.0,
               max_delay: float = 60.0,
               backoff_factor: float = 2.0,
               exceptions: Tuple[type, ...] = (Exception,),
               operation_name: str = None):
    """동기 함수용 재시도 데코레이터"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            retry_manager = RetryManager(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor
            )
            
            name = operation_name or func.__name__
            
            return retry_manager.retry_sync(
                func, *args,
                operation_name=name,
                exceptions=exceptions,
                **kwargs
            )
        
        return wrapper
    return decorator

def circuit_breaker(failure_threshold: int = 5,
                   recovery_timeout: float = 60.0,
                   expected_exception: type = Exception):
    """서킷 브레이커 데코레이터"""
    
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                return await breaker.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                return breaker.call_sync(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator

# 편의 함수들
def create_retry_manager(max_attempts: int = 3,
                        base_delay: float = 1.0,
                        max_delay: float = 60.0,
                        backoff_factor: float = 2.0) -> RetryManager:
    """재시도 관리자를 생성합니다."""
    return RetryManager(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor
    )

def create_circuit_breaker(failure_threshold: int = 5,
                          recovery_timeout: float = 60.0,
                          expected_exception: type = Exception) -> CircuitBreaker:
    """서킷 브레이커를 생성합니다."""
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )

# ... existing code continues ... 

class ManualInterventionSystem:
    """수동 개입 시스템"""
    
    def __init__(self, error_recovery_system: ErrorRecoverySystem):
        """
        수동 개입 시스템 초기화
        
        Args:
            error_recovery_system: 에러 복구 시스템
        """
        self.error_recovery_system = error_recovery_system
        
        # 개입 요청 큐
        self.pending_interventions: List[InterventionRequest] = []
        self.completed_interventions: List[InterventionRequest] = []
        self.active_interventions: Dict[str, InterventionRequest] = {}
        
        # 에스컬레이션 규칙
        self.escalation_rules: Dict[ErrorType, EscalationRule] = {}
        
        # 알림 시스템
        self.notification_channels: List[NotificationChannel] = []
        self.notification_history: deque = deque(maxlen=100)
        
        # 상태
        self.is_active = False
        self.intervention_count = 0
        
        # 기본 에스컬레이션 규칙 설정
        self._setup_default_escalation_rules()
        
        logger.info("수동 개입 시스템이 초기화되었습니다.")
    
    def _setup_default_escalation_rules(self):
        """기본 에스컬레이션 규칙을 설정합니다."""
        
        # Google 보안 챌린지 - 즉시 에스컬레이션
        self.escalation_rules[ErrorType.GOOGLE_SECURITY_CHALLENGE] = EscalationRule(
            error_type=ErrorType.GOOGLE_SECURITY_CHALLENGE,
            escalation_delay=0,  # 즉시
            max_auto_attempts=0,
            notification_channels=['admin', 'security_team'],
            priority=InterventionPriority.URGENT,
            timeout_minutes=30
        )
        
        # 캡챠 챌린지 - 즉시 에스컬레이션
        self.escalation_rules[ErrorType.CAPTCHA_CHALLENGE] = EscalationRule(
            error_type=ErrorType.CAPTCHA_CHALLENGE,
            escalation_delay=0,
            max_auto_attempts=0,
            notification_channels=['admin'],
            priority=InterventionPriority.HIGH,
            timeout_minutes=15
        )
        
        # 메모리 에러 - 5분 후 에스컬레이션
        self.escalation_rules[ErrorType.MEMORY_ERROR] = EscalationRule(
            error_type=ErrorType.MEMORY_ERROR,
            escalation_delay=300,
            max_auto_attempts=2,
            notification_channels=['admin', 'devops'],
            priority=InterventionPriority.HIGH,
            timeout_minutes=60
        )
        
        # 시스템 과부하 - 10분 후 에스컬레이션
        self.escalation_rules[ErrorType.SYSTEM_OVERLOAD] = EscalationRule(
            error_type=ErrorType.SYSTEM_OVERLOAD,
            escalation_delay=600,
            max_auto_attempts=3,
            notification_channels=['devops'],
            priority=InterventionPriority.MEDIUM,
            timeout_minutes=120
        )
    
    async def request_intervention(self, 
                                 error_event: ErrorEvent,
                                 intervention_type: 'InterventionType',
                                 priority: 'InterventionPriority' = InterventionPriority.MEDIUM,
                                 timeout_minutes: int = 60,
                                 required_skills: List[str] = None) -> str:
        """
        수동 개입을 요청합니다.
        
        Args:
            error_event: 에러 이벤트
            intervention_type: 개입 타입
            priority: 우선순위
            timeout_minutes: 타임아웃 (분)
            required_skills: 필요한 기술/권한
            
        Returns:
            개입 요청 ID
        """
        self.intervention_count += 1
        
        # 개입 요청 생성
        intervention_request = InterventionRequest(
            id=f"intervention_{int(time.time())}_{self.intervention_count}",
            error_event=error_event,
            intervention_type=intervention_type,
            priority=priority,
            created_at=datetime.now(),
            timeout_at=datetime.now() + timedelta(minutes=timeout_minutes),
            required_skills=required_skills or [],
            status=InterventionStatus.PENDING
        )
        
        # 큐에 추가
        self.pending_interventions.append(intervention_request)
        self.pending_interventions.sort(key=lambda x: x.priority.value, reverse=True)
        
        # 알림 전송
        await self._send_intervention_notification(intervention_request)
        
        logger.warning(f"수동 개입 요청: {intervention_request.id} - {error_event.error_type.value}")
        
        return intervention_request.id
    
    async def assign_intervention(self, intervention_id: str, assignee: str) -> bool:
        """
        개입 요청을 담당자에게 할당합니다.
        
        Args:
            intervention_id: 개입 요청 ID
            assignee: 담당자
            
        Returns:
            할당 성공 여부
        """
        # 대기 중인 요청에서 찾기
        for i, request in enumerate(self.pending_interventions):
            if request.id == intervention_id:
                # 상태 업데이트
                request.status = InterventionStatus.ASSIGNED
                request.assignee = assignee
                request.assigned_at = datetime.now()
                
                # 활성 개입으로 이동
                self.active_interventions[intervention_id] = request
                self.pending_interventions.pop(i)
                
                logger.info(f"개입 요청 할당: {intervention_id} -> {assignee}")
                
                # 할당 알림
                await self._send_assignment_notification(request)
                
                return True
        
        logger.error(f"개입 요청을 찾을 수 없음: {intervention_id}")
        return False
    
    async def complete_intervention(self, 
                                  intervention_id: str,
                                  resolution: str,
                                  success: bool = True,
                                  additional_notes: str = "") -> bool:
        """
        개입을 완료합니다.
        
        Args:
            intervention_id: 개입 요청 ID
            resolution: 해결 방법
            success: 성공 여부
            additional_notes: 추가 노트
            
        Returns:
            완료 처리 성공 여부
        """
        if intervention_id not in self.active_interventions:
            logger.error(f"활성 개입을 찾을 수 없음: {intervention_id}")
            return False
        
        request = self.active_interventions[intervention_id]
        
        # 상태 업데이트
        request.status = InterventionStatus.COMPLETED if success else InterventionStatus.FAILED
        request.completed_at = datetime.now()
        request.resolution = resolution
        request.additional_notes = additional_notes
        
        # 완료된 개입으로 이동
        self.completed_interventions.append(request)
        del self.active_interventions[intervention_id]
        
        # 원래 에러 이벤트 업데이트
        if success:
            request.error_event.resolved = True
            request.error_event.resolution_time = datetime.now()
        
        logger.info(f"개입 완료: {intervention_id} - {'성공' if success else '실패'}")
        
        # 완료 알림
        await self._send_completion_notification(request)
        
        return True
    
    async def escalate_intervention(self, intervention_id: str, new_priority: 'InterventionPriority') -> bool:
        """
        개입을 에스컬레이션합니다.
        
        Args:
            intervention_id: 개입 요청 ID
            new_priority: 새로운 우선순위
            
        Returns:
            에스컬레이션 성공 여부
        """
        # 대기 중인 요청에서 찾기
        for request in self.pending_interventions:
            if request.id == intervention_id:
                old_priority = request.priority
                request.priority = new_priority
                request.escalated_at = datetime.now()
                
                # 우선순위 재정렬
                self.pending_interventions.sort(key=lambda x: x.priority.value, reverse=True)
                
                logger.warning(f"개입 에스컬레이션: {intervention_id} - {old_priority.value} -> {new_priority.value}")
                
                # 에스컬레이션 알림
                await self._send_escalation_notification(request, old_priority)
                
                return True
        
        # 활성 개입에서 찾기
        if intervention_id in self.active_interventions:
            request = self.active_interventions[intervention_id]
            old_priority = request.priority
            request.priority = new_priority
            request.escalated_at = datetime.now()
            
            logger.warning(f"활성 개입 에스컬레이션: {intervention_id} - {old_priority.value} -> {new_priority.value}")
            
            # 에스컬레이션 알림
            await self._send_escalation_notification(request, old_priority)
            
            return True
        
        logger.error(f"개입 요청을 찾을 수 없음: {intervention_id}")
        return False
    
    async def _send_intervention_notification(self, request: 'InterventionRequest'):
        """개입 요청 알림을 전송합니다."""
        notification = InterventionNotification(
            type=NotificationType.INTERVENTION_REQUESTED,
            intervention_request=request,
            timestamp=datetime.now(),
            message=f"수동 개입 필요: {request.error_event.error_type.value}"
        )
        
        await self._send_notification(notification)
    
    async def _send_assignment_notification(self, request: 'InterventionRequest'):
        """할당 알림을 전송합니다."""
        notification = InterventionNotification(
            type=NotificationType.INTERVENTION_ASSIGNED,
            intervention_request=request,
            timestamp=datetime.now(),
            message=f"개입 할당됨: {request.assignee}"
        )
        
        await self._send_notification(notification)
    
    async def _send_completion_notification(self, request: 'InterventionRequest'):
        """완료 알림을 전송합니다."""
        notification = InterventionNotification(
            type=NotificationType.INTERVENTION_COMPLETED,
            intervention_request=request,
            timestamp=datetime.now(),
            message=f"개입 완료: {request.resolution}"
        )
        
        await self._send_notification(notification)
    
    async def _send_escalation_notification(self, request: 'InterventionRequest', old_priority: 'InterventionPriority'):
        """에스컬레이션 알림을 전송합니다."""
        notification = InterventionNotification(
            type=NotificationType.INTERVENTION_ESCALATED,
            intervention_request=request,
            timestamp=datetime.now(),
            message=f"개입 에스컬레이션: {old_priority.value} -> {request.priority.value}"
        )
        
        await self._send_notification(notification)
    
    async def _send_notification(self, notification: 'InterventionNotification'):
        """알림을 전송합니다."""
        self.notification_history.append(notification)
        
        for channel in self.notification_channels:
            try:
                await channel.send_notification(notification)
            except Exception as e:
                logger.error(f"알림 전송 실패 ({channel.name}): {e}")
    
    def add_notification_channel(self, channel: 'NotificationChannel'):
        """알림 채널을 추가합니다."""
        self.notification_channels.append(channel)
        logger.info(f"알림 채널 추가: {channel.name}")
    
    def get_intervention_status(self) -> Dict[str, Any]:
        """개입 상태를 반환합니다."""
        return {
            'total_interventions': self.intervention_count,
            'pending_count': len(self.pending_interventions),
            'active_count': len(self.active_interventions),
            'completed_count': len(self.completed_interventions),
            'pending_requests': [
                {
                    'id': req.id,
                    'error_type': req.error_event.error_type.value,
                    'priority': req.priority.value,
                    'created_at': req.created_at.isoformat(),
                    'timeout_at': req.timeout_at.isoformat(),
                    'required_skills': req.required_skills
                }
                for req in self.pending_interventions
            ],
            'active_requests': [
                {
                    'id': req.id,
                    'error_type': req.error_event.error_type.value,
                    'priority': req.priority.value,
                    'assignee': req.assignee,
                    'assigned_at': req.assigned_at.isoformat() if req.assigned_at else None,
                    'timeout_at': req.timeout_at.isoformat()
                }
                for req in self.active_interventions.values()
            ]
        }

# 데이터 클래스들
@dataclass
class InterventionRequest:
    """개입 요청"""
    id: str
    error_event: ErrorEvent
    intervention_type: 'InterventionType'
    priority: 'InterventionPriority'
    created_at: datetime
    timeout_at: datetime
    required_skills: List[str]
    status: 'InterventionStatus'
    assignee: Optional[str] = None
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    resolution: Optional[str] = None
    additional_notes: Optional[str] = None

@dataclass
class EscalationRule:
    """에스컬레이션 규칙"""
    error_type: ErrorType
    escalation_delay: int  # 초
    max_auto_attempts: int
    notification_channels: List[str]
    priority: 'InterventionPriority'
    timeout_minutes: int

@dataclass
class InterventionNotification:
    """개입 알림"""
    type: 'NotificationType'
    intervention_request: InterventionRequest
    timestamp: datetime
    message: str

# 열거형들
class InterventionType(Enum):
    """개입 타입"""
    MANUAL_VERIFICATION = "manual_verification"
    CAPTCHA_SOLVING = "captcha_solving"
    SECURITY_CHALLENGE = "security_challenge"
    SYSTEM_MAINTENANCE = "system_maintenance"
    CONFIGURATION_CHANGE = "configuration_change"
    EMERGENCY_RESPONSE = "emergency_response"

class InterventionPriority(Enum):
    """개입 우선순위"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class InterventionStatus(Enum):
    """개입 상태"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class NotificationType(Enum):
    """알림 타입"""
    INTERVENTION_REQUESTED = "intervention_requested"
    INTERVENTION_ASSIGNED = "intervention_assigned"
    INTERVENTION_COMPLETED = "intervention_completed"
    INTERVENTION_ESCALATED = "intervention_escalated"
    INTERVENTION_TIMEOUT = "intervention_timeout"

# 알림 채널 클래스들
class NotificationChannel:
    """알림 채널 기본 클래스"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def send_notification(self, notification: InterventionNotification):
        """알림을 전송합니다. 서브클래스에서 구현해야 합니다."""
        raise NotImplementedError

class EmailNotificationChannel(NotificationChannel):
    """이메일 알림 채널"""
    
    def __init__(self, smtp_server: str, smtp_port: int, username: str, password: str, recipients: List[str]):
        super().__init__("email")
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients
    
    async def send_notification(self, notification: InterventionNotification):
        """이메일로 알림을 전송합니다."""
        try:
            subject = f"Google Account Creator - {notification.type.value}"
            body = self._format_notification(notification)
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = ', '.join(self.recipients)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            logger.info(f"이메일 알림 전송 완료: {notification.intervention_request.id}")
            
        except Exception as e:
            logger.error(f"이메일 알림 전송 실패: {e}")
    
    def _format_notification(self, notification: InterventionNotification) -> str:
        """알림을 포맷합니다."""
        req = notification.intervention_request
        
        return f"""
Google Account Creator 수동 개입 알림

알림 타입: {notification.type.value}
개입 요청 ID: {req.id}
에러 타입: {req.error_event.error_type.value}
우선순위: {req.priority.value}
생성 시간: {req.created_at}
타임아웃: {req.timeout_at}
담당자: {req.assignee or 'N/A'}

에러 메시지: {req.error_event.error_message}
컴포넌트: {req.error_event.component}
디바이스: {req.error_event.device_id or 'N/A'}

해결 방법: {req.resolution or 'N/A'}
추가 노트: {req.additional_notes or 'N/A'}

메시지: {notification.message}
        """.strip()

class SlackNotificationChannel(NotificationChannel):
    """Slack 알림 채널"""
    
    def __init__(self, webhook_url: str, channel: str = "#alerts"):
        super().__init__("slack")
        self.webhook_url = webhook_url
        self.channel = channel
    
    async def send_notification(self, notification: InterventionNotification):
        """Slack으로 알림을 전송합니다."""
        try:
            import aiohttp
            
            payload = {
                "channel": self.channel,
                "text": f"Google Account Creator - {notification.type.value}",
                "attachments": [{
                    "color": self._get_color(notification.intervention_request.priority),
                    "fields": [
                        {"title": "개입 ID", "value": notification.intervention_request.id, "short": True},
                        {"title": "에러 타입", "value": notification.intervention_request.error_event.error_type.value, "short": True},
                        {"title": "우선순위", "value": notification.intervention_request.priority.value, "short": True},
                        {"title": "담당자", "value": notification.intervention_request.assignee or "미할당", "short": True},
                        {"title": "메시지", "value": notification.message, "short": False}
                    ]
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Slack 알림 전송 완료: {notification.intervention_request.id}")
                    else:
                        logger.error(f"Slack 알림 전송 실패: {response.status}")
            
        except Exception as e:
            logger.error(f"Slack 알림 전송 실패: {e}")
    
    def _get_color(self, priority: InterventionPriority) -> str:
        """우선순위에 따른 색상을 반환합니다."""
        colors = {
            InterventionPriority.LOW: "#36a64f",
            InterventionPriority.MEDIUM: "#ffcc00",
            InterventionPriority.HIGH: "#ff9900",
            InterventionPriority.URGENT: "#ff0000",
            InterventionPriority.CRITICAL: "#8b0000"
        }
        return colors.get(priority, "#dddddd")

class FileNotificationChannel(NotificationChannel):
    """파일 알림 채널"""
    
    def __init__(self, file_path: str):
        super().__init__("file")
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def send_notification(self, notification: InterventionNotification):
        """파일로 알림을 저장합니다."""
        try:
            notification_data = {
                "timestamp": notification.timestamp.isoformat(),
                "type": notification.type.value,
                "message": notification.message,
                "intervention_request": {
                    "id": notification.intervention_request.id,
                    "error_type": notification.intervention_request.error_event.error_type.value,
                    "priority": notification.intervention_request.priority.value,
                    "status": notification.intervention_request.status.value,
                    "assignee": notification.intervention_request.assignee,
                    "error_message": notification.intervention_request.error_event.error_message,
                    "component": notification.intervention_request.error_event.component
                }
            }
            
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(notification_data, ensure_ascii=False) + '\n')
            
            logger.debug(f"파일 알림 저장 완료: {notification.intervention_request.id}")
            
        except Exception as e:
            logger.error(f"파일 알림 저장 실패: {e}")

class AdminInterface:
    """관리자 인터페이스"""
    
    def __init__(self, manual_intervention_system: ManualInterventionSystem):
        """
        관리자 인터페이스 초기화
        
        Args:
            manual_intervention_system: 수동 개입 시스템
        """
        self.intervention_system = manual_intervention_system
        self.error_recovery_system = manual_intervention_system.error_recovery_system
        
        # 명령어 매핑
        self.commands = {
            'status': self._cmd_status,
            'list_interventions': self._cmd_list_interventions,
            'assign': self._cmd_assign_intervention,
            'complete': self._cmd_complete_intervention,
            'escalate': self._cmd_escalate_intervention,
            'system_pause': self._cmd_system_pause,
            'system_resume': self._cmd_system_resume,
            'system_emergency_stop': self._cmd_system_emergency_stop,
            'help': self._cmd_help
        }
        
        logger.info("관리자 인터페이스가 초기화되었습니다.")
    
    async def execute_command(self, command: str, args: List[str] = None) -> Dict[str, Any]:
        """
        관리자 명령을 실행합니다.
        
        Args:
            command: 명령어
            args: 명령어 인수
            
        Returns:
            실행 결과
        """
        args = args or []
        
        if command not in self.commands:
            return {
                'success': False,
                'error': f'알 수 없는 명령어: {command}',
                'available_commands': list(self.commands.keys())
            }
        
        try:
            result = await self.commands[command](args)
            return {
                'success': True,
                'command': command,
                'result': result
            }
        except Exception as e:
            logger.error(f"명령어 실행 오류 ({command}): {e}")
            return {
                'success': False,
                'command': command,
                'error': str(e)
            }
    
    async def _cmd_status(self, args: List[str]) -> Dict[str, Any]:
        """시스템 상태를 반환합니다."""
        return {
            'system_status': self.error_recovery_system.get_system_status(),
            'intervention_status': self.intervention_system.get_intervention_status(),
            'timestamp': datetime.now().isoformat()
        }
    
    async def _cmd_list_interventions(self, args: List[str]) -> Dict[str, Any]:
        """개입 요청 목록을 반환합니다."""
        status_filter = args[0] if args else None
        
        interventions = []
        
        # 대기 중인 요청
        if status_filter is None or status_filter == 'pending':
            interventions.extend([
                {
                    'id': req.id,
                    'status': 'pending',
                    'error_type': req.error_event.error_type.value,
                    'priority': req.priority.value,
                    'created_at': req.created_at.isoformat(),
                    'timeout_at': req.timeout_at.isoformat(),
                    'required_skills': req.required_skills
                }
                for req in self.intervention_system.pending_interventions
            ])
        
        # 활성 요청
        if status_filter is None or status_filter == 'active':
            interventions.extend([
                {
                    'id': req.id,
                    'status': 'active',
                    'error_type': req.error_event.error_type.value,
                    'priority': req.priority.value,
                    'assignee': req.assignee,
                    'assigned_at': req.assigned_at.isoformat() if req.assigned_at else None,
                    'timeout_at': req.timeout_at.isoformat()
                }
                for req in self.intervention_system.active_interventions.values()
            ])
        
        return {
            'interventions': interventions,
            'total_count': len(interventions),
            'filter': status_filter
        }
    
    async def _cmd_assign_intervention(self, args: List[str]) -> Dict[str, Any]:
        """개입 요청을 할당합니다."""
        if len(args) < 2:
            return {'error': '사용법: assign <intervention_id> <assignee>'}
        
        intervention_id, assignee = args[0], args[1]
        success = await self.intervention_system.assign_intervention(intervention_id, assignee)
        
        return {
            'intervention_id': intervention_id,
            'assignee': assignee,
            'assigned': success
        }
    
    async def _cmd_complete_intervention(self, args: List[str]) -> Dict[str, Any]:
        """개입을 완료합니다."""
        if len(args) < 2:
            return {'error': '사용법: complete <intervention_id> <resolution> [success] [notes]'}
        
        intervention_id = args[0]
        resolution = args[1]
        success = args[2].lower() == 'true' if len(args) > 2 else True
        notes = args[3] if len(args) > 3 else ""
        
        completed = await self.intervention_system.complete_intervention(
            intervention_id, resolution, success, notes
        )
        
        return {
            'intervention_id': intervention_id,
            'resolution': resolution,
            'success': success,
            'completed': completed
        }
    
    async def _cmd_escalate_intervention(self, args: List[str]) -> Dict[str, Any]:
        """개입을 에스컬레이션합니다."""
        if len(args) < 2:
            return {'error': '사용법: escalate <intervention_id> <priority>'}
        
        intervention_id = args[0]
        priority_str = args[1].upper()
        
        try:
            new_priority = InterventionPriority[priority_str]
        except KeyError:
            return {'error': f'잘못된 우선순위: {priority_str}'}
        
        escalated = await self.intervention_system.escalate_intervention(intervention_id, new_priority)
        
        return {
            'intervention_id': intervention_id,
            'new_priority': new_priority.value,
            'escalated': escalated
        }
    
    async def _cmd_system_pause(self, args: List[str]) -> Dict[str, Any]:
        """시스템을 일시정지합니다."""
        reason = args[0] if args else "Manual pause via admin interface"
        await self.error_recovery_system.pause_system(reason)
        
        return {
            'action': 'pause',
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _cmd_system_resume(self, args: List[str]) -> Dict[str, Any]:
        """시스템을 재개합니다."""
        await self.error_recovery_system.resume_system()
        
        return {
            'action': 'resume',
            'timestamp': datetime.now().isoformat()
        }
    
    async def _cmd_system_emergency_stop(self, args: List[str]) -> Dict[str, Any]:
        """시스템을 비상 정지합니다."""
        reason = args[0] if args else "Emergency stop via admin interface"
        await self.error_recovery_system.emergency_stop(reason)
        
        return {
            'action': 'emergency_stop',
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _cmd_help(self, args: List[str]) -> Dict[str, Any]:
        """도움말을 반환합니다."""
        help_text = """
관리자 인터페이스 명령어:

status - 시스템 상태 확인
list_interventions [pending|active] - 개입 요청 목록
assign <intervention_id> <assignee> - 개입 요청 할당
complete <intervention_id> <resolution> [success] [notes] - 개입 완료
escalate <intervention_id> <priority> - 개입 에스컬레이션
system_pause [reason] - 시스템 일시정지
system_resume - 시스템 재개
system_emergency_stop [reason] - 시스템 비상정지
help - 이 도움말 표시
        """.strip()
        
        return {'help': help_text}

# 편의 함수들
def create_manual_intervention_system(error_recovery_system: ErrorRecoverySystem) -> ManualInterventionSystem:
    """수동 개입 시스템을 생성합니다."""
    return ManualInterventionSystem(error_recovery_system)

def create_admin_interface(manual_intervention_system: ManualInterventionSystem) -> AdminInterface:
    """관리자 인터페이스를 생성합니다."""
    return AdminInterface(manual_intervention_system)

# ... existing code continues ... 

class WatchdogProcess:
    """워치독 프로세스 - 시스템 헬스 모니터링 및 자동 복구"""
    
    def __init__(self, 
                 error_recovery_system: ErrorRecoverySystem,
                 check_interval: int = 30,
                 restart_threshold: int = 3,
                 max_restart_attempts: int = 5):
        """
        워치독 프로세스 초기화
        
        Args:
            error_recovery_system: 에러 복구 시스템
            check_interval: 헬스 체크 간격 (초)
            restart_threshold: 재시작 임계값 (연속 실패 횟수)
            max_restart_attempts: 최대 재시작 시도 횟수
        """
        self.error_recovery_system = error_recovery_system
        self.check_interval = check_interval
        self.restart_threshold = restart_threshold
        self.max_restart_attempts = max_restart_attempts
        
        # 상태
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        
        # 헬스 체크 시스템
        self.health_checkers: List[HealthChecker] = []
        self.health_status: Dict[str, HealthStatus] = {}
        
        # 모니터링 통계
        self.check_count = 0
        self.failure_count = 0
        self.restart_count = 0
        self.restart_attempts: Dict[str, int] = defaultdict(int)
        
        # 히스토리
        self.health_history: deque = deque(maxlen=1000)
        self.restart_history: deque = deque(maxlen=100)
        
        # 워치독 태스크
        self.watchdog_task: Optional[asyncio.Task] = None
        
        # 기본 헬스 체커 설정
        self._setup_default_health_checkers()
        
        logger.info("워치독 프로세스가 초기화되었습니다.")
    
    def _setup_default_health_checkers(self):
        """기본 헬스 체커들을 설정합니다."""
        
        # ADB 서버 헬스 체커
        self.health_checkers.append(ADBHealthChecker())
        
        # 시스템 리소스 헬스 체커
        self.health_checkers.append(SystemResourceHealthChecker())
        
        # 워커 프로세스 헬스 체커
        self.health_checkers.append(WorkerProcessHealthChecker())
        
        # 네트워크 연결 헬스 체커
        self.health_checkers.append(NetworkHealthChecker())
        
        # 디스크 공간 헬스 체커
        self.health_checkers.append(DiskSpaceHealthChecker())
        
        logger.info(f"{len(self.health_checkers)}개의 헬스 체커가 등록되었습니다.")
    
    async def start(self):
        """워치독 프로세스를 시작합니다."""
        if self.is_running:
            logger.warning("워치독 프로세스가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # 워치독 태스크 시작
        self.watchdog_task = asyncio.create_task(self._watchdog_loop())
        
        logger.info("워치독 프로세스가 시작되었습니다.")
    
    async def stop(self):
        """워치독 프로세스를 정지합니다."""
        if not self.is_running:
            logger.warning("워치독 프로세스가 실행 중이 아닙니다.")
            return
        
        self.is_running = False
        
        # 워치독 태스크 취소
        if self.watchdog_task:
            self.watchdog_task.cancel()
            try:
                await self.watchdog_task
            except asyncio.CancelledError:
                pass
        
        logger.info("워치독 프로세스가 정지되었습니다.")
    
    async def pause(self):
        """워치독 프로세스를 일시정지합니다."""
        self.is_paused = True
        logger.info("워치독 프로세스가 일시정지되었습니다.")
    
    async def resume(self):
        """워치독 프로세스를 재개합니다."""
        self.is_paused = False
        logger.info("워치독 프로세스가 재개되었습니다.")
    
    async def _watchdog_loop(self):
        """워치독 메인 루프"""
        try:
            while self.is_running:
                if not self.is_paused:
                    await self._perform_health_checks()
                    await self._analyze_health_status()
                    await self._handle_unhealthy_components()
                
                # 다음 체크까지 대기
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info("워치독 루프가 취소되었습니다.")
        except Exception as e:
            logger.error(f"워치독 루프 오류: {e}")
            # 워치독 자체 재시작
            await self._restart_watchdog()
    
    async def _perform_health_checks(self):
        """모든 헬스 체커를 실행합니다."""
        self.check_count += 1
        check_timestamp = datetime.now()
        
        # 병렬로 헬스 체크 실행
        check_tasks = []
        for checker in self.health_checkers:
            task = asyncio.create_task(self._run_health_check(checker))
            check_tasks.append(task)
        
        # 모든 체크 완료 대기
        results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # 결과 처리
        for checker, result in zip(self.health_checkers, results):
            if isinstance(result, Exception):
                # 헬스 체커 자체에서 오류 발생
                health_status = HealthStatus(
                    component=checker.name,
                    is_healthy=False,
                    timestamp=check_timestamp,
                    message=f"헬스 체크 오류: {result}",
                    metrics={}
                )
            else:
                health_status = result
            
            # 상태 저장
            self.health_status[checker.name] = health_status
            self.health_history.append(health_status)
        
        logger.debug(f"헬스 체크 완료 (#{self.check_count})")
    
    async def _run_health_check(self, checker: 'HealthChecker') -> HealthStatus:
        """개별 헬스 체크를 실행합니다."""
        try:
            return await checker.check_health()
        except Exception as e:
            logger.error(f"헬스 체크 실패 ({checker.name}): {e}")
            return HealthStatus(
                component=checker.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"체크 실패: {e}",
                metrics={}
            )
    
    async def _analyze_health_status(self):
        """헬스 상태를 분석합니다."""
        unhealthy_components = []
        
        for component, status in self.health_status.items():
            if not status.is_healthy:
                unhealthy_components.append(component)
        
        if unhealthy_components:
            self.failure_count += 1
            logger.warning(f"비정상 컴포넌트 감지: {unhealthy_components}")
            
            # 에러 이벤트 생성
            error_event = ErrorEvent(
                error_type=ErrorType.SYSTEM_OVERLOAD,
                error_message=f"헬스 체크 실패: {', '.join(unhealthy_components)}",
                component="watchdog",
                timestamp=datetime.now(),
                severity=ErrorSeverity.HIGH,
                device_id=None,
                context={
                    'unhealthy_components': unhealthy_components,
                    'health_status': {
                        comp: {
                            'is_healthy': status.is_healthy,
                            'message': status.message,
                            'metrics': status.metrics
                        }
                        for comp, status in self.health_status.items()
                    }
                }
            )
            
            # 에러 복구 시스템에 전달
            await self.error_recovery_system.handle_error(
                error_type=error_event.error_type,
                error_message=error_event.error_message,
                component=error_event.component,
                context=error_event.context
            )
    
    async def _handle_unhealthy_components(self):
        """비정상 컴포넌트를 처리합니다."""
        for component, status in self.health_status.items():
            if not status.is_healthy:
                await self._handle_unhealthy_component(component, status)
    
    async def _handle_unhealthy_component(self, component: str, status: HealthStatus):
        """개별 비정상 컴포넌트를 처리합니다."""
        restart_attempts = self.restart_attempts[component]
        
        if restart_attempts >= self.max_restart_attempts:
            logger.error(f"컴포넌트 최대 재시작 횟수 초과: {component}")
            
            # 수동 개입 요청
            if hasattr(self.error_recovery_system, 'manual_intervention_system'):
                error_event = ErrorEvent(
                    error_type=ErrorType.WORKER_CRASHED,
                    error_message=f"컴포넌트 복구 실패: {component}",
                    component=component,
                    timestamp=datetime.now(),
                    severity=ErrorSeverity.CRITICAL
                )
                
                await self.error_recovery_system.manual_intervention_system.request_intervention(
                    error_event=error_event,
                    intervention_type=InterventionType.SYSTEM_MAINTENANCE,
                    priority=InterventionPriority.HIGH,
                    timeout_minutes=120
                )
            
            return
        
        # 재시작 시도
        logger.info(f"컴포넌트 재시작 시도: {component} (시도 {restart_attempts + 1}/{self.max_restart_attempts})")
        
        restart_success = await self._restart_component(component, status)
        
        if restart_success:
            logger.info(f"컴포넌트 재시작 성공: {component}")
            self.restart_attempts[component] = 0  # 재시작 카운터 리셋
            
            # 재시작 히스토리 기록
            restart_record = {
                'component': component,
                'timestamp': datetime.now(),
                'attempt': restart_attempts + 1,
                'success': True,
                'reason': status.message
            }
            self.restart_history.append(restart_record)
            self.restart_count += 1
            
        else:
            logger.error(f"컴포넌트 재시작 실패: {component}")
            self.restart_attempts[component] += 1
            
            # 재시작 히스토리 기록
            restart_record = {
                'component': component,
                'timestamp': datetime.now(),
                'attempt': restart_attempts + 1,
                'success': False,
                'reason': status.message
            }
            self.restart_history.append(restart_record)
    
    async def _restart_component(self, component: str, status: HealthStatus) -> bool:
        """컴포넌트를 재시작합니다."""
        try:
            # 컴포넌트별 재시작 로직
            if component == "adb_server":
                return await self._restart_adb_server()
            elif component == "worker_processes":
                return await self._restart_worker_processes()
            elif component == "network":
                return await self._restart_network_components()
            else:
                logger.warning(f"알 수 없는 컴포넌트 재시작 요청: {component}")
                return False
                
        except Exception as e:
            logger.error(f"컴포넌트 재시작 중 오류 ({component}): {e}")
            return False
    
    async def _restart_adb_server(self) -> bool:
        """ADB 서버를 재시작합니다."""
        try:
            # ADB 서버 종료
            result = subprocess.run(['adb', 'kill-server'], 
                                  capture_output=True, text=True, timeout=10)
            
            # 잠시 대기
            await asyncio.sleep(2)
            
            # ADB 서버 시작
            result = subprocess.run(['adb', 'start-server'], 
                                  capture_output=True, text=True, timeout=10)
            
            # 디바이스 연결 확인
            await asyncio.sleep(3)
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"ADB 서버 재시작 실패: {e}")
            return False
    
    async def _restart_worker_processes(self) -> bool:
        """워커 프로세스들을 재시작합니다."""
        try:
            # 이 기능은 메인 시스템과 통합되어야 함
            # 여기서는 기본적인 시그널 전송만 구현
            logger.info("워커 프로세스 재시작 요청됨")
            
            # 실제 구현에서는 워커 매니저와 통신해야 함
            # await self.error_recovery_system.restart_workers()
            
            return True
            
        except Exception as e:
            logger.error(f"워커 프로세스 재시작 실패: {e}")
            return False
    
    async def _restart_network_components(self) -> bool:
        """네트워크 컴포넌트를 재시작합니다."""
        try:
            # VPN/프록시 재연결 등
            logger.info("네트워크 컴포넌트 재시작 요청됨")
            
            # 실제 구현에서는 네트워크 관리자와 통신해야 함
            # await self.error_recovery_system.restart_network()
            
            return True
            
        except Exception as e:
            logger.error(f"네트워크 컴포넌트 재시작 실패: {e}")
            return False
    
    async def _restart_watchdog(self):
        """워치독 자체를 재시작합니다."""
        logger.warning("워치독 자체 재시작")
        
        try:
            await self.stop()
            await asyncio.sleep(5)
            await self.start()
            
        except Exception as e:
            logger.critical(f"워치독 재시작 실패: {e}")
    
    def add_health_checker(self, checker: 'HealthChecker'):
        """헬스 체커를 추가합니다."""
        self.health_checkers.append(checker)
        logger.info(f"헬스 체커 추가: {checker.name}")
    
    def get_watchdog_status(self) -> Dict[str, Any]:
        """워치독 상태를 반환합니다."""
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'uptime_seconds': uptime,
            'check_count': self.check_count,
            'failure_count': self.failure_count,
            'restart_count': self.restart_count,
            'health_checkers': [checker.name for checker in self.health_checkers],
            'current_health_status': {
                comp: {
                    'is_healthy': status.is_healthy,
                    'message': status.message,
                    'last_check': status.timestamp.isoformat()
                }
                for comp, status in self.health_status.items()
            },
            'recent_restarts': [
                {
                    'component': record['component'],
                    'timestamp': record['timestamp'].isoformat(),
                    'attempt': record['attempt'],
                    'success': record['success'],
                    'reason': record['reason']
                }
                for record in list(self.restart_history)[-10:]
            ]
        }

# 헬스 체크 관련 클래스들
@dataclass
class HealthStatus:
    """헬스 상태"""
    component: str
    is_healthy: bool
    timestamp: datetime
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)

class HealthChecker:
    """헬스 체커 기본 클래스"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def check_health(self) -> HealthStatus:
        """헬스 체크를 수행합니다. 서브클래스에서 구현해야 합니다."""
        raise NotImplementedError

class ADBHealthChecker(HealthChecker):
    """ADB 서버 헬스 체커"""
    
    def __init__(self):
        super().__init__("adb_server")
    
    async def check_health(self) -> HealthStatus:
        """ADB 서버 헬스를 체크합니다."""
        try:
            # ADB 서버 상태 확인
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                return HealthStatus(
                    component=self.name,
                    is_healthy=False,
                    timestamp=datetime.now(),
                    message=f"ADB 명령 실패: {result.stderr}",
                    metrics={'return_code': result.returncode}
                )
            
            # 연결된 디바이스 수 확인
            output_lines = result.stdout.strip().split('\n')
            device_lines = [line for line in output_lines if '\tdevice' in line]
            device_count = len(device_lines)
            
            return HealthStatus(
                component=self.name,
                is_healthy=True,
                timestamp=datetime.now(),
                message=f"ADB 서버 정상, 연결된 디바이스: {device_count}개",
                metrics={'device_count': device_count}
            )
            
        except subprocess.TimeoutExpired:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message="ADB 명령 타임아웃",
                metrics={}
            )
        except Exception as e:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"ADB 체크 오류: {e}",
                metrics={}
            )

class SystemResourceHealthChecker(HealthChecker):
    """시스템 리소스 헬스 체커"""
    
    def __init__(self, cpu_threshold: float = 90.0, memory_threshold: float = 90.0):
        super().__init__("system_resources")
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
    
    async def check_health(self) -> HealthStatus:
        """시스템 리소스 헬스를 체크합니다."""
        try:
            import psutil
            
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # 헬스 상태 판단
            is_healthy = (cpu_percent < self.cpu_threshold and 
                         memory_percent < self.memory_threshold)
            
            message_parts = []
            if cpu_percent >= self.cpu_threshold:
                message_parts.append(f"CPU 과부하: {cpu_percent:.1f}%")
            if memory_percent >= self.memory_threshold:
                message_parts.append(f"메모리 과부하: {memory_percent:.1f}%")
            
            message = ("; ".join(message_parts) if message_parts 
                      else f"시스템 리소스 정상 (CPU: {cpu_percent:.1f}%, 메모리: {memory_percent:.1f}%)")
            
            return HealthStatus(
                component=self.name,
                is_healthy=is_healthy,
                timestamp=datetime.now(),
                message=message,
                metrics={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent,
                    'memory_available_gb': memory.available / 1024 / 1024 / 1024
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"시스템 리소스 체크 오류: {e}",
                metrics={}
            )

class WorkerProcessHealthChecker(HealthChecker):
    """워커 프로세스 헬스 체커"""
    
    def __init__(self):
        super().__init__("worker_processes")
    
    async def check_health(self) -> HealthStatus:
        """워커 프로세스 헬스를 체크합니다."""
        try:
            import psutil
            
            # 현재 프로세스의 자식 프로세스들 확인
            current_process = psutil.Process()
            worker_processes = []
            
            for child in current_process.children(recursive=True):
                try:
                    if 'python' in child.name().lower():
                        worker_processes.append({
                            'pid': child.pid,
                            'name': child.name(),
                            'status': child.status(),
                            'cpu_percent': child.cpu_percent(),
                            'memory_mb': child.memory_info().rss / 1024 / 1024
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 좀비 프로세스 확인
            zombie_processes = [p for p in worker_processes if p['status'] == 'zombie']
            
            is_healthy = len(zombie_processes) == 0
            
            if zombie_processes:
                message = f"좀비 프로세스 발견: {len(zombie_processes)}개"
            else:
                message = f"워커 프로세스 정상 ({len(worker_processes)}개 실행 중)"
            
            return HealthStatus(
                component=self.name,
                is_healthy=is_healthy,
                timestamp=datetime.now(),
                message=message,
                metrics={
                    'total_workers': len(worker_processes),
                    'zombie_workers': len(zombie_processes),
                    'worker_processes': worker_processes
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"워커 프로세스 체크 오류: {e}",
                metrics={}
            )

class NetworkHealthChecker(HealthChecker):
    """네트워크 연결 헬스 체커"""
    
    def __init__(self, test_hosts: List[str] = None):
        super().__init__("network")
        self.test_hosts = test_hosts or ['8.8.8.8', 'google.com', '1.1.1.1']
    
    async def check_health(self) -> HealthStatus:
        """네트워크 연결 헬스를 체크합니다."""
        try:
            import socket
            import asyncio
            
            connectivity_results = []
            
            for host in self.test_hosts:
                try:
                    # DNS 확인 및 연결 테스트
                    start_time = time.time()
                    
                    if host.replace('.', '').isdigit():  # IP 주소
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        result = sock.connect_ex((host, 53))  # DNS 포트
                        sock.close()
                        response_time = time.time() - start_time
                        success = result == 0
                    else:  # 도메인
                        socket.gethostbyname(host)
                        response_time = time.time() - start_time
                        success = True
                    
                    connectivity_results.append({
                        'host': host,
                        'success': success,
                        'response_time_ms': response_time * 1000
                    })
                    
                except Exception as e:
                    connectivity_results.append({
                        'host': host,
                        'success': False,
                        'error': str(e)
                    })
            
            # 성공한 연결 수 확인
            successful_connections = sum(1 for result in connectivity_results if result['success'])
            success_rate = successful_connections / len(connectivity_results)
            
            is_healthy = success_rate >= 0.5  # 50% 이상 성공
            
            if is_healthy:
                avg_response_time = sum(
                    result.get('response_time_ms', 0) 
                    for result in connectivity_results if result['success']
                ) / max(successful_connections, 1)
                
                message = f"네트워크 연결 정상 ({successful_connections}/{len(connectivity_results)} 성공, 평균 응답시간: {avg_response_time:.1f}ms)"
            else:
                message = f"네트워크 연결 불안정 ({successful_connections}/{len(connectivity_results)} 성공)"
            
            return HealthStatus(
                component=self.name,
                is_healthy=is_healthy,
                timestamp=datetime.now(),
                message=message,
                metrics={
                    'success_rate': success_rate,
                    'successful_connections': successful_connections,
                    'total_tests': len(connectivity_results),
                    'connectivity_results': connectivity_results
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"네트워크 체크 오류: {e}",
                metrics={}
            )

class DiskSpaceHealthChecker(HealthChecker):
    """디스크 공간 헬스 체커"""
    
    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 95.0):
        super().__init__("disk_space")
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
    
    async def check_health(self) -> HealthStatus:
        """디스크 공간 헬스를 체크합니다."""
        try:
            import psutil
            
            # 루트 파티션 확인
            disk_usage = psutil.disk_usage('/')
            used_percent = (disk_usage.used / disk_usage.total) * 100
            
            # 로그 디렉토리 확인
            log_disk_usage = None
            try:
                log_disk_usage = psutil.disk_usage('/var/log')
                log_used_percent = (log_disk_usage.used / log_disk_usage.total) * 100
            except:
                log_used_percent = used_percent  # 같은 파티션
            
            # 헬스 상태 판단
            is_healthy = (used_percent < self.critical_threshold and 
                         log_used_percent < self.critical_threshold)
            
            if used_percent >= self.critical_threshold:
                message = f"디스크 공간 위험: {used_percent:.1f}% 사용"
            elif used_percent >= self.warning_threshold:
                message = f"디스크 공간 주의: {used_percent:.1f}% 사용"
            else:
                message = f"디스크 공간 정상: {used_percent:.1f}% 사용"
            
            return HealthStatus(
                component=self.name,
                is_healthy=is_healthy,
                timestamp=datetime.now(),
                message=message,
                metrics={
                    'disk_used_percent': used_percent,
                    'disk_total_gb': disk_usage.total / 1024 / 1024 / 1024,
                    'disk_used_gb': disk_usage.used / 1024 / 1024 / 1024,
                    'disk_free_gb': disk_usage.free / 1024 / 1024 / 1024,
                    'log_used_percent': log_used_percent if log_disk_usage else None
                }
            )
            
        except Exception as e:
            return HealthStatus(
                component=self.name,
                is_healthy=False,
                timestamp=datetime.now(),
                message=f"디스크 공간 체크 오류: {e}",
                metrics={}
            )
