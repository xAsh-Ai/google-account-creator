"""
디바이스 관리 시스템 모듈

이 모듈은 여러 ADB 디바이스를 관리하고 상태를 추적하는 기능을 제공합니다.
- 디바이스 자동 발견 및 연결
- 디바이스 상태 실시간 모니터링
- 디바이스 통신 프로토콜 관리
- 디바이스 그룹 및 풀 관리
- 디바이스 건강 상태 체크 및 복구
"""

import asyncio
import threading
import time
import logging
from typing import Dict, List, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import subprocess
import json
from enum import Enum
from pathlib import Path
import psutil

from ..core.adb_controller import ADBController

# 로깅 설정
logger = logging.getLogger(__name__)

class DeviceStatus(Enum):
    """디바이스 상태 열거형"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    MAINTENANCE = "maintenance"

class DeviceCapability(Enum):
    """디바이스 능력 열거형"""
    BASIC_AUTOMATION = "basic_automation"
    ADVANCED_AUTOMATION = "advanced_automation"
    HIGH_PERFORMANCE = "high_performance"
    TESTING_ONLY = "testing_only"

@dataclass
class DeviceInfo:
    """디바이스 정보 데이터 클래스"""
    device_id: str
    name: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    api_level: Optional[int] = None
    screen_resolution: Optional[str] = None
    screen_density: Optional[int] = None
    battery_level: Optional[int] = None
    available_storage: Optional[str] = None
    total_memory: Optional[str] = None
    capabilities: Set[DeviceCapability] = field(default_factory=set)
    last_seen: datetime = field(default_factory=datetime.now)
    connection_type: str = "usb"  # usb, wireless
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DevicePool:
    """디바이스 풀 데이터 클래스"""
    pool_id: str
    name: str
    devices: Set[str] = field(default_factory=set)
    max_concurrent: int = 5
    capabilities_required: Set[DeviceCapability] = field(default_factory=set)
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

class DeviceMonitor:
    """디바이스 모니터링 클래스"""
    
    def __init__(self, check_interval: int = 30):
        """
        디바이스 모니터 초기화
        
        Args:
            check_interval: 모니터링 간격 (초)
        """
        self.check_interval = check_interval
        self.is_monitoring = False
        self.monitor_thread = None
        self.callbacks: Dict[str, List[Callable]] = {
            'device_connected': [],
            'device_disconnected': [],
            'device_status_changed': [],
            'device_error': []
        }
        logger.info(f"디바이스 모니터가 초기화되었습니다. 체크 간격: {check_interval}초")
    
    def add_callback(self, event_type: str, callback: Callable) -> None:
        """
        이벤트 콜백을 추가합니다.
        
        Args:
            event_type: 이벤트 타입
            callback: 콜백 함수
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            logger.debug(f"콜백 추가됨: {event_type}")
    
    def start_monitoring(self) -> None:
        """모니터링을 시작합니다."""
        if self.is_monitoring:
            logger.warning("이미 모니터링이 실행 중입니다.")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("디바이스 모니터링이 시작되었습니다.")
    
    def stop_monitoring(self) -> None:
        """모니터링을 중지합니다."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("디바이스 모니터링이 중지되었습니다.")
    
    def _monitor_loop(self) -> None:
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                # 디바이스 상태 체크 로직은 DeviceManager에서 호출
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(self.check_interval)
    
    def trigger_event(self, event_type: str, *args, **kwargs) -> None:
        """
        이벤트를 트리거합니다.
        
        Args:
            event_type: 이벤트 타입
            *args: 위치 인수
            **kwargs: 키워드 인수
        """
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"콜백 실행 오류 ({event_type}): {e}")

class DeviceManager:
    """메인 디바이스 관리 클래스"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        디바이스 매니저 초기화
        
        Args:
            config_file: 설정 파일 경로
        """
        self.devices: Dict[str, DeviceInfo] = {}
        self.device_controllers: Dict[str, ADBController] = {}
        self.device_status: Dict[str, DeviceStatus] = {}
        self.device_pools: Dict[str, DevicePool] = {}
        self.monitor = DeviceMonitor()
        self.config_file = config_file or "data/device_config.json"
        
        # 기본 풀 생성
        self.device_pools["default"] = DevicePool(
            pool_id="default",
            name="기본 디바이스 풀",
            max_concurrent=3
        )
        
        # 이벤트 콜백 등록
        self._register_callbacks()
        
        # 설정 로드
        self._load_config()
        
        logger.info("디바이스 매니저가 초기화되었습니다.")
    
    def _register_callbacks(self) -> None:
        """이벤트 콜백을 등록합니다."""
        self.monitor.add_callback('device_connected', self._on_device_connected)
        self.monitor.add_callback('device_disconnected', self._on_device_disconnected)
        self.monitor.add_callback('device_status_changed', self._on_device_status_changed)
        self.monitor.add_callback('device_error', self._on_device_error)
    
    def _load_config(self) -> None:
        """설정 파일을 로드합니다."""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 디바이스 풀 설정 로드
                if 'device_pools' in config:
                    for pool_data in config['device_pools']:
                        pool = DevicePool(
                            pool_id=pool_data['pool_id'],
                            name=pool_data['name'],
                            devices=set(pool_data.get('devices', [])),
                            max_concurrent=pool_data.get('max_concurrent', 5),
                            capabilities_required=set([
                                DeviceCapability(cap) for cap in pool_data.get('capabilities_required', [])
                            ]),
                            priority=pool_data.get('priority', 1),
                            metadata=pool_data.get('metadata', {})
                        )
                        self.device_pools[pool.pool_id] = pool
                
                logger.info("디바이스 설정이 로드되었습니다.")
            else:
                logger.info("설정 파일이 없습니다. 기본 설정을 사용합니다.")
                
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
    
    def _save_config(self) -> None:
        """설정을 파일에 저장합니다."""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            config = {
                'device_pools': [
                    {
                        'pool_id': pool.pool_id,
                        'name': pool.name,
                        'devices': list(pool.devices),
                        'max_concurrent': pool.max_concurrent,
                        'capabilities_required': [cap.value for cap in pool.capabilities_required],
                        'priority': pool.priority,
                        'metadata': pool.metadata
                    }
                    for pool in self.device_pools.values()
                ]
            }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.debug("디바이스 설정이 저장되었습니다.")
            
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")
    
    async def discover_devices(self) -> List[str]:
        """
        연결된 ADB 디바이스를 발견합니다.
        
        Returns:
            발견된 디바이스 ID 목록
        """
        try:
            logger.info("디바이스 발견 시작...")
            
            # ADB 디바이스 목록 가져오기
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"ADB 명령 실패: {result.stderr}")
                return []
            
            # 출력 파싱
            device_ids = []
            lines = result.stdout.strip().split('\n')[1:]  # 첫 번째 줄은 헤더
            
            for line in lines:
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        device_id = parts[0]
                        status = parts[1]
                        
                        if status == 'device':
                            device_ids.append(device_id)
                            await self._update_device_info(device_id)
                        elif status == 'unauthorized':
                            self.device_status[device_id] = DeviceStatus.UNAUTHORIZED
                            logger.warning(f"디바이스 {device_id}가 인증되지 않았습니다.")
                        else:
                            self.device_status[device_id] = DeviceStatus.OFFLINE
            
            logger.info(f"{len(device_ids)}개의 디바이스를 발견했습니다: {device_ids}")
            return device_ids
            
        except subprocess.TimeoutExpired:
            logger.error("ADB 명령 시간 초과")
            return []
        except Exception as e:
            logger.error(f"디바이스 발견 실패: {e}")
            return []
    
    async def _update_device_info(self, device_id: str) -> None:
        """
        디바이스 정보를 업데이트합니다.
        
        Args:
            device_id: 디바이스 ID
        """
        try:
            # ADB 컨트롤러 생성 또는 재사용
            if device_id not in self.device_controllers:
                self.device_controllers[device_id] = ADBController(device_id)
            
            controller = self.device_controllers[device_id]
            
            # 디바이스 정보 수집
            device_info = DeviceInfo(device_id=device_id)
            
            # 디바이스 속성 가져오기
            try:
                # 모델명
                model_result = await controller.shell_command("getprop ro.product.model")
                if model_result['success']:
                    device_info.model = model_result['output'].strip()
                
                # Android 버전
                version_result = await controller.shell_command("getprop ro.build.version.release")
                if version_result['success']:
                    device_info.android_version = version_result['output'].strip()
                
                # API 레벨
                api_result = await controller.shell_command("getprop ro.build.version.sdk")
                if api_result['success']:
                    device_info.api_level = int(api_result['output'].strip())
                
                # 화면 해상도
                resolution_result = await controller.shell_command("wm size")
                if resolution_result['success']:
                    device_info.screen_resolution = resolution_result['output'].strip()
                
                # 화면 밀도
                density_result = await controller.shell_command("wm density")
                if density_result['success']:
                    density_str = density_result['output'].strip()
                    if 'Physical density:' in density_str:
                        device_info.screen_density = int(density_str.split(':')[1].strip())
                
                # 배터리 레벨
                battery_result = await controller.shell_command("dumpsys battery | grep level")
                if battery_result['success']:
                    battery_str = battery_result['output'].strip()
                    if 'level:' in battery_str:
                        device_info.battery_level = int(battery_str.split(':')[1].strip())
                
                # 저장 공간
                storage_result = await controller.shell_command("df /data | tail -1")
                if storage_result['success']:
                    device_info.available_storage = storage_result['output'].strip()
                
                # 메모리 정보
                memory_result = await controller.shell_command("cat /proc/meminfo | grep MemTotal")
                if memory_result['success']:
                    device_info.total_memory = memory_result['output'].strip()
                
                # 디바이스 능력 평가
                device_info.capabilities = self._assess_device_capabilities(device_info)
                
                # 디바이스 정보 저장
                self.devices[device_id] = device_info
                self.device_status[device_id] = DeviceStatus.AVAILABLE
                
                logger.info(f"디바이스 {device_id} 정보 업데이트 완료: {device_info.model}")
                
            except Exception as e:
                logger.warning(f"디바이스 {device_id} 속성 수집 실패: {e}")
                self.device_status[device_id] = DeviceStatus.ERROR
                
        except Exception as e:
            logger.error(f"디바이스 {device_id} 정보 업데이트 실패: {e}")
            self.device_status[device_id] = DeviceStatus.ERROR
    
    def _assess_device_capabilities(self, device_info: DeviceInfo) -> Set[DeviceCapability]:
        """
        디바이스 능력을 평가합니다.
        
        Args:
            device_info: 디바이스 정보
        
        Returns:
            디바이스 능력 집합
        """
        capabilities = set()
        
        # 기본 자동화 능력 (모든 디바이스)
        capabilities.add(DeviceCapability.BASIC_AUTOMATION)
        
        # API 레벨 기반 능력
        if device_info.api_level and device_info.api_level >= 28:
            capabilities.add(DeviceCapability.ADVANCED_AUTOMATION)
        
        # 고성능 디바이스 판단 (메모리, 해상도 기반)
        if (device_info.total_memory and 'GB' in device_info.total_memory and 
            device_info.screen_resolution and '1080' in device_info.screen_resolution):
            capabilities.add(DeviceCapability.HIGH_PERFORMANCE)
        
        # 테스트 전용 디바이스 판단 (에뮬레이터 등)
        if device_info.model and ('emulator' in device_info.model.lower() or 
                                 'sdk' in device_info.model.lower()):
            capabilities.add(DeviceCapability.TESTING_ONLY)
        
        return capabilities
    
    def get_available_devices(self, 
                            pool_id: Optional[str] = None,
                            capabilities: Optional[Set[DeviceCapability]] = None) -> List[str]:
        """
        사용 가능한 디바이스 목록을 가져옵니다.
        
        Args:
            pool_id: 특정 풀의 디바이스만 조회
            capabilities: 필요한 능력
        
        Returns:
            사용 가능한 디바이스 ID 목록
        """
        available_devices = []
        
        for device_id, status in self.device_status.items():
            if status != DeviceStatus.AVAILABLE:
                continue
            
            # 풀 필터링
            if pool_id and pool_id in self.device_pools:
                pool = self.device_pools[pool_id]
                if pool.devices and device_id not in pool.devices:
                    continue
            
            # 능력 필터링
            if capabilities and device_id in self.devices:
                device_capabilities = self.devices[device_id].capabilities
                if not capabilities.issubset(device_capabilities):
                    continue
            
            available_devices.append(device_id)
        
        logger.debug(f"사용 가능한 디바이스: {available_devices}")
        return available_devices
    
    def reserve_device(self, device_id: str, task_id: Optional[str] = None) -> bool:
        """
        디바이스를 예약합니다.
        
        Args:
            device_id: 디바이스 ID
            task_id: 작업 ID
        
        Returns:
            예약 성공 여부
        """
        if device_id not in self.device_status:
            logger.warning(f"알 수 없는 디바이스: {device_id}")
            return False
        
        if self.device_status[device_id] != DeviceStatus.AVAILABLE:
            logger.warning(f"디바이스 {device_id}가 사용 불가능합니다: {self.device_status[device_id]}")
            return False
        
        self.device_status[device_id] = DeviceStatus.BUSY
        
        # 메타데이터에 작업 정보 저장
        if device_id in self.devices:
            self.devices[device_id].metadata['current_task'] = task_id
            self.devices[device_id].metadata['reserved_at'] = datetime.now().isoformat()
        
        logger.info(f"디바이스 {device_id}가 예약되었습니다 (작업: {task_id})")
        return True
    
    def release_device(self, device_id: str) -> bool:
        """
        디바이스 예약을 해제합니다.
        
        Args:
            device_id: 디바이스 ID
        
        Returns:
            해제 성공 여부
        """
        if device_id not in self.device_status:
            logger.warning(f"알 수 없는 디바이스: {device_id}")
            return False
        
        self.device_status[device_id] = DeviceStatus.AVAILABLE
        
        # 메타데이터 정리
        if device_id in self.devices:
            self.devices[device_id].metadata.pop('current_task', None)
            self.devices[device_id].metadata.pop('reserved_at', None)
            self.devices[device_id].last_seen = datetime.now()
        
        logger.info(f"디바이스 {device_id} 예약이 해제되었습니다.")
        return True
    
    def get_device_controller(self, device_id: str) -> Optional[ADBController]:
        """
        디바이스 컨트롤러를 가져옵니다.
        
        Args:
            device_id: 디바이스 ID
        
        Returns:
            ADB 컨트롤러 또는 None
        """
        return self.device_controllers.get(device_id)
    
    def create_device_pool(self, 
                          pool_id: str,
                          name: str,
                          devices: Optional[List[str]] = None,
                          max_concurrent: int = 5,
                          capabilities_required: Optional[Set[DeviceCapability]] = None) -> bool:
        """
        새로운 디바이스 풀을 생성합니다.
        
        Args:
            pool_id: 풀 ID
            name: 풀 이름
            devices: 포함할 디바이스 목록
            max_concurrent: 최대 동시 사용 디바이스 수
            capabilities_required: 필요한 능력
        
        Returns:
            생성 성공 여부
        """
        if pool_id in self.device_pools:
            logger.warning(f"디바이스 풀 {pool_id}가 이미 존재합니다.")
            return False
        
        pool = DevicePool(
            pool_id=pool_id,
            name=name,
            devices=set(devices or []),
            max_concurrent=max_concurrent,
            capabilities_required=capabilities_required or set()
        )
        
        self.device_pools[pool_id] = pool
        self._save_config()
        
        logger.info(f"디바이스 풀 '{name}' (ID: {pool_id})가 생성되었습니다.")
        return True
    
    def add_device_to_pool(self, device_id: str, pool_id: str) -> bool:
        """
        디바이스를 풀에 추가합니다.
        
        Args:
            device_id: 디바이스 ID
            pool_id: 풀 ID
        
        Returns:
            추가 성공 여부
        """
        if pool_id not in self.device_pools:
            logger.warning(f"디바이스 풀 {pool_id}가 존재하지 않습니다.")
            return False
        
        if device_id not in self.devices:
            logger.warning(f"디바이스 {device_id}가 등록되지 않았습니다.")
            return False
        
        self.device_pools[pool_id].devices.add(device_id)
        self._save_config()
        
        logger.info(f"디바이스 {device_id}가 풀 {pool_id}에 추가되었습니다.")
        return True
    
    async def health_check(self, device_id: str) -> bool:
        """
        디바이스 건강 상태를 체크합니다.
        
        Args:
            device_id: 디바이스 ID
        
        Returns:
            건강 상태
        """
        try:
            if device_id not in self.device_controllers:
                return False
            
            controller = self.device_controllers[device_id]
            
            # 기본 연결 테스트
            result = await controller.shell_command("echo 'ping'")
            if not result['success'] or 'ping' not in result['output']:
                logger.warning(f"디바이스 {device_id} 연결 실패")
                self.device_status[device_id] = DeviceStatus.ERROR
                return False
            
            # 배터리 레벨 체크
            battery_result = await controller.shell_command("dumpsys battery | grep level")
            if battery_result['success']:
                battery_str = battery_result['output'].strip()
                if 'level:' in battery_str:
                    battery_level = int(battery_str.split(':')[1].strip())
                    if battery_level < 20:
                        logger.warning(f"디바이스 {device_id} 배터리 부족: {battery_level}%")
                        # 배터리 부족이지만 에러는 아님
            
            # 저장 공간 체크
            storage_result = await controller.shell_command("df /data")
            if storage_result['success']:
                lines = storage_result['output'].strip().split('\n')
                if len(lines) > 1:
                    parts = lines[-1].split()
                    if len(parts) >= 5:
                        used_percent = parts[4].replace('%', '')
                        if used_percent.isdigit() and int(used_percent) > 90:
                            logger.warning(f"디바이스 {device_id} 저장 공간 부족: {used_percent}%")
            
            self.device_status[device_id] = DeviceStatus.AVAILABLE
            if device_id in self.devices:
                self.devices[device_id].last_seen = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"디바이스 {device_id} 건강 체크 실패: {e}")
            self.device_status[device_id] = DeviceStatus.ERROR
            return False
    
    async def cleanup_device(self, device_id: str) -> bool:
        """
        디바이스를 정리합니다.
        
        Args:
            device_id: 디바이스 ID
        
        Returns:
            정리 성공 여부
        """
        try:
            if device_id not in self.device_controllers:
                return False
            
            controller = self.device_controllers[device_id]
            
            # 실행 중인 앱 종료
            await controller.shell_command("am force-stop com.android.chrome")
            await controller.shell_command("am force-stop com.google.android.gms")
            
            # 임시 파일 정리
            await controller.shell_command("rm -rf /sdcard/tmp/*")
            await controller.shell_command("rm -rf /data/local/tmp/*")
            
            # 캐시 정리
            await controller.shell_command("pm clear com.android.chrome")
            
            logger.info(f"디바이스 {device_id} 정리 완료")
            return True
            
        except Exception as e:
            logger.error(f"디바이스 {device_id} 정리 실패: {e}")
            return False
    
    def get_device_statistics(self) -> Dict[str, Any]:
        """
        디바이스 통계를 가져옵니다.
        
        Returns:
            디바이스 통계
        """
        total_devices = len(self.devices)
        status_counts = {}
        capability_counts = {}
        
        for status in self.device_status.values():
            status_counts[status.value] = status_counts.get(status.value, 0) + 1
        
        for device in self.devices.values():
            for capability in device.capabilities:
                capability_counts[capability.value] = capability_counts.get(capability.value, 0) + 1
        
        return {
            'total_devices': total_devices,
            'status_counts': status_counts,
            'capability_counts': capability_counts,
            'pools': {
                pool_id: {
                    'name': pool.name,
                    'device_count': len(pool.devices),
                    'max_concurrent': pool.max_concurrent
                }
                for pool_id, pool in self.device_pools.items()
            },
            'last_updated': datetime.now().isoformat()
        }
    
    def start_monitoring(self) -> None:
        """디바이스 모니터링을 시작합니다."""
        self.monitor.start_monitoring()
    
    def stop_monitoring(self) -> None:
        """디바이스 모니터링을 중지합니다."""
        self.monitor.stop_monitoring()
    
    # 이벤트 콜백 메서드들
    def _on_device_connected(self, device_id: str) -> None:
        """디바이스 연결 이벤트 핸들러"""
        logger.info(f"디바이스 연결됨: {device_id}")
    
    def _on_device_disconnected(self, device_id: str) -> None:
        """디바이스 연결 해제 이벤트 핸들러"""
        logger.info(f"디바이스 연결 해제됨: {device_id}")
        if device_id in self.device_status:
            self.device_status[device_id] = DeviceStatus.OFFLINE
    
    def _on_device_status_changed(self, device_id: str, old_status: DeviceStatus, new_status: DeviceStatus) -> None:
        """디바이스 상태 변경 이벤트 핸들러"""
        logger.info(f"디바이스 {device_id} 상태 변경: {old_status.value} -> {new_status.value}")
    
    def _on_device_error(self, device_id: str, error: Exception) -> None:
        """디바이스 오류 이벤트 핸들러"""
        logger.error(f"디바이스 {device_id} 오류: {error}")
        if device_id in self.device_status:
            self.device_status[device_id] = DeviceStatus.ERROR


# 편의 함수들
def create_device_manager(config_file: Optional[str] = None) -> DeviceManager:
    """
    디바이스 매니저를 생성합니다.
    
    Args:
        config_file: 설정 파일 경로
    
    Returns:
        DeviceManager 인스턴스
    """
    return DeviceManager(config_file)

async def quick_device_discovery() -> List[str]:
    """
    빠른 디바이스 발견을 수행합니다.
    
    Returns:
        발견된 디바이스 ID 목록
    """
    manager = create_device_manager()
    return await manager.discover_devices()


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_device_manager():
        """디바이스 매니저 테스트"""
        try:
            logger.info("디바이스 매니저 테스트 시작...")
            
            # 디바이스 매니저 생성
            manager = create_device_manager()
            
            # 디바이스 발견
            devices = await manager.discover_devices()
            print(f"✅ 발견된 디바이스: {devices}")
            
            # 사용 가능한 디바이스 조회
            available = manager.get_available_devices()
            print(f"✅ 사용 가능한 디바이스: {available}")
            
            # 디바이스 풀 생성
            if manager.create_device_pool(
                pool_id="test_pool",
                name="테스트 풀",
                max_concurrent=2,
                capabilities_required={DeviceCapability.BASIC_AUTOMATION}
            ):
                print("✅ 디바이스 풀 생성 성공")
            
            # 디바이스 예약 테스트
            if devices:
                device_id = devices[0]
                if manager.reserve_device(device_id, "test_task_001"):
                    print(f"✅ 디바이스 {device_id} 예약 성공")
                    
                    # 건강 체크
                    health = await manager.health_check(device_id)
                    print(f"✅ 디바이스 건강 상태: {health}")
                    
                    # 예약 해제
                    if manager.release_device(device_id):
                        print(f"✅ 디바이스 {device_id} 예약 해제 성공")
            
            # 통계 확인
            stats = manager.get_device_statistics()
            print(f"📊 디바이스 통계: {stats}")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_device_manager()) 