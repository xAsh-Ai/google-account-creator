#!/usr/bin/env python3
"""
비동기 작업 테스트 스크립트

이 스크립트는 다음 비동기 작업 기능들을 테스트합니다:
- 비동기 작업 관리자
- 이벤트 루프 최적화
- 워커 풀 관리
- 작업 스케줄링
- 콜백 메커니즘
- 성능 향상 측정

Usage:
    python scripts/test_async_operations.py
"""

import asyncio
import time
import threading
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Callable

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.async_operations import (
    AsyncOperationManager, AsyncTask, AsyncEventLoop, AsyncWorkerPool,
    CallbackManager, AsyncScheduler, get_async_manager,
    async_operation, background_task, async_context,
    start_async_operations, stop_async_operations,
    convert_sync_to_async, make_async, gather_with_concurrency
)
from core.logger import get_logger

logger = get_logger("AsyncOperationsTest")

class AsyncOperationsTester:
    """포괄적인 비동기 작업 테스트 스위트"""
    
    def __init__(self):
        self.manager = None
        self.test_results = {}
        self.performance_baseline = {}
    
    async def setup(self):
        """테스트 환경 설정"""
        logger.info("🔧 비동기 작업 테스트 환경 설정 중")
        
        # 비동기 관리자 초기화
        self.manager = get_async_manager()
        await self.manager.start()
        
        # 성능 기준선 측정
        await self._measure_baseline_performance()
        
        logger.info("비동기 작업 테스트 환경 준비 완료")
    
    async def cleanup(self):
        """테스트 환경 정리"""
        if self.manager:
            await self.manager.stop()
        
        logger.info("🧹 테스트 환경 정리 완료")
    
    async def _measure_baseline_performance(self):
        """기준 성능 측정"""
        # 동기 작업 성능 측정
        def sync_work(data_size: int = 1000):
            # CPU 집약적 작업 시뮬레이션
            total = 0
            for i in range(data_size):
                total += i ** 2
            return total
        
        start_time = time.time()
        
        # 순차 실행
        for _ in range(10):
            sync_work(1000)
        
        sequential_time = time.time() - start_time
        
        self.performance_baseline = {
            'sequential_execution_time': sequential_time,
            'single_task_time': sequential_time / 10
        }
        
        logger.debug(f"Baseline performance - Sequential: {sequential_time:.3f}s")
    
    async def test_async_event_loop(self) -> Dict[str, Any]:
        """이벤트 루프 테스트"""
        logger.info("🔄 이벤트 루프 테스트 중")
        
        results = {
            'loops_created': 0,
            'loops_started': 0,
            'tasks_processed': 0,
            'performance_metrics': {}
        }
        
        try:
            # 여러 이벤트 루프 생성 및 테스트
            loops = []
            
            for i in range(3):
                loop = AsyncEventLoop(f"test_loop_{i}")
                loop.start()
                loops.append(loop)
                results['loops_created'] += 1
                
                if loop.running:
                    results['loops_started'] += 1
            
            # 각 루프에서 작업 실행
            tasks = []
            
            async def test_coroutine(loop_name: str, task_id: int):
                await asyncio.sleep(0.1)  # 시뮬레이션 작업
                return f"{loop_name}_task_{task_id}"
            
            for i, loop in enumerate(loops):
                for j in range(5):
                    coro = test_coroutine(f"loop_{i}", j)
                    future = loop.submit_coroutine(coro)
                    tasks.append(future)
                    results['tasks_processed'] += 1
            
            # 모든 작업 완료 대기
            completed_tasks = 0
            for task in tasks:
                try:
                    result = task.result(timeout=5)
                    completed_tasks += 1
                except Exception as e:
                    logger.warning(f"Task failed: {e}")
            
            # 루프 통계 수집
            loop_stats = {}
            for loop in loops:
                stats = loop.get_stats()
                loop_stats[loop.name] = stats
                
                # 루프 정지
                loop.stop()
            
            results.update({
                'success': True,
                'completed_tasks': completed_tasks,
                'success_rate': completed_tasks / results['tasks_processed'],
                'loop_stats': loop_stats
            })
            
            logger.info(f"✅ 이벤트 루프 테스트 - {completed_tasks}/{results['tasks_processed']} 작업 완료")
            
        except Exception as e:
            logger.error(f"❌ 이벤트 루프 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_worker_pool(self) -> Dict[str, Any]:
        """워커 풀 테스트"""
        logger.info("👷 워커 풀 테스트 중")
        
        results = {
            'pool_created': False,
            'workers_count': 0,
            'tasks_submitted': 0,
            'tasks_completed': 0,
            'average_execution_time': 0.0
        }
        
        try:
            # 워커 풀 생성
            pool = AsyncWorkerPool(pool_size=8, max_queue_size=100)
            await pool.start()
            results['pool_created'] = True
            results['workers_count'] = pool.pool_size
            
            # 테스트 작업들 생성
            async def test_work(work_id: int, duration: float = 0.1):
                await asyncio.sleep(duration)
                return f"work_{work_id}_completed"
            
            # 작업 제출
            task_ids = []
            for i in range(20):
                task = AsyncTask(
                    task_id=f"test_task_{i}",
                    name=f"test_work_{i}",
                    coroutine=test_work(i, 0.05),
                    priority=5
                )
                
                task_id = await pool.submit_task(task)
                task_ids.append(task_id)
                results['tasks_submitted'] += 1
            
            # 작업 완료 대기
            completed = 0
            execution_times = []
            
            for task_id in task_ids:
                try:
                    start_time = time.time()
                    result = await pool.get_task_result(task_id, timeout=10)
                    execution_time = time.time() - start_time
                    execution_times.append(execution_time)
                    completed += 1
                except Exception as e:
                    logger.warning(f"Task {task_id} failed: {e}")
            
            results['tasks_completed'] = completed
            
            if execution_times:
                results['average_execution_time'] = sum(execution_times) / len(execution_times)
            
            # 풀 통계
            pool_stats = pool.get_stats()
            results['pool_stats'] = pool_stats
            
            # 워커 풀 정지
            await pool.stop()
            
            results.update({
                'success': True,
                'completion_rate': completed / results['tasks_submitted']
            })
            
            logger.info(f"✅ 워커 풀 테스트 - {completed}/{results['tasks_submitted']} 작업 완료")
            
        except Exception as e:
            logger.error(f"❌ 워커 풀 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_callback_mechanism(self) -> Dict[str, Any]:
        """콜백 메커니즘 테스트"""
        logger.info("📞 콜백 메커니즘 테스트 중")
        
        results = {
            'callbacks_registered': 0,
            'callbacks_triggered': 0,
            'one_time_callbacks_triggered': 0,
            'callback_errors': 0
        }
        
        try:
            callback_manager = CallbackManager()
            
            # 콜백 카운터
            callback_count = 0
            one_time_count = 0
            error_count = 0
            
            # 테스트 콜백 함수들
            def test_callback(event_name: str, data: Any):
                nonlocal callback_count
                callback_count += 1
                logger.debug(f"Callback triggered for {event_name}: {data}")
            
            async def async_test_callback(event_name: str, data: Any):
                nonlocal callback_count
                callback_count += 1
                await asyncio.sleep(0.01)  # 시뮬레이션 작업
                logger.debug(f"Async callback triggered for {event_name}: {data}")
            
            def one_time_callback(event_name: str, data: Any):
                nonlocal one_time_count
                one_time_count += 1
                logger.debug(f"One-time callback triggered for {event_name}: {data}")
            
            def error_callback(event_name: str, data: Any):
                nonlocal error_count
                error_count += 1
                raise ValueError("Test callback error")
            
            # 콜백 등록
            callback_manager.register_callback("test_event", test_callback)
            callback_manager.register_callback("test_event", async_test_callback)
            callback_manager.register_callback("test_event", one_time_callback, one_time=True)
            callback_manager.register_callback("test_event", error_callback)
            results['callbacks_registered'] = 4
            
            # 이벤트 트리거
            for i in range(3):
                await callback_manager.trigger_callbacks("test_event", f"data_{i}")
            
            results.update({
                'success': True,
                'callbacks_triggered': callback_count,
                'one_time_callbacks_triggered': one_time_count,
                'callback_errors': error_count,
                'callback_stats': callback_manager.get_stats()
            })
            
            logger.info(f"✅ 콜백 메커니즘 테스트 - {callback_count} 콜백 트리거됨")
            
        except Exception as e:
            logger.error(f"❌ 콜백 메커니즘 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_task_scheduling(self) -> Dict[str, Any]:
        """작업 스케줄링 테스트"""
        logger.info("⏰ 작업 스케줄링 테스트 중")
        
        results = {
            'scheduled_tasks': 0,
            'recurring_tasks': 0,
            'executed_tasks': 0,
            'scheduling_accuracy': 0.0
        }
        
        try:
            # 스케줄러 생성
            worker_pool = AsyncWorkerPool(pool_size=4)
            await worker_pool.start()
            scheduler = AsyncScheduler(worker_pool)
            
            # 실행 시간 추적
            execution_times = []
            
            # 지연 작업 테스트
            async def delayed_work(task_id: str, expected_delay: float):
                start_time = time.time()
                await asyncio.sleep(0.01)  # 시뮬레이션 작업
                actual_delay = time.time() - start_time
                execution_times.append((expected_delay, actual_delay))
                return f"delayed_task_{task_id}"
            
            # 여러 지연 작업 스케줄링
            delayed_tasks = []
            delays = [0.1, 0.2, 0.3, 0.5]
            
            for i, delay in enumerate(delays):
                task = AsyncTask(
                    task_id=f"delayed_{i}",
                    name=f"delayed_work_{i}",
                    coroutine=delayed_work(f"{i}", delay),
                    priority=5
                )
                
                await scheduler.schedule_task(task, delay)
                delayed_tasks.append(task)
                results['scheduled_tasks'] += 1
            
            # 반복 작업 테스트
            recurring_executions = []
            
            async def recurring_work():
                execution_time = time.time()
                recurring_executions.append(execution_time)
                await asyncio.sleep(0.01)
                return f"recurring_execution_{len(recurring_executions)}"
            
            def recurring_task_factory():
                return AsyncTask(
                    task_id=f"recurring_{time.time()}",
                    name="recurring_work",
                    coroutine=recurring_work(),
                    priority=5
                )
            
            # 반복 작업 스케줄링 (0.2초 간격, 최대 5회)
            recurring_id = await scheduler.schedule_recurring_task(
                recurring_task_factory,
                interval=0.2,
                max_executions=5
            )
            results['recurring_tasks'] = 1
            
            # 실행 대기 (충분한 시간)
            await asyncio.sleep(2.0)
            
            # 결과 확인
            results['executed_tasks'] = len(execution_times) + len(recurring_executions)
            
            # 스케줄링 정확도 계산
            if execution_times:
                accuracy_scores = []
                for expected, actual in execution_times:
                    # 실제 지연시간이 예상보다 얼마나 정확한지 (오차 허용)
                    error = abs(actual - expected)
                    accuracy = max(0, 1 - (error / expected)) if expected > 0 else 1
                    accuracy_scores.append(accuracy)
                
                results['scheduling_accuracy'] = sum(accuracy_scores) / len(accuracy_scores)
            
            # 스케줄러 상태
            scheduled_tasks_info = scheduler.get_scheduled_tasks()
            
            # 정리
            await worker_pool.stop()
            
            results.update({
                'success': True,
                'recurring_executions': len(recurring_executions),
                'scheduled_tasks_info': len(scheduled_tasks_info)
            })
            
            logger.info(f"✅ 작업 스케줄링 테스트 - {results['executed_tasks']} 작업 실행됨")
            
        except Exception as e:
            logger.error(f"❌ 작업 스케줄링 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_async_decorators(self) -> Dict[str, Any]:
        """비동기 데코레이터 테스트"""
        logger.info("🎭 비동기 데코레이터 테스트 중")
        
        results = {
            'sync_to_async_converted': False,
            'background_task_executed': False,
            'async_context_worked': False,
            'decorator_performance': {}
        }
        
        try:
            # @async_operation 데코레이터 테스트
            @async_operation(priority=3, timeout=5.0)
            def sync_function(data: str, multiplier: int = 2):
                time.sleep(0.1)  # 동기 작업 시뮬레이션
                return data * multiplier
            
            # 동기 함수를 비동기로 실행
            result = await sync_function("test", 3)
            results['sync_to_async_converted'] = result == "testtesttest"
            
            # @background_task 데코레이터 테스트
            background_results = []
            
            @background_task(delay=0.1)
            async def background_function(data: str):
                background_results.append(data)
                return f"background_{data}"
            
            # 백그라운드 작업 실행
            task_id = await background_function("test_data")
            
            # 실행 대기
            await asyncio.sleep(0.3)
            
            results['background_task_executed'] = len(background_results) > 0
            
            # async_context 테스트
            context_events = []
            
            # 컨텍스트 매니저에서 콜백 등록
            async def context_callback(operation_name: str, execution_time: float):
                context_events.append((operation_name, execution_time))
            
            self.manager.callback_manager.register_callback(
                'operation_completed', 
                context_callback
            )
            
            async with async_context("test_operation") as context:
                await asyncio.sleep(0.1)  # 시뮬레이션 작업
                results['async_context_worked'] = True
            
            # 컨텍스트 이벤트 확인
            await asyncio.sleep(0.1)  # 콜백 실행 대기
            
            if context_events:
                results['context_callback_triggered'] = True
                results['context_execution_time'] = context_events[0][1]
            
            results.update({
                'success': True,
                'background_results_count': len(background_results),
                'context_events_count': len(context_events)
            })
            
            logger.info("✅ 비동기 데코레이터 테스트 통과")
            
        except Exception as e:
            logger.error(f"❌ 비동기 데코레이터 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_performance_improvement(self) -> Dict[str, Any]:
        """성능 향상 테스트"""
        logger.info("🚀 성능 향상 테스트 중")
        
        results = {
            'baseline_time': 0.0,
            'async_time': 0.0,
            'improvement_factor': 0.0,
            'throughput_improvement': 0.0
        }
        
        try:
            # 동기 작업 정의
            def cpu_intensive_work(size: int = 1000):
                total = 0
                for i in range(size):
                    total += i ** 2
                time.sleep(0.01)  # I/O 시뮬레이션
                return total
            
            # 동기 순차 실행 (기준선)
            start_time = time.time()
            
            sync_results = []
            for i in range(10):
                result = cpu_intensive_work(500)
                sync_results.append(result)
            
            baseline_time = time.time() - start_time
            results['baseline_time'] = baseline_time
            
            # 비동기 병렬 실행
            start_time = time.time()
            
            # 비동기 작업 생성
            async_tasks = []
            for i in range(10):
                task_id = await self.manager.execute_async(
                    cpu_intensive_work,
                    500,
                    priority=5,
                    timeout=10.0
                )
                async_tasks.append(task_id)
            
            # 모든 작업 완료 대기
            async_results = await self.manager.wait_for_completion(
                async_tasks, 
                timeout=15.0
            )
            
            async_time = time.time() - start_time
            results['async_time'] = async_time
            
            # 성능 향상 계산
            if async_time > 0:
                improvement_factor = baseline_time / async_time
                results['improvement_factor'] = improvement_factor
                
                # 처리량 향상 (작업/초)
                baseline_throughput = len(sync_results) / baseline_time
                async_throughput = len([r for r in async_results if not isinstance(r, Exception)]) / async_time
                
                if baseline_throughput > 0:
                    results['throughput_improvement'] = async_throughput / baseline_throughput
            
            # 결과 검증
            successful_async = sum(1 for r in async_results if not isinstance(r, Exception))
            
            results.update({
                'success': True,
                'sync_results_count': len(sync_results),
                'async_results_count': successful_async,
                'async_success_rate': successful_async / len(async_tasks),
                'performance_gain_percentage': (improvement_factor - 1) * 100 if improvement_factor > 1 else 0
            })
            
            logger.info(f"✅ 성능 향상 테스트 - {improvement_factor:.2f}x 개선 ({results['performance_gain_percentage']:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ 성능 향상 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def test_utility_functions(self) -> Dict[str, Any]:
        """유틸리티 함수 테스트"""
        logger.info("🔧 유틸리티 함수 테스트 중")
        
        results = {
            'convert_sync_to_async_worked': False,
            'make_async_worked': False,
            'gather_with_concurrency_worked': False,
            'utility_performance': {}
        }
        
        try:
            # convert_sync_to_async 테스트
            def sync_utility_func(x: int, y: int) -> int:
                time.sleep(0.05)
                return x + y
            
            result = await convert_sync_to_async(sync_utility_func, 10, 20)
            results['convert_sync_to_async_worked'] = result == 30
            
            # make_async 테스트
            async_utility_func = make_async(sync_utility_func)
            result = await async_utility_func(5, 15)
            results['make_async_worked'] = result == 20
            
            # gather_with_concurrency 테스트
            async def async_work_item(item_id: int):
                await asyncio.sleep(0.02)
                return f"item_{item_id}"
            
            # 동시성 제한이 있는 gather
            start_time = time.time()
            
            coroutines = [async_work_item(i) for i in range(20)]
            results_list = await gather_with_concurrency(coroutines, max_concurrent=5)
            
            gather_time = time.time() - start_time
            
            results['gather_with_concurrency_worked'] = len(results_list) == 20
            results['utility_performance']['gather_time'] = gather_time
            results['utility_performance']['gather_results_count'] = len(results_list)
            
            # 모든 결과가 올바른지 확인
            expected_results = [f"item_{i}" for i in range(20)]
            results['gather_results_correct'] = sorted(results_list) == sorted(expected_results)
            
            results.update({
                'success': True,
                'all_utilities_working': all([
                    results['convert_sync_to_async_worked'],
                    results['make_async_worked'],
                    results['gather_with_concurrency_worked']
                ])
            })
            
            logger.info("✅ 유틸리티 함수 테스트 통과")
            
        except Exception as e:
            logger.error(f"❌ 유틸리티 함수 테스트 실패: {e}")
            results.update({'success': False, 'error': str(e)})
        
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """포괄적 테스트 실행"""
        logger.info("🚀 포괄적 비동기 작업 테스트 시작")
        
        all_results = {
            'test_suite': 'Async Operations',
            'timestamp': time.time(),
            'tests': {}
        }
        
        # 테스트 환경 설정
        await self.setup()
        
        try:
            # 개별 테스트 실행
            test_methods = [
                ('async_event_loop', self.test_async_event_loop),
                ('worker_pool', self.test_worker_pool),
                ('callback_mechanism', self.test_callback_mechanism),
                ('task_scheduling', self.test_task_scheduling),
                ('async_decorators', self.test_async_decorators),
                ('performance_improvement', self.test_performance_improvement),
                ('utility_functions', self.test_utility_functions)
            ]
            
            for test_name, test_method in test_methods:
                logger.info(f"🔍 {test_name} 테스트 실행 중...")
                
                test_start = time.time()
                test_result = await test_method()
                test_duration = time.time() - test_start
                
                test_result['duration'] = test_duration
                all_results['tests'][test_name] = test_result
                
                if test_result.get('success', False):
                    logger.info(f"✅ {test_name} 테스트 통과 ({test_duration:.2f}s)")
                else:
                    logger.error(f"❌ {test_name} 테스트 실패: {test_result.get('error', '알 수 없는 오류')}")
            
            # 전체 결과 계산
            successful_tests = sum(1 for result in all_results['tests'].values() if result.get('success', False))
            total_tests = len(all_results['tests'])
            
            # 성능 보고서 생성
            performance_report = self.manager.get_performance_report()
            
            all_results.update({
                'success': successful_tests == total_tests,
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
                'total_duration': time.time() - all_results['timestamp'],
                'performance_report': performance_report,
                'baseline_performance': self.performance_baseline
            })
            
            logger.info(f"📊 테스트 요약: {successful_tests}/{total_tests} 테스트 통과 ({all_results['success_rate']:.1%})")
            
        except Exception as e:
            logger.error(f"❌ 테스트 스위트 실패: {e}")
            all_results.update({
                'success': False,
                'error': str(e)
            })
        
        finally:
            await self.cleanup()
        
        return all_results
    
    def save_test_results(self, results: Dict[str, Any], filename: str = None):
        """테스트 결과 저장"""
        if filename is None:
            filename = f"async_operations_test_results_{int(time.time())}.json"
        
        results_dir = Path("profiling_results")
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / filename
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"💾 테스트 결과 저장됨: {results_file}")
            
        except Exception as e:
            logger.error(f"테스트 결과 저장 실패: {e}")

async def main():
    """메인 테스트 함수"""
    tester = AsyncOperationsTester()
    
    try:
        # 포괄적 테스트 실행
        results = await tester.run_comprehensive_test()
        
        # 결과 저장
        tester.save_test_results(results)
        
        # 요약 출력
        print("\n" + "="*80)
        print("🔄 비동기 작업 테스트 결과")
        print("="*80)
        
        if results.get('success', False):
            print(f"✅ 모든 테스트 통과 ({results['successful_tests']}/{results['total_tests']})")
        else:
            print(f"❌ 일부 테스트 실패 ({results['successful_tests']}/{results['total_tests']})")
        
        print(f"⏱️  전체 소요 시간: {results.get('total_duration', 0):.2f}s")
        
        # 개별 테스트 결과
        for test_name, test_result in results.get('tests', {}).items():
            status = "✅ 통과" if test_result.get('success', False) else "❌ 실패"
            duration = test_result.get('duration', 0)
            print(f"  {status} {test_name.replace('_', ' ').title()} ({duration:.2f}s)")
            
            if not test_result.get('success', False) and 'error' in test_result:
                print(f"    오류: {test_result['error']}")
        
        # 성능 개선 요약
        if 'performance_improvement' in results.get('tests', {}):
            perf_test = results['tests']['performance_improvement']
            if perf_test.get('success', False):
                improvement = perf_test.get('improvement_factor', 1.0)
                print(f"\n🚀 성능 개선: {improvement:.2f}x 빨라짐 ({perf_test.get('performance_gain_percentage', 0):.1f}% 향상)")
        
        print("="*80)
        
        # 적절한 종료 코드 반환
        return 0 if results.get('success', False) else 1
        
    except Exception as e:
        logger.error(f"테스트 실행 실패: {e}")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main())) 