"""
리소스 관리 시스템 모듈

이 모듈은 멀티 디바이스 환경에서 시스템 리소스를 효율적으로 관리하고 최적화하는 시스템을 제공합니다.
- CPU, 메모리, 네트워크 등 시스템 리소스 모니터링
- 디바이스별 리소스 사용량 추적
- 동적 리소스 할당 및 제한
- API 호출 제한 및 관리 (VPN, SMS 등)
- 성능 최적화 및 부하 분산
"""

import asyncio
import threading
import time
import logging
import psutil
from typing import Dict, List, Optional, Any, Callable, Set, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
from collections import defaultdict, deque
import aiohttp
import subprocess

from .device_manager import DeviceManager, DeviceStatus, DeviceInfo
from .work_queue import WorkQueueManager, TaskStatus, WorkTask
from .parallel_executor import ParallelExecutor, ExecutorStatus

# 로깅 설정
logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """리소스 타입 열거형"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    API_CALLS = "api_calls"
    VPN_CONNECTIONS = "vpn_connections"
    SMS_REQUESTS = "sms_requests"
    DEVICE_SESSIONS = "device_sessions"

class ResourceStatus(Enum):
    """리소스 상태 열거형"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"

class AllocationStrategy(Enum):
    """할당 전략 열거형"""
    FAIR_SHARE = "fair_share"
    PRIORITY_BASED = "priority_based"
    LOAD_BASED = "load_based"
    CAPABILITY_BASED = "capability_based"

@dataclass
class ResourceLimit:
    """리소스 제한 데이터 클래스"""
    resource_type: ResourceType
    max_value: Union[int, float]
    warning_threshold: Union[int, float]
    critical_threshold: Union[int, float]
    unit: str = ""
    per_device: bool = False
    reset_interval: Optional[int] = None  # 초 단위, None이면 리셋 없음

@dataclass
class ResourceUsage:
    """리소스 사용량 데이터 클래스"""
    resource_type: ResourceType
    current_value: Union[int, float]
    peak_value: Union[int, float]
    average_value: Union[int, float]
    timestamp: datetime = field(default_factory=datetime.now)
    device_id: Optional[str] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceAllocation:
    """리소스 할당 데이터 클래스"""
    allocation_id: str
    resource_type: ResourceType
    allocated_amount: Union[int, float]
    device_id: Optional[str] = None
    worker_id: Optional[str] = None
    task_id: Optional[str] = None
    allocated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceMetrics:
    """리소스 메트릭 데이터 클래스"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 시스템 메트릭
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_usage: float = 0.0
    
    # API 사용량
    api_calls_count: int = 0
    vpn_connections: int = 0
    sms_requests_count: int = 0
    device_sessions: int = 0
    
    # 디바이스별 메트릭
    device_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 알림 및 경고
    warnings: List[str] = field(default_factory=list)
    critical_alerts: List[str] = field(default_factory=list)

class SystemMonitor:
    """시스템 모니터링 클래스"""
    
    def __init__(self, monitoring_interval: int = 30):
        """
        시스템 모니터 초기화
        
        Args:
            monitoring_interval: 모니터링 간격 (초)
        """
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self.monitor_thread = None
        self.metrics_history: deque = deque(maxlen=1000)
        
        logger.info("시스템 모니터가 초기화되었습니다.")
    
    def start_monitoring(self) -> None:
        """모니터링을 시작합니다."""
        if self.is_monitoring:
            logger.warning("이미 모니터링이 실행 중입니다.")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("시스템 모니터링이 시작되었습니다.")
    
    def stop_monitoring(self) -> None:
        """모니터링을 중지합니다."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("시스템 모니터링이 중지되었습니다.")
    
    def _monitoring_loop(self) -> None:
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                metrics = self._collect_system_metrics()
                self.metrics_history.append(metrics)
                
                # 임계값 체크
                self._check_thresholds(metrics)
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"시스템 모니터링 오류: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_system_metrics(self) -> ResourceMetrics:
        """시스템 메트릭을 수집합니다."""
        metrics = ResourceMetrics()
        
        try:
            # CPU 사용률
            metrics.cpu_usage = psutil.cpu_percent(interval=1)
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            metrics.memory_usage = memory.percent
            
            # 디스크 사용률
            disk = psutil.disk_usage('/')
            metrics.disk_usage = (disk.used / disk.total) * 100
            
            # 네트워크 사용량 (간단한 버전)
            net_io = psutil.net_io_counters()
            metrics.network_usage = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)  # MB
            
            logger.debug(f"시스템 메트릭 수집됨: CPU {metrics.cpu_usage:.1f}%, "
                       f"메모리 {metrics.memory_usage:.1f}%, 디스크 {metrics.disk_usage:.1f}%")
            
        except Exception as e:
            logger.error(f"메트릭 수집 오류: {e}")
        
        return metrics
    
    def _check_thresholds(self, metrics: ResourceMetrics) -> None:
        """임계값을 체크하고 알림을 생성합니다."""
        # CPU 임계값 체크
        if metrics.cpu_usage > 90:
            metrics.critical_alerts.append(f"CPU 사용률 위험: {metrics.cpu_usage:.1f}%")
        elif metrics.cpu_usage > 80:
            metrics.warnings.append(f"CPU 사용률 경고: {metrics.cpu_usage:.1f}%")
        
        # 메모리 임계값 체크
        if metrics.memory_usage > 95:
            metrics.critical_alerts.append(f"메모리 사용률 위험: {metrics.memory_usage:.1f}%")
        elif metrics.memory_usage > 85:
            metrics.warnings.append(f"메모리 사용률 경고: {metrics.memory_usage:.1f}%")
        
        # 디스크 임계값 체크
        if metrics.disk_usage > 95:
            metrics.critical_alerts.append(f"디스크 사용률 위험: {metrics.disk_usage:.1f}%")
        elif metrics.disk_usage > 90:
            metrics.warnings.append(f"디스크 사용률 경고: {metrics.disk_usage:.1f}%")
    
    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """현재 메트릭을 반환합니다."""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def get_metrics_history(self, hours: int = 1) -> List[ResourceMetrics]:
        """지정된 시간 동안의 메트릭 히스토리를 반환합니다."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metrics for metrics in self.metrics_history
            if metrics.timestamp > cutoff_time
        ]

class ApiLimitManager:
    """API 제한 관리 클래스"""
    
    def __init__(self):
        """API 제한 관리자 초기화"""
        self.limits: Dict[str, ResourceLimit] = {}
        self.usage_counters: Dict[str, int] = defaultdict(int)
        self.last_reset: Dict[str, datetime] = {}
        self.active_requests: Dict[str, Set[str]] = defaultdict(set)
        
        self._setup_default_limits()
        
        logger.info("API 제한 관리자가 초기화되었습니다.")
    
    def _setup_default_limits(self) -> None:
        """기본 API 제한을 설정합니다."""
        default_limits = [
            ResourceLimit(
                resource_type=ResourceType.API_CALLS,
                max_value=1000,
                warning_threshold=800,
                critical_threshold=950,
                unit="requests/hour",
                reset_interval=3600
            ),
            ResourceLimit(
                resource_type=ResourceType.VPN_CONNECTIONS,
                max_value=10,
                warning_threshold=8,
                critical_threshold=9,
                unit="connections"
            ),
            ResourceLimit(
                resource_type=ResourceType.SMS_REQUESTS,
                max_value=50,
                warning_threshold=40,
                critical_threshold=45,
                unit="requests/hour",
                reset_interval=3600
            ),
            ResourceLimit(
                resource_type=ResourceType.DEVICE_SESSIONS,
                max_value=20,
                warning_threshold=15,
                critical_threshold=18,
                unit="sessions"
            )
        ]
        
        for limit in default_limits:
            self.limits[limit.resource_type.value] = limit
    
    async def request_resource(self, 
                              resource_type: ResourceType,
                              amount: int = 1,
                              request_id: Optional[str] = None) -> bool:
        """
        리소스 사용을 요청합니다.
        
        Args:
            resource_type: 리소스 타입
            amount: 요청량
            request_id: 요청 ID
        
        Returns:
            승인 여부
        """
        resource_key = resource_type.value
        
        # 제한 확인
        if resource_key not in self.limits:
            return True  # 제한이 없으면 승인
        
        limit = self.limits[resource_key]
        
        # 리셋 간격 체크
        if limit.reset_interval:
            self._check_reset(resource_key, limit)
        
        # 현재 사용량 확인
        current_usage = self.usage_counters[resource_key]
        
        if current_usage + amount <= limit.max_value:
            self.usage_counters[resource_key] += amount
            
            if request_id:
                self.active_requests[resource_key].add(request_id)
            
            logger.debug(f"리소스 승인: {resource_type.value} +{amount} "
                       f"({current_usage + amount}/{limit.max_value})")
            return True
        else:
            logger.warning(f"리소스 제한 초과: {resource_type.value} "
                         f"({current_usage + amount}/{limit.max_value})")
            return False
    
    def release_resource(self, 
                        resource_type: ResourceType,
                        amount: int = 1,
                        request_id: Optional[str] = None) -> None:
        """리소스를 해제합니다."""
        resource_key = resource_type.value
        
        if resource_key in self.usage_counters:
            self.usage_counters[resource_key] = max(0, 
                self.usage_counters[resource_key] - amount)
        
        if request_id and resource_key in self.active_requests:
            self.active_requests[resource_key].discard(request_id)
        
        logger.debug(f"리소스 해제: {resource_type.value} -{amount}")
    
    def _check_reset(self, resource_key: str, limit: ResourceLimit) -> None:
        """리셋 간격을 체크하고 필요시 카운터를 리셋합니다."""
        now = datetime.now()
        last_reset = self.last_reset.get(resource_key)
        
        if (not last_reset or 
            (now - last_reset).total_seconds() >= limit.reset_interval):
            self.usage_counters[resource_key] = 0
            self.last_reset[resource_key] = now
            logger.info(f"리소스 카운터 리셋: {resource_key}")
    
    def get_usage_status(self) -> Dict[str, Dict[str, Any]]:
        """현재 사용 상태를 반환합니다."""
        status = {}
        
        for resource_key, limit in self.limits.items():
            current_usage = self.usage_counters[resource_key]
            usage_percentage = (current_usage / limit.max_value) * 100
            
            # 상태 결정
            if current_usage >= limit.critical_threshold:
                resource_status = ResourceStatus.CRITICAL
            elif current_usage >= limit.warning_threshold:
                resource_status = ResourceStatus.WARNING
            else:
                resource_status = ResourceStatus.NORMAL
            
            status[resource_key] = {
                "current_usage": current_usage,
                "max_value": limit.max_value,
                "usage_percentage": usage_percentage,
                "status": resource_status.value,
                "active_requests": len(self.active_requests.get(resource_key, set())),
                "last_reset": self.last_reset.get(resource_key)
            }
        
        return status

class ResourceAllocator:
    """리소스 할당자 클래스"""
    
    def __init__(self, strategy: AllocationStrategy = AllocationStrategy.LOAD_BASED):
        """
        리소스 할당자 초기화
        
        Args:
            strategy: 할당 전략
        """
        self.strategy = strategy
        self.allocations: Dict[str, ResourceAllocation] = {}
        self.device_quotas: Dict[str, Dict[ResourceType, float]] = {}
        
        logger.info(f"리소스 할당자가 초기화되었습니다 (전략: {strategy.value})")
    
    def allocate_resources(self,
                          device_id: str,
                          resource_requirements: Dict[ResourceType, float],
                          priority: int = 1,
                          duration: Optional[int] = None) -> bool:
        """
        디바이스에 리소스를 할당합니다.
        
        Args:
            device_id: 디바이스 ID
            resource_requirements: 필요한 리소스 (타입: 양)
            priority: 우선순위
            duration: 할당 지속 시간 (초)
        
        Returns:
            할당 성공 여부
        """
        try:
            allocation_id = f"alloc_{device_id}_{int(time.time())}"
            
            # 가용성 체크
            if not self._check_availability(resource_requirements):
                logger.warning(f"디바이스 {device_id}에 대한 리소스 할당 실패: 가용 리소스 부족")
                return False
            
            # 할당 생성
            for resource_type, amount in resource_requirements.items():
                allocation = ResourceAllocation(
                    allocation_id=f"{allocation_id}_{resource_type.value}",
                    resource_type=resource_type,
                    allocated_amount=amount,
                    device_id=device_id,
                    expires_at=datetime.now() + timedelta(seconds=duration) if duration else None
                )
                
                self.allocations[allocation.allocation_id] = allocation
            
            # 디바이스 할당량 업데이트
            if device_id not in self.device_quotas:
                self.device_quotas[device_id] = {}
            
            for resource_type, amount in resource_requirements.items():
                current_quota = self.device_quotas[device_id].get(resource_type, 0)
                self.device_quotas[device_id][resource_type] = current_quota + amount
            
            logger.info(f"디바이스 {device_id}에 리소스 할당 완료: {resource_requirements}")
            return True
            
        except Exception as e:
            logger.error(f"리소스 할당 오류: {e}")
            return False
    
    def _check_availability(self, resource_requirements: Dict[ResourceType, float]) -> bool:
        """리소스 가용성을 체크합니다."""
        # 현재 할당된 리소스 계산
        current_allocations = defaultdict(float)
        
        for allocation in self.allocations.values():
            if not allocation.expires_at or allocation.expires_at > datetime.now():
                current_allocations[allocation.resource_type] += allocation.allocated_amount
        
        # 시스템 제한과 비교 (간단한 버전)
        system_limits = {
            ResourceType.CPU: 100.0,      # 100% CPU
            ResourceType.MEMORY: 100.0,   # 100% Memory
            ResourceType.NETWORK: 1000.0, # 1000 Mbps
            ResourceType.API_CALLS: 1000.0 # 1000 calls/hour
        }
        
        for resource_type, required_amount in resource_requirements.items():
            current_usage = current_allocations[resource_type]
            system_limit = system_limits.get(resource_type, float('inf'))
            
            if current_usage + required_amount > system_limit:
                return False
        
        return True
    
    def release_allocation(self, allocation_id: str) -> bool:
        """할당을 해제합니다."""
        if allocation_id in self.allocations:
            allocation = self.allocations[allocation_id]
            del self.allocations[allocation_id]
            
            # 디바이스 할당량 업데이트
            if allocation.device_id and allocation.device_id in self.device_quotas:
                device_quotas = self.device_quotas[allocation.device_id]
                if allocation.resource_type in device_quotas:
                    device_quotas[allocation.resource_type] = max(0, 
                        device_quotas[allocation.resource_type] - allocation.allocated_amount)
            
            logger.debug(f"리소스 할당 해제: {allocation_id}")
            return True
        
        return False
    
    def cleanup_expired_allocations(self) -> int:
        """만료된 할당을 정리합니다."""
        now = datetime.now()
        expired_allocations = [
            allocation_id for allocation_id, allocation in self.allocations.items()
            if allocation.expires_at and allocation.expires_at <= now
        ]
        
        for allocation_id in expired_allocations:
            self.release_allocation(allocation_id)
        
        if expired_allocations:
            logger.info(f"{len(expired_allocations)}개의 만료된 할당이 정리되었습니다.")
        
        return len(expired_allocations)
    
    def get_device_allocations(self, device_id: str) -> Dict[ResourceType, float]:
        """디바이스의 현재 할당량을 반환합니다."""
        return self.device_quotas.get(device_id, {}).copy()

class ResourceManager:
    """리소스 관리자 메인 클래스"""
    
    def __init__(self,
                 device_manager: DeviceManager,
                 queue_manager: WorkQueueManager,
                 executor: ParallelExecutor,
                 config_file: Optional[str] = None):
        """
        리소스 관리자 초기화
        
        Args:
            device_manager: 디바이스 매니저
            queue_manager: 큐 관리자
            executor: 병렬 실행기
            config_file: 설정 파일 경로
        """
        self.device_manager = device_manager
        self.queue_manager = queue_manager
        self.executor = executor
        self.config_file = config_file or "data/resource_config.json"
        
        # 컴포넌트
        self.system_monitor = SystemMonitor()
        self.api_limit_manager = ApiLimitManager()
        self.allocator = ResourceAllocator()
        
        # 최적화 설정
        self.optimization_enabled = True
        self.optimization_interval = 300  # 5분
        self.optimization_thread = None
        
        # 상태
        self.is_running = False
        
        # 설정 로드
        self._load_config()
        
        logger.info("리소스 관리자가 초기화되었습니다.")
    
    def _load_config(self) -> None:
        """설정을 로드합니다."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 최적화 설정 적용
                self.optimization_enabled = config.get('optimization_enabled', True)
                self.optimization_interval = config.get('optimization_interval', 300)
                
                logger.info("리소스 관리 설정이 로드되었습니다.")
            else:
                logger.info("설정 파일이 없습니다. 기본 설정을 사용합니다.")
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
    
    async def start(self) -> None:
        """리소스 관리자를 시작합니다."""
        if self.is_running:
            logger.warning("리소스 관리자가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        
        # 시스템 모니터링 시작
        self.system_monitor.start_monitoring()
        
        # 최적화 스레드 시작
        if self.optimization_enabled:
            self.optimization_thread = threading.Thread(
                target=self._optimization_loop, daemon=True
            )
            self.optimization_thread.start()
        
        logger.info("리소스 관리자가 시작되었습니다.")
    
    async def stop(self) -> None:
        """리소스 관리자를 중지합니다."""
        self.is_running = False
        
        # 시스템 모니터링 중지
        self.system_monitor.stop_monitoring()
        
        # 최적화 스레드 정리
        if self.optimization_thread:
            self.optimization_thread.join(timeout=10)
        
        logger.info("리소스 관리자가 중지되었습니다.")
    
    async def request_api_access(self, 
                               api_type: str,
                               device_id: str,
                               request_id: Optional[str] = None) -> bool:
        """
        API 접근을 요청합니다.
        
        Args:
            api_type: API 타입 (vpn, sms, etc.)
            device_id: 디바이스 ID
            request_id: 요청 ID
        
        Returns:
            승인 여부
        """
        resource_map = {
            'vpn': ResourceType.VPN_CONNECTIONS,
            'sms': ResourceType.SMS_REQUESTS,
            'api': ResourceType.API_CALLS
        }
        
        resource_type = resource_map.get(api_type, ResourceType.API_CALLS)
        
        # API 제한 체크
        if not await self.api_limit_manager.request_resource(
            resource_type, 1, request_id
        ):
            logger.warning(f"API 접근 거부: {api_type} (제한 초과)")
            return False
        
        # 디바이스별 리소스 할당 체크
        device_allocations = self.allocator.get_device_allocations(device_id)
        max_concurrent = device_allocations.get(ResourceType.API_CALLS, 5)
        
        # 현재 디바이스의 활성 요청 수 확인 (간단한 버전)
        # 실제 구현에서는 더 정교한 추적 필요
        
        logger.info(f"API 접근 승인: {api_type} (디바이스: {device_id})")
        return True
    
    def release_api_access(self,
                          api_type: str,
                          device_id: str,
                          request_id: Optional[str] = None) -> None:
        """API 접근을 해제합니다."""
        resource_map = {
            'vpn': ResourceType.VPN_CONNECTIONS,
            'sms': ResourceType.SMS_REQUESTS,
            'api': ResourceType.API_CALLS
        }
        
        resource_type = resource_map.get(api_type, ResourceType.API_CALLS)
        
        self.api_limit_manager.release_resource(resource_type, 1, request_id)
        logger.debug(f"API 접근 해제: {api_type} (디바이스: {device_id})")
    
    def allocate_device_resources(self,
                                 device_id: str,
                                 cpu_percent: float = 25.0,
                                 memory_percent: float = 25.0,
                                 network_mbps: float = 10.0,
                                 max_api_calls: float = 50.0) -> bool:
        """디바이스에 리소스를 할당합니다."""
        resource_requirements = {
            ResourceType.CPU: cpu_percent,
            ResourceType.MEMORY: memory_percent,
            ResourceType.NETWORK: network_mbps,
            ResourceType.API_CALLS: max_api_calls
        }
        
        return self.allocator.allocate_resources(
            device_id, resource_requirements, duration=3600  # 1시간
        )
    
    def _optimization_loop(self) -> None:
        """리소스 최적화 루프"""
        while self.is_running:
            try:
                self._perform_optimization()
                time.sleep(self.optimization_interval)
                
            except Exception as e:
                logger.error(f"리소스 최적화 오류: {e}")
                time.sleep(self.optimization_interval)
    
    def _perform_optimization(self) -> None:
        """리소스 최적화를 수행합니다."""
        try:
            # 만료된 할당 정리
            cleaned_count = self.allocator.cleanup_expired_allocations()
            
            # 시스템 메트릭 확인
            current_metrics = self.system_monitor.get_current_metrics()
            if not current_metrics:
                return
            
            # 최적화 규칙 적용
            optimizations_applied = []
            
            # CPU 사용률이 높으면 작업 제한
            if current_metrics.cpu_usage > 85:
                optimizations_applied.append("CPU 사용률이 높아 새 작업 제한")
                # 실제 구현에서는 queue_manager나 executor에 제한 신호 전송
            
            # 메모리 사용률이 높으면 정리 작업 수행
            if current_metrics.memory_usage > 90:
                optimizations_applied.append("메모리 사용률이 높아 정리 작업 수행")
                # 실제 구현에서는 가비지 컬렉션이나 캐시 정리 수행
            
            # 최적화 로그
            if optimizations_applied or cleaned_count > 0:
                logger.info(f"리소스 최적화 수행됨: "
                          f"정리된 할당 {cleaned_count}개, "
                          f"적용된 최적화: {optimizations_applied}")
            
        except Exception as e:
            logger.error(f"리소스 최적화 수행 오류: {e}")
    
    def get_resource_status(self) -> Dict[str, Any]:
        """전체 리소스 상태를 반환합니다."""
        current_metrics = self.system_monitor.get_current_metrics()
        api_status = self.api_limit_manager.get_usage_status()
        
        # 디바이스별 할당 현황
        device_allocations = {}
        for device_id in self.device_manager.devices.keys():
            device_allocations[device_id] = self.allocator.get_device_allocations(device_id)
        
        return {
            "system_metrics": {
                "cpu_usage": current_metrics.cpu_usage if current_metrics else 0,
                "memory_usage": current_metrics.memory_usage if current_metrics else 0,
                "disk_usage": current_metrics.disk_usage if current_metrics else 0,
                "network_usage": current_metrics.network_usage if current_metrics else 0,
                "timestamp": current_metrics.timestamp.isoformat() if current_metrics else None
            },
            "api_limits": api_status,
            "device_allocations": device_allocations,
            "total_allocations": len(self.allocator.allocations),
            "optimization_enabled": self.optimization_enabled,
            "last_updated": datetime.now().isoformat()
        }
    
    def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """성능 보고서를 생성합니다."""
        metrics_history = self.system_monitor.get_metrics_history(hours)
        
        if not metrics_history:
            return {"error": "메트릭 히스토리가 없습니다"}
        
        # 통계 계산
        cpu_values = [m.cpu_usage for m in metrics_history]
        memory_values = [m.memory_usage for m in metrics_history]
        disk_values = [m.disk_usage for m in metrics_history]
        
        return {
            "period_hours": hours,
            "data_points": len(metrics_history),
            "cpu_stats": {
                "average": sum(cpu_values) / len(cpu_values),
                "peak": max(cpu_values),
                "minimum": min(cpu_values)
            },
            "memory_stats": {
                "average": sum(memory_values) / len(memory_values),
                "peak": max(memory_values),
                "minimum": min(memory_values)
            },
            "disk_stats": {
                "average": sum(disk_values) / len(disk_values),
                "peak": max(disk_values),
                "minimum": min(disk_values)
            },
            "alerts_summary": {
                "total_warnings": sum(len(m.warnings) for m in metrics_history),
                "total_critical": sum(len(m.critical_alerts) for m in metrics_history)
            },
            "generated_at": datetime.now().isoformat()
        }


# 편의 함수들
def create_resource_manager(device_manager: DeviceManager,
                           queue_manager: WorkQueueManager,
                           executor: ParallelExecutor,
                           config_file: Optional[str] = None) -> ResourceManager:
    """
    리소스 관리자를 생성합니다.
    
    Args:
        device_manager: 디바이스 매니저
        queue_manager: 큐 관리자
        executor: 병렬 실행기
        config_file: 설정 파일 경로
    
    Returns:
        ResourceManager 인스턴스
    """
    return ResourceManager(device_manager, queue_manager, executor, config_file)


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_resource_manager():
        """리소스 관리자 테스트"""
        try:
            logger.info("리소스 관리자 테스트 시작...")
            
            # 목 의존성 생성
            from .device_manager import create_device_manager
            from .work_queue import create_work_queue_manager
            from .parallel_executor import create_parallel_executor
            
            device_manager = create_device_manager()
            queue_manager = create_work_queue_manager(device_manager)
            executor = create_parallel_executor()
            
            # 리소스 관리자 생성
            resource_manager = create_resource_manager(
                device_manager, queue_manager, executor
            )
            
            # 리소스 관리자 시작
            await resource_manager.start()
            
            # 디바이스 리소스 할당 테스트
            device_id = "test_device_001"
            success = resource_manager.allocate_device_resources(
                device_id, cpu_percent=30, memory_percent=40, max_api_calls=100
            )
            print(f"✅ 디바이스 리소스 할당: {success}")
            
            # API 접근 테스트
            for i in range(5):
                api_access = await resource_manager.request_api_access("sms", device_id, f"req_{i}")
                print(f"📱 SMS API 접근 {i+1}: {api_access}")
                
                if api_access:
                    await asyncio.sleep(1)  # 시뮬레이션
                    resource_manager.release_api_access("sms", device_id, f"req_{i}")
            
            # 상태 확인
            await asyncio.sleep(5)
            status = resource_manager.get_resource_status()
            print(f"📊 리소스 상태: CPU {status['system_metrics']['cpu_usage']:.1f}%, "
                  f"메모리 {status['system_metrics']['memory_usage']:.1f}%")
            
            # API 제한 상태 확인
            for api_type, api_info in status['api_limits'].items():
                print(f"🔗 {api_type}: {api_info['current_usage']}/{api_info['max_value']} "
                      f"({api_info['usage_percentage']:.1f}%)")
            
            # 성능 보고서 생성
            await asyncio.sleep(2)
            performance_report = resource_manager.get_performance_report(hours=1)
            if 'cpu_stats' in performance_report:
                cpu_stats = performance_report['cpu_stats']
                print(f"📈 CPU 성능: 평균 {cpu_stats['average']:.1f}%, "
                      f"최대 {cpu_stats['peak']:.1f}%")
            
            # 리소스 관리자 중지
            await resource_manager.stop()
            print("✅ 리소스 관리자 테스트 완료")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_resource_manager()) 