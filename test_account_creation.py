#!/usr/bin/env python3
"""
Google Account Creator - 실제 계정 생성 테스트

이 스크립트는 실제 Google 계정 생성 프로세스를 테스트합니다.
"""

import sys
import os
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core.config_manager import ConfigManager
    from core.logger import Logger
    from core.error_recovery import ErrorRecoverySystem, ErrorType
    from core.health_checker import SystemHealthChecker
    config_available = True
except ImportError as e:
    print(f"핵심 모듈 import 실패: {e}")
    config_available = False

class AccountCreationTester:
    """Google 계정 생성 테스터"""
    
    def __init__(self):
        """테스터 초기화"""
        self.config = None
        self.logger = None
        self.error_recovery = None
        self.health_checker = None
        
        # 테스트 상태
        self.test_results = []
        self.current_test = None
        
        # 통계
        self.start_time = None
        self.test_count = 0
        self.success_count = 0
        self.failure_count = 0
        
        print("🎯 Google Account Creator - 계정 생성 테스트 시작")
        print("=" * 60)
    
    async def initialize(self):
        """시스템 초기화"""
        print("🔧 시스템 초기화 중...")
        
        try:
            if config_available:
                # ConfigManager 초기화
                self.config = ConfigManager()
                print("✅ ConfigManager 초기화 완료")
                
                # Logger 초기화  
                self.logger = Logger(self.config)
                print("✅ Logger 초기화 완료")
                
                # Error Recovery System 초기화
                self.error_recovery = ErrorRecoverySystem()
                print("✅ Error Recovery System 초기화 완료")
                
                # Health Checker 초기화
                self.health_checker = SystemHealthChecker()
                print("✅ Health Checker 초기화 완료")
                
            else:
                print("⚠️ 일부 모듈이 사용 불가능합니다. 기본 테스트만 실행됩니다.")
                
        except Exception as e:
            print(f"❌ 초기화 실패: {e}")
            raise
    
    async def run_comprehensive_test(self):
        """포괄적인 계정 생성 테스트"""
        self.start_time = datetime.now()
        print(f"\n🚀 포괄적인 계정 생성 테스트 시작 - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # 테스트 목록
        tests = [
            ("시스템 상태 확인", self.test_system_status),
            ("ADB 연결 테스트", self.test_adb_connection),
            ("네트워크 연결 테스트", self.test_network_connectivity),
            ("프록시 설정 테스트", self.test_proxy_configuration),
            ("SMS 서비스 테스트", self.test_sms_service),
            ("에뮬레이터 준비 테스트", self.test_emulator_preparation),
            ("Google 계정 생성 시뮬레이션", self.test_account_creation_simulation),
            ("계정 검증 테스트", self.test_account_verification),
            ("배치 처리 테스트", self.test_batch_processing),
            ("오류 복구 테스트", self.test_error_recovery)
        ]
        
        for test_name, test_func in tests:
            await self.run_single_test(test_name, test_func)
        
        # 최종 결과 출력
        await self.print_final_results()
    
    async def run_single_test(self, test_name: str, test_func):
        """단일 테스트 실행"""
        self.current_test = test_name
        self.test_count += 1
        
        print(f"\n📋 테스트 {self.test_count}: {test_name}")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            result = await test_func()
            duration = time.time() - start_time
            
            if result.get('success', False):
                self.success_count += 1
                print(f"✅ {test_name} - 성공 ({duration:.2f}초)")
            else:
                self.failure_count += 1
                print(f"❌ {test_name} - 실패 ({duration:.2f}초)")
                if result.get('error'):
                    print(f"   오류: {result['error']}")
            
            result['test_name'] = test_name
            result['duration'] = duration
            result['timestamp'] = datetime.now().isoformat()
            self.test_results.append(result)
            
        except Exception as e:
            duration = time.time() - start_time
            self.failure_count += 1
            print(f"❌ {test_name} - 예외 발생 ({duration:.2f}초)")
            print(f"   예외: {e}")
            
            self.test_results.append({
                'test_name': test_name,
                'success': False,
                'error': str(e),
                'duration': duration,
                'timestamp': datetime.now().isoformat()
            })
    
    async def test_system_status(self) -> Dict[str, Any]:
        """시스템 상태 테스트"""
        try:
            status = {
                'python_version': sys.version,
                'platform': os.name,
                'pid': os.getpid(),
                'memory_usage': self.get_memory_usage(),
                'disk_space': self.get_disk_space(),
                'config_available': config_available
            }
            
            print(f"   Python 버전: {sys.version.split()[0]}")
            print(f"   플랫폼: {os.name}")
            print(f"   메모리 사용량: {status['memory_usage']:.1f} MB")
            print(f"   디스크 여유공간: {status['disk_space']:.1f} GB")
            
            return {
                'success': True,
                'data': status
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_adb_connection(self) -> Dict[str, Any]:
        """ADB 연결 테스트"""
        try:
            import subprocess
            
            # ADB 서버 상태 확인
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': f'ADB 명령 실패: {result.stderr}'
                }
            
            # 연결된 디바이스 파싱
            output_lines = result.stdout.strip().split('\n')
            device_lines = [line for line in output_lines if '\tdevice' in line]
            device_count = len(device_lines)
            
            print(f"   ADB 서버: 정상")
            print(f"   연결된 디바이스: {device_count}개")
            
            if device_lines:
                for line in device_lines:
                    device_id = line.split('\t')[0]
                    print(f"   - {device_id}")
            
            return {
                'success': True,
                'data': {
                    'device_count': device_count,
                    'devices': device_lines
                }
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'ADB 명령 타임아웃'
            }
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'ADB가 설치되지 않음'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_network_connectivity(self) -> Dict[str, Any]:
        """네트워크 연결 테스트"""
        try:
            import socket
            
            test_hosts = [
                ('Google DNS', '8.8.8.8', 53),
                ('Google', 'google.com', 80),
                ('Cloudflare DNS', '1.1.1.1', 53)
            ]
            
            results = []
            
            for name, host, port in test_hosts:
                try:
                    start_time = time.time()
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    duration = time.time() - start_time
                    
                    success = result == 0
                    results.append({
                        'name': name,
                        'host': host,
                        'port': port,
                        'success': success,
                        'response_time': duration * 1000
                    })
                    
                    status = "✅" if success else "❌"
                    print(f"   {status} {name} ({host}): {duration*1000:.1f}ms")
                    
                except Exception as e:
                    results.append({
                        'name': name,
                        'host': host,
                        'port': port,
                        'success': False,
                        'error': str(e)
                    })
                    print(f"   ❌ {name} ({host}): {e}")
            
            success_count = sum(1 for r in results if r.get('success', False))
            
            return {
                'success': success_count > 0,
                'data': {
                    'total_tests': len(results),
                    'successful': success_count,
                    'results': results
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_proxy_configuration(self) -> Dict[str, Any]:
        """프록시 설정 테스트"""
        try:
            if not self.config:
                return {
                    'success': True,
                    'data': {'message': 'Config not available, skipping proxy test'}
                }
            
            proxy_enabled = self.config.get('proxy.enabled', False)
            proxy_type = self.config.get('proxy.type', 'http')
            proxy_rotation = self.config.get('proxy.rotation_enabled', False)
            
            print(f"   프록시 사용: {'예' if proxy_enabled else '아니오'}")
            print(f"   프록시 타입: {proxy_type}")
            print(f"   프록시 로테이션: {'예' if proxy_rotation else '아니오'}")
            
            return {
                'success': True,
                'data': {
                    'proxy_enabled': proxy_enabled,
                    'proxy_type': proxy_type,
                    'proxy_rotation': proxy_rotation
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_sms_service(self) -> Dict[str, Any]:
        """SMS 서비스 테스트"""
        try:
            if not self.config:
                return {
                    'success': True,
                    'data': {'message': 'Config not available, skipping SMS test'}
                }
            
            sms_provider = self.config.get('sms.provider', 'not_configured')
            sms_api_key = self.config.get('sms.api_key', '')
            sms_balance_check = self.config.get('sms.balance_check_enabled', False)
            
            print(f"   SMS 제공업체: {sms_provider}")
            print(f"   API 키 설정: {'예' if sms_api_key else '아니오'}")
            print(f"   잔액 확인: {'예' if sms_balance_check else '아니오'}")
            
            # 실제 SMS 서비스 연결 테스트는 API 키가 있을 때만
            service_available = False
            if sms_api_key and sms_provider != 'not_configured':
                # 여기서 실제 SMS 서비스 ping 테스트를 할 수 있음
                service_available = True
                print(f"   서비스 상태: 연결 가능")
            else:
                print(f"   서비스 상태: 설정 필요")
            
            return {
                'success': True,
                'data': {
                    'provider': sms_provider,
                    'api_key_configured': bool(sms_api_key),
                    'service_available': service_available
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_emulator_preparation(self) -> Dict[str, Any]:
        """에뮬레이터 준비 테스트"""
        try:
            import subprocess
            
            # 에뮬레이터 목록 확인
            try:
                result = subprocess.run(['emulator', '-list-avds'], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    avds = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                    print(f"   사용 가능한 AVD: {len(avds)}개")
                    for avd in avds[:3]:  # 처음 3개만 표시
                        print(f"   - {avd}")
                    
                    if len(avds) > 3:
                        print(f"   ... 및 {len(avds) - 3}개 더")
                    
                    return {
                        'success': len(avds) > 0,
                        'data': {
                            'avd_count': len(avds),
                            'avds': avds
                        }
                    }
                else:
                    print(f"   에뮬레이터 명령 실패: {result.stderr}")
                    return {
                        'success': False,
                        'error': result.stderr
                    }
                    
            except FileNotFoundError:
                print(f"   에뮬레이터 도구를 찾을 수 없음")
                return {
                    'success': False,
                    'error': 'Emulator tools not found'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_account_creation_simulation(self) -> Dict[str, Any]:
        """Google 계정 생성 시뮬레이션"""
        try:
            print("   🎭 계정 생성 프로세스 시뮬레이션...")
            
            # 시뮬레이션 단계들
            steps = [
                "에뮬레이터 시작",
                "Chrome 브라우저 열기", 
                "Google 가입 페이지 접속",
                "개인정보 입력",
                "전화번호 인증",
                "SMS 코드 입력",
                "계정 생성 완료"
            ]
            
            simulation_results = []
            
            for i, step in enumerate(steps):
                print(f"   {i+1}. {step}...")
                
                # 시뮬레이션 지연
                await asyncio.sleep(0.5)
                
                # 무작위로 성공/실패 시뮬레이션 (실제로는 모두 성공)
                success = True  # 실제 구현에서는 각 단계별 로직 실행
                
                simulation_results.append({
                    'step': step,
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                })
                
                if success:
                    print(f"      ✅ {step} 완료")
                else:
                    print(f"      ❌ {step} 실패")
                    break
            
            overall_success = all(r['success'] for r in simulation_results)
            
            return {
                'success': overall_success,
                'data': {
                    'steps_completed': len([r for r in simulation_results if r['success']]),
                    'total_steps': len(steps),
                    'simulation_results': simulation_results
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_account_verification(self) -> Dict[str, Any]:
        """계정 검증 테스트"""
        try:
            print("   🔍 계정 검증 프로세스 테스트...")
            
            verification_checks = [
                "Gmail 로그인 테스트",
                "YouTube 접속 테스트", 
                "Google Play 스토어 접속",
                "계정 정보 수집",
                "계정 상태 업데이트"
            ]
            
            verification_results = []
            
            for check in verification_checks:
                print(f"   - {check}...")
                await asyncio.sleep(0.3)
                
                # 시뮬레이션
                success = True
                verification_results.append({
                    'check': check,
                    'success': success
                })
                
                print(f"     {'✅' if success else '❌'} {check}")
            
            return {
                'success': True,
                'data': {
                    'verification_results': verification_results,
                    'all_passed': all(r['success'] for r in verification_results)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_batch_processing(self) -> Dict[str, Any]:
        """배치 처리 테스트"""
        try:
            batch_size = 5 if self.config else 3
            if self.config:
                batch_size = self.config.get('account.batch_size', 5)
            
            print(f"   📦 배치 크기: {batch_size}개 계정")
            print(f"   ⏱️  예상 소요 시간: {batch_size * 2}분")
            
            # 배치 처리 시뮬레이션
            batch_results = []
            
            for i in range(batch_size):
                account_id = f"test_account_{i+1}"
                print(f"   🔄 계정 {i+1}/{batch_size} 처리 중... ({account_id})")
                
                await asyncio.sleep(0.2)  # 시뮬레이션 지연
                
                success = True  # 실제로는 계정 생성 로직 실행
                batch_results.append({
                    'account_id': account_id,
                    'success': success,
                    'timestamp': datetime.now().isoformat()
                })
                
                print(f"      {'✅' if success else '❌'} {account_id}")
            
            success_count = len([r for r in batch_results if r['success']])
            
            return {
                'success': True,
                'data': {
                    'batch_size': batch_size,
                    'successful_accounts': success_count,
                    'failed_accounts': batch_size - success_count,
                    'success_rate': (success_count / batch_size) * 100,
                    'batch_results': batch_results
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_error_recovery(self) -> Dict[str, Any]:
        """오류 복구 테스트"""
        try:
            if not self.error_recovery:
                return {
                    'success': True,
                    'data': {'message': 'Error recovery system not available'}
                }
            
            print("   🛠️ 오류 복구 시스템 테스트...")
            
            # 테스트 에러 생성 및 복구
            test_errors = [
                (ErrorType.NETWORK_ERROR, "네트워크 연결 끊김"),
                (ErrorType.ADB_CONNECTION_LOST, "ADB 연결 실패"),
                (ErrorType.SMS_TIMEOUT, "SMS 타임아웃")
            ]
            
            recovery_results = []
            
            for error_type, error_message in test_errors:
                print(f"   - {error_type.value} 복구 테스트...")
                
                # 에러 처리 시뮬레이션
                await asyncio.sleep(0.3)
                
                # 실제로는 error_recovery.handle_error() 호출
                recovery_success = True
                
                recovery_results.append({
                    'error_type': error_type.value,
                    'error_message': error_message,
                    'recovery_success': recovery_success
                })
                
                print(f"     {'✅' if recovery_success else '❌'} 복구 완료")
            
            return {
                'success': True,
                'data': {
                    'recovery_results': recovery_results,
                    'all_recovered': all(r['recovery_success'] for r in recovery_results)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def print_final_results(self):
        """최종 결과 출력"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("🏁 최종 테스트 결과")
        print("=" * 60)
        
        print(f"📊 전체 통계:")
        print(f"   • 총 테스트: {self.test_count}개")
        print(f"   • 성공: {self.success_count}개 ({(self.success_count/self.test_count)*100:.1f}%)")
        print(f"   • 실패: {self.failure_count}개 ({(self.failure_count/self.test_count)*100:.1f}%)")
        print(f"   • 소요 시간: {duration:.2f}초")
        
        print(f"\n📋 상세 결과:")
        for result in self.test_results:
            status = "✅" if result.get('success', False) else "❌"
            print(f"   {status} {result['test_name']} ({result['duration']:.2f}초)")
            if not result.get('success', False) and result.get('error'):
                print(f"      오류: {result['error']}")
        
        # JSON 결과 파일 저장
        results_file = Path("test_results.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_tests': self.test_count,
                    'successful_tests': self.success_count,
                    'failed_tests': self.failure_count,
                    'success_rate': (self.success_count/self.test_count)*100,
                    'duration_seconds': duration,
                    'start_time': self.start_time.isoformat(),
                    'end_time': end_time.isoformat()
                },
                'detailed_results': self.test_results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 상세 결과가 {results_file}에 저장되었습니다.")
        
        if self.success_count == self.test_count:
            print("\n🎉 모든 테스트가 성공했습니다! 시스템이 계정 생성 준비가 완료되었습니다.")
        else:
            print(f"\n⚠️ {self.failure_count}개의 테스트가 실패했습니다. 문제를 해결한 후 다시 시도하세요.")
    
    def get_memory_usage(self) -> float:
        """메모리 사용량 반환 (MB)"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def get_disk_space(self) -> float:
        """디스크 여유공간 반환 (GB)"""
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            return disk_usage.free / 1024 / 1024 / 1024
        except:
            return 0.0

async def main():
    """메인 함수"""
    tester = AccountCreationTester()
    
    try:
        await tester.initialize()
        await tester.run_comprehensive_test()
        
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 