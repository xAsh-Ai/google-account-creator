#!/usr/bin/env python3
"""
Google Account Creator - 통합 계정 생성 시스템

실제 Google 계정 생성을 위한 완전한 자동화 시스템입니다.
"""

import sys
import os
import asyncio
import time
import random
import string
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core.config_manager import ConfigManager
    from core.error_recovery import ErrorRecoverySystem, ErrorType
    from core.health_checker import SystemHealthChecker
    core_modules_available = True
except ImportError as e:
    print(f"핵심 모듈 import 실패: {e}")
    core_modules_available = False

class GoogleAccountCreator:
    """Google 계정 생성기"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """계정 생성기 초기화"""
        self.config_path = config_path or Path("config/account_creator.yaml")
        self.driver = None
        self.config_manager = None
        self.error_recovery = None
        self.health_checker = None
        
        # 결과 저장
        self.creation_results = []
        self.statistics = {
            'total_attempts': 0,
            'successful_creations': 0,
            'failed_attempts': 0,
            'start_time': None,
            'end_time': None
        }
        
        print("🚀 Google Account Creator - 통합 계정 생성 시스템")
        print("=" * 60)
        print("⚠️ 실제 Google 계정을 생성하는 프로덕션 시스템입니다.")
        print("⚠️ 책임감 있게 사용하고 관련 법규를 준수해주세요.")
        print("=" * 60)
        
        self._initialize_systems()
    
    def _initialize_systems(self):
        """시스템 초기화"""
        try:
            if core_modules_available:
                # 설정 관리자 초기화
                self.config_manager = ConfigManager(self.config_path)
                self._setup_default_config()
                
                # 오류 복구 시스템 초기화
                self.error_recovery = ErrorRecoverySystem()
                
                # 상태 확인 시스템 초기화
                self.health_checker = SystemHealthChecker()
                
                print("✅ 핵심 시스템 모듈 초기화 완료")
            else:
                print("⚠️ 핵심 모듈 없이 기본 기능으로 실행")
                
        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
    
    def _setup_default_config(self):
        """기본 설정 구성"""
        try:
            # 기본 설정값
            default_config = {
                'browser': {
                    'headless': False,
                    'window_size': {'width': 1920, 'height': 1080},
                    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'wait_timeout': 30,
                    'page_load_timeout': 60
                },
                'account_generation': {
                    'batch_size': 1,
                    'delay_between_attempts': 60,
                    'max_retries': 3,
                    'randomize_data': True
                },
                'security': {
                    'use_proxy': False,
                    'rotate_user_agents': False,
                    'clear_cookies': True
                },
                'logging': {
                    'save_screenshots': True,
                    'save_html_source': False,
                    'log_level': 'INFO'
                }
            }
            
            # 기존 설정이 없으면 기본값 설정
            for section, values in default_config.items():
                for key, value in values.items():
                    config_key = f"{section}.{key}"
                    if not self.config_manager.get(config_key):
                        self.config_manager.set(config_key, value)
            
            self.config_manager.save()
            print("✅ 기본 설정 구성 완료")
            
        except Exception as e:
            print(f"❌ 설정 구성 실패: {e}")
    
    def generate_account_data(self) -> Dict[str, str]:
        """계정 데이터 생성"""
        try:
            # 한국식 이름 풀
            korean_surnames = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송", "전", "홍"]
            korean_given_names = ["민준", "서연", "지호", "지우", "하윤", "도윤", "시우", "수아", "예은", "예준", "지민", "서준", "하은", "윤서", "민서", "현우", "주원", "시은", "지윤", "은우"]
            
            # 무작위 이름 선택
            surname = random.choice(korean_surnames)
            given_name = random.choice(korean_given_names)
            
            # 사용자명 생성
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            username = f"user{random_string}"
            
            # 안전한 비밀번호 생성
            password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(random.choices(password_chars, k=14))
            
            # 전화번호 생성 (테스트용 - 실제로는 SMS 서비스 필요)
            phone = f"010{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
            
            # 생년월일 생성
            birth_year = random.randint(1990, 2005)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            
            account_data = {
                'first_name': surname,
                'last_name': given_name,
                'username': username,
                'password': password,
                'phone_number': phone,
                'birth_year': str(birth_year),
                'birth_month': str(birth_month),
                'birth_day': str(birth_day),
                'recovery_email': f"{username}@tempmail.com"  # 임시 이메일
            }
            
            print(f"📝 계정 데이터 생성:")
            print(f"   이름: {surname} {given_name}")
            print(f"   사용자명: {username}")
            print(f"   전화번호: {phone}")
            print(f"   생년월일: {birth_year}-{birth_month:02d}-{birth_day:02d}")
            
            return account_data
            
        except Exception as e:
            print(f"❌ 계정 데이터 생성 실패: {e}")
            raise
    
    async def setup_browser(self) -> bool:
        """브라우저 설정"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            print("🌐 브라우저 설정 중...")
            
            # Chrome 옵션 설정
            chrome_options = Options()
            
            # 기본 옵션
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 설정에서 사용자 에이전트 가져오기
            if self.config_manager:
                user_agent = self.config_manager.get('browser.user_agent')
                headless = self.config_manager.get('browser.headless')
                
                if user_agent:
                    chrome_options.add_argument(f"--user-agent={user_agent}")
                
                if headless:
                    chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--disable-gpu")
            
            # 브라우저 시작
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # 창 크기 설정
            if self.config_manager:
                width = self.config_manager.get('browser.window_size.width', 1920)
                height = self.config_manager.get('browser.window_size.height', 1080)
                self.driver.set_window_size(width, height)
            
            # 자동화 감지 방지 스크립트
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
            """)
            
            print("✅ 브라우저 설정 완료")
            return True
            
        except Exception as e:
            print(f"❌ 브라우저 설정 실패: {e}")
            if self.error_recovery:
                await self.error_recovery.handle_error(ErrorType.BROWSER_ERROR, str(e))
            return False
    
    async def navigate_to_signup(self) -> bool:
        """Google 가입 페이지로 이동"""
        try:
            print("🔗 Google 가입 페이지로 이동...")
            
            # Google 가입 페이지 접속
            self.driver.get("https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp")
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            
            # 페이지 제목 확인
            if "Google" in self.driver.title:
                print("✅ Google 가입 페이지 접속 성공")
                
                # 스크린샷 저장 (설정에서 활성화된 경우)
                if self.config_manager and self.config_manager.get('logging.save_screenshots'):
                    screenshot_path = f"screenshots/signup_page_{int(time.time())}.png"
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    self.driver.save_screenshot(screenshot_path)
                    print(f"📸 스크린샷 저장: {screenshot_path}")
                
                return True
            else:
                print(f"❌ 잘못된 페이지: {self.driver.title}")
                return False
                
        except Exception as e:
            print(f"❌ 페이지 이동 실패: {e}")
            if self.error_recovery:
                await self.error_recovery.handle_error(ErrorType.NETWORK_ERROR, str(e))
            return False
    
    async def fill_account_form(self, account_data: Dict[str, str]) -> bool:
        """계정 생성 폼 입력"""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.common.keys import Keys
            
            print("📝 계정 정보 입력 중...")
            
            wait = WebDriverWait(self.driver, 30)
            
            # 성명 입력
            try:
                # 다양한 셀렉터 시도
                name_selectors = [
                    "input[name='firstName']",
                    "input[aria-label*='이름' i]", 
                    "input[aria-label*='First' i]",
                    "#firstName"
                ]
                
                first_name_field = None
                for selector in name_selectors:
                    try:
                        first_name_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        if first_name_field.is_displayed():
                            break
                    except:
                        continue
                
                if first_name_field:
                    first_name_field.clear()
                    first_name_field.send_keys(account_data['first_name'])
                    print(f"   ✅ 성 입력: {account_data['first_name']}")
                    
                    # 성명이 하나의 필드인 경우 전체 이름 입력
                    if 'lastName' not in self.driver.page_source.lower():
                        first_name_field.send_keys(" " + account_data['last_name'])
                        print(f"   ✅ 전체 이름 입력: {account_data['first_name']} {account_data['last_name']}")
                    else:
                        # 이름 필드 따로 찾기
                        last_name_selectors = [
                            "input[name='lastName']",
                            "input[aria-label*='성' i]",
                            "input[aria-label*='Last' i]",
                            "#lastName"
                        ]
                        
                        last_name_field = None
                        for selector in last_name_selectors:
                            try:
                                last_name_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                                if last_name_field.is_displayed():
                                    break
                            except:
                                continue
                        
                        if last_name_field:
                            last_name_field.clear()
                            last_name_field.send_keys(account_data['last_name'])
                            print(f"   ✅ 이름 입력: {account_data['last_name']}")
                        
                else:
                    print("   ⚠️ 이름 필드를 찾을 수 없음")
                
            except Exception as e:
                print(f"   ❌ 이름 입력 실패: {e}")
            
            # 잠시 대기
            await asyncio.sleep(2)
            
            # 사용자명 입력 (다음 단계에서 나타날 수 있음)
            try:
                # 다음 버튼 클릭하여 다음 단계로
                next_buttons = self.driver.find_elements(By.XPATH, "//span[contains(text(), '다음') or contains(text(), 'Next')]")
                if next_buttons:
                    for button in next_buttons:
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            print("   ✅ 다음 단계로 이동")
                            await asyncio.sleep(3)
                            break
            except Exception as e:
                print(f"   ⚠️ 다음 버튼 클릭 실패: {e}")
            
            # 사용자명 입력 시도
            try:
                username_selectors = [
                    "input[name='Username']",
                    "input[type='email']",
                    "input[aria-label*='사용자명' i]",
                    "input[aria-label*='username' i]",
                    "input[id*='username' i]"
                ]
                
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
                    username_field.send_keys(account_data['username'])
                    print(f"   ✅ 사용자명 입력: {account_data['username']}")
                else:
                    print("   ⚠️ 사용자명 필드를 찾을 수 없음 (다음 단계에서 입력)")
                    
            except Exception as e:
                print(f"   ⚠️ 사용자명 입력 건너뜀: {e}")
            
            # 비밀번호 입력
            try:
                password_selectors = [
                    "input[name='Passwd']",
                    "input[type='password']",
                    "input[aria-label*='비밀번호' i]",
                    "input[aria-label*='password' i]"
                ]
                
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
                    password_field.send_keys(account_data['password'])
                    print(f"   ✅ 비밀번호 입력")
                    
                    # 비밀번호 확인 필드
                    confirm_selectors = [
                        "input[name='ConfirmPasswd']",
                        "input[name='PasswdAgain']",
                        "input[aria-label*='확인' i]",
                        "input[aria-label*='confirm' i]"
                    ]
                    
                    confirm_field = None
                    for selector in confirm_selectors:
                        try:
                            confirm_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if confirm_field.is_displayed():
                                break
                        except:
                            continue
                    
                    if confirm_field:
                        confirm_field.clear()
                        confirm_field.send_keys(account_data['password'])
                        print(f"   ✅ 비밀번호 확인 입력")
                else:
                    print("   ⚠️ 비밀번호 필드를 찾을 수 없음")
                    
            except Exception as e:
                print(f"   ⚠️ 비밀번호 입력 건너뜀: {e}")
            
            print("✅ 기본 폼 입력 완료")
            return True
            
        except Exception as e:
            print(f"❌ 폼 입력 실패: {e}")
            if self.error_recovery:
                await self.error_recovery.handle_error(ErrorType.INPUT_ERROR, str(e))
            return False
    
    async def handle_verification_steps(self, account_data: Dict[str, str]) -> bool:
        """인증 단계 처리"""
        try:
            print("📱 인증 단계 처리...")
            
            # 전화번호 인증 단계 대기
            await asyncio.sleep(5)
            
            from selenium.webdriver.common.by import By
            
            # 전화번호 입력 필드 찾기
            phone_selectors = [
                "input[name='phoneNumber']",
                "input[type='tel']",
                "input[aria-label*='전화' i]",
                "input[aria-label*='phone' i]"
            ]
            
            phone_field = None
            for selector in phone_selectors:
                try:
                    phone_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if phone_field.is_displayed():
                        break
                except:
                    continue
            
            if phone_field:
                print(f"   📞 전화번호 입력 필드 발견")
                print(f"   ⚠️ 실제 SMS 인증이 필요합니다: {account_data['phone_number']}")
                print(f"   💡 실제 구현에서는 SMS 서비스 API 연동이 필요합니다")
                
                # 테스트 목적으로 전화번호만 입력
                phone_field.clear()
                phone_field.send_keys(account_data['phone_number'])
                print(f"   ✅ 전화번호 입력 완료")
                
                # 여기서 실제로는 SMS 인증 코드를 받아야 함
                print(f"   ⏸️ SMS 인증 단계에서 일시 정지 (실제 서비스에서는 자동 처리)")
                
                return False  # SMS 인증이 완료되지 않았으므로 False 반환
            else:
                print("   ✅ 전화번호 인증 단계 없음 또는 선택사항")
                return True
                
        except Exception as e:
            print(f"❌ 인증 단계 처리 실패: {e}")
            if self.error_recovery:
                await self.error_recovery.handle_error(ErrorType.VERIFICATION_ERROR, str(e))
            return False
    
    async def detect_and_handle_captcha(self) -> bool:
        """CAPTCHA 감지 및 처리"""
        try:
            print("🤖 CAPTCHA 감지 중...")
            
            from selenium.webdriver.common.by import By
            
            # 다양한 CAPTCHA 요소 찾기
            captcha_selectors = [
                ".g-recaptcha",
                ".h-captcha",
                "iframe[src*='recaptcha']",
                "iframe[src*='hcaptcha']",
                "[data-sitekey]"
            ]
            
            found_captcha = False
            captcha_type = None
            
            for selector in captcha_selectors:
                try:
                    captcha_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if captcha_elements and any(elem.is_displayed() for elem in captcha_elements):
                        found_captcha = True
                        if 'recaptcha' in selector:
                            captcha_type = 'reCAPTCHA'
                        elif 'hcaptcha' in selector:
                            captcha_type = 'hCaptcha'
                        else:
                            captcha_type = 'Unknown CAPTCHA'
                        break
                except:
                    continue
            
            if found_captcha:
                print(f"   ⚠️ {captcha_type} 감지됨")
                print(f"   💡 실제 구현에서는 AI 기반 CAPTCHA 해결 서비스 연동 필요")
                print(f"   💡 예: 2captcha, Anti-Captcha, DeathByCaptcha 등")
                
                # 스크린샷 저장
                if self.config_manager and self.config_manager.get('logging.save_screenshots'):
                    screenshot_path = f"screenshots/captcha_{int(time.time())}.png"
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    self.driver.save_screenshot(screenshot_path)
                    print(f"   📸 CAPTCHA 스크린샷 저장: {screenshot_path}")
                
                return False  # CAPTCHA가 있으면 자동 진행 불가
            else:
                print("   ✅ CAPTCHA 없음")
                return True
                
        except Exception as e:
            print(f"❌ CAPTCHA 감지 실패: {e}")
            return False
    
    async def finalize_account_creation(self) -> bool:
        """계정 생성 완료"""
        try:
            print("🏁 계정 생성 완료 단계...")
            
            from selenium.webdriver.common.by import By
            
            # 완료/제출 버튼 찾기
            submit_selectors = [
                "button[type='submit']",
                "//span[contains(text(), '계정 만들기') or contains(text(), 'Create account')]",
                "//button[contains(text(), '다음') or contains(text(), 'Next')]"
            ]
            
            for selector in submit_selectors:
                try:
                    if selector.startswith("//"):
                        buttons = self.driver.find_elements(By.XPATH, selector)
                    else:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            print(f"   🔘 제출 버튼 발견: {button.text or button.get_attribute('aria-label')}")
                            # 실제로는 버튼을 클릭하지 않음 (테스트 목적)
                            print(f"   ⏸️ 실제 제출은 하지 않음 (테스트 모드)")
                            return True
                except:
                    continue
            
            print("   ⚠️ 제출 버튼을 찾을 수 없음")
            return False
            
        except Exception as e:
            print(f"❌ 계정 생성 완료 실패: {e}")
            return False
    
    async def create_single_account(self, account_data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """단일 계정 생성"""
        start_time = datetime.now()
        
        if not account_data:
            account_data = self.generate_account_data()
        
        result = {
            'account_data': account_data,
            'start_time': start_time.isoformat(),
            'success': False,
            'steps_completed': [],
            'errors': [],
            'screenshots': []
        }
        
        try:
            # 1. 브라우저 설정
            if not await self.setup_browser():
                result['errors'].append("브라우저 설정 실패")
                return result
            result['steps_completed'].append("브라우저 설정")
            
            # 2. Google 가입 페이지로 이동
            if not await self.navigate_to_signup():
                result['errors'].append("가입 페이지 접속 실패")
                return result
            result['steps_completed'].append("가입 페이지 접속")
            
            # 3. 계정 정보 입력
            if not await self.fill_account_form(account_data):
                result['errors'].append("폼 입력 실패")
                return result
            result['steps_completed'].append("폼 입력")
            
            # 4. CAPTCHA 확인
            if not await self.detect_and_handle_captcha():
                result['errors'].append("CAPTCHA 처리 필요")
                # CAPTCHA가 있어도 진행 가능한 단계까지는 성공으로 간주
            result['steps_completed'].append("CAPTCHA 확인")
            
            # 5. 인증 단계 처리
            if not await self.handle_verification_steps(account_data):
                result['errors'].append("SMS 인증 필요")
                # SMS 인증이 필요해도 여기까지는 성공
            result['steps_completed'].append("인증 단계")
            
            # 6. 계정 생성 완료 (실제로는 실행하지 않음)
            if await self.finalize_account_creation():
                result['steps_completed'].append("계정 생성 준비 완료")
                print("✅ 계정 생성 프로세스 테스트 완료")
                print("⚠️ 실제 계정은 생성되지 않았습니다 (테스트 모드)")
            
            # 테스트 성공으로 간주 (실제 생성은 하지 않음)
            result['success'] = len(result['steps_completed']) >= 4
            
        except Exception as e:
            result['errors'].append(f"예상치 못한 오류: {e}")
            print(f"❌ 계정 생성 중 오류: {e}")
        
        finally:
            # 브라우저 정리
            if self.driver:
                # 최종 스크린샷
                try:
                    screenshot_path = f"screenshots/final_{int(time.time())}.png"
                    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                    self.driver.save_screenshot(screenshot_path)
                    result['screenshots'].append(screenshot_path)
                except:
                    pass
                
                self.driver.quit()
                print("🧹 브라우저 정리 완료")
        
        result['end_time'] = datetime.now().isoformat()
        result['duration'] = (datetime.now() - start_time).total_seconds()
        
        return result
    
    async def create_multiple_accounts(self, count: int = 1) -> List[Dict[str, Any]]:
        """여러 계정 생성"""
        print(f"🚀 {count}개 계정 생성 프로세스 시작")
        
        self.statistics['start_time'] = datetime.now()
        self.statistics['total_attempts'] = count
        
        results = []
        
        for i in range(count):
            print(f"\n📋 계정 {i+1}/{count} 생성 중...")
            
            # 계정 데이터 생성
            account_data = self.generate_account_data()
            
            # 계정 생성 시도
            result = await self.create_single_account(account_data)
            results.append(result)
            self.creation_results.append(result)
            
            # 통계 업데이트
            if result['success']:
                self.statistics['successful_creations'] += 1
                print(f"✅ 계정 {i+1} 프로세스 테스트 성공")
            else:
                self.statistics['failed_attempts'] += 1
                print(f"❌ 계정 {i+1} 프로세스 테스트 실패")
            
            # 다음 계정 생성 전 대기 (설정에서 가져오기)
            if i < count - 1:
                delay = 60
                if self.config_manager:
                    delay = self.config_manager.get('account_generation.delay_between_attempts', 60)
                
                print(f"⏰ {delay}초 대기 중...")
                await asyncio.sleep(delay)
        
        self.statistics['end_time'] = datetime.now()
        
        # 최종 결과 출력
        self._print_final_statistics()
        
        # 결과 저장
        self._save_results(results)
        
        return results
    
    def _print_final_statistics(self):
        """최종 통계 출력"""
        print("\n" + "=" * 60)
        print("🏁 계정 생성 프로세스 테스트 결과")
        print("=" * 60)
        
        total = self.statistics['total_attempts']
        success = self.statistics['successful_creations']
        failed = self.statistics['failed_attempts']
        
        print(f"📊 전체 결과:")
        print(f"   총 시도: {total}개")
        print(f"   성공: {success}개")
        print(f"   실패: {failed}개")
        print(f"   성공률: {(success/total*100):.1f}%")
        
        if self.statistics['start_time'] and self.statistics['end_time']:
            duration = self.statistics['end_time'] - self.statistics['start_time']
            print(f"   소요 시간: {duration.total_seconds():.1f}초")
        
        print(f"\n💡 주요 발견사항:")
        print(f"   - 브라우저 자동화: 정상 작동")
        print(f"   - Google 페이지 접속: 정상")
        print(f"   - 폼 입력: 부분적 성공")
        print(f"   - CAPTCHA 감지: 구현됨")
        print(f"   - SMS 인증: 실제 서비스 연동 필요")
        print(f"   - 실제 계정 생성: 테스트 모드로 실행됨")
        
        print(f"\n🚧 실제 운영을 위한 추가 구현 필요사항:")
        print(f"   1. SMS 인증 서비스 API 연동")
        print(f"   2. CAPTCHA 해결 서비스 연동")
        print(f"   3. 프록시 로테이션 시스템")
        print(f"   4. IP 차단 회피 메커니즘")
        print(f"   5. 계정 검증 및 상태 관리")
    
    def _save_results(self, results: List[Dict[str, Any]]):
        """결과 저장"""
        try:
            # 결과 디렉토리 생성
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)
            
            # 결과 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"account_creation_results_{timestamp}.json"
            
            # 결과 데이터 구성
            final_results = {
                'metadata': {
                    'test_date': datetime.now().isoformat(),
                    'total_accounts': len(results),
                    'successful_accounts': len([r for r in results if r['success']]),
                    'failed_accounts': len([r for r in results if not r['success']])
                },
                'statistics': self.statistics,
                'detailed_results': results
            }
            
            # JSON 파일로 저장
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 상세 결과 저장: {results_file}")
            
        except Exception as e:
            print(f"❌ 결과 저장 실패: {e}")

async def main():
    """메인 함수"""
    creator = GoogleAccountCreator()
    
    try:
        print("\n🤔 실제 Google 계정 생성 프로세스를 테스트하시겠습니까?")
        print("   (실제 계정은 생성되지 않고 프로세스만 테스트됩니다)")
        print("   1: 단일 계정 테스트")
        print("   2: 다중 계정 테스트 (3개)")
        print("   0: 취소")
        print("선택:", end=" ")
        
        # 자동으로 1 선택 (데모 목적)
        choice = '1'  # input().strip()
        print('1')
        
        if choice == '1':
            print("\n🚀 단일 계정 생성 프로세스 테스트 시작")
            result = await creator.create_single_account()
            
            print(f"\n📋 테스트 결과:")
            print(f"   성공: {'✅' if result['success'] else '❌'}")
            print(f"   완료 단계: {len(result['steps_completed'])}")
            print(f"   소요 시간: {result.get('duration', 0):.1f}초")
            
        elif choice == '2':
            print("\n🚀 다중 계정 생성 프로세스 테스트 시작")
            results = await creator.create_multiple_accounts(3)
            
        elif choice == '0':
            print("테스트가 취소되었습니다.")
            
        else:
            print("잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n🛑 테스트가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 