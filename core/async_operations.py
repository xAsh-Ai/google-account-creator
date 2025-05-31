"""
Asynchronous Operations Module

고급 비동기 작업 관리 시스템:
- 차단 작업을 비동기로 변환
- 콜백 메커니즘 구현  
- async/await 패턴 최적화
- 이벤트 루프 관리
- 동시성 제어
- 백그라운드 작업 스케줄링
"""

import asyncio
import threading
import time
import queue
import weakref
from typing import Dict, List, Any, Optional, Callable, Union, Coroutine, TypeVar, Generic
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from functools import wraps, partial
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
import logging
import json
import traceback
from pathlib import Path
import signal
import uuid

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')
R = TypeVar('R')

@dataclass
class AsyncTask:
    """비동기 작업 정의"""
    task_id: str
    name: str
    coroutine: Coroutine
    priority: int = 5  # 1(높음) - 10(낮음)
    timeout: Optional[float] = None
    callback: Optional[Callable[[Any], None]] = None
    error_callback: Optional[Callable[[Exception], None]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None
    
    @property
    def duration(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

@dataclass
class AsyncWorker:
    """비동기 워커 상태"""
    worker_id: str
    thread_id: Optional[int] = None
    is_busy: bool = False
    current_task: Optional[str] = None
    tasks_completed: int = 0
    total_execution_time: float = 0.0
    last_activity: float = field(default_factory=time.time)
    
    @property
    def average_execution_time(self) -> float:
        return self.total_execution_time / max(1, self.tasks_completed)

class CallbackManager:
    """콜백 메커니즘 관리"""
    
    def __init__(self):
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.one_time_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self.callback_stats: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
    
    def register_callback(self, event: str, callback: Callable, one_time: bool = False):
        """콜백 등록"""
        with self._lock:
            if one_time:
                self.one_time_callbacks[event].append(callback)
            else:
                self.callbacks[event].append(callback)
            
            logger.debug(f"Registered {'one-time' if one_time else 'persistent'} callback for event: {event}")
    
    def unregister_callback(self, event: str, callback: Callable):
        """콜백 해제"""
        with self._lock:
            if callback in self.callbacks[event]:
                self.callbacks[event].remove(callback)
            if callback in self.one_time_callbacks[event]:
                self.one_time_callbacks[event].remove(callback)
    
    async def trigger_callbacks(self, event: str, *args, **kwargs):
        """콜백 트리거"""
        with self._lock:
            # 지속적 콜백 실행
            persistent_callbacks = self.callbacks.get(event, []).copy()
            
            # 일회성 콜백 실행 및 제거
            one_time_callbacks = self.one_time_callbacks.get(event, []).copy()
            if event in self.one_time_callbacks:
                self.one_time_callbacks[event].clear()
            
            self.callback_stats[event] += len(persistent_callbacks) + len(one_time_callbacks)
        
        # 콜백 실행 (락 외부에서)
        all_callbacks = persistent_callbacks + one_time_callbacks
        
        for callback in all_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for event '{event}': {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """콜백 통계"""
        with self._lock:
            return {
                'total_events': len(self.callback_stats),
                'total_triggers': sum(self.callback_stats.values()),
                'events': dict(self.callback_stats),
                'registered_callbacks': {
                    event: len(callbacks) 
                    for event, callbacks in self.callbacks.items()
                },
                'one_time_callbacks': {
                    event: len(callbacks)
                    for event, callbacks in self.one_time_callbacks.items()
                }
            }

class AsyncEventLoop:
    """전용 이벤트 루프 관리"""
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.exception_handler = None
        
        # 성능 메트릭
        self.tasks_processed = 0
        self.total_processing_time = 0.0
        self.peak_concurrent_tasks = 0
        self.current_tasks = 0
        
        self._stats_lock = threading.Lock()
    
    def start(self):
        """이벤트 루프 시작"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
        # 루프가 시작될 때까지 대기
        while self.loop is None:
            time.sleep(0.01)
        
        logger.info(f"Async event loop '{self.name}' started")
    
    def stop(self):
        """이벤트 루프 정지"""
        if not self.running:
            return
        
        self.running = False
        
        if self.loop and not self.loop.is_closed():
            # 루프에 정지 신호 보내기
            asyncio.run_coroutine_threadsafe(self._stop_loop(), self.loop)
        
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info(f"Async event loop '{self.name}' stopped")
    
    def _run_event_loop(self):
        """이벤트 루프 실행"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 예외 핸들러 설정
        if self.exception_handler:
            self.loop.set_exception_handler(self.exception_handler)
        else:
            self.loop.set_exception_handler(self._default_exception_handler)
        
        try:
            self.loop.run_until_complete(self._event_loop_worker())
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            self.loop.close()
    
    async def _event_loop_worker(self):
        """이벤트 루프 워커"""
        while self.running:
            try:
                # 주기적으로 통계 업데이트
                await asyncio.sleep(0.1)
                
                with self._stats_lock:
                    self.current_tasks = len([
                        task for task in asyncio.all_tasks(self.loop)
                        if not task.done()
                    ])
                    
                    if self.current_tasks > self.peak_concurrent_tasks:
                        self.peak_concurrent_tasks = self.current_tasks
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event loop worker error: {e}")
    
    async def _stop_loop(self):
        """루프 정지"""
        # 모든 실행 중인 태스크 취소
        tasks = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
        
        for task in tasks:
            task.cancel()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self.loop.stop()
    
    def _default_exception_handler(self, context):
        """기본 예외 핸들러"""
        exception = context.get('exception')
        message = context.get('message', 'Unhandled exception in async event loop')
        
        logger.error(f"Async event loop exception: {message}")
        if exception:
            logger.error(f"Exception details: {exception}")
    
    def submit_coroutine(self, coro: Coroutine) -> Future:
        """코루틴 제출"""
        if not self.running or not self.loop:
            raise RuntimeError("Event loop is not running")
        
        return asyncio.run_coroutine_threadsafe(self._track_coroutine(coro), self.loop)
    
    async def _track_coroutine(self, coro: Coroutine):
        """코루틴 실행 추적"""
        start_time = time.time()
        
        try:
            result = await coro
            
            with self._stats_lock:
                self.tasks_processed += 1
                self.total_processing_time += time.time() - start_time
            
            return result
            
        except Exception as e:
            with self._stats_lock:
                self.tasks_processed += 1
                self.total_processing_time += time.time() - start_time
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """이벤트 루프 통계"""
        with self._stats_lock:
            return {
                'name': self.name,
                'running': self.running,
                'tasks_processed': self.tasks_processed,
                'total_processing_time': self.total_processing_time,
                'average_processing_time': (
                    self.total_processing_time / max(1, self.tasks_processed)
                ),
                'peak_concurrent_tasks': self.peak_concurrent_tasks,
                'current_tasks': self.current_tasks
            }

class AsyncWorkerPool:
    """비동기 워커 풀"""
    
    def __init__(self, 
                 pool_size: int = 10,
                 max_queue_size: int = 1000,
                 worker_timeout: float = 300.0):
        self.pool_size = pool_size
        self.max_queue_size = max_queue_size
        self.worker_timeout = worker_timeout
        
        self.workers: Dict[str, AsyncWorker] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.result_futures: Dict[str, Future] = {}
        
        self.event_loops: List[AsyncEventLoop] = []
        self.current_loop_index = 0
        
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # 통계
        self.stats = {
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'queue_full_events': 0
        }
        self._stats_lock = threading.Lock()
    
    async def start(self):
        """워커 풀 시작"""
        if self.running:
            return
        
        self.running = True
        
        # 이벤트 루프 생성 및 시작
        for i in range(max(1, self.pool_size // 4)):  # 루프당 4개 워커
            loop = AsyncEventLoop(f"worker_loop_{i}")
            loop.start()
            self.event_loops.append(loop)
        
        # 워커 생성
        for i in range(self.pool_size):
            worker_id = f"worker_{i}"
            worker = AsyncWorker(worker_id=worker_id)
            self.workers[worker_id] = worker
        
        # 작업 디스패처 시작
        asyncio.create_task(self._task_dispatcher())
        
        logger.info(f"Async worker pool started with {self.pool_size} workers")
    
    async def stop(self):
        """워커 풀 정지"""
        if not self.running:
            return
        
        self.running = False
        self._shutdown_event.set()
        
        # 큐에 남은 작업 처리 대기
        await self.task_queue.join()
        
        # 이벤트 루프 정지
        for loop in self.event_loops:
            loop.stop()
        
        logger.info("Async worker pool stopped")
    
    async def submit_task(self, task: AsyncTask) -> str:
        """작업 제출"""
        if not self.running:
            raise RuntimeError("Worker pool is not running")
        
        try:
            await self.task_queue.put(task)
            
            with self._stats_lock:
                self.stats['tasks_submitted'] += 1
            
            logger.debug(f"Task {task.task_id} submitted to worker pool")
            return task.task_id
            
        except asyncio.QueueFull:
            with self._stats_lock:
                self.stats['queue_full_events'] += 1
            raise RuntimeError("Worker pool queue is full")
    
    async def _task_dispatcher(self):
        """작업 디스패처"""
        while self.running or not self.task_queue.empty():
            try:
                # 타임아웃으로 정기적 체크
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # 사용 가능한 워커 찾기
                available_worker = self._find_available_worker()
                
                if available_worker:
                    # 작업 할당
                    await self._assign_task_to_worker(available_worker, task)
                else:
                    # 사용 가능한 워커가 없으면 다시 큐에 넣기
                    await self.task_queue.put(task)
                    await asyncio.sleep(0.1)  # 잠시 대기
                
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                # 타임아웃은 정상 - 정기적 체크를 위함
                continue
            except Exception as e:
                logger.error(f"Task dispatcher error: {e}")
    
    def _find_available_worker(self) -> Optional[AsyncWorker]:
        """사용 가능한 워커 찾기"""
        for worker in self.workers.values():
            if not worker.is_busy:
                return worker
        return None
    
    async def _assign_task_to_worker(self, worker: AsyncWorker, task: AsyncTask):
        """워커에 작업 할당"""
        worker.is_busy = True
        worker.current_task = task.task_id
        worker.last_activity = time.time()
        
        # 라운드 로빈으로 이벤트 루프 선택
        event_loop = self.event_loops[self.current_loop_index]
        self.current_loop_index = (self.current_loop_index + 1) % len(self.event_loops)
        
        # 작업 실행
        future = event_loop.submit_coroutine(
            self._execute_task(worker, task)
        )
        
        # 결과 저장
        self.result_futures[task.task_id] = future
    
    async def _execute_task(self, worker: AsyncWorker, task: AsyncTask):
        """작업 실행"""
        start_time = time.time()
        task.started_at = start_time
        
        try:
            # 타임아웃 설정
            if task.timeout:
                result = await asyncio.wait_for(task.coroutine, timeout=task.timeout)
            else:
                result = await task.coroutine
            
            # 성공 콜백 실행
            if task.callback:
                try:
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback(result)
                    else:
                        task.callback(result)
                except Exception as e:
                    logger.error(f"Task callback error: {e}")
            
            # 통계 업데이트
            execution_time = time.time() - start_time
            
            with self._stats_lock:
                self.stats['tasks_completed'] += 1
                self.stats['total_execution_time'] += execution_time
            
            worker.tasks_completed += 1
            worker.total_execution_time += execution_time
            
            return result
            
        except Exception as e:
            # 에러 콜백 실행
            if task.error_callback:
                try:
                    if asyncio.iscoroutinefunction(task.error_callback):
                        await task.error_callback(e)
                    else:
                        task.error_callback(e)
                except Exception as callback_error:
                    logger.error(f"Task error callback error: {callback_error}")
            
            with self._stats_lock:
                self.stats['tasks_failed'] += 1
            
            logger.error(f"Task {task.task_id} failed: {e}")
            raise
            
        finally:
            task.completed_at = time.time()
            worker.is_busy = False
            worker.current_task = None
            worker.last_activity = time.time()
    
    async def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """작업 결과 가져오기"""
        if task_id not in self.result_futures:
            raise KeyError(f"Task {task_id} not found")
        
        future = self.result_futures[task_id]
        
        try:
            if timeout:
                result = await asyncio.wait_for(
                    asyncio.wrap_future(future), 
                    timeout=timeout
                )
            else:
                result = await asyncio.wrap_future(future)
            
            # 결과 정리
            del self.result_futures[task_id]
            return result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task_id} timed out")
    
    def get_stats(self) -> Dict[str, Any]:
        """워커 풀 통계"""
        with self._stats_lock:
            stats = self.stats.copy()
        
        # 워커 통계
        worker_stats = {}
        for worker_id, worker in self.workers.items():
            worker_stats[worker_id] = {
                'is_busy': worker.is_busy,
                'current_task': worker.current_task,
                'tasks_completed': worker.tasks_completed,
                'average_execution_time': worker.average_execution_time,
                'last_activity': worker.last_activity
            }
        
        # 이벤트 루프 통계
        loop_stats = {}
        for loop in self.event_loops:
            loop_stats[loop.name] = loop.get_stats()
        
        return {
            'pool_stats': stats,
            'worker_stats': worker_stats,
            'loop_stats': loop_stats,
            'queue_size': self.task_queue.qsize(),
            'running': self.running
        }

class AsyncScheduler:
    """비동기 스케줄러"""
    
    def __init__(self, worker_pool: AsyncWorkerPool):
        self.worker_pool = worker_pool
        self.scheduled_tasks: Dict[str, asyncio.TimerHandle] = {}
        self.recurring_tasks: Dict[str, Dict[str, Any]] = {}
        self.callback_manager = CallbackManager()
        
        self._lock = threading.RLock()
    
    async def schedule_task(self, 
                          task: AsyncTask, 
                          delay: float = 0.0) -> str:
        """작업 스케줄링"""
        if delay <= 0:
            return await self.worker_pool.submit_task(task)
        
        def delayed_submit():
            asyncio.create_task(self.worker_pool.submit_task(task))
        
        loop = asyncio.get_event_loop()
        handle = loop.call_later(delay, delayed_submit)
        
        with self._lock:
            self.scheduled_tasks[task.task_id] = handle
        
        logger.debug(f"Task {task.task_id} scheduled for {delay}s later")
        return task.task_id
    
    async def schedule_recurring_task(self,
                                    task_factory: Callable[[], AsyncTask],
                                    interval: float,
                                    max_executions: Optional[int] = None) -> str:
        """반복 작업 스케줄링"""
        recurring_id = str(uuid.uuid4())
        
        recurring_info = {
            'task_factory': task_factory,
            'interval': interval,
            'max_executions': max_executions,
            'execution_count': 0,
            'next_execution': time.time() + interval,
            'active': True
        }
        
        with self._lock:
            self.recurring_tasks[recurring_id] = recurring_info
        
        # 첫 번째 실행 스케줄링
        await self._schedule_next_recurring(recurring_id)
        
        logger.info(f"Recurring task {recurring_id} scheduled (interval: {interval}s)")
        return recurring_id
    
    async def _schedule_next_recurring(self, recurring_id: str):
        """다음 반복 실행 스케줄링"""
        with self._lock:
            if recurring_id not in self.recurring_tasks:
                return
            
            info = self.recurring_tasks[recurring_id]
            
            # 최대 실행 횟수 체크
            if (info['max_executions'] and 
                info['execution_count'] >= info['max_executions']):
                info['active'] = False
                return
            
            if not info['active']:
                return
        
        # 다음 실행 시간 계산
        current_time = time.time()
        delay = max(0, info['next_execution'] - current_time)
        
        async def recurring_executor():
            try:
                # 작업 생성 및 실행
                task = info['task_factory']()
                await self.worker_pool.submit_task(task)
                
                # 실행 횟수 증가
                with self._lock:
                    info['execution_count'] += 1
                    info['next_execution'] = time.time() + info['interval']
                
                # 다음 실행 스케줄링
                await self._schedule_next_recurring(recurring_id)
                
            except Exception as e:
                logger.error(f"Recurring task {recurring_id} error: {e}")
        
        loop = asyncio.get_event_loop()
        loop.call_later(delay, lambda: asyncio.create_task(recurring_executor()))
    
    def cancel_scheduled_task(self, task_id: str) -> bool:
        """스케줄된 작업 취소"""
        with self._lock:
            if task_id in self.scheduled_tasks:
                handle = self.scheduled_tasks[task_id]
                handle.cancel()
                del self.scheduled_tasks[task_id]
                logger.debug(f"Cancelled scheduled task {task_id}")
                return True
            return False
    
    def cancel_recurring_task(self, recurring_id: str) -> bool:
        """반복 작업 취소"""
        with self._lock:
            if recurring_id in self.recurring_tasks:
                self.recurring_tasks[recurring_id]['active'] = False
                logger.info(f"Cancelled recurring task {recurring_id}")
                return True
            return False
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """스케줄된 작업 목록"""
        with self._lock:
            scheduled = []
            
            for task_id, handle in self.scheduled_tasks.items():
                if not handle.cancelled():
                    scheduled.append({
                        'task_id': task_id,
                        'when': handle.when(),
                        'cancelled': handle.cancelled()
                    })
            
            for recurring_id, info in self.recurring_tasks.items():
                if info['active']:
                    scheduled.append({
                        'recurring_id': recurring_id,
                        'interval': info['interval'],
                        'execution_count': info['execution_count'],
                        'max_executions': info['max_executions'],
                        'next_execution': info['next_execution']
                    })
            
            return scheduled

class AsyncOperationManager:
    """비동기 작업 관리자"""
    
    def __init__(self, 
                 worker_pool_size: int = 20,
                 max_queue_size: int = 2000):
        self.worker_pool = AsyncWorkerPool(worker_pool_size, max_queue_size)
        self.scheduler = AsyncScheduler(self.worker_pool)
        self.callback_manager = CallbackManager()
        
        # 작업 변환 레지스트리
        self.sync_to_async_registry: Dict[str, Callable] = {}
        
        # 성능 메트릭
        self.performance_metrics = {
            'total_operations': 0,
            'async_operations': 0,
            'sync_operations': 0,
            'conversion_success_rate': 0.0,
            'average_response_time': 0.0,
            'throughput_improvement': 0.0
        }
        
        self._metrics_lock = threading.Lock()
        self.running = False
    
    async def start(self):
        """관리자 시작"""
        if self.running:
            return
        
        await self.worker_pool.start()
        self.running = True
        
        logger.info("Async operation manager started")
    
    async def stop(self):
        """관리자 정지"""
        if not self.running:
            return
        
        await self.worker_pool.stop()
        self.running = False
        
        logger.info("Async operation manager stopped")
    
    def register_async_conversion(self, sync_func_name: str, async_func: Callable):
        """동기 함수의 비동기 변환 등록"""
        self.sync_to_async_registry[sync_func_name] = async_func
        logger.debug(f"Registered async conversion for {sync_func_name}")
    
    async def execute_async(self, 
                          operation: Union[Callable, Coroutine],
                          *args,
                          priority: int = 5,
                          timeout: Optional[float] = None,
                          callback: Optional[Callable] = None,
                          error_callback: Optional[Callable] = None,
                          **kwargs) -> str:
        """비동기 작업 실행"""
        # 코루틴 생성
        if asyncio.iscoroutinefunction(operation):
            coro = operation(*args, **kwargs)
        elif asyncio.iscoroutine(operation):
            coro = operation
        else:
            # 동기 함수를 비동기로 변환
            func_name = getattr(operation, '__name__', str(operation))
            
            if func_name in self.sync_to_async_registry:
                async_func = self.sync_to_async_registry[func_name]
                coro = async_func(*args, **kwargs)
            else:
                # 기본 변환 (ThreadPoolExecutor 사용)
                loop = asyncio.get_event_loop()
                coro = loop.run_in_executor(None, partial(operation, *args, **kwargs))
        
        # AsyncTask 생성
        task_id = str(uuid.uuid4())
        task = AsyncTask(
            task_id=task_id,
            name=getattr(operation, '__name__', 'unknown_operation'),
            coroutine=coro,
            priority=priority,
            timeout=timeout,
            callback=callback,
            error_callback=error_callback,
            metadata={'args': args, 'kwargs': kwargs}
        )
        
        # 작업 제출
        await self.worker_pool.submit_task(task)
        
        with self._metrics_lock:
            self.performance_metrics['total_operations'] += 1
            self.performance_metrics['async_operations'] += 1
        
        return task_id
    
    async def execute_batch_async(self,
                                operations: List[Dict[str, Any]],
                                max_concurrent: int = 10) -> List[str]:
        """배치 비동기 실행"""
        task_ids = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(op_dict):
            async with semaphore:
                operation = op_dict['operation']
                args = op_dict.get('args', ())
                kwargs = op_dict.get('kwargs', {})
                
                return await self.execute_async(
                    operation, *args,
                    priority=op_dict.get('priority', 5),
                    timeout=op_dict.get('timeout'),
                    callback=op_dict.get('callback'),
                    error_callback=op_dict.get('error_callback'),
                    **kwargs
                )
        
        # 모든 작업 동시 실행
        tasks = [execute_with_semaphore(op_dict) for op_dict in operations]
        task_ids = await asyncio.gather(*tasks)
        
        logger.info(f"Submitted {len(task_ids)} operations in batch")
        return task_ids
    
    async def wait_for_completion(self, 
                                task_ids: List[str],
                                timeout: Optional[float] = None) -> List[Any]:
        """작업 완료 대기"""
        results = []
        
        for task_id in task_ids:
            try:
                result = await self.worker_pool.get_task_result(task_id, timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                results.append(e)
        
        return results
    
    def get_performance_report(self) -> Dict[str, Any]:
        """성능 보고서 생성"""
        with self._metrics_lock:
            metrics = self.performance_metrics.copy()
        
        # 워커 풀 통계
        worker_stats = self.worker_pool.get_stats()
        
        # 스케줄러 통계
        scheduled_tasks = self.scheduler.get_scheduled_tasks()
        
        # 콜백 통계
        callback_stats = self.callback_manager.get_stats()
        
        return {
            'performance_metrics': metrics,
            'worker_pool_stats': worker_stats,
            'scheduled_tasks_count': len(scheduled_tasks),
            'callback_stats': callback_stats,
            'registered_conversions': len(self.sync_to_async_registry),
            'running': self.running
        }

# 데코레이터들

def async_operation(priority: int = 5, 
                   timeout: Optional[float] = None,
                   manager: Optional[AsyncOperationManager] = None):
    """비동기 작업 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            op_manager = manager or get_async_manager()
            
            if not asyncio.iscoroutinefunction(func):
                # 동기 함수를 비동기로 실행
                task_id = await op_manager.execute_async(
                    func, *args, 
                    priority=priority,
                    timeout=timeout,
                    **kwargs
                )
                return await op_manager.worker_pool.get_task_result(task_id)
            else:
                # 이미 비동기 함수
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def background_task(delay: float = 0.0,
                   recurring: bool = False,
                   interval: Optional[float] = None):
    """백그라운드 작업 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            manager = get_async_manager()
            
            if recurring and interval:
                # 반복 작업
                def task_factory():
                    return AsyncTask(
                        task_id=str(uuid.uuid4()),
                        name=func.__name__,
                        coroutine=func(*args, **kwargs),
                        priority=5
                    )
                
                return await manager.scheduler.schedule_recurring_task(
                    task_factory, interval
                )
            else:
                # 일회성 지연 작업
                task = AsyncTask(
                    task_id=str(uuid.uuid4()),
                    name=func.__name__,
                    coroutine=func(*args, **kwargs),
                    priority=5
                )
                
                return await manager.scheduler.schedule_task(task, delay)
        
        return wrapper
    return decorator

@asynccontextmanager
async def async_context(operation_name: str = "async_operation"):
    """비동기 컨텍스트 관리자"""
    manager = get_async_manager()
    
    start_time = time.time()
    
    try:
        yield manager
    finally:
        execution_time = time.time() - start_time
        await manager.callback_manager.trigger_callbacks(
            'operation_completed',
            operation_name=operation_name,
            execution_time=execution_time
        )

# 전역 관리자 인스턴스
_async_manager: Optional[AsyncOperationManager] = None

def get_async_manager() -> AsyncOperationManager:
    """전역 비동기 관리자 가져오기"""
    global _async_manager
    
    if _async_manager is None:
        _async_manager = AsyncOperationManager()
    
    return _async_manager

async def start_async_operations():
    """전역 비동기 작업 시작"""
    manager = get_async_manager()
    await manager.start()

async def stop_async_operations():
    """전역 비동기 작업 정지"""
    global _async_manager
    
    if _async_manager:
        await _async_manager.stop()
        _async_manager = None

# 유틸리티 함수들

async def convert_sync_to_async(sync_func: Callable, *args, **kwargs) -> Any:
    """동기 함수를 비동기로 변환 실행"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(sync_func, *args, **kwargs))

def make_async(sync_func: Callable) -> Callable:
    """동기 함수를 비동기 함수로 변환"""
    @wraps(sync_func)
    async def async_wrapper(*args, **kwargs):
        return await convert_sync_to_async(sync_func, *args, **kwargs)
    
    return async_wrapper

async def gather_with_concurrency(coroutines: List[Coroutine], 
                                max_concurrent: int = 10) -> List[Any]:
    """동시성 제한이 있는 gather"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_semaphore(coro):
        async with semaphore:
            return await coro
    
    tasks = [run_with_semaphore(coro) for coro in coroutines]
    return await asyncio.gather(*tasks)

def run_async_in_thread(coro: Coroutine) -> Any:
    """별도 스레드에서 비동기 코드 실행"""
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result() 