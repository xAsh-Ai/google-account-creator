"""
병렬 실행 프레임워크 모듈

이 모듈은 여러 디바이스에서 작업을 병렬로 실행하는 프레임워크를 제공합니다.
- 멀티프로세싱 기반 병렬 실행
- 작업 동기화 및 결과 집계
- 리소스 제한 및 성능 최적화
- 실시간 진행 상황 모니터링
- 동적 워커 스케일링
"""

import asyncio
import multiprocessing as mp
import threading
import time
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import signal
import queue
import concurrent.futures
from pathlib import Path

from .device_manager import DeviceManager, create_device_manager
from .work_queue import WorkQueueManager, TaskType, TaskPriority, WorkTask, create_work_queue_manager
from ..core.account_creator import GoogleAccountCreator, PersonalInfo
from ..core.account_logger import AccountLogger, create_account_logger

# 로깅 설정
logger = logging.getLogger(__name__)

class ExecutorStatus(Enum):
    """실행기 상태 열거형"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class WorkerStatus(Enum):
    """워커 상태 열거형"""
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    STOPPING = "stopping"

@dataclass
class WorkerInfo:
    """워커 정보 데이터 클래스"""
    worker_id: str
    process_id: Optional[int] = None
    device_id: Optional[str] = None
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: Optional[str] = None
    
    # 성능 메트릭
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    last_activity: datetime = field(default_factory=datetime.now)
    
    # 에러 정보
    last_error: Optional[str] = None
    error_count: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    """실행 결과 데이터 클래스"""
    task_id: str
    worker_id: str
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExecutionMetrics:
    """실행 메트릭 데이터 클래스"""
    total_workers: int = 0
    active_workers: int = 0
    idle_workers: int = 0
    error_workers: int = 0
    
    # 작업 메트릭
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    
    # 성능 메트릭
    tasks_per_minute: float = 0.0
    average_execution_time: float = 0.0
    success_rate: float = 0.0
    
    # 시스템 메트릭
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
    last_updated: datetime = field(default_factory=datetime.now)

class WorkerProcess:
    """개별 워커 프로세스 클래스"""
    
    def __init__(self, worker_id: str, config: Dict[str, Any]):
        """
        워커 프로세스 초기화
        
        Args:
            worker_id: 워커 ID
            config: 설정 정보
        """
        self.worker_id = worker_id
        self.config = config
        self.device_manager = None
        self.account_creator = None
        self.account_logger = None
        
        # 통신용 큐
        self.task_queue = mp.Queue(maxsize=10)
        self.result_queue = mp.Queue()
        self.control_queue = mp.Queue()
        
        # 프로세스 제어
        self.process = None
        self.is_running = False
        
        logger.info(f"워커 프로세스 {worker_id} 초기화됨")
    
    def start(self) -> bool:
        """워커 프로세스를 시작합니다."""
        try:
            self.process = mp.Process(target=self._worker_main, daemon=True)
            self.process.start()
            self.is_running = True
            
            logger.info(f"워커 프로세스 {self.worker_id} 시작됨 (PID: {self.process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"워커 프로세스 {self.worker_id} 시작 실패: {e}")
            return False
    
    def stop(self, timeout: int = 30) -> bool:
        """워커 프로세스를 중지합니다."""
        try:
            if not self.is_running:
                return True
            
            # 중지 신호 전송
            self.control_queue.put({"command": "stop"})
            
            # 프로세스 종료 대기
            if self.process:
                self.process.join(timeout=timeout)
                
                if self.process.is_alive():
                    # 강제 종료
                    self.process.terminate()
                    self.process.join(timeout=5)
                    
                    if self.process.is_alive():
                        self.process.kill()
                        self.process.join()
            
            self.is_running = False
            logger.info(f"워커 프로세스 {self.worker_id} 중지됨")
            return True
            
        except Exception as e:
            logger.error(f"워커 프로세스 {self.worker_id} 중지 실패: {e}")
            return False
    
    def assign_task(self, task_data: Dict[str, Any]) -> bool:
        """워커에 작업을 할당합니다."""
        try:
            if not self.is_running:
                return False
            
            self.task_queue.put(task_data, timeout=5)
            logger.debug(f"작업 할당됨: 워커 {self.worker_id}")
            return True
            
        except queue.Full:
            logger.warning(f"워커 {self.worker_id} 작업 큐가 가득 참")
            return False
        except Exception as e:
            logger.error(f"워커 {self.worker_id} 작업 할당 실패: {e}")
            return False
    
    def get_result(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """워커에서 결과를 가져옵니다."""
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"워커 {self.worker_id} 결과 가져오기 실패: {e}")
            return None
    
    def _worker_main(self) -> None:
        """워커 메인 프로세스"""
        try:
            # 프로세스 이름 설정
            mp.current_process().name = f"Worker-{self.worker_id}"
            
            # 시그널 핸들러 설정
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            # 로깅 설정
            logging.basicConfig(
                level=logging.INFO,
                format=f'%(asctime)s - Worker-{self.worker_id} - %(levelname)s - %(message)s'
            )
            
            # 컴포넌트 초기화
            self._initialize_components()
            
            logger.info(f"워커 {self.worker_id} 메인 루프 시작")
            
            # 메인 루프
            self._worker_loop()
            
        except Exception as e:
            logger.error(f"워커 {self.worker_id} 메인 프로세스 오류: {e}")
            self.result_queue.put({
                "type": "error",
                "worker_id": self.worker_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def _initialize_components(self) -> None:
        """워커 컴포넌트를 초기화합니다."""
        try:
            # 디바이스 매니저 초기화
            self.device_manager = create_device_manager()
            
            # 계정 생성기 초기화
            self.account_creator = GoogleAccountCreator()
            
            # 계정 로거 초기화
            self.account_logger = create_account_logger()
            
            logger.info(f"워커 {self.worker_id} 컴포넌트 초기화 완료")
            
        except Exception as e:
            logger.error(f"워커 {self.worker_id} 컴포넌트 초기화 실패: {e}")
            raise
    
    def _worker_loop(self) -> None:
        """워커 메인 루프"""
        while True:
            try:
                # 제어 명령 확인
                try:
                    control_msg = self.control_queue.get(timeout=0.1)
                    if control_msg.get("command") == "stop":
                        logger.info(f"워커 {self.worker_id} 중지 명령 수신")
                        break
                except queue.Empty:
                    pass
                
                # 작업 확인
                try:
                    task_data = self.task_queue.get(timeout=1.0)
                    result = self._execute_task(task_data)
                    self.result_queue.put(result)
                    
                except queue.Empty:
                    # 작업이 없으면 계속 대기
                    continue
                
            except Exception as e:
                logger.error(f"워커 {self.worker_id} 루프 오류: {e}")
                self.result_queue.put({
                    "type": "error",
                    "worker_id": self.worker_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
    
    def _execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """작업을 실행합니다."""
        start_time = datetime.now()
        task_id = task_data.get("task_id", "unknown")
        
        try:
            logger.info(f"워커 {self.worker_id} 작업 {task_id} 실행 시작")
            
            # 상태 업데이트
            self.result_queue.put({
                "type": "status",
                "worker_id": self.worker_id,
                "status": "working",
                "task_id": task_id,
                "timestamp": start_time.isoformat()
            })
            
            # 작업 타입에 따른 실행
            task_type = task_data.get("task_type", "account_creation")
            
            if task_type == "account_creation":
                result_data = self._execute_account_creation(task_data)
            elif task_type == "device_setup":
                result_data = self._execute_device_setup(task_data)
            elif task_type == "cleanup":
                result_data = self._execute_cleanup(task_data)
            else:
                raise ValueError(f"지원하지 않는 작업 타입: {task_type}")
            
            # 성공 결과 반환
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "type": "result",
                "worker_id": self.worker_id,
                "task_id": task_id,
                "success": True,
                "result_data": result_data,
                "execution_time": execution_time,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            # 실패 결과 반환
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"워커 {self.worker_id} 작업 {task_id} 실행 실패: {e}")
            
            return {
                "type": "result",
                "worker_id": self.worker_id,
                "task_id": task_id,
                "success": False,
                "error_message": str(e),
                "execution_time": execution_time,
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now().isoformat()
            }
    
    def _execute_account_creation(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """계정 생성 작업을 실행합니다."""
        payload = task_data.get("payload", {})
        
        # 개인 정보 생성
        personal_info = PersonalInfo(
            first_name=payload.get("first_name", "테스트"),
            last_name=payload.get("last_name", "사용자"),
            username=payload.get("username", f"user_{int(time.time())}"),
            password=payload.get("password", "TempPass123!"),
            birth_year=payload.get("birth_year", 1990),
            birth_month=payload.get("birth_month", 5),
            birth_day=payload.get("birth_day", 15),
            gender=payload.get("gender", "male")
        )
        
        # 시뮬레이션 (실제로는 account_creator.create_account() 호출)
        time.sleep(payload.get("simulation_time", 30))  # 30초 시뮬레이션
        
        # 결과 데이터
        return {
            "email": f"{personal_info.username}@gmail.com",
            "password": personal_info.password,
            "personal_info": {
                "first_name": personal_info.first_name,
                "last_name": personal_info.last_name,
                "birth_year": personal_info.birth_year,
                "birth_month": personal_info.birth_month,
                "birth_day": personal_info.birth_day,
                "gender": personal_info.gender
            },
            "creation_time": datetime.now().isoformat()
        }
    
    def _execute_device_setup(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """디바이스 설정 작업을 실행합니다."""
        # 시뮬레이션
        time.sleep(10)
        return {"device_setup": "completed"}
    
    def _execute_cleanup(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """정리 작업을 실행합니다."""
        # 시뮬레이션
        time.sleep(5)
        return {"cleanup": "completed"}
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"워커 {self.worker_id} 시그널 {signum} 수신")

class ParallelExecutor:
    """병렬 실행 프레임워크 메인 클래스"""
    
    def __init__(self, 
                 max_workers: int = 4,
                 max_concurrent_tasks: int = 10,
                 auto_scale: bool = True):
        """
        병렬 실행기 초기화
        
        Args:
            max_workers: 최대 워커 수
            max_concurrent_tasks: 최대 동시 작업 수
            auto_scale: 자동 스케일링 활성화
        """
        self.max_workers = max_workers
        self.max_concurrent_tasks = max_concurrent_tasks
        self.auto_scale = auto_scale
        
        # 컴포넌트
        self.device_manager = create_device_manager()
        self.queue_manager = create_work_queue_manager(
            self.device_manager, 
            max_concurrent_tasks=max_concurrent_tasks
        )
        
        # 워커 관리
        self.workers: Dict[str, WorkerProcess] = {}
        self.worker_info: Dict[str, WorkerInfo] = {}
        
        # 상태 관리
        self.status = ExecutorStatus.STOPPED
        self.metrics = ExecutionMetrics()
        
        # 결과 처리
        self.results: List[ExecutionResult] = []
        self.result_callbacks: List[Callable] = []
        
        # 제어 스레드
        self.monitor_thread = None
        self.result_processor_thread = None
        self.is_running = False
        
        # 동기화
        self._lock = threading.RLock()
        
        logger.info(f"병렬 실행기 초기화됨 (최대 워커: {max_workers})")
    
    def add_result_callback(self, callback: Callable[[ExecutionResult], None]) -> None:
        """결과 처리 콜백을 추가합니다."""
        self.result_callbacks.append(callback)
    
    async def start(self) -> bool:
        """병렬 실행기를 시작합니다."""
        try:
            if self.status != ExecutorStatus.STOPPED:
                logger.warning("병렬 실행기가 이미 실행 중입니다.")
                return False
            
            self.status = ExecutorStatus.STARTING
            logger.info("병렬 실행기 시작 중...")
            
            # 디바이스 발견
            devices = await self.device_manager.discover_devices()
            if not devices:
                logger.warning("사용 가능한 디바이스가 없습니다.")
            
            # 큐 관리자 시작
            await self.queue_manager.start()
            
            # 초기 워커 생성
            initial_workers = min(self.max_workers, len(devices) if devices else 2)
            for i in range(initial_workers):
                self._create_worker(f"worker_{i}")
            
            # 모니터링 스레드 시작
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            # 결과 처리 스레드 시작
            self.result_processor_thread = threading.Thread(target=self._result_processor_loop, daemon=True)
            self.result_processor_thread.start()
            
            self.status = ExecutorStatus.RUNNING
            logger.info(f"병렬 실행기 시작됨 ({len(self.workers)}개 워커)")
            return True
            
        except Exception as e:
            logger.error(f"병렬 실행기 시작 실패: {e}")
            self.status = ExecutorStatus.ERROR
            return False
    
    async def stop(self, timeout: int = 60) -> bool:
        """병렬 실행기를 중지합니다."""
        try:
            if self.status == ExecutorStatus.STOPPED:
                return True
            
            self.status = ExecutorStatus.STOPPING
            logger.info("병렬 실행기 중지 중...")
            
            # 실행 플래그 해제
            self.is_running = False
            
            # 워커들 중지
            with self._lock:
                for worker in self.workers.values():
                    worker.stop(timeout=30)
                
                self.workers.clear()
                self.worker_info.clear()
            
            # 큐 관리자 중지
            await self.queue_manager.stop()
            
            # 스레드 정리
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=10)
            
            if self.result_processor_thread and self.result_processor_thread.is_alive():
                self.result_processor_thread.join(timeout=10)
            
            self.status = ExecutorStatus.STOPPED
            logger.info("병렬 실행기 중지됨")
            return True
            
        except Exception as e:
            logger.error(f"병렬 실행기 중지 실패: {e}")
            self.status = ExecutorStatus.ERROR
            return False
    
    def submit_batch_task(self, 
                         task_type: TaskType,
                         batch_data: List[Dict[str, Any]],
                         priority: TaskPriority = TaskPriority.NORMAL) -> List[str]:
        """배치 작업을 제출합니다."""
        task_ids = []
        
        for i, data in enumerate(batch_data):
            try:
                task_id = self.queue_manager.submit_task(
                    task_type=task_type,
                    payload=data,
                    priority=priority,
                    metadata={"batch_index": i, "batch_size": len(batch_data)}
                )
                task_ids.append(task_id)
                
            except Exception as e:
                logger.error(f"배치 작업 {i} 제출 실패: {e}")
        
        logger.info(f"배치 작업 제출됨: {len(task_ids)}개 작업")
        return task_ids
    
    def _create_worker(self, worker_id: str) -> bool:
        """새로운 워커를 생성합니다."""
        try:
            with self._lock:
                if worker_id in self.workers:
                    return False
                
                # 워커 프로세스 생성
                worker_config = {
                    "device_manager_config": "data/device_config.json",
                    "logging_level": "INFO"
                }
                
                worker = WorkerProcess(worker_id, worker_config)
                
                if worker.start():
                    self.workers[worker_id] = worker
                    self.worker_info[worker_id] = WorkerInfo(
                        worker_id=worker_id,
                        process_id=worker.process.pid if worker.process else None
                    )
                    
                    logger.info(f"워커 {worker_id} 생성됨")
                    return True
                else:
                    logger.error(f"워커 {worker_id} 시작 실패")
                    return False
                    
        except Exception as e:
            logger.error(f"워커 {worker_id} 생성 실패: {e}")
            return False
    
    def _remove_worker(self, worker_id: str) -> bool:
        """워커를 제거합니다."""
        try:
            with self._lock:
                if worker_id not in self.workers:
                    return False
                
                worker = self.workers[worker_id]
                worker.stop()
                
                del self.workers[worker_id]
                del self.worker_info[worker_id]
                
                logger.info(f"워커 {worker_id} 제거됨")
                return True
                
        except Exception as e:
            logger.error(f"워커 {worker_id} 제거 실패: {e}")
            return False
    
    def _monitor_loop(self) -> None:
        """모니터링 루프"""
        while self.is_running:
            try:
                self._update_metrics()
                
                # 자동 스케일링
                if self.auto_scale:
                    self._auto_scale_workers()
                
                # 워커 상태 확인
                self._check_worker_health()
                
                time.sleep(30)  # 30초마다 모니터링
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                time.sleep(30)
    
    def _result_processor_loop(self) -> None:
        """결과 처리 루프"""
        while self.is_running:
            try:
                # 모든 워커에서 결과 수집
                for worker_id, worker in list(self.workers.items()):
                    result_data = worker.get_result(timeout=0.1)
                    if result_data:
                        self._process_result(result_data)
                
                time.sleep(0.1)  # 짧은 대기
                
            except Exception as e:
                logger.error(f"결과 처리 루프 오류: {e}")
                time.sleep(1)
    
    def _process_result(self, result_data: Dict[str, Any]) -> None:
        """결과를 처리합니다."""
        try:
            result_type = result_data.get("type")
            worker_id = result_data.get("worker_id")
            
            if result_type == "result":
                # 작업 결과 처리
                execution_result = ExecutionResult(
                    task_id=result_data.get("task_id"),
                    worker_id=worker_id,
                    success=result_data.get("success", False),
                    result_data=result_data.get("result_data"),
                    error_message=result_data.get("error_message"),
                    execution_time=result_data.get("execution_time", 0.0),
                    started_at=datetime.fromisoformat(result_data.get("started_at")),
                    completed_at=datetime.fromisoformat(result_data.get("completed_at", datetime.now().isoformat()))
                )
                
                self.results.append(execution_result)
                
                # 워커 정보 업데이트
                if worker_id in self.worker_info:
                    worker_info = self.worker_info[worker_id]
                    worker_info.status = WorkerStatus.IDLE
                    worker_info.current_task = None
                    worker_info.last_activity = datetime.now()
                    
                    if execution_result.success:
                        worker_info.tasks_completed += 1
                    else:
                        worker_info.tasks_failed += 1
                        worker_info.last_error = execution_result.error_message
                        worker_info.error_count += 1
                    
                    worker_info.total_execution_time += execution_result.execution_time
                
                # 콜백 호출
                for callback in self.result_callbacks:
                    try:
                        callback(execution_result)
                    except Exception as e:
                        logger.error(f"결과 콜백 오류: {e}")
                
                logger.debug(f"작업 결과 처리됨: {execution_result.task_id} (성공: {execution_result.success})")
                
            elif result_type == "status":
                # 상태 업데이트 처리
                if worker_id in self.worker_info:
                    worker_info = self.worker_info[worker_id]
                    status_str = result_data.get("status", "idle")
                    
                    if status_str == "working":
                        worker_info.status = WorkerStatus.WORKING
                        worker_info.current_task = result_data.get("task_id")
                    elif status_str == "idle":
                        worker_info.status = WorkerStatus.IDLE
                        worker_info.current_task = None
                    
                    worker_info.last_activity = datetime.now()
                
            elif result_type == "error":
                # 에러 처리
                if worker_id in self.worker_info:
                    worker_info = self.worker_info[worker_id]
                    worker_info.status = WorkerStatus.ERROR
                    worker_info.last_error = result_data.get("error")
                    worker_info.error_count += 1
                    worker_info.last_activity = datetime.now()
                
                logger.error(f"워커 {worker_id} 에러: {result_data.get('error')}")
                
        except Exception as e:
            logger.error(f"결과 처리 오류: {e}")
    
    def _update_metrics(self) -> None:
        """메트릭을 업데이트합니다."""
        try:
            with self._lock:
                # 워커 상태 카운트
                self.metrics.total_workers = len(self.workers)
                self.metrics.active_workers = sum(
                    1 for info in self.worker_info.values() 
                    if info.status == WorkerStatus.WORKING
                )
                self.metrics.idle_workers = sum(
                    1 for info in self.worker_info.values() 
                    if info.status == WorkerStatus.IDLE
                )
                self.metrics.error_workers = sum(
                    1 for info in self.worker_info.values() 
                    if info.status == WorkerStatus.ERROR
                )
                
                # 작업 메트릭
                queue_metrics = self.queue_manager.get_metrics()
                self.metrics.total_tasks = queue_metrics.total_tasks
                self.metrics.completed_tasks = queue_metrics.completed_tasks
                self.metrics.failed_tasks = queue_metrics.failed_tasks
                self.metrics.pending_tasks = queue_metrics.pending_tasks
                
                # 성능 메트릭
                self.metrics.tasks_per_minute = queue_metrics.throughput_per_minute
                self.metrics.average_execution_time = queue_metrics.average_execution_time
                
                if self.metrics.total_tasks > 0:
                    self.metrics.success_rate = (
                        self.metrics.completed_tasks / self.metrics.total_tasks * 100
                    )
                
                # 시스템 메트릭 (간단한 버전)
                try:
                    import psutil
                    self.metrics.cpu_usage = psutil.cpu_percent(interval=0.1)
                    self.metrics.memory_usage = psutil.virtual_memory().percent
                except ImportError:
                    pass
                
                self.metrics.last_updated = datetime.now()
                
        except Exception as e:
            logger.error(f"메트릭 업데이트 오류: {e}")
    
    def _auto_scale_workers(self) -> None:
        """워커 자동 스케일링"""
        try:
            # 큐 상태 확인
            queue_status = self.queue_manager.get_queue_status()
            pending_tasks = queue_status.get("main_queue_size", 0) + queue_status.get("retry_queue_size", 0)
            
            current_workers = len(self.workers)
            target_workers = current_workers
            
            # 스케일 업 조건
            if (pending_tasks > current_workers * 2 and 
                current_workers < self.max_workers and
                self.metrics.idle_workers < 2):
                target_workers = min(current_workers + 1, self.max_workers)
                
            # 스케일 다운 조건
            elif (pending_tasks == 0 and 
                  self.metrics.idle_workers > 2 and
                  current_workers > 1):
                target_workers = max(current_workers - 1, 1)
            
            # 워커 수 조정
            if target_workers > current_workers:
                new_worker_id = f"worker_{int(time.time())}"
                self._create_worker(new_worker_id)
                logger.info(f"워커 스케일 업: {current_workers} -> {target_workers}")
                
            elif target_workers < current_workers:
                # 가장 오래된 idle 워커 제거
                idle_workers = [
                    worker_id for worker_id, info in self.worker_info.items()
                    if info.status == WorkerStatus.IDLE
                ]
                
                if idle_workers:
                    worker_to_remove = min(idle_workers, 
                                         key=lambda w: self.worker_info[w].last_activity)
                    self._remove_worker(worker_to_remove)
                    logger.info(f"워커 스케일 다운: {current_workers} -> {target_workers}")
                    
        except Exception as e:
            logger.error(f"자동 스케일링 오류: {e}")
    
    def _check_worker_health(self) -> None:
        """워커 건강 상태를 확인합니다."""
        try:
            current_time = datetime.now()
            unhealthy_workers = []
            
            for worker_id, worker_info in self.worker_info.items():
                # 30분 이상 비활성 워커 체크
                if (current_time - worker_info.last_activity).total_seconds() > 1800:
                    unhealthy_workers.append(worker_id)
                
                # 에러 상태가 10분 이상 지속
                elif (worker_info.status == WorkerStatus.ERROR and
                      (current_time - worker_info.last_activity).total_seconds() > 600):
                    unhealthy_workers.append(worker_id)
                
                # 프로세스 상태 확인
                elif worker_id in self.workers:
                    worker = self.workers[worker_id]
                    if worker.process and not worker.process.is_alive():
                        unhealthy_workers.append(worker_id)
            
            # 비정상 워커 재시작
            for worker_id in unhealthy_workers:
                logger.warning(f"비정상 워커 감지: {worker_id}, 재시작 중...")
                self._remove_worker(worker_id)
                
                # 새 워커 생성
                if len(self.workers) < self.max_workers:
                    new_worker_id = f"worker_{int(time.time())}"
                    self._create_worker(new_worker_id)
                    
        except Exception as e:
            logger.error(f"워커 건강 체크 오류: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """실행기 상태를 반환합니다."""
        return {
            "status": self.status.value,
            "workers": {
                worker_id: {
                    "process_id": info.process_id,
                    "device_id": info.device_id,
                    "status": info.status.value,
                    "current_task": info.current_task,
                    "tasks_completed": info.tasks_completed,
                    "tasks_failed": info.tasks_failed,
                    "error_count": info.error_count,
                    "last_error": info.last_error,
                    "last_activity": info.last_activity.isoformat()
                }
                for worker_id, info in self.worker_info.items()
            },
            "metrics": {
                "total_workers": self.metrics.total_workers,
                "active_workers": self.metrics.active_workers,
                "idle_workers": self.metrics.idle_workers,
                "error_workers": self.metrics.error_workers,
                "total_tasks": self.metrics.total_tasks,
                "completed_tasks": self.metrics.completed_tasks,
                "failed_tasks": self.metrics.failed_tasks,
                "pending_tasks": self.metrics.pending_tasks,
                "tasks_per_minute": self.metrics.tasks_per_minute,
                "average_execution_time": self.metrics.average_execution_time,
                "success_rate": self.metrics.success_rate,
                "cpu_usage": self.metrics.cpu_usage,
                "memory_usage": self.metrics.memory_usage,
                "last_updated": self.metrics.last_updated.isoformat()
            },
            "queue_status": self.queue_manager.get_queue_status()
        }
    
    def get_results(self, limit: Optional[int] = None) -> List[ExecutionResult]:
        """실행 결과를 반환합니다."""
        if limit:
            return self.results[-limit:]
        return self.results.copy()


# 편의 함수들
def create_parallel_executor(max_workers: int = 4, 
                           max_concurrent_tasks: int = 10,
                           auto_scale: bool = True) -> ParallelExecutor:
    """
    병렬 실행기를 생성합니다.
    
    Args:
        max_workers: 최대 워커 수
        max_concurrent_tasks: 최대 동시 작업 수
        auto_scale: 자동 스케일링 활성화
    
    Returns:
        ParallelExecutor 인스턴스
    """
    return ParallelExecutor(max_workers, max_concurrent_tasks, auto_scale)


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_parallel_executor():
        """병렬 실행기 테스트"""
        try:
            logger.info("병렬 실행기 테스트 시작...")
            
            # 병렬 실행기 생성
            executor = create_parallel_executor(max_workers=3, max_concurrent_tasks=6)
            
            # 결과 콜백 등록
            def result_callback(result: ExecutionResult):
                print(f"✅ 작업 완료: {result.task_id} (성공: {result.success}, 시간: {result.execution_time:.2f}초)")
            
            executor.add_result_callback(result_callback)
            
            # 실행기 시작
            await executor.start()
            
            # 배치 작업 제출
            batch_data = [
                {"first_name": f"사용자{i}", "simulation_time": 10}
                for i in range(8)
            ]
            
            task_ids = executor.submit_batch_task(
                task_type=TaskType.ACCOUNT_CREATION,
                batch_data=batch_data,
                priority=TaskPriority.NORMAL
            )
            
            print(f"📋 배치 작업 제출됨: {len(task_ids)}개")
            
            # 진행 상황 모니터링
            for _ in range(12):  # 2분간 모니터링
                await asyncio.sleep(10)
                
                status = executor.get_status()
                metrics = status["metrics"]
                
                print(f"📊 상태: 워커 {metrics['active_workers']}/{metrics['total_workers']}, "
                      f"완료 {metrics['completed_tasks']}, 실패 {metrics['failed_tasks']}, "
                      f"대기 {metrics['pending_tasks']}")
            
            # 결과 확인
            results = executor.get_results()
            successful_results = [r for r in results if r.success]
            
            print(f"🎯 최종 결과: {len(successful_results)}/{len(results)} 성공")
            
            # 실행기 중지
            await executor.stop()
            print("✅ 병렬 실행기 테스트 완료")
            
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_parallel_executor()) 