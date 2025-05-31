"""
작업 큐 시스템 모듈

이 모듈은 멀티 디바이스 환경에서 작업을 관리하고 분배하는 큐 시스템을 제공합니다.
- 우선순위 기반 작업 큐
- 로드 밸런싱 및 작업 분배
- 작업 상태 추적 및 모니터링
- 작업 재시도 및 실패 처리
- 디바이스 능력 기반 작업 할당
"""

import asyncio
import uuid
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Callable, Set, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
import heapq
from collections import defaultdict, deque

from .device_manager import DeviceManager, DeviceCapability, DeviceStatus

# 로깅 설정
logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """작업 우선순위 열거형"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5

class TaskStatus(Enum):
    """작업 상태 열거형"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class TaskType(Enum):
    """작업 타입 열거형"""
    ACCOUNT_CREATION = "account_creation"
    DEVICE_SETUP = "device_setup"
    CLEANUP = "cleanup"
    HEALTH_CHECK = "health_check"
    MAINTENANCE = "maintenance"
    TESTING = "testing"

@dataclass
class WorkTask:
    """작업 데이터 클래스"""
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    payload: Dict[str, Any]
    
    # 작업 요구사항
    required_capabilities: Set[DeviceCapability] = field(default_factory=set)
    estimated_duration: Optional[int] = None  # 초 단위
    max_retries: int = 3
    timeout: Optional[int] = None  # 초 단위
    
    # 상태 정보
    status: TaskStatus = TaskStatus.PENDING
    assigned_device: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 실행 정보
    retry_count: int = 0
    error_messages: List[str] = field(default_factory=list)
    progress: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """우선순위 비교 (heapq용)"""
        # 우선순위가 높을수록 먼저 처리 (값이 클수록)
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        # 우선순위가 같으면 생성 시간이 빠른 것부터
        return self.created_at < other.created_at

@dataclass
class QueueMetrics:
    """큐 메트릭 데이터 클래스"""
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # 성능 메트릭
    average_wait_time: float = 0.0
    average_execution_time: float = 0.0
    throughput_per_minute: float = 0.0
    
    # 디바이스별 메트릭
    device_utilization: Dict[str, float] = field(default_factory=dict)
    device_task_counts: Dict[str, int] = field(default_factory=dict)
    
    last_updated: datetime = field(default_factory=datetime.now)

class TaskQueue:
    """우선순위 기반 작업 큐 클래스"""
    
    def __init__(self, name: str = "default", max_size: Optional[int] = None):
        """
        작업 큐 초기화
        
        Args:
            name: 큐 이름
            max_size: 최대 큐 크기 (None이면 무제한)
        """
        self.name = name
        self.max_size = max_size
        self._queue = []  # heapq로 사용
        self._tasks: Dict[str, WorkTask] = {}
        self._lock = threading.RLock()
        
        logger.info(f"작업 큐 '{name}' 초기화됨 (최대 크기: {max_size})")
    
    def put(self, task: WorkTask) -> bool:
        """
        작업을 큐에 추가합니다.
        
        Args:
            task: 작업 객체
        
        Returns:
            추가 성공 여부
        """
        with self._lock:
            if self.max_size and len(self._queue) >= self.max_size:
                logger.warning(f"큐 '{self.name}'가 가득 참: {len(self._queue)}/{self.max_size}")
                return False
            
            if task.task_id in self._tasks:
                logger.warning(f"중복 작업 ID: {task.task_id}")
                return False
            
            heapq.heappush(self._queue, task)
            self._tasks[task.task_id] = task
            
            logger.debug(f"작업 {task.task_id} 큐에 추가됨 (우선순위: {task.priority.name})")
            return True
    
    def get(self, timeout: Optional[float] = None) -> Optional[WorkTask]:
        """
        우선순위가 가장 높은 작업을 가져옵니다.
        
        Args:
            timeout: 대기 시간 (초)
        
        Returns:
            작업 객체 또는 None
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                if self._queue:
                    task = heapq.heappop(self._queue)
                    logger.debug(f"작업 {task.task_id} 큐에서 가져옴")
                    return task
            
            if timeout is not None and (time.time() - start_time) >= timeout:
                return None
            
            time.sleep(0.1)  # 짧은 대기
    
    def peek(self) -> Optional[WorkTask]:
        """
        큐의 다음 작업을 확인합니다 (제거하지 않음).
        
        Returns:
            다음 작업 또는 None
        """
        with self._lock:
            return self._queue[0] if self._queue else None
    
    def remove(self, task_id: str) -> bool:
        """
        특정 작업을 큐에서 제거합니다.
        
        Args:
            task_id: 작업 ID
        
        Returns:
            제거 성공 여부
        """
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            
            # 큐에서 제거
            try:
                self._queue.remove(task)
                heapq.heapify(self._queue)  # 힙 속성 복원
                del self._tasks[task_id]
                
                logger.debug(f"작업 {task_id} 큐에서 제거됨")
                return True
            except ValueError:
                # 이미 큐에서 제거된 상태
                del self._tasks[task_id]
                return True
    
    def get_task(self, task_id: str) -> Optional[WorkTask]:
        """
        특정 작업을 조회합니다.
        
        Args:
            task_id: 작업 ID
        
        Returns:
            작업 객체 또는 None
        """
        with self._lock:
            return self._tasks.get(task_id)
    
    def size(self) -> int:
        """큐 크기를 반환합니다."""
        with self._lock:
            return len(self._queue)
    
    def empty(self) -> bool:
        """큐가 비어있는지 확인합니다."""
        with self._lock:
            return len(self._queue) == 0
    
    def clear(self) -> None:
        """큐를 비웁니다."""
        with self._lock:
            self._queue.clear()
            self._tasks.clear()
            logger.info(f"큐 '{self.name}' 초기화됨")

class LoadBalancer:
    """로드 밸런서 클래스"""
    
    def __init__(self, strategy: str = "round_robin"):
        """
        로드 밸런서 초기화
        
        Args:
            strategy: 로드 밸런싱 전략 ("round_robin", "least_loaded", "capability_based")
        """
        self.strategy = strategy
        self.device_loads: Dict[str, int] = defaultdict(int)
        self.device_capabilities: Dict[str, Set[DeviceCapability]] = {}
        self.round_robin_index = 0
        
        logger.info(f"로드 밸런서 초기화됨 (전략: {strategy})")
    
    def select_device(self, 
                     available_devices: List[str],
                     task: WorkTask,
                     device_manager: DeviceManager) -> Optional[str]:
        """
        작업에 적합한 디바이스를 선택합니다.
        
        Args:
            available_devices: 사용 가능한 디바이스 목록
            task: 작업 객체
            device_manager: 디바이스 매니저
        
        Returns:
            선택된 디바이스 ID 또는 None
        """
        if not available_devices:
            return None
        
        # 능력 필터링
        suitable_devices = []
        for device_id in available_devices:
            device_info = device_manager.devices.get(device_id)
            if device_info:
                if task.required_capabilities.issubset(device_info.capabilities):
                    suitable_devices.append(device_id)
        
        if not suitable_devices:
            logger.warning(f"작업 {task.task_id}에 적합한 디바이스가 없습니다.")
            return None
        
        # 전략에 따른 선택
        if self.strategy == "round_robin":
            return self._round_robin_select(suitable_devices)
        elif self.strategy == "least_loaded":
            return self._least_loaded_select(suitable_devices)
        elif self.strategy == "capability_based":
            return self._capability_based_select(suitable_devices, task, device_manager)
        else:
            return suitable_devices[0]  # 기본값
    
    def _round_robin_select(self, devices: List[str]) -> str:
        """라운드 로빈 방식으로 디바이스 선택"""
        device = devices[self.round_robin_index % len(devices)]
        self.round_robin_index += 1
        return device
    
    def _least_loaded_select(self, devices: List[str]) -> str:
        """부하가 가장 적은 디바이스 선택"""
        return min(devices, key=lambda d: self.device_loads.get(d, 0))
    
    def _capability_based_select(self, 
                                devices: List[str], 
                                task: WorkTask,
                                device_manager: DeviceManager) -> str:
        """능력 기반 디바이스 선택 (고성능 작업은 고성능 디바이스에)"""
        # 고성능 디바이스 우선 선택
        high_performance_devices = []
        for device_id in devices:
            device_info = device_manager.devices.get(device_id)
            if device_info and DeviceCapability.HIGH_PERFORMANCE in device_info.capabilities:
                high_performance_devices.append(device_id)
        
        if high_performance_devices and task.priority.value >= TaskPriority.HIGH.value:
            return self._least_loaded_select(high_performance_devices)
        
        return self._least_loaded_select(devices)
    
    def assign_task(self, device_id: str, task: WorkTask) -> None:
        """디바이스에 작업 할당"""
        self.device_loads[device_id] += 1
        logger.debug(f"디바이스 {device_id} 부하 증가: {self.device_loads[device_id]}")
    
    def complete_task(self, device_id: str, task: WorkTask) -> None:
        """작업 완료 시 부하 감소"""
        if device_id in self.device_loads and self.device_loads[device_id] > 0:
            self.device_loads[device_id] -= 1
            logger.debug(f"디바이스 {device_id} 부하 감소: {self.device_loads[device_id]}")

class WorkQueueManager:
    """작업 큐 관리자 클래스"""
    
    def __init__(self, 
                 device_manager: DeviceManager,
                 max_concurrent_tasks: int = 10,
                 load_balancing_strategy: str = "least_loaded"):
        """
        큐 관리자 초기화
        
        Args:
            device_manager: 디바이스 매니저
            max_concurrent_tasks: 최대 동시 작업 수
            load_balancing_strategy: 로드 밸런싱 전략
        """
        self.device_manager = device_manager
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # 큐들
        self.task_queue = TaskQueue("main", max_size=1000)
        self.retry_queue = TaskQueue("retry", max_size=500)
        
        # 실행 중인 작업 추적
        self.running_tasks: Dict[str, WorkTask] = {}
        self.completed_tasks: deque = deque(maxlen=1000)  # 최근 완료된 작업들
        
        # 로드 밸런서
        self.load_balancer = LoadBalancer(load_balancing_strategy)
        
        # 메트릭
        self.metrics = QueueMetrics()
        
        # 제어 변수
        self.is_running = False
        self.dispatcher_task = None
        self.metrics_task = None
        
        # 콜백
        self.task_callbacks: Dict[str, List[Callable]] = {
            'task_assigned': [],
            'task_started': [],
            'task_completed': [],
            'task_failed': [],
            'task_retried': []
        }
        
        logger.info("작업 큐 관리자가 초기화되었습니다.")
    
    def add_task_callback(self, event_type: str, callback: Callable) -> None:
        """
        작업 이벤트 콜백을 추가합니다.
        
        Args:
            event_type: 이벤트 타입
            callback: 콜백 함수
        """
        if event_type in self.task_callbacks:
            self.task_callbacks[event_type].append(callback)
    
    def _trigger_callback(self, event_type: str, task: WorkTask, **kwargs) -> None:
        """콜백 트리거"""
        if event_type in self.task_callbacks:
            for callback in self.task_callbacks[event_type]:
                try:
                    callback(task, **kwargs)
                except Exception as e:
                    logger.error(f"콜백 실행 오류 ({event_type}): {e}")
    
    def submit_task(self, 
                   task_type: TaskType,
                   payload: Dict[str, Any],
                   priority: TaskPriority = TaskPriority.NORMAL,
                   required_capabilities: Optional[Set[DeviceCapability]] = None,
                   estimated_duration: Optional[int] = None,
                   max_retries: int = 3,
                   timeout: Optional[int] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        새로운 작업을 제출합니다.
        
        Args:
            task_type: 작업 타입
            payload: 작업 데이터
            priority: 우선순위
            required_capabilities: 필요한 디바이스 능력
            estimated_duration: 예상 실행 시간 (초)
            max_retries: 최대 재시도 횟수
            timeout: 타임아웃 (초)
            metadata: 추가 메타데이터
        
        Returns:
            작업 ID
        """
        task_id = str(uuid.uuid4())
        
        task = WorkTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            payload=payload,
            required_capabilities=required_capabilities or set(),
            estimated_duration=estimated_duration,
            max_retries=max_retries,
            timeout=timeout,
            metadata=metadata or {}
        )
        
        if self.task_queue.put(task):
            logger.info(f"작업 {task_id} 제출됨 (타입: {task_type.value}, 우선순위: {priority.name})")
            return task_id
        else:
            logger.error(f"작업 {task_id} 제출 실패: 큐가 가득 참")
            raise RuntimeError("작업 큐가 가득 참")
    
    def cancel_task(self, task_id: str) -> bool:
        """
        작업을 취소합니다.
        
        Args:
            task_id: 작업 ID
        
        Returns:
            취소 성공 여부
        """
        # 대기 중인 작업 제거
        if self.task_queue.remove(task_id):
            task = self.task_queue.get_task(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            logger.info(f"작업 {task_id} 취소됨")
            return True
        
        # 재시도 큐에서 제거
        if self.retry_queue.remove(task_id):
            task = self.retry_queue.get_task(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            logger.info(f"재시도 작업 {task_id} 취소됨")
            return True
        
        # 실행 중인 작업은 취소 불가 (실제 구현에서는 더 복잡한 로직 필요)
        if task_id in self.running_tasks:
            logger.warning(f"실행 중인 작업 {task_id}는 취소할 수 없습니다.")
            return False
        
        logger.warning(f"작업 {task_id}를 찾을 수 없습니다.")
        return False
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        작업 상태를 조회합니다.
        
        Args:
            task_id: 작업 ID
        
        Returns:
            작업 상태 또는 None
        """
        # 큐에서 확인
        task = self.task_queue.get_task(task_id)
        if task:
            return task.status
        
        # 재시도 큐에서 확인
        task = self.retry_queue.get_task(task_id)
        if task:
            return task.status
        
        # 실행 중인 작업에서 확인
        if task_id in self.running_tasks:
            return self.running_tasks[task_id].status
        
        # 완료된 작업에서 확인
        for task in self.completed_tasks:
            if task.task_id == task_id:
                return task.status
        
        return None
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 정보를 조회합니다.
        
        Args:
            task_id: 작업 ID
        
        Returns:
            작업 정보 딕셔너리 또는 None
        """
        task = None
        
        # 여러 위치에서 작업 찾기
        task = (self.task_queue.get_task(task_id) or 
                self.retry_queue.get_task(task_id) or
                self.running_tasks.get(task_id))
        
        if not task:
            # 완료된 작업에서 찾기
            for completed_task in self.completed_tasks:
                if completed_task.task_id == task_id:
                    task = completed_task
                    break
        
        if not task:
            return None
        
        # 실행 시간 계산
        execution_time = None
        if task.started_at and task.completed_at:
            execution_time = (task.completed_at - task.started_at).total_seconds()
        elif task.started_at:
            execution_time = (datetime.now() - task.started_at).total_seconds()
        
        return {
            'task_id': task.task_id,
            'task_type': task.task_type.value,
            'priority': task.priority.name,
            'status': task.status.value,
            'assigned_device': task.assigned_device,
            'created_at': task.created_at.isoformat(),
            'assigned_at': task.assigned_at.isoformat() if task.assigned_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'execution_time': execution_time,
            'retry_count': task.retry_count,
            'max_retries': task.max_retries,
            'error_messages': task.error_messages,
            'progress': task.progress,
            'metadata': task.metadata
        }
    
    async def start(self) -> None:
        """큐 관리자를 시작합니다."""
        if self.is_running:
            logger.warning("큐 관리자가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        
        # 디스패처 및 메트릭 태스크 시작
        self.dispatcher_task = asyncio.create_task(self._dispatcher_loop())
        self.metrics_task = asyncio.create_task(self._metrics_loop())
        
        logger.info("작업 큐 관리자가 시작되었습니다.")
    
    async def stop(self) -> None:
        """큐 관리자를 중지합니다."""
        self.is_running = False
        
        # 태스크 취소
        if self.dispatcher_task:
            self.dispatcher_task.cancel()
            try:
                await self.dispatcher_task
            except asyncio.CancelledError:
                pass
        
        if self.metrics_task:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass
        
        logger.info("작업 큐 관리자가 중지되었습니다.")
    
    async def _dispatcher_loop(self) -> None:
        """작업 디스패처 루프"""
        while self.is_running:
            try:
                # 동시 실행 제한 확인
                if len(self.running_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(1)
                    continue
                
                # 사용 가능한 디바이스 확인
                available_devices = self.device_manager.get_available_devices()
                if not available_devices:
                    await asyncio.sleep(2)
                    continue
                
                # 다음 작업 가져오기 (재시도 큐 우선)
                task = self.retry_queue.get(timeout=0.1)
                if not task:
                    task = self.task_queue.get(timeout=0.1)
                
                if not task:
                    await asyncio.sleep(0.5)
                    continue
                
                # 적합한 디바이스 선택
                device_id = self.load_balancer.select_device(
                    available_devices, task, self.device_manager
                )
                
                if not device_id:
                    # 적합한 디바이스가 없으면 다시 큐에 넣기
                    if task.status == TaskStatus.RETRYING:
                        self.retry_queue.put(task)
                    else:
                        self.task_queue.put(task)
                    await asyncio.sleep(1)
                    continue
                
                # 디바이스 예약 및 작업 할당
                if self.device_manager.reserve_device(device_id, task.task_id):
                    await self._assign_task(task, device_id)
                else:
                    # 예약 실패 시 다시 큐에 넣기
                    if task.status == TaskStatus.RETRYING:
                        self.retry_queue.put(task)
                    else:
                        self.task_queue.put(task)
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"디스패처 루프 오류: {e}")
                await asyncio.sleep(1)
    
    async def _assign_task(self, task: WorkTask, device_id: str) -> None:
        """작업을 디바이스에 할당합니다."""
        try:
            # 작업 상태 업데이트
            task.status = TaskStatus.ASSIGNED
            task.assigned_device = device_id
            task.assigned_at = datetime.now()
            
            # 실행 중인 작업 목록에 추가
            self.running_tasks[task.task_id] = task
            
            # 로드 밸런서에 할당 통지
            self.load_balancer.assign_task(device_id, task)
            
            # 콜백 트리거
            self._trigger_callback('task_assigned', task, device_id=device_id)
            
            # 작업 실행 태스크 생성
            execution_task = asyncio.create_task(self._execute_task(task))
            
            logger.info(f"작업 {task.task_id}이 디바이스 {device_id}에 할당되었습니다.")
            
        except Exception as e:
            logger.error(f"작업 할당 오류: {e}")
            # 실패 시 디바이스 해제
            self.device_manager.release_device(device_id)
            # 작업을 재시도 큐로 이동
            task.status = TaskStatus.PENDING
            self.task_queue.put(task)
    
    async def _execute_task(self, task: WorkTask) -> None:
        """작업을 실행합니다."""
        device_id = task.assigned_device
        
        try:
            # 작업 시작
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            self._trigger_callback('task_started', task, device_id=device_id)
            
            logger.info(f"작업 {task.task_id} 실행 시작 (디바이스: {device_id})")
            
            # 실제 작업 실행 로직 (여기서는 시뮬레이션)
            # 실제 구현에서는 task.task_type에 따라 적절한 실행기 호출
            await self._simulate_task_execution(task)
            
            # 작업 완료
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            logger.info(f"작업 {task.task_id} 완료됨")
            
            self._trigger_callback('task_completed', task, device_id=device_id)
            
        except Exception as e:
            # 작업 실패
            task.status = TaskStatus.FAILED
            task.error_messages.append(str(e))
            task.completed_at = datetime.now()
            
            logger.error(f"작업 {task.task_id} 실패: {e}")
            
            self._trigger_callback('task_failed', task, device_id=device_id, error=e)
            
            # 재시도 처리
            if task.retry_count < task.max_retries:
                await self._retry_task(task)
            
        finally:
            # 정리 작업
            self.running_tasks.pop(task.task_id, None)
            self.completed_tasks.append(task)
            
            # 로드 밸런서에 완료 통지
            self.load_balancer.complete_task(device_id, task)
            
            # 디바이스 해제
            self.device_manager.release_device(device_id)
    
    async def _simulate_task_execution(self, task: WorkTask) -> None:
        """
        작업 실행 시뮬레이션 (실제 구현에서는 제거될 부분)
        
        Args:
            task: 실행할 작업
        """
        # 시뮬레이션을 위한 가짜 실행 시간
        execution_time = task.estimated_duration or 30
        
        # 진행 상황 업데이트 시뮬레이션
        for i in range(10):
            await asyncio.sleep(execution_time / 10)
            progress = (i + 1) * 10
            task.progress['completion'] = progress
            
            logger.debug(f"작업 {task.task_id} 진행률: {progress}%")
        
        # 가끔 실패 시뮬레이션 (10% 확률)
        import random
        if random.random() < 0.1:
            raise Exception("시뮬레이션 실패")
    
    async def _retry_task(self, task: WorkTask) -> None:
        """작업을 재시도합니다."""
        task.retry_count += 1
        task.status = TaskStatus.RETRYING
        task.assigned_device = None
        task.assigned_at = None
        task.started_at = None
        
        # 재시도 큐에 추가
        self.retry_queue.put(task)
        
        logger.info(f"작업 {task.task_id} 재시도됨 ({task.retry_count}/{task.max_retries})")
        
        self._trigger_callback('task_retried', task, retry_count=task.retry_count)
    
    async def _metrics_loop(self) -> None:
        """메트릭 업데이트 루프"""
        while self.is_running:
            try:
                await self._update_metrics()
                await asyncio.sleep(30)  # 30초마다 메트릭 업데이트
            except Exception as e:
                logger.error(f"메트릭 업데이트 오류: {e}")
                await asyncio.sleep(30)
    
    async def _update_metrics(self) -> None:
        """메트릭을 업데이트합니다."""
        # 기본 카운트
        self.metrics.total_tasks = (
            self.task_queue.size() + 
            self.retry_queue.size() + 
            len(self.running_tasks) + 
            len(self.completed_tasks)
        )
        self.metrics.pending_tasks = self.task_queue.size() + self.retry_queue.size()
        self.metrics.running_tasks = len(self.running_tasks)
        
        # 완료/실패 작업 카운트
        completed_count = 0
        failed_count = 0
        total_wait_time = 0
        total_execution_time = 0
        
        for task in self.completed_tasks:
            if task.status == TaskStatus.COMPLETED:
                completed_count += 1
            elif task.status == TaskStatus.FAILED:
                failed_count += 1
            
            # 대기 시간 계산
            if task.assigned_at:
                wait_time = (task.assigned_at - task.created_at).total_seconds()
                total_wait_time += wait_time
            
            # 실행 시간 계산
            if task.started_at and task.completed_at:
                execution_time = (task.completed_at - task.started_at).total_seconds()
                total_execution_time += execution_time
        
        self.metrics.completed_tasks = completed_count
        self.metrics.failed_tasks = failed_count
        
        # 평균 시간 계산
        total_completed = len(self.completed_tasks)
        if total_completed > 0:
            self.metrics.average_wait_time = total_wait_time / total_completed
            self.metrics.average_execution_time = total_execution_time / total_completed
        
        # 처리량 계산 (분당)
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        recent_completions = sum(
            1 for task in self.completed_tasks
            if task.completed_at and task.completed_at > one_minute_ago
        )
        self.metrics.throughput_per_minute = recent_completions
        
        # 디바이스별 메트릭
        device_task_counts = defaultdict(int)
        for task in self.running_tasks.values():
            if task.assigned_device:
                device_task_counts[task.assigned_device] += 1
        
        self.metrics.device_task_counts = dict(device_task_counts)
        
        # 디바이스 활용률 (간단한 계산)
        total_devices = len(self.device_manager.devices)
        if total_devices > 0:
            active_devices = len([d for d in device_task_counts.keys()])
            overall_utilization = active_devices / total_devices
            
            for device_id in self.device_manager.devices.keys():
                device_load = device_task_counts.get(device_id, 0)
                self.metrics.device_utilization[device_id] = min(1.0, device_load / 3.0)  # 3개 작업을 100%로 가정
        
        self.metrics.last_updated = datetime.now()
    
    def get_metrics(self) -> QueueMetrics:
        """현재 메트릭을 반환합니다."""
        return self.metrics
    
    def get_queue_status(self) -> Dict[str, Any]:
        """큐 상태를 반환합니다."""
        return {
            'main_queue_size': self.task_queue.size(),
            'retry_queue_size': self.retry_queue.size(),
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.completed_tasks),
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'is_running': self.is_running,
            'device_loads': dict(self.load_balancer.device_loads),
            'metrics': {
                'total_tasks': self.metrics.total_tasks,
                'pending_tasks': self.metrics.pending_tasks,
                'running_tasks': self.metrics.running_tasks,
                'completed_tasks': self.metrics.completed_tasks,
                'failed_tasks': self.metrics.failed_tasks,
                'average_wait_time': self.metrics.average_wait_time,
                'average_execution_time': self.metrics.average_execution_time,
                'throughput_per_minute': self.metrics.throughput_per_minute,
                'last_updated': self.metrics.last_updated.isoformat()
            }
        }


# 편의 함수들
def create_work_queue_manager(device_manager: DeviceManager, 
                             max_concurrent_tasks: int = 10,
                             load_balancing_strategy: str = "least_loaded") -> WorkQueueManager:
    """
    작업 큐 관리자를 생성합니다.
    
    Args:
        device_manager: 디바이스 매니저
        max_concurrent_tasks: 최대 동시 작업 수
        load_balancing_strategy: 로드 밸런싱 전략
    
    Returns:
        WorkQueueManager 인스턴스
    """
    return WorkQueueManager(device_manager, max_concurrent_tasks, load_balancing_strategy)


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_work_queue():
        """작업 큐 시스템 테스트"""
        try:
            logger.info("작업 큐 시스템 테스트 시작...")
            
            # 디바이스 매니저 및 큐 관리자 생성
            from .device_manager import create_device_manager
            
            device_manager = create_device_manager()
            queue_manager = create_work_queue_manager(device_manager, max_concurrent_tasks=3)
            
            # 큐 관리자 시작
            await queue_manager.start()
            
            # 테스트 작업 제출
            task_ids = []
            for i in range(5):
                task_id = queue_manager.submit_task(
                    task_type=TaskType.ACCOUNT_CREATION,
                    payload={'test_data': f'task_{i}'},
                    priority=TaskPriority.NORMAL if i < 3 else TaskPriority.HIGH,
                    estimated_duration=10,
                    required_capabilities={DeviceCapability.BASIC_AUTOMATION}
                )
                task_ids.append(task_id)
                print(f"✅ 작업 {i+1} 제출됨: {task_id}")
            
            # 잠시 실행
            await asyncio.sleep(5)
            
            # 상태 확인
            status = queue_manager.get_queue_status()
            print(f"📊 큐 상태: {status}")
            
            # 개별 작업 상태 확인
            for task_id in task_ids[:2]:
                task_info = queue_manager.get_task_info(task_id)
                if task_info:
                    print(f"📋 작업 {task_id}: {task_info['status']}")
            
            # 메트릭 확인
            metrics = queue_manager.get_metrics()
            print(f"📈 메트릭: 총 {metrics.total_tasks}개, 실행 중 {metrics.running_tasks}개")
            
            # 더 오래 실행해서 완료 확인
            await asyncio.sleep(30)
            
            final_status = queue_manager.get_queue_status()
            print(f"🏁 최종 상태: {final_status}")
            
            # 큐 관리자 중지
            await queue_manager.stop()
            print("✅ 작업 큐 시스템 테스트 완료")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_work_queue()) 