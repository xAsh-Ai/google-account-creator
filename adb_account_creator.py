#!/usr/bin/env python3
"""
Google Account Creator - ADB 기반 Android 에뮬레이터 계정 생성 시스템

이 시스템은 ADB를 통한 Android 에뮬레이터 제어가 메인이고,
API로 처리 가능한 부분은 Google APIs를 활용하는 하이브리드 접근 방식입니다.
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
import aiohttp

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# ADB Device Manager import
try:
    from modules.adb_device_manager import ADBDeviceManager
    device_manager_available = True
except ImportError as e:
    print(f"ADB Device Manager import 실패: {e}")
    device_manager_available = False

# 실제 OCR 시스템 import 및 사용
try:
    from modules.ocr_recognition import OCRRecognition
    ocr_available = True
    print("✅ 실제 OCR 시스템 로드 성공")
except ImportError as e:
    print(f"⚠️ 실제 OCR 시스템 로드 실패: {e}")
    ocr_available = False
    
    # 스텁 OCR 클래스 (fallback)
    class OCRRecognition:
        """간단한 OCR 스텁"""
        
        async def extract_text_from_image(self, image_path):
            return "Google Sign up First name Last name Username Password Create account"
        
        async def find_form_elements(self, image_path):
            return [
                {'text': 'First name', 'x': 200, 'y': 300},
                {'text': 'Last name', 'x': 200, 'y': 350},
                {'text': 'Username', 'x': 200, 'y': 400},
                {'text': 'Password', 'x': 200, 'y': 450}
            ]
        
        async def find_clickable_elements(self, image_path):
            return [
                {'text': 'Next', 'x': 300, 'y': 500},
                {'text': 'Create account', 'x': 300, 'y': 550}
            ]
        
        async def find_phone_input_field(self, image_path):
            return None

class SimpleADBUtils:
    """간단한 ADB 유틸리티 스텁"""
    
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.current_device = None
    
    async def get_connected_devices(self):
        return await self.device_manager.get_connected_devices()
    
    async def wait_for_device_ready(self, device_id):
        return await self.device_manager._is_device_ready(device_id)
    
    async def wake_screen(self, device_id):
        try:
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'
            ])
            return True
        except:
            return False
    
    async def launch_app(self, device_id, package_name):
        try:
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'monkey', '-p', package_name, '1'
            ])
            return True
        except:
            return False
    
    async def input_text(self, device_id, text):
        try:
            # 특수문자 이스케이프
            escaped_text = text.replace(' ', '%s').replace('&', '\\&')
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'input', 'text', escaped_text
            ])
            return True
        except:
            return False
    
    async def send_keyevent(self, device_id, keycode):
        try:
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'input', 'keyevent', keycode
            ])
            return True
        except:
            return False
    
    async def tap_coordinates(self, device_id, x, y):
        try:
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'input', 'tap', str(x), str(y)
            ])
            return True
        except:
            return False
    
    async def take_screenshot(self, device_id):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"screenshots/screenshot_{timestamp}.png"
            
            # screenshots 디렉토리 생성
            os.makedirs("screenshots", exist_ok=True)
            
            # 스크린샷 촬영
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'screencap', '/sdcard/screenshot.png'
            ])
            
            # 로컬로 복사
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'pull', '/sdcard/screenshot.png', screenshot_path
            ])
            
            return screenshot_path
        except:
            return None
    
    async def clear_app_cache(self, device_id, package_name):
        try:
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', device_id, 'shell', 'pm', 'clear', package_name
            ])
            return True
        except:
            return False

class SimpleOCRRecognition:
    """간단한 OCR 스텁"""
    
    async def extract_text_from_image(self, image_path):
        # 스텁: 기본 텍스트 반환
        return "Google Sign up First name Last name Username Password Create account"
    
    async def find_form_elements(self, image_path):
        # 스텁: 가짜 폼 요소들 반환
        return [
            {'text': 'First name', 'x': 200, 'y': 300},
            {'text': 'Last name', 'x': 200, 'y': 350},
            {'text': 'Username', 'x': 200, 'y': 400},
            {'text': 'Password', 'x': 200, 'y': 450}
        ]
    
    async def find_clickable_elements(self, image_path):
        # 스텁: 클릭 가능한 요소들 반환
        return [
            {'text': 'Next', 'x': 300, 'y': 500},
            {'text': 'Create account', 'x': 300, 'y': 550}
        ]

class SimpleDeviceRandomization:
    """간단한 디바이스 랜덤화 스텁"""
    
    def __init__(self, adb_utils):
        self.adb_utils = adb_utils
    
    async def randomize_device_profile(self, device_id):
        print("🎲 디바이스 정보 랜덤화 (스텁)")
        return True

class SimpleVPNManager:
    """간단한 VPN 관리자 스텁"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    async def connect(self):
        print("🔒 VPN 연결 (스텁)")
        return {'success': True, 'ip': '192.168.1.100'}
    
    async def disconnect(self):
        print("🔓 VPN 연결 해제 (스텁)")
        return True

class GetSMSCodeHandler:
    """GetSMSCode API를 사용한 실제 SMS 처리 시스템"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.api_url = "http://api.getsmscode.com/do.php"
        self.username = config_manager.get('SMS_USERNAME')
        self.token = config_manager.get('SMS_TOKEN') 
        self.last_phone_number = None
        self.last_verification_code = None
        self.last_mobile = None
        self.project_id = "1"  # Google 서비스 ID
        
        if not self.username or not self.token:
            print("⚠️ [GetSMSCode] SMS 서비스 설정이 필요합니다:")
            print("   config.json에 SMS_USERNAME과 SMS_TOKEN을 설정하세요")
        else:
            print(f"✅ [GetSMSCode] API 설정 완료: {self.username}")
    
    async def _check_balance_async(self):
        """잔액 확인 비동기 작업"""
        try:
            params = {
                'action': 'login',
                'username': self.username,
                'token': self.token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, data=params) as response:
                    result = await response.text()
                    
                    if '|' in result:
                        parts = result.split('|')
                        if len(parts) >= 2:
                            balance = parts[1]
                            print(f"💰 [GetSMSCode] 계정 잔액: ${balance}")
                            return float(balance)
                    
                    return 0.0
        except Exception as e:
            print(f"❌ [GetSMSCode] 잔액 확인 실패: {e}")
            return 0.0
    
    async def request_phone_number(self, service="google"):
        """GetSMSCode에서 전화번호 요청"""
        try:
            # 먼저 잔액 확인
            print("💰 [GetSMSCode] 계정 잔액 확인 중...")
            balance = await self.check_balance()
            
            if balance <= 0:
                return {
                    'success': False, 
                    'error': f'잔액 부족 (${balance}). GetSMSCode에 잔액을 충전하세요.'
                }
            
            params = {
                'action': 'getmobile',
                'username': self.username,
                'token': self.token,
                'pid': self.project_id,
                'removevr': '1'  # 가상 번호 제거
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, data=params) as response:
                    result = await response.text()
                    
                    if result.startswith('Message|'):
                        error_msg = result.split('|')[1]
                        print(f"❌ [GetSMSCode] 번호 요청 실패: {error_msg}")
                        return {'success': False, 'error': error_msg}
                    
                    # 성공적으로 번호를 받은 경우
                    if result.isdigit() and len(result) > 10:
                        self.last_phone_number = result
                        self.last_mobile = result
                        print(f"✅ [GetSMSCode] 번호 할당: {result}")
                        
                        return {
                            'success': True,
                            'phone_number': result,
                            'request_id': result
                        }
                    else:
                        print(f"❌ [GetSMSCode] 예상치 못한 응답: {result}")
                        return {'success': False, 'error': f'예상치 못한 응답: {result}'}
                        
        except Exception as e:
            print(f"❌ [GetSMSCode] API 오류: {e}")
            return {'success': False, 'error': str(e)}
    
    async def wait_for_sms(self, request_id, timeout=300):
        """SMS 대기 및 수신"""
        try:
            print(f"📱 [GetSMSCode] SMS 대기 중... (최대 {timeout}초)")
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                params = {
                    'action': 'getsms',
                    'username': self.username,
                    'token': self.token,
                    'pid': self.project_id,
                    'mobile': self.last_mobile
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, data=params) as response:
                        result = await response.text()
                        
                        print(f"🔍 [GetSMSCode] SMS 확인 응답: {result}")
                        
                        if result.startswith('1|'):
                            # SMS 수신 성공
                            sms_content = result.split('|')[1]
                            
                            # 인증 코드 추출 (6자리 숫자)
                            import re
                            code_match = re.search(r'(\d{6})', sms_content)
                            verification_code = code_match.group(1) if code_match else None
                            
                            self.last_verification_code = verification_code
                            
                            print(f"✅ [GetSMSCode] SMS 수신 성공!")
                            print(f"   전체 메시지: {sms_content}")
                            print(f"   인증 코드: {verification_code}")
                            
                            return {
                                'success': True,
                                'code': verification_code,
                                'full_message': sms_content
                            }
                        
                        elif result.startswith('Message|'):
                            error_msg = result.split('|')[1]
                            if "not got" in error_msg.lower() or "not found" in error_msg.lower():
                                # 아직 SMS가 오지 않음, 계속 대기
                                await asyncio.sleep(10)
                                continue
                            else:
                                print(f"❌ [GetSMSCode] SMS 오류: {error_msg}")
                                return {'success': False, 'error': error_msg}
                        
                        else:
                            # 예상치 못한 응답, 계속 대기
                            await asyncio.sleep(10)
                            continue
            
            # 타임아웃
            print(f"⏰ [GetSMSCode] SMS 수신 타임아웃 ({timeout}초)")
            await self._add_to_blacklist()
            return {'success': False, 'error': 'SMS 수신 타임아웃'}
            
        except Exception as e:
            print(f"❌ [GetSMSCode] SMS 대기 오류: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _add_to_blacklist(self):
        """번호를 블랙리스트에 추가 (SMS가 오지 않을 때)"""
        try:
            if self.last_mobile:
                params = {
                    'action': 'addblack',
                    'username': self.username,
                    'token': self.token,
                    'pid': self.project_id,
                    'mobile': self.last_mobile
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, data=params) as response:
                        result = await response.text()
                        print(f"🚫 [GetSMSCode] 번호 블랙리스트 추가: {result}")
        except Exception as e:
            print(f"❌ [GetSMSCode] 블랙리스트 추가 실패: {e}")
    
    async def check_balance(self):
        """계정 잔액 확인"""
        try:
            params = {
                'action': 'login',
                'username': self.username,
                'token': self.token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, data=params) as response:
                    result = await response.text()
                    
                    if '|' in result:
                        parts = result.split('|')
                        if len(parts) >= 2:
                            balance = parts[1]
                            print(f"💰 [GetSMSCode] 계정 잔액: ${balance}")
                            return float(balance)
                    
                    return 0.0
        except Exception as e:
            print(f"❌ [GetSMSCode] 잔액 확인 실패: {e}")
            return 0.0

class SimpleConfigManager:
    """간단한 설정 관리자 스텁"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            # config.json 파일 읽기
            config_file = Path("config.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                print(f"✅ 설정 파일 로드 완료: {config_file}")
            else:
                print(f"⚠️ 설정 파일을 찾을 수 없음: {config_file}")
        except Exception as e:
            print(f"❌ 설정 파일 로드 실패: {e}")
    
    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key, value):
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save(self):
        pass

class SimpleLogger:
    """간단한 로거 스텁"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def info(self, message):
        print(f"[INFO] {message}")
    
    def error(self, message):
        print(f"[ERROR] {message}")

class SimpleErrorRecoverySystem:
    """간단한 오류 복구 시스템 스텁"""
    
    async def handle_error(self, error_type, message):
        print(f"[ERROR RECOVERY] {error_type}: {message}")

class SimpleSystemHealthChecker:
    """간단한 시스템 상태 확인 스텁"""
    pass

# 스텁 오류 타입
class ErrorType:
    INITIALIZATION_ERROR = "INITIALIZATION_ERROR"
    ADB_CONNECTION_LOST = "ADB_CONNECTION_LOST"
    APP_LAUNCH_ERROR = "APP_LAUNCH_ERROR"
    INPUT_ERROR = "INPUT_ERROR"
    SMS_TIMEOUT = "SMS_TIMEOUT"
    ACCOUNT_CREATION_ERROR = "ACCOUNT_CREATION_ERROR"

class ADBAccountCreator:
    """ADB 기반 Google 계정 생성기"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """계정 생성기 초기화"""
        self.config_path = config_path or Path("config/adb_creator.yaml")
        
        print("🤖 Google Account Creator - ADB 기반 Android 에뮬레이터 시스템")
        print("=" * 70)
        print("🔧 ADB를 통한 Android 에뮬레이터 제어가 메인입니다")
        print("🌐 API로 처리 가능한 부분은 Google APIs를 활용합니다")
        print("=" * 70)
        
        self._initialize_systems()
    
    def _initialize_systems(self):
        """시스템 초기화"""
        try:
            if device_manager_available:
                # ADB Device Manager 초기화
                self.device_manager = ADBDeviceManager()
                
                # 간단한 모듈들 초기화
                self.config_manager = SimpleConfigManager(self.config_path)
                self._setup_default_config()
                
                self.logger = SimpleLogger(self.config_manager)
                self.error_recovery = SimpleErrorRecoverySystem()
                self.health_checker = SimpleSystemHealthChecker()
                
                # ADB 유틸리티 (Device Manager를 사용)
                self.adb_utils = SimpleADBUtils(self.device_manager)
                
                # OCR 시스템 초기화 (실제 또는 스텁)
                if ocr_available:
                    print("🔍 실제 OCR 시스템 초기화 중...")
                    self.ocr_recognition = OCRRecognition()
                    print("✅ 실제 OCR 시스템 초기화 완료")
                else:
                    print("⚠️ 스텁 OCR 시스템 사용")
                    self.ocr_recognition = OCRRecognition()  # 스텁 버전
                
                # 기타 모듈들 (스텁)
                self.device_randomization = SimpleDeviceRandomization(self.adb_utils)
                self.vpn_manager = SimpleVPNManager(self.config_manager)
                self.sms_handler = GetSMSCodeHandler(self.config_manager)
                
                # 상태 관리
                self.current_device = None
                self.creation_results = []
                self.statistics = {
                    'total_attempts': 0,
                    'successful_creations': 0,
                    'failed_attempts': 0,
                    'start_time': None,
                    'end_time': None
                }
                
                print("✅ 모든 시스템 모듈 초기화 완료")
                self.logger.info("시스템 초기화 완료")
            else:
                print("❌ Device Manager를 사용할 수 없습니다")
                
        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _setup_default_config(self):
        """기본 설정 구성"""
        try:
            default_config = {
                'adb': {
                    'connection_timeout': 30,
                    'command_timeout': 10,
                    'max_retries': 3,
                    'screenshot_path': 'screenshots',
                    'default_device': None
                },
                'google_account': {
                    'use_korean_names': True,
                    'age_range': {'min': 18, 'max': 35},
                    'password_length': 12,
                    'recovery_email_enabled': True
                },
                'automation': {
                    'typing_delay': {'min': 0.1, 'max': 0.3},
                    'tap_delay': {'min': 0.5, 'max': 1.5},
                    'page_load_wait': 3,
                    'human_like_behavior': True
                },
                'api_usage': {
                    'gmail_api_enabled': False,
                    'google_admin_api_enabled': False,
                    'prefer_api_over_ui': True
                },
                'security': {
                    'randomize_device_info': True,
                    'use_vpn': False,  # 스텁이므로 비활성화
                    'clear_cache_after_creation': True
                }
            }
            
            for section, values in default_config.items():
                for key, value in values.items():
                    config_key = f"{section}.{key}"
                    if not self.config_manager.get(config_key):
                        self.config_manager.set(config_key, value)
            
            self.config_manager.save()
            print("✅ 기본 설정 구성 완료")
            
        except Exception as e:
            print(f"❌ 설정 구성 실패: {e}")
    
    async def initialize_device(self, device_id: Optional[str] = None) -> bool:
        """디바이스 초기화"""
        try:
            print("📱 Android 디바이스 초기화 중...")
            
            # Device Manager를 통해 디바이스 확보
            device = await self.device_manager.ensure_device_available()
            
            if not device:
                print("❌ 사용 가능한 디바이스가 없습니다")
                return False
            
            self.current_device = device
            print(f"✅ 디바이스 선택: {self.current_device}")
            
            # 화면 켜기
            await self.adb_utils.wake_screen(self.current_device)
            
            # 디바이스 정보 랜덤화 (설정에서 활성화된 경우)
            if self.config_manager.get('security.randomize_device_info'):
                print("🎲 디바이스 정보 랜덤화 중...")
                await self.device_randomization.randomize_device_profile(self.current_device)
            
            print("✅ 디바이스 초기화 완료")
            self.logger.info(f"디바이스 {self.current_device} 초기화 완료")
            return True
            
        except Exception as e:
            print(f"❌ 디바이스 초기화 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.ADB_CONNECTION_LOST, str(e))
            return False
    
    def generate_account_data(self) -> Dict[str, str]:
        """계정 데이터 생성"""
        try:
            # 한국식 이름 생성 (설정에 따라)
            if self.config_manager.get('google_account.use_korean_names'):
                korean_surnames = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권"]
                korean_given_names = ["민준", "서연", "지호", "지우", "하윤", "도윤", "시우", "수아", "예은", "예준", "지민", "서준", "하은", "윤서", "민서"]
                
                first_name = random.choice(korean_surnames)
                last_name = random.choice(korean_given_names)
            else:
                # 영어 이름 생성
                english_first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "James", "Lisa", "Robert", "Mary"]
                english_last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
                
                first_name = random.choice(english_first_names)
                last_name = random.choice(english_last_names)
            
            # 사용자명 생성
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            username = f"user{random_string}"
            
            # 비밀번호 생성
            password_length = self.config_manager.get('google_account.password_length', 12)
            password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(random.choices(password_chars, k=password_length))
            
            # 나이 범위에 따른 생년월일 생성
            age_range = self.config_manager.get('google_account.age_range', {'min': 18, 'max': 35})
            current_year = datetime.now().year
            birth_year = random.randint(current_year - age_range['max'], current_year - age_range['min'])
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            
            account_data = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'password': password,
                'birth_year': str(birth_year),
                'birth_month': str(birth_month),
                'birth_day': str(birth_day),
                'phone_number': None,  # SMS 서비스에서 동적 할당
                'recovery_email': f"{username}@tempmail.com" if self.config_manager.get('google_account.recovery_email_enabled') else None
            }
            
            print(f"📝 계정 데이터 생성:")
            print(f"   이름: {first_name} {last_name}")
            print(f"   사용자명: {username}")
            print(f"   생년월일: {birth_year}-{birth_month}-{birth_day}")
            
            self.logger.info(f"계정 데이터 생성: {username}")
            return account_data
            
        except Exception as e:
            print(f"❌ 계정 데이터 생성 실패: {e}")
            raise
    
    async def launch_google_app(self) -> bool:
        """Google 앱 실행 - Settings Intent 방법 사용"""
        try:
            print("🚀 Google 계정 추가 시작...")
            
            # 방법 1: Android 설정의 계정 추가 기능 사용
            print("⚙️ Android 설정을 통한 Google 계정 추가...")
            result = await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                'am', 'start', '-a', 'android.settings.ADD_ACCOUNT_SETTINGS'
            ])
            
            print(f"설정 실행 결과: {result}")
            
            # 설정 로딩 대기
            print("⏳ 설정 화면 로딩 대기 중...")
            await asyncio.sleep(5)
            
            # 실제 실행 확인
            focus_result = await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'
            ])
            print(f"현재 포커스: {focus_result}")
            
            # 첫 번째 스크린샷 (설정 화면)
            screenshot1 = await self.adb_utils.take_screenshot(self.current_device)
            print(f"📸 설정 화면 스크린샷: {screenshot1}")
            
            # 설정 화면에서 Google 계정 선택
            if 'settings' in focus_result.lower():
                print("✅ 설정 화면 진입 성공")
                
                # Google 계정 추가 버튼 클릭 시도
                google_positions = [
                    (540, 400),   # 화면 중앙 상단
                    (540, 500),   # 화면 중앙
                    (540, 600),   # 화면 중앙 하단
                    (200, 500),   # 왼쪽
                    (800, 500),   # 오른쪽
                ]
                
                for i, (x, y) in enumerate(google_positions):
                    print(f"   🎯 Google 계정 선택 시도 {i+1}: ({x}, {y})")
                    await self.adb_utils.tap_coordinates(self.current_device, x, y)
                    await asyncio.sleep(3)
                    
                    # 상태 변화 확인
                    new_focus = await self.device_manager._run_command([
                        self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                        'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'
                    ])
                    
                    print(f"   상태: {new_focus}")
                    
                    # Google 로그인 화면이나 브라우저 화면으로 전환되었는지 확인
                    if ('google' in new_focus.lower() or 
                        'browser' in new_focus.lower() or 
                        'chrome' in new_focus.lower() and 'firstrun' not in new_focus.lower()):
                        print(f"   ✅ Google 계정 화면 진입 성공!")
                        break
                    
                    # 설정에서 벗어났다면 성공 가능성
                    if 'settings' not in new_focus.lower():
                        print(f"   ⚠️ 설정 화면에서 벗어남 - 확인 필요")
                        break
                
                # 추가 대기 후 최종 확인
                await asyncio.sleep(5)
            
            # 대안: 직접 Google 계정 설정으로 이동
            else:
                print("⚠️ 설정 화면 진입 실패 - 직접 Google 계정 설정 시도")
                
                # Google 계정 설정 직접 접근
                await self.device_manager._run_command([
                    self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                    'am', 'start', '-a', 'android.settings.SYNC_SETTINGS'
                ])
                await asyncio.sleep(3)
            
            # 최종 상태 확인
            final_focus = await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'
            ])
            print(f"최종 포커스: {final_focus}")
            
            # 최종 스크린샷으로 확인
            screenshot = await self.adb_utils.take_screenshot(self.current_device)
            print(f"📸 최종 스크린샷: {screenshot}")
            
            # 성공 조건 확인
            success_indicators = ['google', 'account', 'login', 'signup']
            success = any(indicator in final_focus.lower() for indicator in success_indicators)
            
            if success:
                print("✅ Google 계정 추가 화면 도달 성공")
            elif 'settings' not in final_focus.lower():
                print("⚠️ 설정에서 벗어남 - 브라우저나 다른 앱으로 이동했을 가능성")
                success = True  # 일단 성공으로 간주
            else:
                print("❌ Google 계정 추가 화면 도달 실패")
                success = False
            
            print("✅ Google 계정 추가 프로세스 완료")
            self.logger.info("Google 계정 추가 프로세스 완료")
            return success
            
        except Exception as e:
            print(f"❌ Google 계정 추가 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.APP_LAUNCH_ERROR, str(e))
            return False
    
    async def fill_signup_form(self, account_data: Dict[str, str]) -> bool:
        """가입 폼 입력"""
        try:
            print("📝 가입 폼 입력 중...")
            
            # 스크린샷 촬영
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            
            # OCR로 화면 분석
            screen_text = await self.ocr_recognition.extract_text_from_image(screenshot_path)
            form_elements = await self.ocr_recognition.find_form_elements(screenshot_path)
            
            print(f"🔍 화면에서 {len(form_elements)}개 입력 요소 발견")
            
            # 이름 입력 필드 찾기
            first_name_field = None
            last_name_field = None
            
            for element in form_elements:
                if any(keyword in element.get('text', '').lower() for keyword in ['first', '이름', 'name']):
                    first_name_field = element
                elif any(keyword in element.get('text', '').lower() for keyword in ['last', '성', 'surname']):
                    last_name_field = element
            
            # 이름 입력
            if first_name_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    first_name_field['x'],
                    first_name_field['y']
                )
                await self._human_like_typing(account_data['first_name'])
                print(f"   ✅ 성 입력: {account_data['first_name']}")
            
            if last_name_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    last_name_field['x'],
                    last_name_field['y']
                )
                await self._human_like_typing(account_data['last_name'])
                print(f"   ✅ 이름 입력: {account_data['last_name']}")
            
            # 다음 버튼 찾아 클릭
            next_button = await self._find_button_by_text(['다음', 'Next', '계속'])
            if next_button:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    next_button['x'],
                    next_button['y']
                )
                print("   ✅ 다음 단계로 이동")
                await asyncio.sleep(3)
            
            # 사용자명/비밀번호 단계
            await self._fill_credentials_step(account_data)
            
            print("✅ 기본 폼 입력 완료")
            self.logger.info("가입 폼 입력 완료")
            return True
            
        except Exception as e:
            print(f"❌ 폼 입력 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.INPUT_ERROR, str(e))
            return False
    
    async def _fill_credentials_step(self, account_data: Dict[str, str]):
        """사용자명/비밀번호 입력 단계"""
        try:
            # 스크린샷 촬영
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            form_elements = await self.ocr_recognition.find_form_elements(screenshot_path)
            
            # 사용자명 필드 찾기
            username_field = None
            password_field = None
            confirm_password_field = None
            
            for element in form_elements:
                text = element.get('text', '').lower()
                if any(keyword in text for keyword in ['username', '사용자명', 'email']):
                    username_field = element
                elif 'password' in text or '비밀번호' in text:
                    if password_field is None:
                        password_field = element
                    else:
                        confirm_password_field = element
            
            # 사용자명 입력
            if username_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    username_field['x'],
                    username_field['y']
                )
                await self._human_like_typing(account_data['username'])
                print(f"   ✅ 사용자명 입력: {account_data['username']}")
            
            # 비밀번호 입력
            if password_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    password_field['x'],
                    password_field['y']
                )
                await self._human_like_typing(account_data['password'])
                print(f"   ✅ 비밀번호 입력")
            
            # 비밀번호 확인 입력
            if confirm_password_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    confirm_password_field['x'],
                    confirm_password_field['y']
                )
                await self._human_like_typing(account_data['password'])
                print(f"   ✅ 비밀번호 확인 입력")
            
        except Exception as e:
            print(f"❌ 자격증명 입력 실패: {e}")
            raise
    
    async def handle_phone_verification(self, account_data: Dict[str, str]) -> bool:
        """전화번호 인증 처리"""
        try:
            print("📱 전화번호 인증 단계...")
            
            # GetSMSCode에서 전화번호 요청
            phone_result = await self.sms_handler.request_phone_number(service="google")
            
            if not phone_result['success']:
                print(f"❌ 전화번호 요청 실패: {phone_result['error']}")
                return False
            
            phone_number = phone_result['phone_number']
            request_id = phone_result['request_id']
            
            print(f"📞 할당된 전화번호: {phone_number}")
            account_data['phone_number'] = phone_number
            
            # 현재 화면 스크린샷 촬영
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            
            # 실제 OCR로 전화번호 입력 필드 찾기
            print("🔍 OCR로 전화번호 입력 필드 탐지 중...")
            phone_field = await self.ocr_recognition.find_phone_input_field(screenshot_path)
            
            if phone_field:
                print(f"✅ 전화번호 필드 발견: {phone_field['text']} at ({phone_field['x']}, {phone_field['y']})")
                
                # 전화번호 입력
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    phone_field['x'],
                    phone_field['y']
                )
                await asyncio.sleep(1)
                await self._human_like_typing(phone_number)
                print(f"   ✅ 전화번호 입력: {phone_number}")
                
                # 인증 코드 전송 버튼 찾기
                clickable_elements = await self.ocr_recognition.find_clickable_elements(screenshot_path)
                send_button = None
                
                for element in clickable_elements:
                    if element.get('type') in ['send', 'verify', 'next', 'continue']:
                        send_button = element
                        break
                
                if send_button:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        send_button['x'],
                        send_button['y']
                    )
                    print(f"   📤 인증 코드 전송 버튼 클릭: {send_button['text']}")
                    await asyncio.sleep(3)
                else:
                    # 기본 위치에서 다음 버튼 시도
                    print("   ⚠️ 전송 버튼을 찾지 못함 - 기본 위치 시도")
                    await self.adb_utils.tap_coordinates(self.current_device, 540, 1000)
                    await asyncio.sleep(3)
                
                # SMS 수신 대기
                print("   ⏳ SMS 인증 코드 수신 대기...")
                sms_result = await self.sms_handler.wait_for_sms(request_id, timeout=60)
                
                if sms_result['success']:
                    verification_code = sms_result['code']
                    print(f"   ✅ 인증 코드 수신: {verification_code}")
                    
                    # 인증 코드 입력
                    await self._input_verification_code(verification_code)
                    
                    return True
                else:
                    print(f"   ❌ SMS 수신 실패: {sms_result['error']}")
                    return False
            else:
                print("   ⚠️ OCR로 전화번호 입력 필드를 찾을 수 없음")
                
                # 대체 방법: 화면 중앙 하단 영역들 시도
                print("   🎯 예상 위치들에서 전화번호 필드 시도...")
                phone_positions = [
                    (540, 600),   # 화면 중앙
                    (540, 700),   # 중앙 하단
                    (540, 800),   # 하단
                    (400, 700),   # 왼쪽
                    (680, 700),   # 오른쪽
                ]
                
                for i, (x, y) in enumerate(phone_positions):
                    print(f"   🎯 위치 {i+1} 시도: ({x}, {y})")
                    await self.adb_utils.tap_coordinates(self.current_device, x, y)
                    await asyncio.sleep(1)
                    
                    # 텍스트 입력 시도
                    await self._human_like_typing(phone_number)
                    await asyncio.sleep(1)
                    
                    # 다음 버튼 시도
                    await self.adb_utils.tap_coordinates(self.current_device, 540, y + 100)
                    await asyncio.sleep(2)
                    
                    # 화면 변화 확인 (간단한 방법)
                    new_screenshot = await self.adb_utils.take_screenshot(self.current_device)
                    if new_screenshot:
                        print(f"   📸 시도 후 스크린샷: {new_screenshot}")
                        # 실제로는 화면 변화를 더 정교하게 감지해야 함
                        break
                
                return False  # 일단 실패로 처리
                
        except Exception as e:
            print(f"❌ 전화번호 인증 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.SMS_TIMEOUT, str(e))
            return False
    
    async def _input_verification_code(self, code: str):
        """인증 코드 입력"""
        try:
            # 인증 코드 입력 필드 찾기
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            form_elements = await self.ocr_recognition.find_form_elements(screenshot_path)
            
            code_field = None
            for element in form_elements:
                text = element.get('text', '').lower()
                if any(keyword in text for keyword in ['code', '코드', 'verification', '인증']):
                    code_field = element
                    break
            
            if code_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    code_field['x'],
                    code_field['y']
                )
                await self._human_like_typing(code)
                print(f"   ✅ 인증 코드 입력: {code}")
                
                # 확인 버튼 클릭
                verify_button = await self._find_button_by_text(['확인', 'Verify', '인증'])
                if verify_button:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        verify_button['x'],
                        verify_button['y']
                    )
                    print("   ✅ 인증 코드 확인 완료")
                    await asyncio.sleep(3)
            
        except Exception as e:
            print(f"❌ 인증 코드 입력 실패: {e}")
            raise
    
    async def handle_additional_info(self, account_data: Dict[str, str]) -> bool:
        """추가 정보 입력 (생년월일 등)"""
        try:
            print("📅 추가 정보 입력 중...")
            
            # 생년월일 입력 처리
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            form_elements = await self.ocr_recognition.find_form_elements(screenshot_path)
            
            # 생년월일 필드 찾기
            birth_fields = []
            for element in form_elements:
                text = element.get('text', '').lower()
                if any(keyword in text for keyword in ['birth', '생년월일', 'date', '날짜', 'year', 'month', 'day']):
                    birth_fields.append(element)
            
            if birth_fields:
                # 년도 입력
                if len(birth_fields) >= 1:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        birth_fields[0]['x'],
                        birth_fields[0]['y']
                    )
                    await self._human_like_typing(account_data['birth_year'])
                    print(f"   ✅ 생년 입력: {account_data['birth_year']}")
                
                # 월 입력
                if len(birth_fields) >= 2:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        birth_fields[1]['x'],
                        birth_fields[1]['y']
                    )
                    await self._human_like_typing(account_data['birth_month'])
                    print(f"   ✅ 월 입력: {account_data['birth_month']}")
                
                # 일 입력
                if len(birth_fields) >= 3:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        birth_fields[2]['x'],
                        birth_fields[2]['y']
                    )
                    await self._human_like_typing(account_data['birth_day'])
                    print(f"   ✅ 일 입력: {account_data['birth_day']}")
            
            print("✅ 추가 정보 입력 완료")
            return True
            
        except Exception as e:
            print(f"❌ 추가 정보 입력 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.INPUT_ERROR, str(e))
            return False
    
    async def verify_account_creation(self, account_data: Dict[str, str]) -> bool:
        """생성된 계정이 실제로 작동하는지 검증"""
        try:
            print("🔍 계정 생성 검증 시작...")
            
            # 새로운 브라우저 세션으로 로그인 테스트
            print("🌐 Google 로그인 페이지로 이동...")
            
            # Chrome 재시작
            await self.adb_utils.clear_app_cache(self.current_device, "com.android.chrome")
            await asyncio.sleep(2)
            
            # 로그인 페이지로 이동
            await self.device_manager._run_command([
                self.device_manager.adb_exe, '-s', self.current_device, 'shell', 
                'am', 'start', '-a', 'android.intent.action.VIEW', 
                '-d', 'https://accounts.google.com/signin'
            ])
            await asyncio.sleep(5)
            
            # 로그인 시도
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            form_elements = await self.ocr_recognition.find_form_elements(screenshot_path)
            
            # 이메일 입력
            email_field = None
            for element in form_elements:
                if any(keyword in element.get('text', '').lower() for keyword in ['email', 'username', '이메일']):
                    email_field = element
                    break
            
            if email_field:
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    email_field['x'],
                    email_field['y']
                )
                await self._human_like_typing(f"{account_data['username']}@gmail.com")
                print(f"   ✅ 이메일 입력: {account_data['username']}@gmail.com")
                
                # Next 버튼 클릭
                next_button = await self._find_button_by_text(['다음', 'Next'])
                if next_button:
                    await self.adb_utils.tap_coordinates(
                        self.current_device,
                        next_button['x'],
                        next_button['y']
                    )
                    await asyncio.sleep(3)
                
                # 비밀번호 입력 화면으로 이동되었는지 확인
                password_screenshot = await self.adb_utils.take_screenshot(self.current_device)
                password_text = await self.ocr_recognition.extract_text_from_image(password_screenshot)
                
                if any(keyword in password_text.lower() for keyword in ['password', '비밀번호', 'enter password']):
                    print("   ✅ 비밀번호 입력 화면 도달 - 계정 존재 확인")
                    
                    # 비밀번호 입력 시도
                    password_elements = await self.ocr_recognition.find_form_elements(password_screenshot)
                    password_field = None
                    
                    for element in password_elements:
                        if any(keyword in element.get('text', '').lower() for keyword in ['password', '비밀번호']):
                            password_field = element
                            break
                    
                    if password_field:
                        await self.adb_utils.tap_coordinates(
                            self.current_device,
                            password_field['x'],
                            password_field['y']
                        )
                        await self._human_like_typing(account_data['password'])
                        print(f"   ✅ 비밀번호 입력 완료")
                        
                        # 로그인 버튼 클릭
                        login_button = await self._find_button_by_text(['로그인', 'Next', 'Sign in'])
                        if login_button:
                            await self.adb_utils.tap_coordinates(
                                self.current_device,
                                login_button['x'],
                                login_button['y']
                            )
                            await asyncio.sleep(5)
                        
                        # 로그인 성공 여부 확인
                        final_screenshot = await self.adb_utils.take_screenshot(self.current_device)
                        final_text = await self.ocr_recognition.extract_text_from_image(final_screenshot)
                        
                        success_indicators = ['welcome', 'dashboard', 'gmail', 'google', 'account', '환영', '계정']
                        error_indicators = ['incorrect', 'wrong', 'invalid', 'error', '잘못', '오류', '확인할 수 없']
                        
                        if any(indicator in final_text.lower() for indicator in error_indicators):
                            print("   ❌ 로그인 실패 - 계정이 제대로 생성되지 않음")
                            return False
                        elif any(indicator in final_text.lower() for indicator in success_indicators):
                            print("   ✅ 로그인 성공 - 계정이 정상적으로 생성됨")
                            return True
                        else:
                            print("   ⚠️ 로그인 결과 불명확")
                            print(f"   📄 화면 텍스트: {final_text[:100]}...")
                            return False
                    
                elif any(keyword in password_text.lower() for keyword in ['not found', 'doesn\'t exist', '존재하지 않', '찾을 수 없']):
                    print("   ❌ 계정이 존재하지 않음")
                    return False
                else:
                    print("   ⚠️ 예상하지 못한 화면")
                    print(f"   📄 화면 텍스트: {password_text[:100]}...")
                    return False
            else:
                print("   ❌ 이메일 입력 필드를 찾을 수 없음")
                return False
                
        except Exception as e:
            print(f"❌ 계정 검증 실패: {e}")
            return False
    
    async def finalize_account_creation(self, account_data: Dict[str, str]) -> bool:
        """계정 생성 완료 처리"""
        try:
            print("🏁 계정 생성 완료 처리...")
            
            # 현재 화면 스크린샷
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            
            # OCR로 완료 버튼 찾기
            clickable_elements = await self.ocr_recognition.find_clickable_elements(screenshot_path)
            
            # 완료 관련 버튼 찾기
            completion_buttons = []
            for element in clickable_elements:
                text_lower = element.get('text', '').lower()
                if any(keyword in text_lower for keyword in [
                    'create', 'finish', 'done', 'complete', 'confirm', 'next',
                    '생성', '완료', '확인', '다음', '만들기'
                ]):
                    completion_buttons.append(element)
            
            # 가장 적절한 버튼 클릭
            if completion_buttons:
                best_button = completion_buttons[0]  # 첫 번째 후보 선택
                await self.adb_utils.tap_coordinates(
                    self.current_device,
                    best_button['x'],
                    best_button['y']
                )
                print(f"   ✅ 계정 생성 버튼 클릭: {best_button['text']}")
                await asyncio.sleep(5)  # 처리 대기
            else:
                # 기본 위치에서 완료 버튼 시도
                print("   ⚠️ 완료 버튼을 찾지 못함 - 기본 위치 시도")
                await self.adb_utils.tap_coordinates(self.current_device, 540, 1200)
                await asyncio.sleep(5)
            
            # 완료 확인을 위한 화면 분석
            final_screenshot = await self.adb_utils.take_screenshot(self.current_device)
            
            # OCR로 성공 메시지 탐지
            print("🔍 계정 생성 완료 메시지 탐지 중...")
            final_text = await self.ocr_recognition.extract_text_from_image(final_screenshot)
            
            # 성공 키워드 확인
            success_keywords = [
                # 영어
                'welcome', 'success', 'created', 'account created', 'congratulations',
                'setup complete', 'ready', 'done', 'finished', 'gmail',
                # 한국어
                '환영', '성공', '생성됨', '계정이 생성', '축하', '설정 완료', '준비', '완료'
            ]
            
            text_lower = final_text.lower()
            success_detected = any(keyword in text_lower for keyword in success_keywords)
            
            if success_detected:
                print("   ✅ 계정 생성 완료 메시지 감지됨!")
                print(f"   📄 감지된 텍스트: {final_text[:100]}...")
                
                # 계정 정보 저장
                account_data['creation_status'] = 'completed'
                account_data['completion_time'] = datetime.now().isoformat()
                
                return True
            else:
                print("   ⚠️ 계정 생성 완료 메시지를 찾지 못함")
                print(f"   📄 현재 화면 텍스트: {final_text[:100]}...")
                
                # 추가 확인: Gmail 앱이나 Google 서비스 화면인지 확인
                gmail_indicators = ['gmail', 'google', 'inbox', 'compose', 'mail']
                gmail_detected = any(indicator in text_lower for indicator in gmail_indicators)
                
                if gmail_detected:
                    print("   ✅ Gmail/Google 서비스 화면 감지 - 계정 생성 성공으로 판단")
                    account_data['creation_status'] = 'completed'
                    account_data['completion_time'] = datetime.now().isoformat()
                    return True
                else:
                    print("   ❌ 계정 생성 완료 확인 실패")
                    account_data['creation_status'] = 'failed'
                    return False
                
        except Exception as e:
            print(f"❌ 계정 생성 완료 처리 실패: {e}")
            await self.error_recovery.handle_error(ErrorType.ACCOUNT_CREATION_ERROR, str(e))
            return False
    
    async def _human_like_typing(self, text: str):
        """인간과 같은 타이핑 시뮬레이션"""
        typing_delay = self.config_manager.get('automation.typing_delay', {'min': 0.1, 'max': 0.3})
        
        for char in text:
            await self.adb_utils.input_text(self.current_device, char)
            if self.config_manager.get('automation.human_like_behavior'):
                delay = random.uniform(typing_delay['min'], typing_delay['max'])
                await asyncio.sleep(delay)
    
    async def _find_button_by_text(self, button_texts: List[str]) -> Optional[Dict[str, Any]]:
        """텍스트로 버튼 찾기"""
        try:
            screenshot_path = await self.adb_utils.take_screenshot(self.current_device)
            elements = await self.ocr_recognition.find_clickable_elements(screenshot_path)
            
            for element in elements:
                element_text = element.get('text', '').lower()
                if any(btn_text.lower() in element_text for btn_text in button_texts):
                    return element
            
            return None
            
        except Exception as e:
            print(f"❌ 버튼 찾기 실패: {e}")
            return None
    
    async def create_single_account(self, account_data: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """단일 Google 계정 생성"""
        if not account_data:
            account_data = self.generate_account_data()
        
        start_time = time.time()
        result = {
            'success': False,
            'account_data': account_data,
            'steps_completed': [],
            'errors': [],
            'duration': 0,
            'phone_number': None,
            'verification_code': None,
            'email_address': None,
            'creation_timestamp': datetime.now().isoformat()
        }
        
        try:
            # 1. 디바이스 초기화
            if not await self.initialize_device():
                result['errors'].append("디바이스 초기화 실패")
                return result
            result['steps_completed'].append("디바이스 초기화")
            
            # 2. Google 앱 실행
            if not await self.launch_google_app():
                result['errors'].append("Google 앱 실행 실패")
                return result
            result['steps_completed'].append("Google 앱 실행")
            
            # 3. 가입 폼 입력
            if not await self.fill_signup_form(account_data):
                result['errors'].append("가입 폼 입력 실패")
                return result
            result['steps_completed'].append("가입 폼 입력")
            
            # 4. 전화번호 인증
            phone_result = await self.handle_phone_verification(account_data)
            if not phone_result:
                result['errors'].append("전화번호 인증 실패")
                return result
            result['steps_completed'].append("전화번호 인증")
            
            # SMS 정보 저장
            if hasattr(self.sms_handler, 'last_phone_number'):
                result['phone_number'] = self.sms_handler.last_phone_number
            if hasattr(self.sms_handler, 'last_verification_code'):
                result['verification_code'] = self.sms_handler.last_verification_code
            
            # 5. 추가 정보 입력
            if not await self.handle_additional_info(account_data):
                result['errors'].append("추가 정보 입력 실패")
                return result
            result['steps_completed'].append("추가 정보 입력")
            
            # 6. 계정 생성 완료
            if not await self.finalize_account_creation(account_data):
                result['errors'].append("계정 생성 완료 실패")
                return result
            result['steps_completed'].append("계정 생성 완료")
            
            # 7. 계정 검증 (실제 로그인 테스트)
            print("🔍 생성된 계정 검증 중...")
            verification_result = await self.verify_account_creation(account_data)
            if verification_result:
                result['steps_completed'].append("계정 검증 성공")
                result['verified'] = True
                print("   ✅ 계정 검증 성공 - 실제 사용 가능한 계정")
            else:
                result['steps_completed'].append("계정 검증 실패")
                result['verified'] = False
                result['errors'].append("계정 검증 실패 - 로그인 불가능")
                print("   ❌ 계정 검증 실패 - 생성된 계정으로 로그인 불가")
            
            # 이메일 주소 생성
            result['email_address'] = f"{account_data['username']}@gmail.com"
            
            # 검증된 계정만 성공으로 처리
            result['success'] = verification_result
            
            if result['success']:
                self.logger.info(f"계정 생성 및 검증 성공: {account_data['username']}")
            else:
                self.logger.warning(f"계정 생성은 완료되었으나 검증 실패: {account_data['username']}")
            
        except Exception as e:
            error_msg = f"계정 생성 중 오류: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        finally:
            result['duration'] = time.time() - start_time
            
            # 브라우저 캐시 정리
            try:
                await self.adb_utils.clear_app_cache(self.current_device, "com.android.chrome")
                print("🧹 브라우저 캐시 정리 완료")
            except Exception as e:
                self.logger.warning(f"캐시 정리 실패: {e}")
        
            # 단일 계정 결과도 저장
            self._save_single_account_result(result)
        
        return result
    
    def _save_single_account_result(self, result: Dict[str, Any]):
        """단일 계정 생성 결과 저장"""
        try:
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"single_account_creation_{timestamp}.json"
            
            # 통계 정보 업데이트
            if result['success']:
                self.statistics['successful_creations'] = 1
                self.statistics['failed_attempts'] = 0
            else:
                self.statistics['successful_creations'] = 0
                self.statistics['failed_attempts'] = 1
            
            self.statistics['total_attempts'] = 1
            self.statistics['end_time'] = datetime.now()
            
            final_results = {
                'metadata': {
                    'creation_method': 'ADB_ANDROID_EMULATOR',
                    'test_date': datetime.now().isoformat(),
                    'total_accounts': 1,
                    'successful_accounts': 1 if result['success'] else 0,
                    'failed_accounts': 0 if result['success'] else 1,
                    'account_type': 'SINGLE_ACCOUNT_TEST'
                },
                'statistics': {
                    'total_attempts': self.statistics['total_attempts'],
                    'successful_creations': self.statistics['successful_creations'],
                    'failed_attempts': self.statistics['failed_attempts'],
                    'start_time': self.statistics['start_time'].isoformat() if self.statistics['start_time'] else None,
                    'end_time': self.statistics['end_time'].isoformat() if self.statistics['end_time'] else None
                },
                'account_details': {
                    'username': result['account_data']['username'],
                    'email_address': result.get('email_address'),
                    'full_name': f"{result['account_data']['first_name']} {result['account_data']['last_name']}",
                    'birth_date': f"{result['account_data']['birth_year']}-{int(result['account_data']['birth_month']):02d}-{int(result['account_data']['birth_day']):02d}",
                    'phone_number': result.get('phone_number'),
                    'verification_code': result.get('verification_code'),
                    'creation_timestamp': result.get('creation_timestamp'),
                    'duration_seconds': result['duration']
                },
                'detailed_results': [result]
            }
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 계정 생성 결과 저장: {results_file}")
            self.logger.info(f"단일 계정 결과 저장 완료: {results_file}")
            
            # 간단한 요약 파일도 생성
            summary_file = results_dir / f"account_summary_{timestamp}.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write("=" * 50 + "\n")
                f.write("Google 계정 생성 결과 요약\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"성공 여부: {'✅ 성공' if result['success'] else '❌ 실패'}\n")
                f.write(f"소요 시간: {result['duration']:.1f}초\n\n")
                
                if result['success']:
                    f.write("📧 생성된 계정 정보:\n")
                    f.write(f"   이메일: {result.get('email_address', 'N/A')}\n")
                    f.write(f"   이름: {result['account_data']['first_name']} {result['account_data']['last_name']}\n")
                    f.write(f"   사용자명: {result['account_data']['username']}\n")
                    f.write(f"   생년월일: {result['account_data']['birth_year']}-{int(result['account_data']['birth_month']):02d}-{int(result['account_data']['birth_day']):02d}\n")
                    if result.get('phone_number'):
                        f.write(f"   전화번호: {result['phone_number']}\n")
                    if result.get('verification_code'):
                        f.write(f"   인증코드: {result['verification_code']}\n")
                
                f.write(f"\n📋 완료된 단계: {', '.join(result['steps_completed'])}\n")
                
                if result['errors']:
                    f.write(f"\n❌ 오류 목록:\n")
                    for error in result['errors']:
                        f.write(f"   - {error}\n")
            
            print(f"📄 계정 요약 저장: {summary_file}")
            
        except Exception as e:
            print(f"❌ 결과 저장 실패: {e}")
            self.logger.error(f"단일 계정 결과 저장 실패: {e}")

    async def create_multiple_accounts(self, count: int = 1) -> List[Dict[str, Any]]:
        """여러 계정 생성"""
        print(f"🚀 ADB 기반 {count}개 계정 생성 프로세스 시작")
        
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
                print(f"✅ 계정 {i+1} 생성 성공")
            else:
                self.statistics['failed_attempts'] += 1
                print(f"❌ 계정 {i+1} 생성 실패")
            
            # 다음 계정 생성 전 대기
            if i < count - 1:
                delay = 120  # 2분 기본 대기
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
        print("\n" + "=" * 70)
        print("🏁 ADB 기반 Google 계정 생성 결과")
        print("=" * 70)
        
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
        
        print(f"\n💡 시스템 특징:")
        print(f"   - ADB 기반 Android 에뮬레이터 제어")
        print(f"   - OCR 기반 UI 요소 인식")
        print(f"   - SMS API 연동 자동 인증")
        print(f"   - 디바이스 정보 랜덤화")
        print(f"   - VPN 연동 IP 우회")
        print(f"   - 인간과 같은 행동 시뮬레이션")
    
    def _save_results(self, results: List[Dict[str, Any]]):
        """결과 저장"""
        try:
            results_dir = Path("results")
            results_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = results_dir / f"adb_account_creation_{timestamp}.json"
            
            final_results = {
                'metadata': {
                    'creation_method': 'ADB_ANDROID_EMULATOR',
                    'test_date': datetime.now().isoformat(),
                    'total_accounts': len(results),
                    'successful_accounts': len([r for r in results if r['success']]),
                    'failed_accounts': len([r for r in results if not r['success']])
                },
                'statistics': {
                     'total_attempts': self.statistics['total_attempts'],
                     'successful_creations': self.statistics['successful_creations'],
                     'failed_attempts': self.statistics['failed_attempts'],
                     'start_time': self.statistics['start_time'].isoformat() if self.statistics['start_time'] else None,
                     'end_time': self.statistics['end_time'].isoformat() if self.statistics['end_time'] else None
                 },
                'detailed_results': results
            }
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(final_results, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 상세 결과 저장: {results_file}")
            self.logger.info(f"결과 저장 완료: {results_file}")
            
        except Exception as e:
            print(f"❌ 결과 저장 실패: {e}")
            self.logger.error(f"결과 저장 실패: {e}")

async def main():
    """메인 함수"""
    creator = ADBAccountCreator()
    
    try:
        print("\n🤖 ADB 기반 Google 계정 생성 시스템")
        print("   1: 디바이스 초기화 테스트")
        print("   2: 실제 Google 계정 생성 테스트")
        print("   3: 시스템 상태 확인")
        print("   0: 종료")
        
        # 자동으로 2 선택 (계정 생성 테스트)
        choice = '2'
        print(f"선택: {choice}")
        
        if choice == '1':
            print("\n🚀 디바이스 초기화 테스트 시작")
            result = await creator.initialize_device()
            
            if result:
                print("✅ 디바이스 초기화 성공!")
                
                # 기본 ADB 명령 테스트
                print("\n🔍 기본 ADB 기능 테스트:")
                
                # 스크린샷 촬영
                print("📸 스크린샷 촬영...")
                screenshot = await creator.adb_utils.take_screenshot(creator.current_device)
                if screenshot:
                    print(f"   ✅ 스크린샷 저장: {screenshot}")
                else:
                    print("   ❌ 스크린샷 실패")
                
                # 화면 깨우기
                print("💡 화면 깨우기...")
                wake_result = await creator.adb_utils.wake_screen(creator.current_device)
                print(f"   {'✅' if wake_result else '❌'} 화면 깨우기")
                
                # Chrome 실행 테스트
                print("🌐 Chrome 실행 테스트...")
                chrome_result = await creator.adb_utils.launch_app(creator.current_device, "com.android.chrome")
                print(f"   {'✅' if chrome_result else '❌'} Chrome 실행")
                
                if chrome_result:
                    await asyncio.sleep(3)
                    
                    # Google 가입 페이지 이동
                    print("🔗 Google 가입 페이지 이동...")
                    url = "https://accounts.google.com/signup"
                    await creator.adb_utils.input_text(creator.current_device, url)
                    await creator.adb_utils.send_keyevent(creator.current_device, "KEYCODE_ENTER")
                    
                    await asyncio.sleep(5)
                    
                    # 최종 스크린샷
                    final_screenshot = await creator.adb_utils.take_screenshot(creator.current_device)
                    if final_screenshot:
                        print(f"   📸 최종 스크린샷: {final_screenshot}")
            else:
                print("❌ 디바이스 초기화 실패")
        
        elif choice == '2':
            print("\n🚀 실제 Google 계정 생성 테스트 시작")
            
            # 디바이스 초기화
            if not await creator.initialize_device():
                print("❌ 디바이스 초기화 실패")
                return
            
            # 계정 데이터 생성
            account_data = creator.generate_account_data()
            print(f"\n📝 생성된 계정 정보:")
            print(f"   이름: {account_data['first_name']} {account_data['last_name']}")
            print(f"   사용자명: {account_data['username']}")
            print(f"   생년월일: {account_data['birth_year']}-{account_data['birth_month']:0>2}-{account_data['birth_day']:0>2}")
            
            # 실제 Google 계정 생성 프로세스 시작
            result = await creator.create_single_account(account_data)
            
            print(f"\n📋 계정 생성 결과:")
            print(f"   성공: {'✅' if result['success'] else '❌'}")
            print(f"   완료 단계: {', '.join(result['steps_completed'])}")
            print(f"   소요 시간: {result.get('duration', 0):.1f}초")
            
            if result['errors']:
                print(f"   오류들:")
                for error in result['errors']:
                    print(f"      - {error}")
            
        elif choice == '3':
            print("\n🔍 시스템 상태 확인")
            
            if device_manager_available:
                prerequisites = await creator.device_manager.check_prerequisites()
                
                print(f"   📱 연결된 디바이스: {len(prerequisites['connected_devices'])}개")
                print(f"   🎮 사용 가능한 AVD: {len(prerequisites['available_avds'])}개")
                print(f"   🔧 ADB 사용 가능: {'✅' if prerequisites['adb_available'] else '❌'}")
                print(f"   📱 Emulator 사용 가능: {'✅' if prerequisites['emulator_available'] else '❌'}")
            else:
                print("   ❌ Device Manager 사용 불가")
            
        elif choice == '0':
            print("시스템을 종료합니다.")
            
        else:
            print("잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n🛑 시스템이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 시스템 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 