#!/usr/bin/env python3
"""
Google Account Creator - 메인 오케스트레이션 스크립트

이 스크립트는 멀티 디바이스 환경에서 Google 계정 생성 프로세스를 자동화하고 관리합니다.
- 디바이스 자동 발견 및 초기화
- 워커 프로세스 관리 및 작업 분배
- 전역 에러 처리 및 복구
- 설정 관리 및 API 제한
- 실시간 모니터링 및 제어 CLI
"""

import asyncio
import argparse
import signal
import sys
import os
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

# 프로젝트 모듈 import
from workers.device_manager import DeviceManager, DeviceStatus, DeviceInfo
from workers.work_queue import WorkQueueManager, TaskStatus, WorkTask
from workers.parallel_executor import ParallelExecutor, ExecutorStatus
from workers.error_handler import ErrorHandlingSystem, ErrorCategory, ErrorSeverity
from workers.resource_manager import ResourceManager

# 로깅 설정
logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    """애플리케이션 설정 데이터 클래스"""
    # 디바이스 설정
    max_devices: int = 10
    device_timeout: int = 300
    device_retry_attempts: int = 3
    
    # 워커 설정
    max_workers_per_device: int = 2
    worker_timeout: int = 600
    
    # API 제한
    max_api_calls_per_hour: int = 1000
    max_vpn_connections: int = 5
    max_sms_requests_per_hour: int = 50
    
    # 계정 생성 설정
    target_accounts: int = 100
    batch_size: int = 10
    creation_delay: float = 30.0
    
    # 로깅 설정
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/main.log"
    
    # 기타 설정
    config_file: str = "config/config.json"
    data_dir: str = "data"
    enable_monitoring: bool = True
    graceful_shutdown_timeout: int = 30

@dataclass  
class SystemStatus:
    """시스템 상태 데이터 클래스"""
    started_at: datetime = field(default_factory=datetime.now)
    is_running: bool = False
    is_shutting_down: bool = False
    
    # 디바이스 상태
    total_devices: int = 0
    active_devices: int = 0
    failed_devices: int = 0
    
    # 작업 상태
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    
    # 성능 메트릭
    accounts_created: int = 0
    success_rate: float = 0.0
    average_creation_time: float = 0.0
    
    # 에러 통계
    total_errors: int = 0
    critical_errors: int = 0
    last_error: Optional[str] = None
    
    def get_uptime(self) -> timedelta:
        """시스템 가동 시간을 반환합니다."""
        return datetime.now() - self.started_at
    
    def get_status_dict(self) -> Dict[str, Any]:
        """상태를 딕셔너리로 반환합니다."""
        return {
            "started_at": self.started_at.isoformat(),
            "uptime_seconds": self.get_uptime().total_seconds(),
            "is_running": self.is_running,
            "is_shutting_down": self.is_shutting_down,
            "devices": {
                "total": self.total_devices,
                "active": self.active_devices,
                "failed": self.failed_devices
            },
            "tasks": {
                "total": self.total_tasks,
                "completed": self.completed_tasks,
                "failed": self.failed_tasks,
                "pending": self.pending_tasks
            },
            "performance": {
                "accounts_created": self.accounts_created,
                "success_rate": self.success_rate,
                "average_creation_time": self.average_creation_time
            },
            "errors": {
                "total": self.total_errors,
                "critical": self.critical_errors,
                "last_error": self.last_error
            }
        }

class DeviceInitializer:
    """디바이스 초기화 클래스"""
    
    def __init__(self, config: AppConfig):
        """
        디바이스 초기화기 초기화
        
        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self.discovered_devices: List[DeviceInfo] = []
        self.initialized_devices: Dict[str, DeviceInfo] = {}
        self.failed_devices: Set[str] = set()
        
        logger.info("디바이스 초기화기가 생성되었습니다.")
    
    async def discover_devices(self) -> List[DeviceInfo]:
        """
        사용 가능한 디바이스를 검색합니다.
        
        Returns:
            발견된 디바이스 목록
        """
        logger.info("디바이스 검색을 시작합니다...")
        
        try:
            # ADB 디바이스 검색
            discovered = await self._discover_adb_devices()
            
            # 에뮬레이터 검색
            emulator_devices = await self._discover_emulator_devices()
            discovered.extend(emulator_devices)
            
            # 디바이스 필터링 및 검증
            valid_devices = await self._validate_devices(discovered)
            
            self.discovered_devices = valid_devices
            logger.info(f"{len(valid_devices)}개의 유효한 디바이스를 발견했습니다.")
            
            return valid_devices
            
        except Exception as e:
            logger.error(f"디바이스 검색 중 오류: {e}")
            return []
    
    async def _discover_adb_devices(self) -> List[DeviceInfo]:
        """ADB를 통해 연결된 디바이스를 검색합니다."""
        devices = []
        
        try:
            import subprocess
            result = await asyncio.create_subprocess_exec(
                'adb', 'devices', '-l',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                lines = stdout.decode().strip().split('\n')[1:]  # 헤더 제외
                
                for line in lines:
                    line = line.strip()
                    if line and 'device' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            device_id = parts[0]
                            
                            # 디바이스 정보 수집
                            device_info = DeviceInfo(
                                device_id=device_id,
                                device_type="physical" if "emulator" not in device_id else "emulator",
                                status=DeviceStatus.AVAILABLE,
                                capabilities={"adb": True, "android": True},
                                last_seen=datetime.now()
                            )
                            
                            devices.append(device_info)
                            
                logger.info(f"ADB를 통해 {len(devices)}개 디바이스 발견")
                
            else:
                logger.warning(f"ADB 명령 실행 실패: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"ADB 디바이스 검색 오류: {e}")
        
        return devices
    
    async def _discover_emulator_devices(self) -> List[DeviceInfo]:
        """에뮬레이터 디바이스를 검색합니다."""
        devices = []
        
        try:
            # 에뮬레이터 리스트 확인
            result = await asyncio.create_subprocess_exec(
                'emulator', '-list-avds',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                avd_names = stdout.decode().strip().split('\n')
                
                for avd_name in avd_names:
                    if avd_name.strip():
                        # 실행 중인지 확인
                        device_info = DeviceInfo(
                            device_id=f"emulator-{avd_name}",
                            device_type="emulator",
                            status=DeviceStatus.AVAILABLE,
                            capabilities={
                                "adb": True, 
                                "android": True, 
                                "emulator": True,
                                "avd_name": avd_name
                            },
                            last_seen=datetime.now()
                        )
                        
                        devices.append(device_info)
                
                logger.info(f"에뮬레이터에서 {len(devices)}개 AVD 발견")
                
        except Exception as e:
            logger.error(f"에뮬레이터 검색 오류: {e}")
        
        return devices
    
    async def _validate_devices(self, devices: List[DeviceInfo]) -> List[DeviceInfo]:
        """디바이스 유효성을 검증합니다."""
        valid_devices = []
        
        for device in devices:
            try:
                # 디바이스 연결 테스트
                if await self._test_device_connection(device):
                    # 안드로이드 버전 확인
                    android_version = await self._get_android_version(device)
                    if android_version:
                        device.capabilities["android_version"] = android_version
                        
                        # 디바이스 사양 확인
                        specs = await self._get_device_specs(device)
                        device.capabilities.update(specs)
                        
                        valid_devices.append(device)
                        logger.debug(f"디바이스 {device.device_id} 검증 완료")
                    else:
                        logger.warning(f"디바이스 {device.device_id}: 안드로이드 버전 확인 실패")
                else:
                    logger.warning(f"디바이스 {device.device_id}: 연결 테스트 실패")
                    
            except Exception as e:
                logger.error(f"디바이스 {device.device_id} 검증 오류: {e}")
        
        return valid_devices
    
    async def _test_device_connection(self, device: DeviceInfo) -> bool:
        """디바이스 연결을 테스트합니다."""
        try:
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell', 'echo', 'test',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and b'test' in stdout:
                return True
                
        except Exception as e:
            logger.debug(f"디바이스 {device.device_id} 연결 테스트 실패: {e}")
        
        return False
    
    async def _get_android_version(self, device: DeviceInfo) -> Optional[str]:
        """안드로이드 버전을 확인합니다."""
        try:
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell', 
                'getprop', 'ro.build.version.release',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version = stdout.decode().strip()
                return version if version else None
                
        except Exception as e:
            logger.debug(f"디바이스 {device.device_id} 안드로이드 버전 확인 실패: {e}")
        
        return None
    
    async def _get_device_specs(self, device: DeviceInfo) -> Dict[str, Any]:
        """디바이스 사양을 확인합니다."""
        specs = {}
        
        try:
            # 디바이스 모델명
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'getprop', 'ro.product.model',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                specs["model"] = stdout.decode().strip()
            
            # 화면 해상도
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'wm', 'size',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                size_info = stdout.decode().strip()
                if "Physical size:" in size_info:
                    resolution = size_info.split("Physical size:")[-1].strip()
                    specs["resolution"] = resolution
            
            # RAM 정보
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'cat', '/proc/meminfo',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                meminfo = stdout.decode()
                for line in meminfo.split('\n'):
                    if 'MemTotal:' in line:
                        mem_kb = int(line.split()[1])
                        specs["ram_mb"] = mem_kb // 1024
                        break
            
        except Exception as e:
            logger.debug(f"디바이스 {device.device_id} 사양 확인 중 오류: {e}")
        
        return specs
    
    async def initialize_device(self, device: DeviceInfo) -> bool:
        """
        단일 디바이스를 초기화합니다.
        
        Args:
            device: 초기화할 디바이스 정보
            
        Returns:
            초기화 성공 여부
        """
        device_id = device.device_id
        
        if device_id in self.failed_devices:
            logger.warning(f"디바이스 {device_id}: 이전에 초기화 실패한 디바이스입니다.")
            return False
        
        logger.info(f"디바이스 {device_id} 초기화 시작...")
        
        try:
            # 디바이스 상태 확인
            if not await self._test_device_connection(device):
                raise Exception("디바이스 연결 실패")
            
            # 필요한 앱 설치 확인
            if not await self._check_required_apps(device):
                await self._install_required_apps(device)
            
            # 디바이스 설정 구성
            await self._configure_device_settings(device)
            
            # 권한 설정
            await self._setup_device_permissions(device)
            
            # 초기화 완료
            device.status = DeviceStatus.READY
            device.last_seen = datetime.now()
            self.initialized_devices[device_id] = device
            
            logger.info(f"디바이스 {device_id} 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"디바이스 {device_id} 초기화 실패: {e}")
            device.status = DeviceStatus.ERROR
            self.failed_devices.add(device_id)
            return False
    
    async def _check_required_apps(self, device: DeviceInfo) -> bool:
        """필요한 앱이 설치되어 있는지 확인합니다."""
        required_packages = [
            "com.android.chrome",
            "com.google.android.gms"
        ]
        
        try:
            for package in required_packages:
                result = await asyncio.create_subprocess_exec(
                    'adb', '-s', device.device_id, 'shell',
                    'pm', 'list', 'packages', package,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, _ = await result.communicate()
                
                if package not in stdout.decode():
                    logger.info(f"디바이스 {device.device_id}: 필요한 앱 {package} 없음")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"디바이스 {device.device_id} 앱 확인 오류: {e}")
            return False
    
    async def _install_required_apps(self, device: DeviceInfo) -> None:
        """필요한 앱을 설치합니다."""
        logger.info(f"디바이스 {device.device_id}: 필요한 앱 설치 중...")
        
        # 실제 구현에서는 APK 파일 설치 등
        # 여기서는 로그만 출력
        await asyncio.sleep(2)  # 설치 시뮬레이션
        
        logger.info(f"디바이스 {device.device_id}: 앱 설치 완료")
    
    async def _configure_device_settings(self, device: DeviceInfo) -> None:
        """디바이스 설정을 구성합니다."""
        logger.info(f"디바이스 {device.device_id}: 설정 구성 중...")
        
        try:
            # 개발자 옵션 활성화 확인
            result = await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'settings', 'get', 'global', 'development_settings_enabled',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await result.communicate()
            
            if result.returncode != 0 or '1' not in stdout.decode():
                logger.warning(f"디바이스 {device.device_id}: 개발자 옵션이 비활성화되어 있습니다.")
            
            # 화면 켜짐 유지
            await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'settings', 'put', 'global', 'stay_on_while_plugged_in', '3'
            )
            
            # 화면 잠금 해제
            await asyncio.create_subprocess_exec(
                'adb', '-s', device.device_id, 'shell',
                'input', 'keyevent', 'KEYCODE_MENU'
            )
            
            logger.info(f"디바이스 {device.device_id}: 설정 구성 완료")
            
        except Exception as e:
            logger.error(f"디바이스 {device.device_id} 설정 구성 오류: {e}")
    
    async def _setup_device_permissions(self, device: DeviceInfo) -> None:
        """디바이스 권한을 설정합니다."""
        logger.info(f"디바이스 {device.device_id}: 권한 설정 중...")
        
        # 필요한 권한들을 부여
        permissions = [
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.WRITE_EXTERNAL_STORAGE"
        ]
        
        try:
            for permission in permissions:
                # 권한 부여 (실제로는 앱별로 처리해야 함)
                logger.debug(f"권한 설정: {permission}")
            
            logger.info(f"디바이스 {device.device_id}: 권한 설정 완료")
            
        except Exception as e:
            logger.error(f"디바이스 {device.device_id} 권한 설정 오류: {e}")
    
    async def initialize_all_devices(self) -> Dict[str, bool]:
        """
        모든 발견된 디바이스를 초기화합니다.
        
        Returns:
            디바이스별 초기화 결과
        """
        if not self.discovered_devices:
            logger.warning("초기화할 디바이스가 없습니다. 먼저 디바이스를 검색하세요.")
            return {}
        
        logger.info(f"{len(self.discovered_devices)}개 디바이스 초기화 시작...")
        
        # 병렬 초기화
        tasks = []
        for device in self.discovered_devices:
            task = self.initialize_device(device)
            tasks.append((device.device_id, task))
        
        results = {}
        for device_id, task in tasks:
            try:
                success = await task
                results[device_id] = success
            except Exception as e:
                logger.error(f"디바이스 {device_id} 초기화 중 예외: {e}")
                results[device_id] = False
        
        # 결과 요약
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        logger.info(f"디바이스 초기화 완료: {successful}/{total} 성공")
        
        return results
    
    def get_initialized_devices(self) -> List[DeviceInfo]:
        return list(self.initialized_devices.values())

class WorkerManager:
    """워커 관리 클래스"""
    
    def __init__(self, config: AppConfig, device_manager: DeviceManager):
        """
        워커 관리자 초기화
        
        Args:
            config: 애플리케이션 설정
            device_manager: 디바이스 매니저
        """
        self.config = config
        self.device_manager = device_manager
        
        # 워커 상태 관리
        self.active_workers: Dict[str, Any] = {}
        self.worker_processes: Dict[str, Any] = {}
        self.worker_tasks: Dict[str, Set[str]] = {}
        
        # 작업 분배
        self.pending_work_items: List[Any] = []
        self.completed_work_items: List[Any] = []
        self.failed_work_items: List[Any] = []
        
        # 성능 메트릭
        self.worker_metrics: Dict[str, Dict[str, Any]] = {}
        
        # 제어 플래그
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        logger.info("워커 관리자가 초기화되었습니다.")
    
    async def start_workers(self) -> bool:
        """
        모든 사용 가능한 디바이스에 워커를 시작합니다.
        
        Returns:
            워커 시작 성공 여부
        """
        logger.info("워커 시작 프로세스 시작...")
        
        try:
            available_devices = await self.device_manager.get_available_devices()
            
            if not available_devices:
                logger.error("사용 가능한 디바이스가 없습니다.")
                return False
            
            # 각 디바이스에 워커 시작
            successful_workers = 0
            for device in available_devices:
                worker_count = min(
                    self.config.max_workers_per_device,
                    self._calculate_optimal_workers(device)
                )
                
                for i in range(worker_count):
                    worker_id = f"{device.device_id}_worker_{i}"
                    
                    if await self._start_worker(worker_id, device):
                        successful_workers += 1
                        logger.info(f"워커 {worker_id} 시작됨")
                    else:
                        logger.error(f"워커 {worker_id} 시작 실패")
            
            self.is_running = successful_workers > 0
            
            logger.info(f"워커 시작 완료: {successful_workers}개 워커 활성화")
            return self.is_running
            
        except Exception as e:
            logger.error(f"워커 시작 중 오류: {e}")
            return False
    
    def _calculate_optimal_workers(self, device: DeviceInfo) -> int:
        """
        디바이스에 최적화된 워커 수를 계산합니다.
        
        Args:
            device: 디바이스 정보
            
        Returns:
            최적 워커 수
        """
        # 디바이스 사양에 따른 워커 수 조정
        ram_mb = device.capabilities.get("ram_mb", 2048)
        
        if ram_mb >= 8192:  # 8GB 이상
            return min(4, self.config.max_workers_per_device)
        elif ram_mb >= 4096:  # 4GB 이상
            return min(3, self.config.max_workers_per_device)
        elif ram_mb >= 2048:  # 2GB 이상
            return min(2, self.config.max_workers_per_device)
        else:  # 2GB 미만
            return 1
    
    async def _start_worker(self, worker_id: str, device: DeviceInfo) -> bool:
        """
        단일 워커를 시작합니다.
        
        Args:
            worker_id: 워커 ID
            device: 대상 디바이스
            
        Returns:
            워커 시작 성공 여부
        """
        try:
            # 워커 상태 초기화
            worker_info = {
                "worker_id": worker_id,
                "device_id": device.device_id,
                "status": "starting",
                "started_at": datetime.now(),
                "current_task": None,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "last_activity": datetime.now()
            }
            
            self.active_workers[worker_id] = worker_info
            self.worker_tasks[worker_id] = set()
            self.worker_metrics[worker_id] = {
                "accounts_created": 0,
                "average_time": 0.0,
                "success_rate": 0.0,
                "errors": []
            }
            
            # 워커 프로세스 시작 (실제 구현에서는 multiprocessing.Process 사용)
            worker_task = asyncio.create_task(
                self._worker_main_loop(worker_id, device)
            )
            
            self.worker_processes[worker_id] = worker_task
            
            worker_info["status"] = "running"
            logger.debug(f"워커 {worker_id} 시작 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"워커 {worker_id} 시작 실패: {e}")
            
            # 실패한 워커 정리
            self.active_workers.pop(worker_id, None)
            self.worker_tasks.pop(worker_id, None)
            self.worker_metrics.pop(worker_id, None)
            
            return False
    
    async def _worker_main_loop(self, worker_id: str, device: DeviceInfo):
        """
        워커의 메인 실행 루프
        
        Args:
            worker_id: 워커 ID
            device: 대상 디바이스
        """
        logger.info(f"워커 {worker_id} 메인 루프 시작")
        
        try:
            while self.is_running and not self.shutdown_event.is_set():
                # 작업 할당 대기
                work_item = await self._get_next_work_item(worker_id)
                
                if work_item is None:
                    # 작업이 없으면 잠시 대기
                    await asyncio.sleep(5)
                    continue
                
                # 작업 실행
                await self._execute_work_item(worker_id, device, work_item)
                
                # 워커 상태 업데이트
                self._update_worker_activity(worker_id)
                
        except asyncio.CancelledError:
            logger.info(f"워커 {worker_id} 취소됨")
        except Exception as e:
            logger.error(f"워커 {worker_id} 메인 루프 오류: {e}")
        finally:
            await self._cleanup_worker(worker_id)
    
    async def _get_next_work_item(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        워커에게 다음 작업을 할당합니다.
        
        Args:
            worker_id: 워커 ID
            
        Returns:
            할당된 작업 또는 None
        """
        if not self.pending_work_items:
            return None
        
        # 워커 상태 확인
        worker_info = self.active_workers.get(worker_id)
        if not worker_info or worker_info["status"] != "running":
            return None
        
        # 작업 할당
        work_item = self.pending_work_items.pop(0)
        work_item["assigned_worker"] = worker_id
        work_item["assigned_at"] = datetime.now()
        
        # 워커 상태 업데이트
        worker_info["current_task"] = work_item["task_id"]
        
        logger.debug(f"작업 {work_item['task_id']} 워커 {worker_id}에 할당됨")
        
        return work_item
    
    async def _execute_work_item(self, worker_id: str, device: DeviceInfo, work_item: Dict[str, Any]):
        """
        작업을 실행합니다.
        
        Args:
            worker_id: 워커 ID
            device: 대상 디바이스
            work_item: 실행할 작업
        """
        task_id = work_item["task_id"]
        task_type = work_item.get("task_type", "create_account")
        
        logger.info(f"워커 {worker_id}: 작업 {task_id} 실행 시작 ({task_type})")
        
        start_time = time.time()
        success = False
        
        try:
            if task_type == "create_account":
                success = await self._execute_account_creation(worker_id, device, work_item)
            elif task_type == "verify_account":
                success = await self._execute_account_verification(worker_id, device, work_item)
            elif task_type == "cleanup":
                success = await self._execute_cleanup(worker_id, device, work_item)
            else:
                logger.warning(f"알 수 없는 작업 타입: {task_type}")
                success = False
            
            execution_time = time.time() - start_time
            
            # 결과 처리
            if success:
                self.completed_work_items.append(work_item)
                self._update_worker_success(worker_id, execution_time)
                logger.info(f"워커 {worker_id}: 작업 {task_id} 성공 ({execution_time:.1f}초)")
            else:
                self.failed_work_items.append(work_item)
                self._update_worker_failure(worker_id)
                logger.warning(f"워커 {worker_id}: 작업 {task_id} 실패")
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.failed_work_items.append(work_item)
            self._update_worker_failure(worker_id)
            logger.error(f"워커 {worker_id}: 작업 {task_id} 실행 중 오류: {e}")
        
        finally:
            # 워커 상태 정리
            worker_info = self.active_workers.get(worker_id)
            if worker_info:
                worker_info["current_task"] = None
    
    async def _execute_account_creation(self, worker_id: str, device: DeviceInfo, work_item: Dict[str, Any]) -> bool:
        """
        계정 생성 작업을 실행합니다.
        
        Args:
            worker_id: 워커 ID
            device: 대상 디바이스
            work_item: 작업 정보
            
        Returns:
            작업 성공 여부
        """
        # 실제 구현에서는 Google 계정 생성 로직 실행
        # 여기서는 시뮬레이션
        
        logger.info(f"워커 {worker_id}: Google 계정 생성 시작...")
        
        try:
            # 단계별 계정 생성 시뮬레이션
            steps = [
                ("브라우저 열기", 2),
                ("Google 가입 페이지 이동", 1),
                ("개인정보 입력", 3),
                ("전화번호 인증", 5),
                ("약관 동의", 1),
                ("계정 생성 완료", 2)
            ]
            
            for step_name, duration in steps:
                logger.debug(f"워커 {worker_id}: {step_name}")
                await asyncio.sleep(duration)
                
                # 중단 체크
                if self.shutdown_event.is_set():
                    return False
            
            # 계정 정보 저장
            account_data = {
                "email": f"user_{int(time.time())}@gmail.com",
                "password": "generated_password",
                "created_at": datetime.now().isoformat(),
                "device_id": device.device_id,
                "worker_id": worker_id
            }
            
            work_item["result"] = account_data
            
            logger.info(f"워커 {worker_id}: Google 계정 생성 완료 - {account_data['email']}")
            return True
            
        except Exception as e:
            logger.error(f"워커 {worker_id}: 계정 생성 실행 오류: {e}")
            return False
    
    async def _execute_account_verification(self, worker_id: str, device: DeviceInfo, work_item: Dict[str, Any]) -> bool:
        """계정 인증 작업을 실행합니다."""
        logger.info(f"워커 {worker_id}: 계정 인증 시작...")
        
        # 인증 시뮬레이션
        await asyncio.sleep(3)
        
        logger.info(f"워커 {worker_id}: 계정 인증 완료")
        return True
    
    async def _execute_cleanup(self, worker_id: str, device: DeviceInfo, work_item: Dict[str, Any]) -> bool:
        """정리 작업을 실행합니다."""
        logger.info(f"워커 {worker_id}: 정리 작업 시작...")
        
        # 정리 시뮬레이션
        await asyncio.sleep(1)
        
        logger.info(f"워커 {worker_id}: 정리 작업 완료")
        return True
    
    def _update_worker_activity(self, worker_id: str):
        """워커 활동 시간을 업데이트합니다."""
        worker_info = self.active_workers.get(worker_id)
        if worker_info:
            worker_info["last_activity"] = datetime.now()
    
    def _update_worker_success(self, worker_id: str, execution_time: float):
        """워커 성공 메트릭을 업데이트합니다."""
        worker_info = self.active_workers.get(worker_id)
        metrics = self.worker_metrics.get(worker_id)
        
        if worker_info and metrics:
            worker_info["completed_tasks"] += 1
            metrics["accounts_created"] += 1
            
            # 평균 실행 시간 업데이트
            total_tasks = worker_info["completed_tasks"]
            current_avg = metrics["average_time"]
            metrics["average_time"] = ((current_avg * (total_tasks - 1)) + execution_time) / total_tasks
            
            # 성공률 업데이트
            total_attempts = worker_info["completed_tasks"] + worker_info["failed_tasks"]
            metrics["success_rate"] = (worker_info["completed_tasks"] / total_attempts) * 100
    
    def _update_worker_failure(self, worker_id: str):
        """워커 실패 메트릭을 업데이트합니다."""
        worker_info = self.active_workers.get(worker_id)
        metrics = self.worker_metrics.get(worker_id)
        
        if worker_info and metrics:
            worker_info["failed_tasks"] += 1
            
            # 성공률 업데이트
            total_attempts = worker_info["completed_tasks"] + worker_info["failed_tasks"]
            metrics["success_rate"] = (worker_info["completed_tasks"] / total_attempts) * 100
    
    async def _cleanup_worker(self, worker_id: str):
        """워커를 정리합니다."""
        logger.info(f"워커 {worker_id} 정리 중...")
        
        try:
            # 워커 상태 업데이트
            worker_info = self.active_workers.get(worker_id)
            if worker_info:
                worker_info["status"] = "stopped"
                worker_info["stopped_at"] = datetime.now()
            
            # 프로세스 정리
            worker_process = self.worker_processes.pop(worker_id, None)
            if worker_process and not worker_process.done():
                worker_process.cancel()
            
            logger.debug(f"워커 {worker_id} 정리 완료")
            
        except Exception as e:
            logger.error(f"워커 {worker_id} 정리 중 오류: {e}")
    
    async def stop_workers(self):
        """모든 워커를 중지합니다."""
        logger.info("모든 워커 중지 시작...")
        
        self.is_running = False
        self.shutdown_event.set()
        
        # 모든 워커 프로세스 취소
        for worker_id, worker_process in self.worker_processes.items():
            if not worker_process.done():
                worker_process.cancel()
        
        # 워커 프로세스 완료 대기
        if self.worker_processes:
            await asyncio.gather(
                *self.worker_processes.values(),
                return_exceptions=True
            )
        
        logger.info(f"모든 워커 중지 완료: {len(self.active_workers)}개 워커")
    
    def add_work_item(self, task_type: str, task_data: Dict[str, Any]) -> str:
        """
        새 작업을 추가합니다.
        
        Args:
            task_type: 작업 타입
            task_data: 작업 데이터
            
        Returns:
            생성된 작업 ID
        """
        task_id = f"task_{int(time.time())}_{len(self.pending_work_items)}"
        
        work_item = {
            "task_id": task_id,
            "task_type": task_type,
            "task_data": task_data,
            "created_at": datetime.now(),
            "assigned_worker": None,
            "assigned_at": None,
            "result": None
        }
        
        self.pending_work_items.append(work_item)
        
        logger.debug(f"작업 추가됨: {task_id} ({task_type})")
        
        return task_id
    
    def get_worker_status(self) -> Dict[str, Any]:
        """워커 상태 요약을 반환합니다."""
        active_count = len([w for w in self.active_workers.values() if w["status"] == "running"])
        
        return {
            "total_workers": len(self.active_workers),
            "active_workers": active_count,
            "pending_tasks": len(self.pending_work_items),
            "completed_tasks": len(self.completed_work_items),
            "failed_tasks": len(self.failed_work_items),
            "workers": [
                {
                    "worker_id": worker_id,
                    "device_id": info["device_id"],
                    "status": info["status"],
                    "current_task": info["current_task"],
                    "completed_tasks": info["completed_tasks"],
                    "failed_tasks": info["failed_tasks"],
                    "uptime_seconds": (datetime.now() - info["started_at"]).total_seconds(),
                    "metrics": self.worker_metrics.get(worker_id, {})
                }
                for worker_id, info in self.active_workers.items()
            ]
        }
    
    async def monitor_workers(self):
        """워커 상태를 모니터링합니다."""
        logger.info("워커 모니터링 시작...")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # 비활성 워커 확인
                inactive_workers = []
                current_time = datetime.now()
                
                for worker_id, worker_info in self.active_workers.items():
                    last_activity = worker_info["last_activity"]
                    inactive_duration = (current_time - last_activity).total_seconds()
                    
                    # 5분 이상 비활성화된 워커
                    if inactive_duration > 300:
                        inactive_workers.append(worker_id)
                
                # 비활성 워커 재시작
                for worker_id in inactive_workers:
                    logger.warning(f"워커 {worker_id} 비활성 상태 감지, 재시작 시도...")
                    await self._restart_worker(worker_id)
                
                # 주기적 상태 로그
                status = self.get_worker_status()
                logger.info(f"워커 상태: {status['active_workers']}/{status['total_workers']} 활성, "
                          f"대기 작업: {status['pending_tasks']}, 완료: {status['completed_tasks']}")
                
                await asyncio.sleep(60)  # 1분마다 모니터링
                
            except Exception as e:
                logger.error(f"워커 모니터링 오류: {e}")
                await asyncio.sleep(60)
    
    async def _restart_worker(self, worker_id: str) -> bool:
        """워커를 재시작합니다."""
        try:
            # 기존 워커 정리
            await self._cleanup_worker(worker_id)
            
            # 디바이스 정보 가져오기
            worker_info = self.active_workers.get(worker_id)
            if not worker_info:
                return False
            
            device_id = worker_info["device_id"]
            device = await self.device_manager.get_device(device_id)
            
            if device:
                # 워커 재시작
                return await self._start_worker(worker_id, device)
            
            return False
            
        except Exception as e:
            logger.error(f"워커 {worker_id} 재시작 실패: {e}")
            return False

class GoogleAccountCreator:
    """Google Account Creator 메인 클래스"""
    
    def __init__(self, config: AppConfig):
        """
        Google Account Creator 초기화
        
        Args:
            config: 애플리케이션 설정
        """
        self.config = config
        self.status = SystemStatus()
        
        # 핵심 컴포넌트
        self.device_initializer = DeviceInitializer(config)
        self.device_manager: Optional[DeviceManager] = None
        self.queue_manager: Optional[WorkQueueManager] = None
        self.executor: Optional[ParallelExecutor] = None
        self.error_system: Optional[ErrorHandlingSystem] = None
        self.resource_manager: Optional[ResourceManager] = None
        self.worker_manager: Optional[WorkerManager] = None  # 새로 추가
        
        # 제어 플래그
        self.shutdown_event = asyncio.Event()
        self.running_tasks: Set[asyncio.Task] = set()
        
        logger.info("Google Account Creator가 초기화되었습니다.")
    
    async def initialize(self) -> bool:
        """
        시스템 전체를 초기화합니다.
        
        Returns:
            초기화 성공 여부
        """
        logger.info("시스템 초기화 시작...")
        
        try:
            # 1. 디바이스 발견 및 초기화
            logger.info("🔍 단계 1: 디바이스 검색 및 초기화")
            devices = await self.device_initializer.discover_devices()
            
            if not devices:
                logger.error("사용 가능한 디바이스가 없습니다.")
                return False
            
            # 디바이스 초기화
            init_results = await self.device_initializer.initialize_all_devices()
            successful_devices = [
                device_id for device_id, success in init_results.items() 
                if success
            ]
            
            if not successful_devices:
                logger.error("초기화된 디바이스가 없습니다.")
                return False
            
            logger.info(f"✅ {len(successful_devices)}개 디바이스 초기화 완료")
            
            # 2. 핵심 매니저 컴포넌트 생성
            logger.info("🏗️ 단계 2: 핵심 시스템 컴포넌트 초기화")
            
            # 디바이스 매니저
            from workers.device_manager import create_device_manager
            self.device_manager = create_device_manager()
            
            # 초기화된 디바이스들을 매니저에 등록
            for device in self.device_initializer.get_initialized_devices():
                await self.device_manager.add_device(device)
            
            # 작업 큐 매니저
            from workers.work_queue import create_work_queue_manager
            self.queue_manager = create_work_queue_manager(self.device_manager)
            
            # 병렬 실행기
            from workers.parallel_executor import create_parallel_executor
            self.executor = create_parallel_executor()
            
            # 에러 핸들링 시스템
            from workers.error_handler import create_error_handling_system
            self.error_system = create_error_handling_system(
                self.device_manager, self.queue_manager, self.executor
            )
            
            # 리소스 관리자
            from workers.resource_manager import create_resource_manager
            self.resource_manager = create_resource_manager(
                self.device_manager, self.queue_manager, self.executor
            )
            
            # 워커 관리자 (새로 추가)
            self.worker_manager = WorkerManager(self.config, self.device_manager)
            
            logger.info("✅ 핵심 시스템 컴포넌트 초기화 완료")
            
            # 3. 시스템 시작
            logger.info("🚀 단계 3: 시스템 서비스 시작")
            
            # 에러 핸들링 시스템 시작
            self.error_system.start_monitoring()
            
            # 리소스 관리자 시작
            await self.resource_manager.start()
            
            # 디바이스 관리자 시작
            await self.device_manager.start_monitoring()
            
            # 워커 시작 (새로 추가)
            if not await self.worker_manager.start_workers():
                logger.error("워커 시작 실패")
                return False
            
            # 상태 업데이트
            self.status.is_running = True
            self.status.total_devices = len(successful_devices)
            self.status.active_devices = len(successful_devices)
            
            logger.info("✅ 시스템 초기화 및 시작 완료")
            return True
            
        except Exception as e:
            logger.error(f"시스템 초기화 실패: {e}")
            await self._cleanup()
            return False
    
    async def run_main_loop(self) -> None:
        """
        메인 실행 루프를 시작합니다.
        """
        logger.info("메인 실행 루프 시작...")
        
        try:
            # 계정 생성 작업 생성
            await self._create_account_tasks()
            
            # 워커 모니터링 태스크 시작
            monitor_task = asyncio.create_task(self.worker_manager.monitor_workers())
            self.running_tasks.add(monitor_task)
            
            # 진행 상황 모니터링
            while self.status.is_running and not self.shutdown_event.is_set():
                await self._update_system_status()
                
                # 목표 달성 확인
                if self.status.accounts_created >= self.config.target_accounts:
                    logger.info(f"목표 달성! {self.status.accounts_created}개 계정 생성 완료")
                    break
                
                await asyncio.sleep(10)  # 10초마다 상태 확인
            
        except Exception as e:
            logger.error(f"메인 루프 실행 중 오류: {e}")
        finally:
            logger.info("메인 실행 루프 종료")
    
    async def _create_account_tasks(self):
        """계정 생성 작업을 생성합니다."""
        logger.info(f"{self.config.target_accounts}개 계정 생성 작업 생성 중...")
        
        for i in range(self.config.target_accounts):
            task_data = {
                "account_index": i + 1,
                "batch_id": i // self.config.batch_size + 1
            }
            
            task_id = self.worker_manager.add_work_item("create_account", task_data)
            
            # 배치 간 지연
            if (i + 1) % self.config.batch_size == 0:
                await asyncio.sleep(self.config.creation_delay)
        
        logger.info(f"{self.config.target_accounts}개 계정 생성 작업 생성 완료")
    
    async def _update_system_status(self):
        """시스템 상태를 업데이트합니다."""
        try:
            # 워커 상태 가져오기
            worker_status = self.worker_manager.get_worker_status()
            
            # 상태 업데이트
            self.status.completed_tasks = worker_status["completed_tasks"]
            self.status.failed_tasks = worker_status["failed_tasks"]
            self.status.pending_tasks = worker_status["pending_tasks"]
            
            # 계정 생성 수 (완료된 작업 중 create_account 타입)
            completed_accounts = len([
                item for item in self.worker_manager.completed_work_items
                if item.get("task_type") == "create_account"
            ])
            
            self.status.accounts_created = completed_accounts
            
            # 성공률 계산
            total_attempts = self.status.completed_tasks + self.status.failed_tasks
            if total_attempts > 0:
                self.status.success_rate = (self.status.completed_tasks / total_attempts) * 100
            
            # 진행 상황 로그
            progress = (self.status.accounts_created / self.config.target_accounts) * 100
            logger.info(f"진행 상황: {self.status.accounts_created}/{self.config.target_accounts} "
                      f"({progress:.1f}%), 성공률: {self.status.success_rate:.1f}%")
            
        except Exception as e:
            logger.error(f"시스템 상태 업데이트 오류: {e}")
    
    async def _cleanup(self) -> None:
        """시스템 리소스를 정리합니다."""
        logger.info("시스템 리소스 정리 중...")
        
        try:
            # 워커 중지
            if self.worker_manager:
                await self.worker_manager.stop_workers()
            
            # 모든 실행 중인 태스크 정리
            for task in self.running_tasks:
                if not task.done():
                    task.cancel()
            
            # 시스템 컴포넌트 정리
            if self.resource_manager:
                await self.resource_manager.stop()
            
            if self.device_manager:
                await self.device_manager.stop_monitoring()
            
            if self.error_system:
                self.error_system.stop_monitoring()
            
            self.status.is_running = False
            logger.info("시스템 리소스 정리 완료")
            
        except Exception as e:
            logger.error(f"시스템 정리 중 오류: {e}")

async def main():
    """메인 엔트리포인트"""
    print("🚀 Google Account Creator 시작")
    print("=" * 50)
    
    creator = None
    exit_code = 0
    
    try:
        # 명령행 인수 파싱
        args = parse_arguments()
        
        # 설정 로드
        config = load_config(args.config)
        
        # 명령행 인수로 설정 오버라이드
        if hasattr(args, 'target_accounts'):
            config.target_accounts = args.target_accounts
        if hasattr(args, 'batch_size'):
            config.batch_size = args.batch_size
        if hasattr(args, 'creation_delay'):
            config.creation_delay = args.creation_delay
        if hasattr(args, 'max_devices'):
            config.max_devices = args.max_devices
        if hasattr(args, 'device_timeout'):
            config.device_timeout = args.device_timeout
        if hasattr(args, 'max_api_calls'):
            config.max_api_calls_per_hour = args.max_api_calls
        if hasattr(args, 'max_vpn_connections'):
            config.max_vpn_connections = args.max_vpn_connections
        
        config.log_level = args.log_level
        config.log_file = args.log_file
        
        # 로깅 설정
        setup_logging(config)
        
        logger.info(f"설정 완료: {config.target_accounts}개 계정 생성 목표")
        logger.info(f"최대 디바이스: {config.max_devices}개")
        
        # Google Account Creator 인스턴스 생성
        creator = GoogleAccountCreator(config)
        
        # 전역 예외 처리기 설정
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                logger.info("사용자에 의한 중단 감지")
                return
            
            logger.critical(f"처리되지 않은 예외: {exc_type.__name__}: {exc_value}",
                          exc_info=(exc_type, exc_value, exc_traceback))
            
            # 에러 시스템에 보고
            if creator and creator.error_system:
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(creator.error_system.handle_error(
                        error_message=f"{exc_type.__name__}: {exc_value}",
                        error_type="CRITICAL_SYSTEM_ERROR",
                        category=ErrorCategory.SYSTEM_ERROR,
                        severity=ErrorSeverity.FATAL
                    ))
                except RuntimeError:
                    # 이벤트 루프가 없는 경우 동기적으로 로그만 남김
                    logger.critical("이벤트 루프가 없어 에러 시스템에 보고할 수 없습니다.")
        
        sys.excepthook = handle_exception
        
        # 시그널 핸들러 설정 (우아한 종료)
        shutdown_initiated = False
        
        def signal_handler(signum, frame):
            nonlocal shutdown_initiated
            if shutdown_initiated:
                logger.warning("강제 종료 신호를 다시 받았습니다. 즉시 종료합니다.")
                sys.exit(1)
            
            shutdown_initiated = True
            signal_name = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM"
            }.get(signum, f"Signal {signum}")
            
            logger.info(f"{signal_name} 수신됨. 우아한 종료 프로세스 시작...")
            
            if creator:
                creator.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 시스템 초기화
        logger.info("🏗️ 시스템 초기화 중...")
        if not await creator.initialize():
            logger.error("❌ 시스템 초기화 실패. 종료합니다.")
            exit_code = 1
            return exit_code
        
        logger.info("✅ 시스템 초기화 완료!")
        
        # 디바이스만 검색하는 모드
        if args.discover_only:
            device_status = creator.device_initializer.get_device_status()
            print("\n📱 발견된 디바이스:")
            print(json.dumps(device_status, indent=2, ensure_ascii=False))
            return 0
        
        # 건식 실행 모드
        if getattr(args, 'dry_run', False):
            logger.info("🔍 건식 실행 모드: 실제 계정 생성 없이 시뮬레이션만 실행")
            
            # 간단한 시뮬레이션
            for i in range(min(3, creator.config.target_accounts)):
                logger.info(f"시뮬레이션: 계정 {i+1} 생성 중...")
                await asyncio.sleep(1)
            
            logger.info("✅ 시뮬레이션 완료")
            return 0
        
        # 메인 실행 루프 시작
        logger.info("🚀 메인 계정 생성 프로세스 시작...")
        await creator.run_main_loop()
        
        logger.info("✅ Google Account Creator 정상 종료")
        
    except KeyboardInterrupt:
        logger.info("⏸️ 사용자에 의한 중단")
        exit_code = 130  # Standard exit code for SIGINT
        
    except Exception as e:
        logger.critical(f"💥 예상치 못한 치명적 오류: {e}", exc_info=True)
        
        # 에러 시스템에 보고 (가능한 경우)
        if creator and creator.error_system:
            try:
                await creator.error_system.handle_error(
                    error_message=str(e),
                    error_type="FATAL_MAIN_ERROR",
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.FATAL
                )
            except:
                pass  # 에러 시스템도 실패한 경우 무시
        
        exit_code = 1
        
    finally:
        # 정리 작업
        if creator:
            logger.info("🧹 시스템 정리 작업 시작...")
            try:
                await creator._cleanup()
                logger.info("✅ 시스템 정리 완료")
            except Exception as e:
                logger.error(f"❌ 정리 작업 중 오류: {e}")
                exit_code = max(exit_code, 1)  # 이미 에러가 있으면 유지
        
        print(f"\n{'='*50}")
        if exit_code == 0:
            print("✅ Google Account Creator 성공적으로 완료")
        else:
            print(f"❌ Google Account Creator 종료 (코드: {exit_code})")
        
        return exit_code

async def simulate_account_creation(creator: GoogleAccountCreator) -> None:
    """
    계정 생성 시뮬레이션을 실행합니다.
    
    Args:
        creator: Google Account Creator 인스턴스
    """
    logger.info("계정 생성 시뮬레이션 시작...")
    
    try:
        # 시뮬레이션용 작업 생성
        for i in range(min(5, creator.config.target_accounts)):  # 최대 5개만 시뮬레이션
            task_data = {
                "account_index": i + 1,
                "simulation": True
            }
            
            task_id = creator.worker_manager.add_work_item("create_account", task_data)
            logger.info(f"시뮬레이션 작업 생성: {task_id}")
        
        # 시뮬레이션 진행 상황 모니터링
        simulation_duration = 30  # 30초간 시뮬레이션
        start_time = time.time()
        
        while time.time() - start_time < simulation_duration:
            status = creator.worker_manager.get_worker_status()
            completed = status["completed_tasks"]
            pending = status["pending_tasks"]
            
            logger.info(f"시뮬레이션 진행: 완료 {completed}, 대기 {pending}")
            
            if pending == 0:  # 모든 작업 완료
                break
                
            await asyncio.sleep(2)
        
        logger.info("✅ 계정 생성 시뮬레이션 완료")
        
    except Exception as e:
        logger.error(f"시뮬레이션 중 오류: {e}")

async def generate_completion_report(creator: GoogleAccountCreator) -> None:
    """
    완료 보고서를 생성합니다.
    
    Args:
        creator: Google Account Creator 인스턴스
    """
    logger.info("📊 완료 보고서 생성 중...")
    
    try:
        # 최종 상태 수집
        final_status = creator.status.get_status_dict()
        worker_status = creator.worker_manager.get_worker_status()
        
        # 에러 요약
        if creator.error_system:
            error_summary = creator.error_system.get_error_summary(hours=24)
        else:
            error_summary = {"total_errors": 0}
        
        # 보고서 생성
        report = {
            "completion_time": datetime.now().isoformat(),
            "execution_summary": {
                "target_accounts": creator.config.target_accounts,
                "accounts_created": final_status["performance"]["accounts_created"],
                "success_rate": final_status["performance"]["success_rate"],
                "total_devices": final_status["devices"]["total"],
                "active_devices": final_status["devices"]["active"],
                "uptime_hours": final_status["uptime_seconds"] / 3600
            },
            "worker_performance": {
                "total_workers": worker_status["total_workers"],
                "completed_tasks": worker_status["completed_tasks"],
                "failed_tasks": worker_status["failed_tasks"],
                "worker_details": worker_status["workers"]
            },
            "error_analysis": {
                "total_errors": error_summary["total_errors"],
                "critical_errors": final_status["errors"]["critical"],
                "last_error": final_status["errors"]["last_error"]
            },
            "resource_utilization": None  # 리소스 관리자에서 가져올 수 있음
        }
        
        # 리소스 사용량 추가
        if creator.resource_manager:
            resource_status = creator.resource_manager.get_resource_status()
            report["resource_utilization"] = resource_status["system_metrics"]
        
        # 보고서 저장
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"completion_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 요약 로그
        logger.info("📈 실행 요약:")
        logger.info(f"   목표: {report['execution_summary']['target_accounts']}개")
        logger.info(f"   생성: {report['execution_summary']['accounts_created']}개")
        logger.info(f"   성공률: {report['execution_summary']['success_rate']:.1f}%")
        logger.info(f"   실행 시간: {report['execution_summary']['uptime_hours']:.1f}시간")
        logger.info(f"   에러: {report['error_analysis']['total_errors']}개")
        logger.info(f"📄 상세 보고서: {report_file}")
        
    except Exception as e:
        logger.error(f"보고서 생성 중 오류: {e}")

class GlobalErrorHandler:
    """전역 에러 핸들러 클래스"""
    
    def __init__(self, creator: Optional[GoogleAccountCreator] = None):
        """
        전역 에러 핸들러 초기화
        
        Args:
            creator: Google Account Creator 인스턴스
        """
        self.creator = creator
        self.error_count = 0
        self.critical_error_count = 0
        self.last_error_time = None
        
        # 에러 통계
        self.error_categories = defaultdict(int)
        self.error_patterns = []
        
        logger.info("전역 에러 핸들러가 초기화되었습니다.")
    
    async def handle_async_exception(self, exception: Exception, context: Dict[str, Any] = None) -> None:
        """
        비동기 예외를 처리합니다.
        
        Args:
            exception: 발생한 예외
            context: 예외 컨텍스트
        """
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # 에러 카테고리 분류
        category = self._classify_error(exception)
        severity = self._assess_severity(exception, context)
        
        self.error_categories[category.value] += 1
        
        if severity.value >= ErrorSeverity.CRITICAL.value:
            self.critical_error_count += 1
        
        # 로깅
        log_level = {
            ErrorSeverity.LOW: logger.debug,
            ErrorSeverity.MEDIUM: logger.info,
            ErrorSeverity.HIGH: logger.warning,
            ErrorSeverity.CRITICAL: logger.error,
            ErrorSeverity.FATAL: logger.critical
        }.get(severity, logger.error)
        
        log_level(f"비동기 예외 처리: {error_type}: {error_message}")
        
        # 에러 시스템에 보고
        if self.creator and self.creator.error_system:
            try:
                await self.creator.error_system.handle_error(
                    error_message=error_message,
                    error_type=error_type,
                    category=category,
                    severity=severity
                )
            except Exception as e:
                logger.error(f"에러 시스템 보고 실패: {e}")
        
        # 중대한 에러의 경우 시스템 종료 고려
        if severity == ErrorSeverity.FATAL:
            logger.critical("치명적 에러 발생. 시스템 종료를 고려합니다.")
            if self.creator:
                self.creator.shutdown_event.set()
    
    def _classify_error(self, exception: Exception) -> ErrorCategory:
        """예외를 에러 카테고리로 분류합니다."""
        exception_type = type(exception).__name__
        error_message = str(exception).lower()
        
        # 네트워크 관련 에러
        if any(keyword in error_message for keyword in ['connection', 'network', 'timeout', 'dns']):
            return ErrorCategory.NETWORK_ERROR
        
        # 시스템 리소스 관련 에러
        if any(keyword in error_message for keyword in ['memory', 'disk', 'resource', 'permission']):
            return ErrorCategory.RESOURCE_ERROR
        
        # 외부 API 관련 에러
        if any(keyword in error_message for keyword in ['api', 'rate limit', 'quota', 'unauthorized']):
            return ErrorCategory.EXTERNAL_API_ERROR
        
        # 검증 관련 에러
        if 'validation' in error_message or exception_type in ['ValueError', 'TypeError']:
            return ErrorCategory.VALIDATION_ERROR
        
        # 디바이스 관련 에러
        if any(keyword in error_message for keyword in ['device', 'adb', 'emulator']):
            return ErrorCategory.DEVICE_ERROR
        
        # 기본값: 시스템 에러
        return ErrorCategory.SYSTEM_ERROR
    
    def _assess_severity(self, exception: Exception, context: Dict[str, Any] = None) -> ErrorSeverity:
        """예외의 심각도를 평가합니다."""
        exception_type = type(exception).__name__
        error_message = str(exception).lower()
        
        # 치명적 에러
        if exception_type in ['SystemExit', 'KeyboardInterrupt']:
            return ErrorSeverity.FATAL
        
        if any(keyword in error_message for keyword in ['fatal', 'critical', 'corrupt']):
            return ErrorSeverity.FATAL
        
        # 심각한 에러
        if exception_type in ['MemoryError', 'OSError']:
            return ErrorSeverity.CRITICAL
        
        if any(keyword in error_message for keyword in ['failed to start', 'cannot allocate', 'disk full']):
            return ErrorSeverity.CRITICAL
        
        # 높은 우선순위 에러
        if exception_type in ['ConnectionError', 'TimeoutError']:
            return ErrorSeverity.HIGH
        
        if any(keyword in error_message for keyword in ['device disconnected', 'worker failed']):
            return ErrorSeverity.HIGH
        
        # 중간 우선순위 에러
        if exception_type in ['ValueError', 'TypeError', 'AttributeError']:
            return ErrorSeverity.MEDIUM
        
        # 기본값: 낮은 우선순위
        return ErrorSeverity.LOW
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """에러 통계를 반환합니다."""
        return {
            "total_errors": self.error_count,
            "critical_errors": self.critical_error_count,
            "error_categories": dict(self.error_categories),
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "error_rate": self.error_count / max(1, time.time() - time.time()) if self.last_error_time else 0
        }

# 전역 에러 핸들러 인스턴스
global_error_handler = None

def setup_global_error_handling(creator: GoogleAccountCreator) -> None:
    """전역 에러 핸들링을 설정합니다."""
    global global_error_handler
    
    global_error_handler = GlobalErrorHandler(creator)
    
    # asyncio 이벤트 루프 예외 핸들러 설정
    def asyncio_exception_handler(loop, context):
        exception = context.get('exception')
        if exception:
            asyncio.create_task(global_error_handler.handle_async_exception(exception, context))
        else:
            logger.error(f"asyncio 컨텍스트 에러: {context}")
    
    # 현재 이벤트 루프에 예외 핸들러 설정
    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(asyncio_exception_handler)
        logger.info("asyncio 전역 예외 핸들러가 설정되었습니다.")
    except RuntimeError:
        logger.warning("실행 중인 이벤트 루프가 없습니다. 예외 핸들러 설정을 건너뜁니다.")

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 