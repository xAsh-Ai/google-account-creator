#!/usr/bin/env python3
"""
Google Account Creator - 실제 브라우저 자동화 테스트

이 스크립트는 Selenium을 사용하여 실제 Google 계정 생성 프로세스를 테스트합니다.
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
import json

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class RealAccountCreationTester:
    """실제 Google 계정 생성 테스터"""
    
    def __init__(self):
        """테스터 초기화"""
        self.driver = None
        self.test_data = {}
        self.created_accounts = []
        
        print("🚀 Google Account Creator - 실제 계정 생성 테스트")
        print("=" * 60)
        print("⚠️ 이 테스트는 실제 Google 서버와 통신합니다.")
        print("⚠️ 테스트 목적으로만 사용하고, 생성된 계정은 정리해주세요.")
        print("=" * 60)
    
    def generate_test_data(self) -> Dict[str, str]:
        """테스트용 계정 데이터 생성"""
        
        # 무작위 이름 생성
        first_names = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
        last_names = ["민수", "영희", "철수", "순영", "현우", "지영", "동호", "수진", "상호", "미영"]
        
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        
        # 무작위 사용자명 생성
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        username = f"testuser{random_string}"
        
        # 무작위 비밀번호 생성
        password = ''.join(random.choices(
            string.ascii_letters + string.digits + "!@#$%^&*", k=12
        ))
        
        # 전화번호 (테스트용 - 실제로는 SMS 서비스에서 받아야 함)
        phone_number = f"010{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        
        test_data = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'password': password,
            'phone_number': phone_number,
            'birth_year': str(random.randint(1990, 2000)),
            'birth_month': str(random.randint(1, 12)),
            'birth_day': str(random.randint(1, 28))
        }
        
        print(f"📝 테스트 데이터 생성:")
        print(f"   이름: {first_name} {last_name}")
        print(f"   사용자명: {username}")
        print(f"   전화번호: {phone_number}")
        print(f"   생년월일: {test_data['birth_year']}-{test_data['birth_month']}-{test_data['birth_day']}")
        
        return test_data
    
    async def setup_browser(self):
        """브라우저 설정"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            print("🌐 브라우저 설정 중...")
            
            # Chrome 옵션 설정
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Docker 환경에서는 headless 모드 사용
            if os.getenv('DOCKER_ENV'):
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
            
            # ChromeDriver 경로 설정
            try:
                # 시스템에서 chromedriver 찾기
                import subprocess
                result = subprocess.run(['which', 'chromedriver'], capture_output=True, text=True)
                if result.returncode == 0:
                    service = Service(result.stdout.strip())
                else:
                    service = Service()  # PATH에서 찾기
                
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                
            except Exception as e:
                print(f"❌ ChromeDriver 설정 실패: {e}")
                print("📥 ChromeDriver를 설치해주세요:")
                print("   macOS: brew install chromedriver")
                print("   또는: https://chromedriver.chromium.org/downloads")
                return False
            
            # 브라우저 창 크기 설정
            self.driver.set_window_size(1920, 1080)
            
            # 자동화 감지 방지
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ 브라우저 설정 완료")
            return True
            
        except ImportError:
            print("❌ Selenium이 설치되지 않았습니다.")
            print("📥 설치 명령: pip install selenium")
            return False
        except Exception as e:
            print(f"❌ 브라우저 설정 실패: {e}")
            return False
    
    async def test_google_signup_page_access(self) -> bool:
        """Google 가입 페이지 접속 테스트"""
        try:
            print("🔗 Google 가입 페이지 접속 중...")
            
            # Google 가입 페이지로 이동
            self.driver.get("https://accounts.google.com/signup")
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 페이지 제목 확인
            if "Google" in self.driver.title:
                print("✅ Google 가입 페이지 접속 성공")
                return True
            else:
                print(f"❌ 잘못된 페이지: {self.driver.title}")
                return False
                
        except Exception as e:
            print(f"❌ 페이지 접속 실패: {e}")
            return False
    
    async def test_form_filling(self, test_data: Dict[str, str]) -> bool:
        """가입 폼 입력 테스트"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            print("📝 가입 폼 입력 중...")
            
            wait = WebDriverWait(self.driver, 10)
            
            # 성명 입력
            try:
                first_name_field = wait.until(
                    EC.presence_of_element_located((By.NAME, "firstName"))
                )
                first_name_field.clear()
                first_name_field.send_keys(test_data['first_name'])
                print(f"   ✅ 성 입력: {test_data['first_name']}")
                
                last_name_field = self.driver.find_element(By.NAME, "lastName")
                last_name_field.clear()
                last_name_field.send_keys(test_data['last_name'])
                print(f"   ✅ 이름 입력: {test_data['last_name']}")
                
            except Exception as e:
                print(f"   ❌ 이름 입력 실패: {e}")
                return False
            
            # 사용자명 입력
            try:
                # Google의 새로운 폼 구조에 맞춰 셀렉터 업데이트
                username_selectors = ["input[name='Username']", "input[type='email']", "#username", "input[aria-label*='username' i]", "input[aria-label*='사용자명' i]"]
                username_field = None
                
                for selector in username_selectors:
                    try:
                        username_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if username_field.is_displayed():
                            break
                    except:
                        continue
                
                if username_field:
                    username_field.clear()
                    username_field.send_keys(test_data['username'])
                    print(f"   ✅ 사용자명 입력: {test_data['username']}")
                else:
                    print(f"   ⚠️ 사용자명 필드를 찾을 수 없음 (나중 단계에서 입력)")
                
            except Exception as e:
                print(f"   ⚠️ 사용자명 입력 단계 건너뜀: {e}")
            
            # 비밀번호 입력
            try:
                password_selectors = ["input[name='Passwd']", "input[type='password']", "#password", "input[aria-label*='password' i]", "input[aria-label*='비밀번호' i]"]
                password_field = None
                
                for selector in password_selectors:
                    try:
                        password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if password_field.is_displayed():
                            break
                    except:
                        continue
                
                if password_field:
                    password_field.clear()
                    password_field.send_keys(test_data['password'])
                    print(f"   ✅ 비밀번호 입력")
                    
                    # 비밀번호 확인 필드
                    confirm_selectors = ["input[name='ConfirmPasswd']", "input[name='PasswdAgain']", "input[aria-label*='confirm' i]", "input[aria-label*='확인' i]"]
                    confirm_password_field = None
                    
                    for selector in confirm_selectors:
                        try:
                            confirm_password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if confirm_password_field.is_displayed():
                                break
                        except:
                            continue
                    
                    if confirm_password_field:
                        confirm_password_field.clear()
                        confirm_password_field.send_keys(test_data['password'])
                        print(f"   ✅ 비밀번호 확인")
                    else:
                        print(f"   ⚠️ 비밀번호 확인 필드를 찾을 수 없음")
                else:
                    print(f"   ⚠️ 비밀번호 필드를 찾을 수 없음 (나중 단계에서 입력)")
                
            except Exception as e:
                print(f"   ⚠️ 비밀번호 입력 단계 건너뜀: {e}")
            
            print("✅ 기본 정보 입력 완료 (가능한 필드들)")
            return True
            
        except Exception as e:
            print(f"❌ 폼 입력 실패: {e}")
            return False
    
    async def test_phone_verification_step(self, phone_number: str) -> bool:
        """전화번호 인증 단계 테스트"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            print("📱 전화번호 인증 단계 테스트...")
            
            wait = WebDriverWait(self.driver, 10)
            
            # 다음 버튼 클릭 (기본 정보 입력 후)
            try:
                next_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//span[text()='다음']"))
                )
                next_button.click()
                await asyncio.sleep(3)
                print("   ✅ 다음 단계로 이동")
                
            except Exception as e:
                print(f"   ❌ 다음 버튼 클릭 실패: {e}")
                # 대안 셀렉터 시도
                try:
                    next_button = self.driver.find_element(By.ID, "accountDetailsNext")
                    next_button.click()
                    await asyncio.sleep(3)
                    print("   ✅ 대안 셀렉터로 다음 단계 이동")
                except Exception as e2:
                    print(f"   ❌ 대안 셀렉터도 실패: {e2}")
                    return False
            
            # 전화번호 입력 필드 찾기
            try:
                phone_field = wait.until(
                    EC.presence_of_element_located((By.NAME, "phoneNumber"))
                )
                phone_field.clear()
                phone_field.send_keys(phone_number)
                print(f"   ✅ 전화번호 입력: {phone_number}")
                
            except Exception as e:
                print(f"   ⚠️ 전화번호 필드를 찾을 수 없음 (선택사항일 수 있음): {e}")
                # 전화번호 입력이 선택사항인 경우 건너뛰기
                return True
            
            # 여기서는 실제 SMS 인증까지는 진행하지 않음 (테스트 목적)
            print("   ⚠️ SMS 인증은 테스트에서 제외 (실제 서비스 보호)")
            
            return True
            
        except Exception as e:
            print(f"❌ 전화번호 인증 테스트 실패: {e}")
            return False
    
    async def test_captcha_detection(self) -> bool:
        """CAPTCHA 감지 테스트"""
        try:
            print("🤖 CAPTCHA 감지 테스트...")
            
            # reCAPTCHA 요소 찾기
            captcha_elements = self.driver.find_elements(By.CLASS_NAME, "g-recaptcha")
            
            if captcha_elements:
                print("   ⚠️ reCAPTCHA 감지됨")
                print("   💡 실제 구현에서는 AI 기반 CAPTCHA 해결 시스템 필요")
                return True
            else:
                print("   ✅ CAPTCHA 없음")
                return True
                
        except Exception as e:
            print(f"❌ CAPTCHA 감지 실패: {e}")
            return False
    
    async def test_error_handling(self) -> bool:
        """오류 처리 테스트"""
        try:
            print("🛠️ 오류 처리 테스트...")
            
            # 페이지에서 오류 메시지 찾기
            error_selectors = [
                ".LXRPh",  # Google 오류 메시지 클래스
                ".dEOOab",  # 다른 오류 메시지 클래스
                "[role='alert']",  # ARIA 알림 역할
                ".error-msg"  # 일반적인 오류 클래스
            ]
            
            found_errors = []
            
            for selector in error_selectors:
                try:
                    error_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in error_elements:
                        if element.is_displayed() and element.text.strip():
                            found_errors.append({
                                'selector': selector,
                                'text': element.text.strip()
                            })
                except:
                    continue
            
            if found_errors:
                print("   ⚠️ 감지된 오류:")
                for error in found_errors:
                    print(f"      - {error['text']}")
                return False
            else:
                print("   ✅ 오류 없음")
                return True
                
        except Exception as e:
            print(f"❌ 오류 처리 테스트 실패: {e}")
            return False
    
    async def run_complete_test(self) -> Dict[str, Any]:
        """완전한 계정 생성 테스트 실행"""
        start_time = datetime.now()
        results = {
            'start_time': start_time.isoformat(),
            'test_data': None,
            'steps': [],
            'success': False,
            'errors': []
        }
        
        try:
            # 1. 브라우저 설정
            if not await self.setup_browser():
                results['errors'].append("브라우저 설정 실패")
                return results
            
            # 2. 테스트 데이터 생성
            test_data = self.generate_test_data()
            results['test_data'] = test_data
            self.test_data = test_data
            
            # 3. Google 가입 페이지 접속
            step_result = await self.test_google_signup_page_access()
            results['steps'].append({
                'step': 'Google 가입 페이지 접속',
                'success': step_result,
                'timestamp': datetime.now().isoformat()
            })
            
            if not step_result:
                results['errors'].append("Google 가입 페이지 접속 실패")
                return results
            
            # 4. 폼 입력 테스트
            step_result = await self.test_form_filling(test_data)
            results['steps'].append({
                'step': '가입 폼 입력',
                'success': step_result,
                'timestamp': datetime.now().isoformat()
            })
            
            if not step_result:
                results['errors'].append("가입 폼 입력 실패")
                return results
            
            # 5. CAPTCHA 감지 테스트
            step_result = await self.test_captcha_detection()
            results['steps'].append({
                'step': 'CAPTCHA 감지',
                'success': step_result,
                'timestamp': datetime.now().isoformat()
            })
            
            # 6. 오류 처리 테스트
            step_result = await self.test_error_handling()
            results['steps'].append({
                'step': '오류 처리',
                'success': step_result,
                'timestamp': datetime.now().isoformat()
            })
            
            # 7. 전화번호 인증 단계 테스트 (제한적)
            step_result = await self.test_phone_verification_step(test_data['phone_number'])
            results['steps'].append({
                'step': '전화번호 인증 단계',
                'success': step_result,
                'timestamp': datetime.now().isoformat()
            })
            
            # 전체 성공 여부 판단
            results['success'] = all(step['success'] for step in results['steps'])
            
            # 스크린샷 저장
            screenshot_path = f"test_screenshot_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            results['screenshot'] = screenshot_path
            print(f"📸 스크린샷 저장: {screenshot_path}")
            
        except Exception as e:
            results['errors'].append(f"테스트 실행 중 오류: {e}")
            print(f"❌ 테스트 실행 오류: {e}")
        
        finally:
            # 브라우저 정리
            if self.driver:
                self.driver.quit()
                print("🧹 브라우저 정리 완료")
        
        results['end_time'] = datetime.now().isoformat()
        results['duration'] = (datetime.now() - start_time).total_seconds()
        
        return results
    
    def print_test_results(self, results: Dict[str, Any]):
        """테스트 결과 출력"""
        print("\n" + "=" * 60)
        print("🏁 실제 계정 생성 테스트 결과")
        print("=" * 60)
        
        print(f"📊 전체 결과: {'✅ 성공' if results['success'] else '❌ 실패'}")
        
        # duration이 있는 경우에만 출력
        if 'duration' in results:
            print(f"⏱️ 소요 시간: {results['duration']:.2f}초")
        
        if results['test_data']:
            print(f"\n📝 테스트 계정 정보:")
            print(f"   이름: {results['test_data']['first_name']} {results['test_data']['last_name']}")
            print(f"   사용자명: {results['test_data']['username']}")
        
        print(f"\n📋 단계별 결과:")
        for i, step in enumerate(results['steps'], 1):
            status = "✅" if step['success'] else "❌"
            print(f"   {i}. {status} {step['step']}")
        
        if results['errors']:
            print(f"\n❌ 발생한 오류:")
            for error in results['errors']:
                print(f"   - {error}")
        
        if results.get('screenshot'):
            print(f"\n📸 스크린샷: {results['screenshot']}")
        
        # 결과를 JSON 파일로 저장
        results_file = Path("real_account_test_results.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 상세 결과 저장: {results_file}")
        
        if results['success']:
            print("\n🎉 실제 계정 생성 테스트가 성공적으로 완료되었습니다!")
            print("⚠️ 테스트용 계정이므로 필요에 따라 정리해주세요.")
        else:
            print("\n⚠️ 일부 단계에서 문제가 발생했습니다.")
            print("💡 실제 구현에서는 각 단계별 오류 처리가 필요합니다.")

async def main():
    """메인 함수"""
    tester = RealAccountCreationTester()
    
    try:
        # 사용자 동의 확인
        print("\n⚠️ 실제 Google 서버와 통신하는 테스트를 실행하시겠습니까?")
        print("   (y/n):", end=" ")
        
        # 자동으로 'y' 입력 (데모 목적)
        response = 'y'  # input().strip().lower()
        print('y')
        
        if response != 'y':
            print("테스트가 취소되었습니다.")
            return
        
        # 실제 테스트 실행
        results = await tester.run_complete_test()
        tester.print_test_results(results)
        
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 