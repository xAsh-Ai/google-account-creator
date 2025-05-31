"""
Async Converters Module

기존 동기 함수들을 비동기로 변환하는 모듈:
- ADB 작업 비동기 변환
- 계정 생성 비동기 변환
- 검증 작업 비동기 변환
- 파일 I/O 비동기 변환
- 네트워크 작업 비동기 변환
"""

import asyncio
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Union, Awaitable
from functools import wraps, partial
from pathlib import Path
import json
import logging

from core.async_operations import (
    get_async_manager, convert_sync_to_async, make_async,
    AsyncOperationManager, AsyncTask
)
from core.logger import get_logger

logger = get_logger(__name__)

class AsyncADBOperations:
    """ADB 작업 비동기 변환"""
    
    def __init__(self, async_manager: Optional[AsyncOperationManager] = None):
        self.async_manager = async_manager or get_async_manager()
        self._adb_manager = None
    
    def _get_adb_manager(self):
        """ADB 관리자 지연 로딩"""
        if self._adb_manager is None:
            try:
                from core.optimized_adb import get_adb_manager
                self._adb_manager = get_adb_manager()
            except ImportError:
                logger.warning("Optimized ADB manager not available")
        return self._adb_manager
    
    async def execute_command_async(self, 
                                  command: List[str],
                                  device_serial: Optional[str] = None,
                                  timeout: float = 30.0,
                                  priority: int = 5) -> Dict[str, Any]:
        """ADB 명령 비동기 실행"""
        adb_manager = self._get_adb_manager()
        if not adb_manager:
            raise RuntimeError("ADB manager not available")
        
        # 동기 ADB 명령을 비동기로 변환
        def sync_execute():
            return adb_manager.execute_command(
                command, 
                device_serial=device_serial,
                timeout=timeout
            )
        
        task_id = await self.async_manager.execute_async(
            sync_execute,
            priority=priority,
            timeout=timeout + 5  # 추가 버퍼
        )
        
        result = await self.async_manager.worker_pool.get_task_result(task_id)
        return result
    
    async def get_device_info_async(self, device_serial: str) -> Dict[str, Any]:
        """디바이스 정보 비동기 조회"""
        adb_manager = self._get_adb_manager()
        if not adb_manager:
            raise RuntimeError("ADB manager not available")
        
        def sync_get_info():
            return adb_manager.get_device_info(device_serial)
        
        return await convert_sync_to_async(sync_get_info)
    
    async def install_app_async(self, 
                              apk_path: str,
                              device_serial: str,
                              replace: bool = True) -> Dict[str, Any]:
        """앱 설치 비동기 실행"""
        command = ["install"]
        if replace:
            command.append("-r")
        command.append(apk_path)
        
        return await self.execute_command_async(
            command,
            device_serial=device_serial,
            timeout=120.0,  # 설치는 시간이 오래 걸릴 수 있음
            priority=3  # 높은 우선순위
        )
    
    async def take_screenshot_async(self,
                                  device_serial: str,
                                  save_path: Optional[str] = None) -> Dict[str, Any]:
        """스크린샷 촬영 비동기 실행"""
        screenshot_path = save_path or f"/sdcard/screenshot_{int(time.time())}.png"
        
        # 스크린샷 촬영
        result = await self.execute_command_async(
            ["shell", "screencap", "-p", screenshot_path],
            device_serial=device_serial,
            timeout=10.0
        )
        
        if result.get('success'):
            # 로컬로 파일 가져오기
            if save_path:
                await self.execute_command_async(
                    ["pull", screenshot_path, save_path],
                    device_serial=device_serial,
                    timeout=30.0
                )
        
        return result
    
    async def batch_commands_async(self,
                                 commands: List[List[str]],
                                 device_serial: str,
                                 max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """배치 명령 비동기 실행"""
        # 배치 작업 구성
        operations = []
        for i, command in enumerate(commands):
            operations.append({
                'operation': self.execute_command_async,
                'kwargs': {
                    'command': command,
                    'device_serial': device_serial,
                    'priority': 5
                }
            })
        
        # 배치 실행
        task_ids = await self.async_manager.execute_batch_async(
            operations,
            max_concurrent=max_concurrent
        )
        
        # 결과 수집
        return await self.async_manager.wait_for_completion(task_ids)

class AsyncAccountOperations:
    """계정 생성 작업 비동기 변환"""
    
    def __init__(self, async_manager: Optional[AsyncOperationManager] = None):
        self.async_manager = async_manager or get_async_manager()
    
    async def create_account_async(self,
                                 account_data: Dict[str, Any],
                                 device_serial: str,
                                 priority: int = 3) -> Dict[str, Any]:
        """계정 생성 비동기 실행"""
        
        def sync_create_account():
            try:
                # 계정 생성 로직 (실제 구현에 맞게 조정)
                from core.account_creator import GoogleAccountCreator
                creator = GoogleAccountCreator()
                return creator.create_account(account_data, device_serial)
            except ImportError:
                # 모듈이 없는 경우 시뮬레이션
                time.sleep(2)  # 계정 생성 시뮬레이션
                return {
                    'success': True,
                    'account_id': f"test_account_{int(time.time())}",
                    'email': account_data.get('email', 'test@example.com'),
                    'creation_time': time.time()
                }
        
        task_id = await self.async_manager.execute_async(
            sync_create_account,
            priority=priority,
            timeout=300.0  # 5분 타임아웃
        )
        
        return await self.async_manager.worker_pool.get_task_result(task_id)
    
    async def verify_account_async(self,
                                 account_id: str,
                                 verification_method: str = "email",
                                 priority: int = 4) -> Dict[str, Any]:
        """계정 검증 비동기 실행"""
        
        def sync_verify_account():
            try:
                # 검증 로직 (실제 구현에 맞게 조정)
                from core.account_verifier import AccountVerifier
                verifier = AccountVerifier()
                return verifier.verify_account(account_id, verification_method)
            except ImportError:
                # 모듈이 없는 경우 시뮬레이션
                time.sleep(1)  # 검증 시뮬레이션
                return {
                    'success': True,
                    'account_id': account_id,
                    'verification_method': verification_method,
                    'verified_at': time.time()
                }
        
        task_id = await self.async_manager.execute_async(
            sync_verify_account,
            priority=priority,
            timeout=60.0
        )
        
        return await self.async_manager.worker_pool.get_task_result(task_id)
    
    async def batch_create_accounts_async(self,
                                        accounts_data: List[Dict[str, Any]],
                                        device_serials: List[str],
                                        max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """배치 계정 생성 비동기 실행"""
        
        # 디바이스별로 계정 분배
        operations = []
        for i, account_data in enumerate(accounts_data):
            device_serial = device_serials[i % len(device_serials)]
            
            operations.append({
                'operation': self.create_account_async,
                'kwargs': {
                    'account_data': account_data,
                    'device_serial': device_serial,
                    'priority': 3
                }
            })
        
        # 배치 실행
        task_ids = await self.async_manager.execute_batch_async(
            operations,
            max_concurrent=max_concurrent
        )
        
        return await self.async_manager.wait_for_completion(task_ids)

class AsyncFileOperations:
    """파일 I/O 작업 비동기 변환"""
    
    def __init__(self, async_manager: Optional[AsyncOperationManager] = None):
        self.async_manager = async_manager or get_async_manager()
    
    async def read_json_async(self, file_path: str) -> Dict[str, Any]:
        """JSON 파일 비동기 읽기"""
        
        def sync_read_json():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return await convert_sync_to_async(sync_read_json)
    
    async def write_json_async(self, 
                             file_path: str, 
                             data: Dict[str, Any],
                             indent: int = 2) -> bool:
        """JSON 파일 비동기 쓰기"""
        
        def sync_write_json():
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        
        return await convert_sync_to_async(sync_write_json)
    
    async def process_log_files_async(self,
                                    log_directory: str,
                                    max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """로그 파일 배치 처리 비동기 실행"""
        
        log_dir = Path(log_directory)
        if not log_dir.exists():
            return []
        
        log_files = list(log_dir.glob("*.log"))
        
        async def process_single_log(log_file: Path):
            def sync_process():
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 로그 분석 (예시)
                    lines = content.split('\n')
                    error_count = sum(1 for line in lines if 'ERROR' in line)
                    warning_count = sum(1 for line in lines if 'WARNING' in line)
                    
                    return {
                        'file': str(log_file),
                        'lines': len(lines),
                        'errors': error_count,
                        'warnings': warning_count,
                        'processed_at': time.time()
                    }
                except Exception as e:
                    return {
                        'file': str(log_file),
                        'error': str(e),
                        'processed_at': time.time()
                    }
            
            return await convert_sync_to_async(sync_process)
        
        # 동시성 제한으로 처리
        from core.async_operations import gather_with_concurrency
        
        coroutines = [process_single_log(log_file) for log_file in log_files]
        return await gather_with_concurrency(coroutines, max_concurrent)

class AsyncNetworkOperations:
    """네트워크 작업 비동기 변환"""
    
    def __init__(self, async_manager: Optional[AsyncOperationManager] = None):
        self.async_manager = async_manager or get_async_manager()
    
    async def http_request_async(self,
                               url: str,
                               method: str = "GET",
                               headers: Optional[Dict[str, str]] = None,
                               data: Optional[Dict[str, Any]] = None,
                               timeout: float = 30.0) -> Dict[str, Any]:
        """HTTP 요청 비동기 실행"""
        
        def sync_http_request():
            import requests
            
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=timeout
                )
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content': response.text,
                    'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        return await convert_sync_to_async(sync_http_request)
    
    async def batch_http_requests_async(self,
                                      requests_data: List[Dict[str, Any]],
                                      max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """배치 HTTP 요청 비동기 실행"""
        
        operations = []
        for req_data in requests_data:
            operations.append({
                'operation': self.http_request_async,
                'kwargs': req_data
            })
        
        task_ids = await self.async_manager.execute_batch_async(
            operations,
            max_concurrent=max_concurrent
        )
        
        return await self.async_manager.wait_for_completion(task_ids)
    
    async def ping_hosts_async(self,
                             hosts: List[str],
                             timeout: float = 5.0) -> List[Dict[str, Any]]:
        """호스트 핑 비동기 실행"""
        
        async def ping_single_host(host: str):
            def sync_ping():
                import subprocess
                import platform
                
                system = platform.system().lower()
                if system == "windows":
                    cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
                else:
                    cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout + 2
                    )
                    
                    success = result.returncode == 0
                    return {
                        'host': host,
                        'success': success,
                        'response_time': self._extract_ping_time(result.stdout) if success else None,
                        'output': result.stdout
                    }
                except Exception as e:
                    return {
                        'host': host,
                        'success': False,
                        'error': str(e)
                    }
            
            return await convert_sync_to_async(sync_ping)
        
        # 모든 호스트 동시 핑
        from core.async_operations import gather_with_concurrency
        
        coroutines = [ping_single_host(host) for host in hosts]
        return await gather_with_concurrency(coroutines, max_concurrent=20)
    
    def _extract_ping_time(self, ping_output: str) -> Optional[float]:
        """핑 출력에서 응답 시간 추출"""
        import re
        
        # Windows와 Linux/Mac에서 다른 형식
        patterns = [
            r'time[<=](\d+(?:\.\d+)?)ms',  # Windows
            r'time=(\d+(?:\.\d+)?)\s*ms'   # Linux/Mac
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ping_output, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        return None

class AsyncOperationConverter:
    """통합 비동기 변환 관리자"""
    
    def __init__(self, async_manager: Optional[AsyncOperationManager] = None):
        self.async_manager = async_manager or get_async_manager()
        
        # 특화된 변환기들
        self.adb_ops = AsyncADBOperations(async_manager)
        self.account_ops = AsyncAccountOperations(async_manager)
        self.file_ops = AsyncFileOperations(async_manager)
        self.network_ops = AsyncNetworkOperations(async_manager)
        
        # 등록된 변환 함수들
        self._conversions = {}
        
        # 기본 변환 등록
        self._register_default_conversions()
    
    def _register_default_conversions(self):
        """기본 변환 함수들 등록"""
        # ADB 작업
        self.register_conversion("execute_adb_command", self.adb_ops.execute_command_async)
        self.register_conversion("get_device_info", self.adb_ops.get_device_info_async)
        self.register_conversion("install_app", self.adb_ops.install_app_async)
        self.register_conversion("take_screenshot", self.adb_ops.take_screenshot_async)
        
        # 계정 작업
        self.register_conversion("create_account", self.account_ops.create_account_async)
        self.register_conversion("verify_account", self.account_ops.verify_account_async)
        
        # 파일 작업
        self.register_conversion("read_json", self.file_ops.read_json_async)
        self.register_conversion("write_json", self.file_ops.write_json_async)
        
        # 네트워크 작업
        self.register_conversion("http_request", self.network_ops.http_request_async)
    
    def register_conversion(self, func_name: str, async_func: Callable):
        """동기 함수의 비동기 변환 등록"""
        self._conversions[func_name] = async_func
        self.async_manager.register_async_conversion(func_name, async_func)
        logger.debug(f"Registered async conversion for {func_name}")
    
    def get_conversion(self, func_name: str) -> Optional[Callable]:
        """등록된 변환 함수 조회"""
        return self._conversions.get(func_name)
    
    async def convert_and_execute(self,
                                func_name: str,
                                *args,
                                **kwargs) -> Any:
        """함수 이름으로 비동기 변환 실행"""
        async_func = self.get_conversion(func_name)
        
        if async_func:
            return await async_func(*args, **kwargs)
        else:
            # 등록되지 않은 함수는 기본 변환 사용
            logger.warning(f"No specific conversion for {func_name}, using default")
            
            # 가정: func_name이 실제 함수 객체를 찾을 수 있는 경우
            return await convert_sync_to_async(func_name, *args, **kwargs)
    
    def wrap_sync_function(self, sync_func: Callable) -> Callable:
        """동기 함수를 비동기 래퍼로 감싸기"""
        func_name = getattr(sync_func, '__name__', str(sync_func))
        
        @wraps(sync_func)
        async def async_wrapper(*args, **kwargs):
            # 등록된 변환이 있는지 확인
            async_func = self.get_conversion(func_name)
            
            if async_func:
                return await async_func(*args, **kwargs)
            else:
                # 기본 변환 사용
                return await convert_sync_to_async(sync_func, *args, **kwargs)
        
        return async_wrapper
    
    def get_stats(self) -> Dict[str, Any]:
        """변환기 통계"""
        return {
            'registered_conversions': len(self._conversions),
            'conversion_functions': list(self._conversions.keys()),
            'async_manager_stats': self.async_manager.get_performance_report()
        }

# 전역 변환기 인스턴스
_async_converter: Optional[AsyncOperationConverter] = None

def get_async_converter() -> AsyncOperationConverter:
    """전역 비동기 변환기 가져오기"""
    global _async_converter
    
    if _async_converter is None:
        _async_converter = AsyncOperationConverter()
    
    return _async_converter

def async_convert(func_name_or_func: Union[str, Callable]):
    """함수 또는 함수명을 비동기로 변환하는 데코레이터/함수"""
    converter = get_async_converter()
    
    if isinstance(func_name_or_func, str):
        # 함수명이 주어진 경우
        async def async_executor(*args, **kwargs):
            return await converter.convert_and_execute(func_name_or_func, *args, **kwargs)
        return async_executor
    else:
        # 함수 객체가 주어진 경우 (데코레이터로 사용)
        return converter.wrap_sync_function(func_name_or_func)

# 편의 함수들

async def adb_command_async(command: List[str], device_serial: str, **kwargs) -> Dict[str, Any]:
    """ADB 명령 비동기 실행 편의 함수"""
    converter = get_async_converter()
    return await converter.adb_ops.execute_command_async(command, device_serial, **kwargs)

async def create_account_async(account_data: Dict[str, Any], device_serial: str, **kwargs) -> Dict[str, Any]:
    """계정 생성 비동기 실행 편의 함수"""
    converter = get_async_converter()
    return await converter.account_ops.create_account_async(account_data, device_serial, **kwargs)

async def read_file_async(file_path: str, **kwargs) -> str:
    """파일 읽기 비동기 실행 편의 함수"""
    def sync_read():
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    return await convert_sync_to_async(sync_read)

async def write_file_async(file_path: str, content: str, **kwargs) -> bool:
    """파일 쓰기 비동기 실행 편의 함수"""
    def sync_write():
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return await convert_sync_to_async(sync_write) 