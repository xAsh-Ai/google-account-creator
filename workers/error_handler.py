"""
에러 핸들링 및 복구 시스템 모듈

이 모듈은 멀티 디바이스 환경에서 발생하는 다양한 에러를 처리하고 복구하는 시스템을 제공합니다.
- 디바이스 레벨 에러 처리 및 복구
- 작업 레벨 에러 처리 및 재시도
- 시스템 레벨 에러 모니터링 및 대응
- 자동 복구 메커니즘
- 에러 패턴 분석 및 예방
"""

import asyncio
import threading
import time
import logging
import traceback
from typing import Dict, List, Optional, Any, Callable, Set, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import re
from pathlib import Path
from collections import defaultdict, deque
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

from .device_manager import DeviceManager, DeviceStatus, DeviceInfo
from .work_queue import WorkQueueManager, TaskStatus, WorkTask
from .parallel_executor import ParallelExecutor, ExecutorStatus

# 로깅 설정
logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """에러 심각도 열거형"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    FATAL = 5

class ErrorCategory(Enum):
    """에러 카테고리 열거형"""
    DEVICE_ERROR = "device_error"
    NETWORK_ERROR = "network_error"
    TASK_ERROR = "task_error"
    SYSTEM_ERROR = "system_error"
    RESOURCE_ERROR = "resource_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    EXTERNAL_API_ERROR = "external_api_error"

class RecoveryAction(Enum):
    """복구 액션 열거형"""
    RETRY = "retry"
    RESTART_DEVICE = "restart_device"
    RESTART_WORKER = "restart_worker"
    RESTART_SYSTEM = "restart_system"
    SKIP_TASK = "skip_task"
    FALLBACK = "fallback"
    WAIT_AND_RETRY = "wait_and_retry"
    ESCALATE = "escalate"
    ABORT = "abort"

@dataclass
class ErrorEvent:
    """에러 이벤트 데이터 클래스"""
    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    
    # 컨텍스트 정보
    device_id: Optional[str] = None
    worker_id: Optional[str] = None
    task_id: Optional[str] = None
    
    # 에러 세부사항
    error_type: str = ""
    error_message: str = ""
    stack_trace: Optional[str] = None
    error_data: Dict[str, Any] = field(default_factory=dict)
    
    # 복구 정보
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ErrorPattern:
    """에러 패턴 데이터 클래스"""
    pattern_id: str
    category: ErrorCategory
    pattern_regex: str
    description: str
    
    # 발생 통계
    occurrence_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # 복구 전략
    default_actions: List[RecoveryAction] = field(default_factory=list)
    success_rate: float = 0.0
    
    # 예방 조치
    prevention_tips: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RecoveryStrategy:
    """복구 전략 데이터 클래스"""
    strategy_id: str
    name: str
    description: str
    
    # 적용 조건
    applicable_categories: Set[ErrorCategory] = field(default_factory=set)
    applicable_severities: Set[ErrorSeverity] = field(default_factory=set)
    
    # 복구 액션 시퀀스
    action_sequence: List[RecoveryAction] = field(default_factory=list)
    timeout_seconds: int = 300
    
    # 성공 메트릭
    success_count: int = 0
    failure_count: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)

class ErrorDetector:
    """에러 감지기 클래스"""
    
    def __init__(self):
        """에러 감지기 초기화"""
        self.patterns: Dict[str, ErrorPattern] = {}
        self.detection_rules: List[Callable] = []
        self._load_builtin_patterns()
        
        logger.info("에러 감지기가 초기화되었습니다.")
    
    def _load_builtin_patterns(self) -> None:
        """내장 에러 패턴을 로드합니다."""
        builtin_patterns = [
            ErrorPattern(
                pattern_id="device_disconnected",
                category=ErrorCategory.DEVICE_ERROR,
                pattern_regex=r"device .+ disconnected|device not found|no device",
                description="디바이스 연결 해제",
                default_actions=[RecoveryAction.RESTART_DEVICE, RecoveryAction.RETRY]
            ),
            ErrorPattern(
                pattern_id="network_timeout",
                category=ErrorCategory.NETWORK_ERROR,
                pattern_regex=r"timeout|connection timed out|read timeout|network unreachable",
                description="네트워크 타임아웃",
                default_actions=[RecoveryAction.WAIT_AND_RETRY, RecoveryAction.RETRY]
            ),
            ErrorPattern(
                pattern_id="permission_denied",
                category=ErrorCategory.SYSTEM_ERROR,
                pattern_regex=r"permission denied|access denied|authorization failed",
                description="권한 거부",
                default_actions=[RecoveryAction.RESTART_DEVICE, RecoveryAction.ESCALATE]
            ),
            ErrorPattern(
                pattern_id="memory_error",
                category=ErrorCategory.RESOURCE_ERROR,
                pattern_regex=r"out of memory|memory error|cannot allocate",
                description="메모리 부족",
                default_actions=[RecoveryAction.RESTART_WORKER, RecoveryAction.WAIT_AND_RETRY]
            ),
            ErrorPattern(
                pattern_id="api_rate_limit",
                category=ErrorCategory.EXTERNAL_API_ERROR,
                pattern_regex=r"rate limit|too many requests|quota exceeded",
                description="API 요청 제한",
                default_actions=[RecoveryAction.WAIT_AND_RETRY, RecoveryAction.FALLBACK]
            ),
            ErrorPattern(
                pattern_id="app_crash",
                category=ErrorCategory.TASK_ERROR,
                pattern_regex=r"app crashed|application not responding|force close",
                description="앱 크래시",
                default_actions=[RecoveryAction.RESTART_DEVICE, RecoveryAction.RETRY]
            )
        ]
        
        for pattern in builtin_patterns:
            self.patterns[pattern.pattern_id] = pattern
        
        logger.info(f"{len(builtin_patterns)}개의 내장 에러 패턴이 로드되었습니다.")
    
    def detect_error(self, error_message: str, error_data: Dict[str, Any] = None) -> Optional[ErrorPattern]:
        """
        에러 메시지에서 패턴을 감지합니다.
        
        Args:
            error_message: 에러 메시지
            error_data: 추가 에러 데이터
        
        Returns:
            감지된 패턴 또는 None
        """
        error_data = error_data or {}
        
        # 패턴 매칭
        for pattern in self.patterns.values():
            if re.search(pattern.pattern_regex, error_message, re.IGNORECASE):
                pattern.occurrence_count += 1
                pattern.last_seen = datetime.now()
                
                if pattern.first_seen is None:
                    pattern.first_seen = datetime.now()
                
                logger.debug(f"에러 패턴 감지됨: {pattern.pattern_id}")
                return pattern
        
        # 동적 규칙 적용
        for rule in self.detection_rules:
            try:
                result = rule(error_message, error_data)
                if result:
                    return result
            except Exception as e:
                logger.error(f"감지 규칙 실행 오류: {e}")
        
        return None
    
    def add_pattern(self, pattern: ErrorPattern) -> None:
        """새로운 에러 패턴을 추가합니다."""
        self.patterns[pattern.pattern_id] = pattern
        logger.info(f"에러 패턴 추가됨: {pattern.pattern_id}")
    
    def add_detection_rule(self, rule: Callable) -> None:
        """동적 감지 규칙을 추가합니다."""
        self.detection_rules.append(rule)

class RecoveryManager:
    """복구 관리자 클래스"""
    
    def __init__(self, 
                 device_manager: DeviceManager,
                 queue_manager: WorkQueueManager,
                 executor: ParallelExecutor):
        """
        복구 관리자 초기화
        
        Args:
            device_manager: 디바이스 매니저
            queue_manager: 큐 관리자
            executor: 병렬 실행기
        """
        self.device_manager = device_manager
        self.queue_manager = queue_manager
        self.executor = executor
        
        self.strategies: Dict[str, RecoveryStrategy] = {}
        self.recovery_history: deque = deque(maxlen=1000)
        
        self._load_builtin_strategies()
        
        logger.info("복구 관리자가 초기화되었습니다.")
    
    def _load_builtin_strategies(self) -> None:
        """내장 복구 전략을 로드합니다."""
        builtin_strategies = [
            RecoveryStrategy(
                strategy_id="simple_retry",
                name="단순 재시도",
                description="작업을 즉시 재시도합니다.",
                applicable_categories={ErrorCategory.NETWORK_ERROR, ErrorCategory.TIMEOUT_ERROR},
                applicable_severities={ErrorSeverity.LOW, ErrorSeverity.MEDIUM},
                action_sequence=[RecoveryAction.RETRY],
                timeout_seconds=60
            ),
            RecoveryStrategy(
                strategy_id="device_restart",
                name="디바이스 재시작",
                description="디바이스를 재시작하고 작업을 재시도합니다.",
                applicable_categories={ErrorCategory.DEVICE_ERROR, ErrorCategory.SYSTEM_ERROR},
                applicable_severities={ErrorSeverity.MEDIUM, ErrorSeverity.HIGH},
                action_sequence=[RecoveryAction.RESTART_DEVICE, RecoveryAction.WAIT_AND_RETRY, RecoveryAction.RETRY],
                timeout_seconds=300
            ),
            RecoveryStrategy(
                strategy_id="worker_restart",
                name="워커 재시작",
                description="워커를 재시작하고 작업을 재할당합니다.",
                applicable_categories={ErrorCategory.RESOURCE_ERROR, ErrorCategory.SYSTEM_ERROR},
                applicable_severities={ErrorSeverity.HIGH, ErrorSeverity.CRITICAL},
                action_sequence=[RecoveryAction.RESTART_WORKER, RecoveryAction.RETRY],
                timeout_seconds=180
            ),
            RecoveryStrategy(
                strategy_id="wait_and_retry",
                name="대기 후 재시도",
                description="일정 시간 대기 후 작업을 재시도합니다.",
                applicable_categories={ErrorCategory.EXTERNAL_API_ERROR, ErrorCategory.RESOURCE_ERROR},
                applicable_severities={ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH},
                action_sequence=[RecoveryAction.WAIT_AND_RETRY, RecoveryAction.RETRY],
                timeout_seconds=600
            ),
            RecoveryStrategy(
                strategy_id="escalation",
                name="에스컬레이션",
                description="관리자에게 에러를 보고하고 수동 개입을 요청합니다.",
                applicable_categories=set(ErrorCategory),
                applicable_severities={ErrorSeverity.CRITICAL, ErrorSeverity.FATAL},
                action_sequence=[RecoveryAction.ESCALATE],
                timeout_seconds=0
            )
        ]
        
        for strategy in builtin_strategies:
            self.strategies[strategy.strategy_id] = strategy
        
        logger.info(f"{len(builtin_strategies)}개의 내장 복구 전략이 로드되었습니다.")
    
    async def execute_recovery(self, error_event: ErrorEvent) -> bool:
        """
        에러 이벤트에 대한 복구를 실행합니다.
        
        Args:
            error_event: 에러 이벤트
        
        Returns:
            복구 성공 여부
        """
        try:
            # 적합한 전략 선택
            strategy = self._select_strategy(error_event)
            if not strategy:
                logger.warning(f"에러 {error_event.error_id}에 대한 복구 전략을 찾을 수 없습니다.")
                return False
            
            logger.info(f"에러 {error_event.error_id}에 대해 전략 '{strategy.name}' 실행 중...")
            
            # 복구 액션 실행
            success = await self._execute_strategy(error_event, strategy)
            
            # 결과 기록
            if success:
                strategy.success_count += 1
                error_event.resolved = True
                error_event.resolution_time = datetime.now()
                logger.info(f"에러 {error_event.error_id} 복구 성공")
            else:
                strategy.failure_count += 1
                error_event.recovery_attempts += 1
                logger.warning(f"에러 {error_event.error_id} 복구 실패")
            
            # 히스토리에 기록
            self.recovery_history.append({
                "error_id": error_event.error_id,
                "strategy_id": strategy.strategy_id,
                "success": success,
                "timestamp": datetime.now().isoformat()
            })
            
            return success
            
        except Exception as e:
            logger.error(f"복구 실행 중 오류: {e}")
            return False
    
    def _select_strategy(self, error_event: ErrorEvent) -> Optional[RecoveryStrategy]:
        """에러에 적합한 복구 전략을 선택합니다."""
        candidate_strategies = []
        
        for strategy in self.strategies.values():
            # 카테고리 매칭
            if (strategy.applicable_categories and 
                error_event.category not in strategy.applicable_categories):
                continue
            
            # 심각도 매칭
            if (strategy.applicable_severities and
                error_event.severity not in strategy.applicable_severities):
                continue
            
            # 복구 시도 횟수 확인
            if error_event.recovery_attempts >= error_event.max_recovery_attempts:
                # 최대 시도 횟수 초과 시 에스컬레이션 전략만 고려
                if RecoveryAction.ESCALATE in strategy.action_sequence:
                    candidate_strategies.append(strategy)
                continue
            
            candidate_strategies.append(strategy)
        
        if not candidate_strategies:
            return None
        
        # 성공률이 가장 높은 전략 선택
        best_strategy = max(candidate_strategies, key=lambda s: self._calculate_success_rate(s))
        return best_strategy
    
    def _calculate_success_rate(self, strategy: RecoveryStrategy) -> float:
        """전략의 성공률을 계산합니다."""
        total_attempts = strategy.success_count + strategy.failure_count
        if total_attempts == 0:
            return 0.5  # 기본값
        
        return strategy.success_count / total_attempts
    
    async def _execute_strategy(self, error_event: ErrorEvent, strategy: RecoveryStrategy) -> bool:
        """복구 전략을 실행합니다."""
        try:
            for action in strategy.action_sequence:
                success = await self._execute_action(error_event, action)
                if not success:
                    return False
                
                # 액션 간 대기 시간
                await asyncio.sleep(1)
            
            return True
            
        except Exception as e:
            logger.error(f"전략 실행 오류: {e}")
            return False
    
    async def _execute_action(self, error_event: ErrorEvent, action: RecoveryAction) -> bool:
        """개별 복구 액션을 실행합니다."""
        try:
            logger.debug(f"복구 액션 실행: {action.value}")
            
            if action == RecoveryAction.RETRY:
                return await self._action_retry(error_event)
            elif action == RecoveryAction.RESTART_DEVICE:
                return await self._action_restart_device(error_event)
            elif action == RecoveryAction.RESTART_WORKER:
                return await self._action_restart_worker(error_event)
            elif action == RecoveryAction.RESTART_SYSTEM:
                return await self._action_restart_system(error_event)
            elif action == RecoveryAction.SKIP_TASK:
                return await self._action_skip_task(error_event)
            elif action == RecoveryAction.FALLBACK:
                return await self._action_fallback(error_event)
            elif action == RecoveryAction.WAIT_AND_RETRY:
                return await self._action_wait_and_retry(error_event)
            elif action == RecoveryAction.ESCALATE:
                return await self._action_escalate(error_event)
            elif action == RecoveryAction.ABORT:
                return await self._action_abort(error_event)
            else:
                logger.warning(f"알 수 없는 복구 액션: {action}")
                return False
                
        except Exception as e:
            logger.error(f"복구 액션 {action.value} 실행 오류: {e}")
            return False
    
    async def _action_retry(self, error_event: ErrorEvent) -> bool:
        """작업 재시도"""
        if error_event.task_id:
            # 큐 관리자를 통해 작업 재시도
            # 실제 구현에서는 큐 관리자의 재시도 기능 호출
            logger.info(f"작업 {error_event.task_id} 재시도 중...")
            await asyncio.sleep(2)  # 시뮬레이션
            return True
        return False
    
    async def _action_restart_device(self, error_event: ErrorEvent) -> bool:
        """디바이스 재시작"""
        if error_event.device_id:
            # 디바이스 정리 및 재시작
            await self.device_manager.cleanup_device(error_event.device_id)
            logger.info(f"디바이스 {error_event.device_id} 재시작됨")
            await asyncio.sleep(5)  # 재시작 대기
            return True
        return False
    
    async def _action_restart_worker(self, error_event: ErrorEvent) -> bool:
        """워커 재시작"""
        if error_event.worker_id:
            # 워커 재시작 로직 (실제 구현에서는 executor의 워커 재시작 기능 호출)
            logger.info(f"워커 {error_event.worker_id} 재시작됨")
            await asyncio.sleep(3)  # 재시작 대기
            return True
        return False
    
    async def _action_restart_system(self, error_event: ErrorEvent) -> bool:
        """시스템 재시작"""
        logger.critical("시스템 재시작이 요청되었습니다.")
        # 실제 구현에서는 전체 시스템 재시작 로직
        await asyncio.sleep(1)
        return True
    
    async def _action_skip_task(self, error_event: ErrorEvent) -> bool:
        """작업 건너뛰기"""
        if error_event.task_id:
            logger.info(f"작업 {error_event.task_id} 건너뛰기")
            # 작업 상태를 실패로 변경
            return True
        return False
    
    async def _action_fallback(self, error_event: ErrorEvent) -> bool:
        """대체 방법 사용"""
        logger.info("대체 방법으로 전환 중...")
        # 대체 리소스나 방법 사용
        await asyncio.sleep(2)
        return True
    
    async def _action_wait_and_retry(self, error_event: ErrorEvent) -> bool:
        """대기 후 재시도"""
        wait_time = self._calculate_wait_time(error_event)
        logger.info(f"{wait_time}초 대기 후 재시도...")
        await asyncio.sleep(wait_time)
        return True
    
    async def _action_escalate(self, error_event: ErrorEvent) -> bool:
        """에스컬레이션"""
        logger.critical(f"에러 에스컬레이션: {error_event.error_id}")
        # 관리자에게 알림 전송
        await self._send_escalation_notification(error_event)
        return True
    
    async def _action_abort(self, error_event: ErrorEvent) -> bool:
        """작업 중단"""
        logger.error(f"작업 중단: {error_event.error_id}")
        return False
    
    def _calculate_wait_time(self, error_event: ErrorEvent) -> int:
        """대기 시간을 계산합니다."""
        base_wait = 30  # 기본 30초
        multiplier = min(error_event.recovery_attempts, 5)  # 최대 5배
        return base_wait * (2 ** multiplier)  # 지수 백오프
    
    async def _send_escalation_notification(self, error_event: ErrorEvent) -> None:
        """에스컬레이션 알림을 전송합니다."""
        # 실제 구현에서는 이메일, Slack, 등의 알림 전송
        logger.critical(f"에스컬레이션 알림 전송됨: {error_event.error_message}")

class ErrorAnalyzer:
    """에러 분석기 클래스"""
    
    def __init__(self):
        """에러 분석기 초기화"""
        self.error_stats: Dict[str, Any] = defaultdict(int)
        self.trend_data: deque = deque(maxlen=1000)
        
        logger.info("에러 분석기가 초기화되었습니다.")
    
    def analyze_error_trends(self, error_events: List[ErrorEvent]) -> Dict[str, Any]:
        """에러 트렌드를 분석합니다."""
        analysis = {
            "total_errors": len(error_events),
            "category_distribution": defaultdict(int),
            "severity_distribution": defaultdict(int),
            "device_error_counts": defaultdict(int),
            "worker_error_counts": defaultdict(int),
            "hourly_distribution": defaultdict(int),
            "resolution_rate": 0.0,
            "average_resolution_time": 0.0
        }
        
        resolved_times = []
        
        for event in error_events:
            # 카테고리별 분포
            analysis["category_distribution"][event.category.value] += 1
            
            # 심각도별 분포
            analysis["severity_distribution"][event.severity.value] += 1
            
            # 디바이스별 에러 수
            if event.device_id:
                analysis["device_error_counts"][event.device_id] += 1
            
            # 워커별 에러 수
            if event.worker_id:
                analysis["worker_error_counts"][event.worker_id] += 1
            
            # 시간대별 분포
            hour = event.timestamp.hour
            analysis["hourly_distribution"][hour] += 1
            
            # 해결 시간 계산
            if event.resolved and event.resolution_time:
                resolution_time = (event.resolution_time - event.timestamp).total_seconds()
                resolved_times.append(resolution_time)
        
        # 해결률 계산
        resolved_count = sum(1 for event in error_events if event.resolved)
        if error_events:
            analysis["resolution_rate"] = resolved_count / len(error_events) * 100
        
        # 평균 해결 시간 계산
        if resolved_times:
            analysis["average_resolution_time"] = sum(resolved_times) / len(resolved_times)
        
        return dict(analysis)
    
    def identify_problematic_devices(self, error_events: List[ErrorEvent], threshold: int = 5) -> List[str]:
        """문제가 많은 디바이스를 식별합니다."""
        device_counts = defaultdict(int)
        
        for event in error_events:
            if event.device_id:
                device_counts[event.device_id] += 1
        
        problematic_devices = [
            device_id for device_id, count in device_counts.items()
            if count >= threshold
        ]
        
        return problematic_devices
    
    def recommend_preventive_actions(self, error_events: List[ErrorEvent]) -> List[str]:
        """예방 조치를 추천합니다."""
        recommendations = []
        
        # 분석 결과 기반 추천
        analysis = self.analyze_error_trends(error_events)
        
        # 디바이스 에러가 많은 경우
        if analysis["category_distribution"]["device_error"] > len(error_events) * 0.3:
            recommendations.append("디바이스 건강 체크 빈도를 증가시키세요.")
            recommendations.append("디바이스 펌웨어 업데이트를 검토하세요.")
        
        # 네트워크 에러가 많은 경우
        if analysis["category_distribution"]["network_error"] > len(error_events) * 0.2:
            recommendations.append("네트워크 연결 안정성을 점검하세요.")
            recommendations.append("타임아웃 설정을 조정하세요.")
        
        # 리소스 에러가 많은 경우
        if analysis["category_distribution"]["resource_error"] > len(error_events) * 0.15:
            recommendations.append("시스템 리소스 모니터링을 강화하세요.")
            recommendations.append("메모리 사용량을 최적화하세요.")
        
        # 해결률이 낮은 경우
        if analysis["resolution_rate"] < 80:
            recommendations.append("복구 전략을 개선하세요.")
            recommendations.append("에스컬레이션 프로세스를 점검하세요.")
        
        return recommendations

class ErrorHandlingSystem:
    """에러 핸들링 시스템 메인 클래스"""
    
    def __init__(self,
                 device_manager: DeviceManager,
                 queue_manager: WorkQueueManager,
                 executor: ParallelExecutor,
                 config_file: Optional[str] = None):
        """
        에러 핸들링 시스템 초기화
        
        Args:
            device_manager: 디바이스 매니저
            queue_manager: 큐 관리자
            executor: 병렬 실행기
            config_file: 설정 파일 경로
        """
        self.device_manager = device_manager
        self.queue_manager = queue_manager
        self.executor = executor
        self.config_file = config_file or "data/error_config.json"
        
        # 컴포넌트
        self.detector = ErrorDetector()
        self.recovery_manager = RecoveryManager(device_manager, queue_manager, executor)
        self.analyzer = ErrorAnalyzer()
        
        # 에러 이벤트 저장소
        self.error_events: List[ErrorEvent] = []
        self.active_errors: Dict[str, ErrorEvent] = {}
        
        # 모니터링
        self.is_monitoring = False
        self.monitor_thread = None
        
        # 설정 로드
        self._load_config()
        
        logger.info("에러 핸들링 시스템이 초기화되었습니다.")
    
    def _load_config(self) -> None:
        """설정을 로드합니다."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 설정 적용
                logger.info("에러 핸들링 설정이 로드되었습니다.")
            else:
                logger.info("설정 파일이 없습니다. 기본 설정을 사용합니다.")
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
    
    async def handle_error(self, 
                          error_message: str,
                          error_type: str = "",
                          category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
                          severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                          device_id: Optional[str] = None,
                          worker_id: Optional[str] = None,
                          task_id: Optional[str] = None,
                          error_data: Optional[Dict[str, Any]] = None) -> str:
        """
        에러를 처리합니다.
        
        Args:
            error_message: 에러 메시지
            error_type: 에러 타입
            category: 에러 카테고리
            severity: 에러 심각도
            device_id: 디바이스 ID
            worker_id: 워커 ID
            task_id: 작업 ID
            error_data: 추가 에러 데이터
        
        Returns:
            에러 이벤트 ID
        """
        try:
            # 에러 이벤트 생성
            error_id = f"error_{int(time.time())}_{len(self.error_events)}"
            
            error_event = ErrorEvent(
                error_id=error_id,
                timestamp=datetime.now(),
                category=category,
                severity=severity,
                device_id=device_id,
                worker_id=worker_id,
                task_id=task_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=traceback.format_exc() if any(traceback.format_exc().strip()) else None,
                error_data=error_data or {}
            )
            
            # 패턴 감지
            detected_pattern = self.detector.detect_error(error_message, error_data)
            if detected_pattern:
                error_event.recovery_actions = detected_pattern.default_actions.copy()
                error_event.category = detected_pattern.category
            
            # 에러 저장
            self.error_events.append(error_event)
            self.active_errors[error_id] = error_event
            
            logger.error(f"에러 발생: {error_id} - {error_message}")
            
            # 복구 시도 (심각도에 따라)
            if severity.value >= ErrorSeverity.MEDIUM.value:
                recovery_success = await self.recovery_manager.execute_recovery(error_event)
                
                if recovery_success:
                    self.active_errors.pop(error_id, None)
                    logger.info(f"에러 {error_id} 자동 복구 성공")
                else:
                    logger.warning(f"에러 {error_id} 자동 복구 실패")
            
            return error_id
            
        except Exception as e:
            logger.error(f"에러 처리 중 오류: {e}")
            return ""
    
    def start_monitoring(self) -> None:
        """에러 모니터링을 시작합니다."""
        if self.is_monitoring:
            logger.warning("이미 모니터링이 실행 중입니다.")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("에러 모니터링이 시작되었습니다.")
    
    def stop_monitoring(self) -> None:
        """에러 모니터링을 중지합니다."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("에러 모니터링이 중지되었습니다.")
    
    def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                # 활성 에러 상태 확인
                self._check_active_errors()
                
                # 주기적 분석
                if len(self.error_events) % 50 == 0 and self.error_events:
                    self._perform_periodic_analysis()
                
                time.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(60)
    
    def _check_active_errors(self) -> None:
        """활성 에러들을 확인합니다."""
        current_time = datetime.now()
        stale_errors = []
        
        for error_id, error_event in self.active_errors.items():
            # 30분 이상 해결되지 않은 에러
            if (current_time - error_event.timestamp).total_seconds() > 1800:
                stale_errors.append(error_id)
        
        # 오래된 활성 에러 제거
        for error_id in stale_errors:
            self.active_errors.pop(error_id, None)
            logger.warning(f"활성 에러 {error_id}가 타임아웃되었습니다.")
    
    def _perform_periodic_analysis(self) -> None:
        """주기적 분석을 수행합니다."""
        try:
            # 최근 에러들 분석
            recent_errors = [
                event for event in self.error_events
                if (datetime.now() - event.timestamp).total_seconds() < 3600  # 1시간 이내
            ]
            
            if recent_errors:
                analysis = self.analyzer.analyze_error_trends(recent_errors)
                logger.info(f"최근 1시간 에러 분석: {analysis['total_errors']}개 에러, "
                          f"해결률 {analysis['resolution_rate']:.1f}%")
                
                # 문제 디바이스 식별
                problematic_devices = self.analyzer.identify_problematic_devices(recent_errors, 3)
                if problematic_devices:
                    logger.warning(f"문제 디바이스 감지: {problematic_devices}")
        
        except Exception as e:
            logger.error(f"주기적 분석 오류: {e}")
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """에러 요약을 반환합니다."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = [
            event for event in self.error_events
            if event.timestamp > cutoff_time
        ]
        
        analysis = self.analyzer.analyze_error_trends(recent_errors)
        
        return {
            "period_hours": hours,
            "total_errors": len(recent_errors),
            "active_errors": len(self.active_errors),
            "analysis": analysis,
            "problematic_devices": self.analyzer.identify_problematic_devices(recent_errors),
            "recommendations": self.analyzer.recommend_preventive_actions(recent_errors),
            "last_updated": datetime.now().isoformat()
        }
    
    def get_active_errors(self) -> List[Dict[str, Any]]:
        """현재 활성 에러 목록을 반환합니다."""
        return [
            {
                "error_id": error.error_id,
                "category": error.category.value,
                "severity": error.severity.value,
                "message": error.error_message,
                "device_id": error.device_id,
                "worker_id": error.worker_id,
                "task_id": error.task_id,
                "timestamp": error.timestamp.isoformat(),
                "recovery_attempts": error.recovery_attempts
            }
            for error in self.active_errors.values()
        ]


# 편의 함수들
def create_error_handling_system(device_manager: DeviceManager,
                                queue_manager: WorkQueueManager,
                                executor: ParallelExecutor,
                                config_file: Optional[str] = None) -> ErrorHandlingSystem:
    """
    에러 핸들링 시스템을 생성합니다.
    
    Args:
        device_manager: 디바이스 매니저
        queue_manager: 큐 관리자
        executor: 병렬 실행기
        config_file: 설정 파일 경로
    
    Returns:
        ErrorHandlingSystem 인스턴스
    """
    return ErrorHandlingSystem(device_manager, queue_manager, executor, config_file)


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_error_handling():
        """에러 핸들링 시스템 테스트"""
        try:
            logger.info("에러 핸들링 시스템 테스트 시작...")
            
            # 목 의존성 생성 (실제 구현에서는 실제 인스턴스 사용)
            from .device_manager import create_device_manager
            from .work_queue import create_work_queue_manager
            from .parallel_executor import create_parallel_executor
            
            device_manager = create_device_manager()
            queue_manager = create_work_queue_manager(device_manager)
            executor = create_parallel_executor()
            
            # 에러 핸들링 시스템 생성
            error_system = create_error_handling_system(
                device_manager, queue_manager, executor
            )
            
            # 모니터링 시작
            error_system.start_monitoring()
            
            # 테스트 에러들 생성
            test_errors = [
                ("device emulator-5554 disconnected", ErrorCategory.DEVICE_ERROR, ErrorSeverity.HIGH),
                ("network timeout after 30s", ErrorCategory.NETWORK_ERROR, ErrorSeverity.MEDIUM),
                ("permission denied: /dev/input", ErrorCategory.SYSTEM_ERROR, ErrorSeverity.HIGH),
                ("out of memory: cannot allocate", ErrorCategory.RESOURCE_ERROR, ErrorSeverity.CRITICAL),
                ("app crashed: com.google.android.gms", ErrorCategory.TASK_ERROR, ErrorSeverity.MEDIUM)
            ]
            
            error_ids = []
            for error_msg, category, severity in test_errors:
                error_id = await error_system.handle_error(
                    error_message=error_msg,
                    category=category,
                    severity=severity,
                    device_id="test_device_001",
                    worker_id="test_worker_001",
                    task_id="test_task_001"
                )
                error_ids.append(error_id)
                print(f"✅ 에러 처리됨: {error_id} - {error_msg}")
                
                await asyncio.sleep(1)  # 에러 간 간격
            
            # 잠시 대기 후 요약 확인
            await asyncio.sleep(5)
            
            summary = error_system.get_error_summary(hours=1)
            print(f"📊 에러 요약: {summary['total_errors']}개 에러, 활성 {summary['active_errors']}개")
            
            active_errors = error_system.get_active_errors()
            print(f"🚨 활성 에러: {len(active_errors)}개")
            
            # 추천사항 확인
            if summary['recommendations']:
                print("💡 추천사항:")
                for rec in summary['recommendations']:
                    print(f"  - {rec}")
            
            # 모니터링 중지
            error_system.stop_monitoring()
            print("✅ 에러 핸들링 시스템 테스트 완료")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_error_handling()) 