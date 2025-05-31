#!/usr/bin/env python3
"""
간단한 Google 계정 생성 테스트

실제 계정 생성까지는 가지 않고, 프로세스의 각 단계를 테스트합니다.
"""

import sys
import os
import asyncio
import time
import random
import string
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core.config_manager import ConfigManager
    from core.logger import Logger
    config_available = True
except ImportError as e:
    print(f"핵심 모듈 import 실패: {e}")
    config_available = False

class SimpleAccountTester:
    """간단한 계정 생성 테스터"""
    
    def __init__(self):
        """테스터 초기화"""
        self.driver = None
        self.test_results = []
        
        print("🚀 Google Account Creator - 간단한 테스트")
        print("=" * 50)
        print("⚠️ 이 테스트는 실제 계정 생성 없이 프로세스만 확인합니다.")
        print("=" * 50)
    
    def generate_test_data(self) -> Dict[str, str]:
        """테스트용 데이터 생성"""
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        test_data = {
            'first_name': '테스트',
            'last_name': '사용자',
            'username': f"testuser{random_string}",
            'password': 'TestPassword123!',
            'phone_number': f"010{random.randint(1000, 9999)}{random.randint(1000, 9999)}",
            'birth_year': '1995',
            'birth_month': '6',
            'birth_day': '15'
        }
        
        print(f"📝 테스트 데이터 생성:")
        print(f"   이름: {test_data['first_name']} {test_data['last_name']}")
        print(f"   사용자명: {test_data['username']}")
        
        return test_data
    
    async def test_system_modules(self) -> bool:
        """시스템 모듈 테스트"""
        print("🔧 시스템 모듈 테스트...")
        
        try:
            if config_available:
                # ConfigManager 테스트
                config_path = Path("test_config.yaml")
                config_manager = ConfigManager(config_path)
                config_manager.set("test.key", "test_value")
                config_manager.save()
                
                if config_manager.get("test.key") == "test_value":
                    print("   ✅ ConfigManager 작동 확인")
                    self.test_results.append({"step": "ConfigManager", "success": True})
                else:
                    print("   ❌ ConfigManager 실패")
                    self.test_results.append({"step": "ConfigManager", "success": False})
                
                # 테스트 파일 정리
                if config_path.exists():
                    config_path.unlink()
                
                # Logger 테스트
                logger = Logger("test_logger", log_level="INFO")
                logger.info("테스트 로그 메시지")
                print("   ✅ Logger 작동 확인")
                self.test_results.append({"step": "Logger", "success": True})
            else:
                print("   ⚠️ 핵심 모듈을 import할 수 없음")
                self.test_results.append({"step": "Module Import", "success": False})
            
            return True
            
        except Exception as e:
            print(f"   ❌ 시스템 모듈 테스트 실패: {e}")
            self.test_results.append({"step": "System Modules", "success": False})
            return False
    
    async def test_browser_setup(self) -> bool:
        """브라우저 설정 테스트"""
        print("🌐 브라우저 설정 테스트...")
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            print("   ✅ Chrome 브라우저 설정 성공")
            self.test_results.append({"step": "Browser Setup", "success": True})
            return True
            
        except ImportError:
            print("   ❌ Selenium이 설치되지 않음")
            self.test_results.append({"step": "Browser Setup", "success": False})
            return False
        except Exception as e:
            print(f"   ❌ 브라우저 설정 실패: {e}")
            self.test_results.append({"step": "Browser Setup", "success": False})
            return False
    
    async def test_google_access(self) -> bool:
        """Google 접속 테스트"""
        if not self.driver:
            print("   ❌ 브라우저가 설정되지 않음")
            self.test_results.append({"step": "Google Access", "success": False})
            return False
        
        try:
            print("🔗 Google 접속 테스트...")
            
            # Google 메인 페이지 접속
            self.driver.get("https://www.google.com")
            await asyncio.sleep(2)
            
            if "Google" in self.driver.title:
                print("   ✅ Google 메인 페이지 접속 성공")
                
                # Google 계정 페이지 접속
                self.driver.get("https://accounts.google.com")
                await asyncio.sleep(2)
                
                if "Google" in self.driver.title:
                    print("   ✅ Google 계정 페이지 접속 성공")
                    self.test_results.append({"step": "Google Access", "success": True})
                    return True
                else:
                    print(f"   ❌ 계정 페이지 제목 불일치: {self.driver.title}")
                    self.test_results.append({"step": "Google Access", "success": False})
                    return False
            else:
                print(f"   ❌ 메인 페이지 제목 불일치: {self.driver.title}")
                self.test_results.append({"step": "Google Access", "success": False})
                return False
                
        except Exception as e:
            print(f"   ❌ Google 접속 실패: {e}")
            self.test_results.append({"step": "Google Access", "success": False})
            return False
    
    async def test_form_detection(self) -> bool:
        """폼 감지 테스트"""
        if not self.driver:
            print("   ❌ 브라우저가 설정되지 않음")
            self.test_results.append({"step": "Form Detection", "success": False})
            return False
        
        try:
            print("📝 폼 감지 테스트...")
            
            # 가입 페이지로 이동
            self.driver.get("https://accounts.google.com/signup")
            await asyncio.sleep(3)
            
            from selenium.webdriver.common.by import By
            
            # 입력 필드 찾기
            input_elements = self.driver.find_elements(By.TAG_NAME, "input")
            visible_inputs = [elem for elem in input_elements if elem.is_displayed()]
            
            print(f"   📋 총 {len(input_elements)}개 입력 필드 발견")
            print(f"   👁️ {len(visible_inputs)}개 보이는 입력 필드")
            
            if len(visible_inputs) >= 2:  # 최소 2개 이상의 입력 필드 있어야 함
                print("   ✅ 충분한 입력 필드 감지됨")
                self.test_results.append({"step": "Form Detection", "success": True})
                return True
            else:
                print("   ❌ 입력 필드 부족")
                self.test_results.append({"step": "Form Detection", "success": False})
                return False
                
        except Exception as e:
            print(f"   ❌ 폼 감지 실패: {e}")
            self.test_results.append({"step": "Form Detection", "success": False})
            return False
    
    async def test_data_validation(self, test_data: Dict[str, str]) -> bool:
        """데이터 검증 테스트"""
        print("✅ 데이터 검증 테스트...")
        
        try:
            # 사용자명 검증
            if len(test_data['username']) >= 6 and test_data['username'].isalnum():
                print("   ✅ 사용자명 형식 유효")
            else:
                print("   ❌ 사용자명 형식 무효")
                self.test_results.append({"step": "Data Validation", "success": False})
                return False
            
            # 비밀번호 검증
            password = test_data['password']
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(c in "!@#$%^&*" for c in password)
            
            if len(password) >= 8 and has_upper and has_lower and has_digit:
                print("   ✅ 비밀번호 형식 유효")
            else:
                print("   ❌ 비밀번호 형식 무효")
                self.test_results.append({"step": "Data Validation", "success": False})
                return False
            
            # 전화번호 검증
            if test_data['phone_number'].startswith('010') and len(test_data['phone_number']) == 11:
                print("   ✅ 전화번호 형식 유효")
            else:
                print("   ❌ 전화번호 형식 무효")
                self.test_results.append({"step": "Data Validation", "success": False})
                return False
            
            self.test_results.append({"step": "Data Validation", "success": True})
            return True
            
        except Exception as e:
            print(f"   ❌ 데이터 검증 실패: {e}")
            self.test_results.append({"step": "Data Validation", "success": False})
            return False
    
    async def run_complete_test(self) -> Dict[str, Any]:
        """완전한 테스트 실행"""
        start_time = datetime.now()
        
        print("🏁 간단한 계정 생성 테스트 시작")
        print("=" * 50)
        
        # 테스트 데이터 생성
        test_data = self.generate_test_data()
        
        # 각 테스트 단계 실행
        await self.test_system_modules()
        await self.test_browser_setup()
        await self.test_google_access()
        await self.test_form_detection()
        await self.test_data_validation(test_data)
        
        # 결과 정리
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        success_count = sum(1 for result in self.test_results if result['success'])
        total_count = len(self.test_results)
        
        results = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': duration,
            'test_data': test_data,
            'steps': self.test_results,
            'success_count': success_count,
            'total_count': total_count,
            'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
            'overall_success': success_count == total_count
        }
        
        return results
    
    def print_results(self, results: Dict[str, Any]):
        """결과 출력"""
        print("\n" + "=" * 50)
        print("🏁 테스트 결과 요약")
        print("=" * 50)
        
        print(f"📊 전체 결과: {'✅ 성공' if results['overall_success'] else '❌ 일부 실패'}")
        print(f"⏱️ 소요 시간: {results['duration']:.2f}초")
        print(f"📈 성공률: {results['success_rate']:.1f}% ({results['success_count']}/{results['total_count']})")
        
        print(f"\n📋 단계별 결과:")
        for step in results['steps']:
            status = "✅" if step['success'] else "❌"
            print(f"   {status} {step['step']}")
        
        if results['overall_success']:
            print("\n🎉 모든 테스트가 성공했습니다!")
            print("💡 실제 계정 생성 준비가 완료되었습니다.")
        else:
            print("\n⚠️ 일부 테스트에서 문제가 발생했습니다.")
            print("💡 실제 구현 전에 해당 부분을 수정해야 합니다.")
        
        # 정리
        if self.driver:
            self.driver.quit()
            print("\n🧹 브라우저 정리 완료")

async def main():
    """메인 함수"""
    tester = SimpleAccountTester()
    
    try:
        print("🚀 간단한 계정 생성 테스트를 시작하시겠습니까? (y/n):", end=" ")
        response = 'y'  # input().strip().lower()
        print('y')
        
        if response == 'y':
            results = await tester.run_complete_test()
            tester.print_results(results)
        else:
            print("테스트가 취소되었습니다.")
            
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 사용자에 의해 중단되었습니다.")
        if tester.driver:
            tester.driver.quit()
    except Exception as e:
        print(f"\n\n❌ 테스트 중 오류 발생: {e}")
        if tester.driver:
            tester.driver.quit()

if __name__ == "__main__":
    asyncio.run(main()) 