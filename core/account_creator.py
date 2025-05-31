"""
Google 계정 생성 핵심 로직 모듈

이 모듈은 ADB와 OCR을 사용하여 Google 계정을 자동으로 생성하는 핵심 기능을 제공합니다.
- 폼 자동 채우기
- 전화번호 인증 처리
- 계정 설정 완료
- 인간 같은 상호작용 시뮬레이션
"""

import random
import time
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import re

from .adb_controller import ADBController
from .ocr_utils import OCRProcessor
from .device_randomizer import DeviceRandomizer
from .sms_verifier import SMSVerifier
from .phone_verification import PhoneVerification
from .proxy_manager import ProxyManager

# 로깅 설정
logger = logging.getLogger(__name__)

@dataclass
class PersonalInfo:
    """개인 정보 데이터 클래스"""
    first_name: str
    last_name: str
    username: str
    password: str
    birth_year: int
    birth_month: int
    birth_day: int
    gender: str  # 'male', 'female', 'other'
    recovery_email: Optional[str] = None
    phone_number: Optional[str] = None

@dataclass
class AccountCreationResult:
    """계정 생성 결과 데이터 클래스"""
    success: bool
    email: Optional[str] = None
    password: Optional[str] = None
    phone_number: Optional[str] = None
    error_message: Optional[str] = None
    creation_time: Optional[datetime] = None
    steps_completed: List[str] = None

class FormFiller:
    """폼 자동 채우기 클래스"""
    
    def __init__(self, adb_controller: ADBController, ocr_processor: OCRProcessor):
        """
        FormFiller 초기화
        
        Args:
            adb_controller: ADB 컨트롤러 인스턴스
            ocr_processor: OCR 프로세서 인스턴스
        """
        self.adb = adb_controller
        self.ocr = ocr_processor
        logger.info("폼 채우기 모듈이 초기화되었습니다.")
    
    def generate_random_personal_info(self) -> PersonalInfo:
        """
        랜덤한 개인 정보를 생성합니다.
        
        Returns:
            생성된 개인 정보
        """
        # 한국 이름 목록
        korean_first_names = [
            "민준", "서준", "도윤", "예준", "시우", "주원", "하준", "지호", "지후", "준서",
            "서연", "서윤", "지우", "서현", "민서", "하은", "지유", "윤서", "지민", "채원"
        ]
        
        korean_last_names = [
            "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
            "한", "오", "서", "신", "권", "황", "안", "송", "류", "전"
        ]
        
        # 영어 이름 목록
        english_first_names = [
            "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
            "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica"
        ]
        
        english_last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
            "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas"
        ]
        
        # 랜덤하게 한국어 또는 영어 이름 선택
        use_korean = random.choice([True, False])
        
        if use_korean:
            first_name = random.choice(korean_first_names)
            last_name = random.choice(korean_last_names)
        else:
            first_name = random.choice(english_first_names)
            last_name = random.choice(english_last_names)
        
        # 사용자명 생성 (영어 + 숫자)
        username_base = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=random.randint(6, 10)))
        username_suffix = ''.join(random.choices('0123456789', k=random.randint(2, 4)))
        username = username_base + username_suffix
        
        # 비밀번호 생성 (8-12자, 대소문자, 숫자, 특수문자 포함)
        password_length = random.randint(8, 12)
        password_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*'
        password = ''.join(random.choices(password_chars, k=password_length))
        
        # 생년월일 생성 (18-65세)
        current_year = datetime.now().year
        birth_year = random.randint(current_year - 65, current_year - 18)
        birth_month = random.randint(1, 12)
        
        # 월에 따른 일수 계산
        if birth_month in [1, 3, 5, 7, 8, 10, 12]:
            max_day = 31
        elif birth_month in [4, 6, 9, 11]:
            max_day = 30
        else:  # 2월
            max_day = 29 if birth_year % 4 == 0 else 28
        
        birth_day = random.randint(1, max_day)
        
        # 성별 랜덤 선택
        gender = random.choice(['male', 'female', 'other'])
        
        personal_info = PersonalInfo(
            first_name=first_name,
            last_name=last_name,
            username=username,
            password=password,
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            gender=gender
        )
        
        logger.info(f"랜덤 개인정보 생성 완료: {first_name} {last_name}, {username}")
        return personal_info
    
    async def find_and_fill_field(self, field_name: str, value: str, field_type: str = "text") -> bool:
        """
        OCR을 사용하여 필드를 찾고 값을 입력합니다.
        
        Args:
            field_name: 찾을 필드 이름 (예: "First name", "성")
            value: 입력할 값
            field_type: 필드 타입 ("text", "email", "password", "number")
        
        Returns:
            성공 여부
        """
        try:
            logger.info(f"필드 '{field_name}'을 찾아 '{value}' 입력 시도 중...")
            
            # 화면 캡처
            screenshot_path = await self.adb.capture_screenshot()
            if not screenshot_path:
                logger.error("화면 캡처 실패")
                return False
            
            # OCR로 텍스트 인식
            ocr_results = await self.ocr.extract_text_with_coordinates(screenshot_path)
            
            # 필드 라벨 찾기
            field_coords = None
            for result in ocr_results:
                text = result['text'].lower()
                if field_name.lower() in text or any(keyword in text for keyword in field_name.lower().split()):
                    field_coords = result['coordinates']
                    logger.info(f"필드 라벨 발견: {result['text']} at {field_coords}")
                    break
            
            if not field_coords:
                logger.warning(f"필드 '{field_name}' 라벨을 찾을 수 없습니다.")
                # 대안: 입력 필드 직접 찾기
                input_fields = await self.ocr.find_input_fields(screenshot_path)
                if input_fields:
                    field_coords = input_fields[0]['coordinates']
                    logger.info(f"대안으로 첫 번째 입력 필드 사용: {field_coords}")
                else:
                    return False
            
            # 필드 근처의 입력 박스 찾기 (라벨 아래쪽 또는 오른쪽)
            input_coords = await self._find_input_field_near_label(field_coords, ocr_results)
            
            if not input_coords:
                # 라벨 좌표를 그대로 사용 (라벨이 입력 필드일 수도 있음)
                input_coords = field_coords
            
            # 필드 클릭
            await self._human_like_tap(input_coords)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 기존 텍스트 지우기
            await self._clear_field()
            await asyncio.sleep(random.uniform(0.3, 0.7))
            
            # 값 입력 (인간 같은 타이핑)
            await self._human_like_typing(value)
            
            logger.info(f"필드 '{field_name}'에 값 입력 완료")
            return True
            
        except Exception as e:
            logger.error(f"필드 '{field_name}' 입력 실패: {e}")
            return False
    
    async def _find_input_field_near_label(self, label_coords: Dict, ocr_results: List[Dict]) -> Optional[Dict]:
        """
        라벨 근처의 입력 필드를 찾습니다.
        
        Args:
            label_coords: 라벨 좌표
            ocr_results: OCR 결과 목록
        
        Returns:
            입력 필드 좌표 또는 None
        """
        label_x, label_y = label_coords['center']
        
        # 라벨 아래쪽이나 오른쪽에서 입력 필드 찾기
        for result in ocr_results:
            coords = result['coordinates']
            x, y = coords['center']
            
            # 라벨 아래쪽 (y 좌표가 더 큰) 또는 오른쪽 (x 좌표가 더 큰) 영역에서 찾기
            if (y > label_y and abs(x - label_x) < 200) or (x > label_x and abs(y - label_y) < 100):
                # 입력 필드로 보이는 텍스트 패턴 확인
                text = result['text'].lower()
                if any(pattern in text for pattern in ['enter', 'input', '@', '.com', '입력']):
                    return coords
        
        return None
    
    async def _human_like_tap(self, coordinates: Dict) -> None:
        """
        인간 같은 탭 동작을 수행합니다.
        
        Args:
            coordinates: 탭할 좌표
        """
        x, y = coordinates['center']
        
        # 약간의 랜덤 오프셋 추가 (인간은 정확히 중앙을 누르지 않음)
        offset_x = random.randint(-10, 10)
        offset_y = random.randint(-10, 10)
        
        final_x = x + offset_x
        final_y = y + offset_y
        
        await self.adb.tap(final_x, final_y)
        logger.debug(f"탭 실행: ({final_x}, {final_y})")
    
    async def _clear_field(self) -> None:
        """
        현재 필드의 텍스트를 지웁니다.
        """
        # 전체 선택 후 삭제
        await self.adb.key_event("KEYCODE_CTRL_A")  # Ctrl+A
        await asyncio.sleep(0.2)
        await self.adb.key_event("KEYCODE_DEL")  # Delete
        await asyncio.sleep(0.2)
    
    async def _human_like_typing(self, text: str) -> None:
        """
        인간 같은 타이핑을 시뮬레이션합니다.
        
        Args:
            text: 입력할 텍스트
        """
        for char in text:
            await self.adb.input_text(char)
            
            # 랜덤한 타이핑 지연 (50-200ms)
            delay = random.uniform(0.05, 0.2)
            await asyncio.sleep(delay)
            
            # 가끔 실수하는 것처럼 백스페이스 후 다시 입력 (5% 확률)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await self.adb.key_event("KEYCODE_DEL")
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await self.adb.input_text(char)
        
        logger.debug(f"텍스트 입력 완료: {text}")
    
    async def fill_personal_info_form(self, personal_info: PersonalInfo) -> bool:
        """
        개인 정보 폼을 채웁니다.
        
        Args:
            personal_info: 입력할 개인 정보
        
        Returns:
            성공 여부
        """
        try:
            logger.info("개인 정보 폼 채우기 시작...")
            
            # 성 입력
            if not await self.find_and_fill_field("First name", personal_info.first_name):
                if not await self.find_and_fill_field("이름", personal_info.first_name):
                    logger.warning("이름 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 성 입력
            if not await self.find_and_fill_field("Last name", personal_info.last_name):
                if not await self.find_and_fill_field("성", personal_info.last_name):
                    logger.warning("성 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 사용자명 입력
            if not await self.find_and_fill_field("Username", personal_info.username):
                if not await self.find_and_fill_field("사용자명", personal_info.username):
                    logger.warning("사용자명 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 비밀번호 입력
            if not await self.find_and_fill_field("Password", personal_info.password, "password"):
                if not await self.find_and_fill_field("비밀번호", personal_info.password, "password"):
                    logger.warning("비밀번호 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # 비밀번호 확인 입력
            if not await self.find_and_fill_field("Confirm password", personal_info.password, "password"):
                if not await self.find_and_fill_field("비밀번호 확인", personal_info.password, "password"):
                    logger.warning("비밀번호 확인 필드 입력 실패")
            
            logger.info("개인 정보 폼 채우기 완료")
            return True
            
        except Exception as e:
            logger.error(f"개인 정보 폼 채우기 실패: {e}")
            return False
    
    async def fill_birth_date(self, personal_info: PersonalInfo) -> bool:
        """
        생년월일을 입력합니다.
        
        Args:
            personal_info: 개인 정보
        
        Returns:
            성공 여부
        """
        try:
            logger.info("생년월일 입력 시작...")
            
            # 월 입력
            month_str = str(personal_info.birth_month).zfill(2)
            if not await self.find_and_fill_field("Month", month_str):
                if not await self.find_and_fill_field("월", month_str):
                    logger.warning("월 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 일 입력
            day_str = str(personal_info.birth_day).zfill(2)
            if not await self.find_and_fill_field("Day", day_str):
                if not await self.find_and_fill_field("일", day_str):
                    logger.warning("일 필드 입력 실패")
            
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 년 입력
            year_str = str(personal_info.birth_year)
            if not await self.find_and_fill_field("Year", year_str):
                if not await self.find_and_fill_field("년", year_str):
                    logger.warning("년 필드 입력 실패")
            
            logger.info(f"생년월일 입력 완료: {personal_info.birth_year}-{month_str}-{day_str}")
            return True
            
        except Exception as e:
            logger.error(f"생년월일 입력 실패: {e}")
            return False
    
    async def select_gender(self, gender: str) -> bool:
        """
        성별을 선택합니다.
        
        Args:
            gender: 성별 ('male', 'female', 'other')
        
        Returns:
            성공 여부
        """
        try:
            logger.info(f"성별 선택 시작: {gender}")
            
            # 성별 매핑
            gender_mapping = {
                'male': ['Male', '남성', 'M'],
                'female': ['Female', '여성', 'F'],
                'other': ['Other', '기타', 'Rather not say', '선택 안함']
            }
            
            # 화면 캡처 및 OCR
            screenshot_path = await self.adb.capture_screenshot()
            if not screenshot_path:
                return False
            
            ocr_results = await self.ocr.extract_text_with_coordinates(screenshot_path)
            
            # 성별 옵션 찾기
            for result in ocr_results:
                text = result['text']
                for option in gender_mapping[gender]:
                    if option.lower() in text.lower():
                        await self._human_like_tap(result['coordinates'])
                        logger.info(f"성별 선택 완료: {text}")
                        return True
            
            logger.warning(f"성별 옵션을 찾을 수 없습니다: {gender}")
            return False
            
        except Exception as e:
            logger.error(f"성별 선택 실패: {e}")
            return False
    
    async def click_next_button(self) -> bool:
        """
        다음 버튼을 클릭합니다.
        
        Returns:
            성공 여부
        """
        try:
            logger.info("다음 버튼 클릭 시도...")
            
            # 화면 캡처 및 OCR
            screenshot_path = await self.adb.capture_screenshot()
            if not screenshot_path:
                return False
            
            ocr_results = await self.ocr.extract_text_with_coordinates(screenshot_path)
            
            # 다음 버튼 찾기
            next_keywords = ['Next', '다음', 'Continue', '계속', 'Create', '만들기', 'Submit', '제출']
            
            for result in ocr_results:
                text = result['text']
                if any(keyword.lower() in text.lower() for keyword in next_keywords):
                    await self._human_like_tap(result['coordinates'])
                    logger.info(f"버튼 클릭 완료: {text}")
                    await asyncio.sleep(random.uniform(2.0, 4.0))  # 페이지 로딩 대기
                    return True
            
            logger.warning("다음 버튼을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            logger.error(f"다음 버튼 클릭 실패: {e}")
            return False


class GoogleAccountCreator:
    """Google 계정 생성 메인 클래스"""
    
    def __init__(self, 
                 adb_controller: ADBController,
                 ocr_processor: OCRProcessor,
                 device_randomizer: DeviceRandomizer,
                 sms_verifier: SMSVerifier,
                 phone_verification: PhoneVerification,
                 proxy_manager: Optional[ProxyManager] = None):
        """
        GoogleAccountCreator 초기화
        
        Args:
            adb_controller: ADB 컨트롤러
            ocr_processor: OCR 프로세서
            device_randomizer: 디바이스 랜덤화기
            sms_verifier: SMS 인증기
            phone_verification: 전화 인증
            proxy_manager: 프록시 매니저 (선택사항)
        """
        self.adb = adb_controller
        self.ocr = ocr_processor
        self.device_randomizer = device_randomizer
        self.sms_verifier = sms_verifier
        self.phone_verification = phone_verification
        self.proxy_manager = proxy_manager
        
        self.form_filler = FormFiller(adb_controller, ocr_processor)
        
        logger.info("Google 계정 생성기가 초기화되었습니다.")
    
    async def create_account(self, custom_info: Optional[PersonalInfo] = None) -> AccountCreationResult:
        """
        Google 계정을 생성합니다.
        
        Args:
            custom_info: 사용자 지정 개인 정보 (None이면 랜덤 생성)
        
        Returns:
            계정 생성 결과
        """
        start_time = datetime.now()
        steps_completed = []
        
        try:
            logger.info("Google 계정 생성 프로세스 시작...")
            
            # 1. 디바이스 랜덤화
            logger.info("1단계: 디바이스 지문 랜덤화...")
            randomization_results = self.device_randomizer.randomize_all()
            if not any(randomization_results.values()):
                logger.warning("디바이스 랜덤화 실패, 계속 진행...")
            else:
                logger.info(f"디바이스 랜덤화 완료: {randomization_results}")
            steps_completed.append("device_randomization")
            
            # 2. 프록시 설정 (선택사항)
            if self.proxy_manager:
                logger.info("2단계: 프록시 연결...")
                proxy_result = await self.proxy_manager.connect()
                if proxy_result:
                    logger.info("프록시 연결 성공")
                    steps_completed.append("proxy_setup")
                else:
                    logger.warning("프록시 연결 실패, 계속 진행...")
            
            # 3. 개인 정보 준비
            logger.info("3단계: 개인 정보 준비...")
            personal_info = custom_info or self.form_filler.generate_random_personal_info()
            logger.info(f"사용할 개인정보: {personal_info.first_name} {personal_info.last_name}")
            steps_completed.append("personal_info_generation")
            
            # 4. Google 계정 생성 페이지 열기
            logger.info("4단계: Google 계정 생성 페이지 열기...")
            if not await self._open_google_signup_page():
                return AccountCreationResult(
                    success=False,
                    error_message="Google 계정 생성 페이지 열기 실패",
                    steps_completed=steps_completed
                )
            steps_completed.append("signup_page_opened")
            
            # 5. 개인 정보 폼 채우기
            logger.info("5단계: 개인 정보 폼 채우기...")
            if not await self.form_filler.fill_personal_info_form(personal_info):
                return AccountCreationResult(
                    success=False,
                    error_message="개인 정보 폼 채우기 실패",
                    steps_completed=steps_completed
                )
            steps_completed.append("personal_info_filled")
            
            # 6. 생년월일 입력
            logger.info("6단계: 생년월일 입력...")
            if not await self.form_filler.fill_birth_date(personal_info):
                logger.warning("생년월일 입력 실패, 계속 진행...")
            else:
                steps_completed.append("birth_date_filled")
            
            # 7. 성별 선택
            logger.info("7단계: 성별 선택...")
            if not await self.form_filler.select_gender(personal_info.gender):
                logger.warning("성별 선택 실패, 계속 진행...")
            else:
                steps_completed.append("gender_selected")
            
            # 8. 다음 단계로 진행
            logger.info("8단계: 다음 단계로 진행...")
            if not await self.form_filler.click_next_button():
                return AccountCreationResult(
                    success=False,
                    error_message="다음 버튼 클릭 실패",
                    steps_completed=steps_completed
                )
            steps_completed.append("next_step_clicked")
            
            # 9. 전화번호 인증 처리
            logger.info("9단계: 전화번호 인증 처리...")
            phone_result = await self._handle_phone_verification()
            if not phone_result['success']:
                return AccountCreationResult(
                    success=False,
                    error_message=f"전화번호 인증 실패: {phone_result['error']}",
                    steps_completed=steps_completed
                )
            personal_info.phone_number = phone_result['phone_number']
            steps_completed.append("phone_verification_completed")
            
            # 10. 계정 설정 완료
            logger.info("10단계: 계정 설정 완료...")
            if not await self._complete_account_setup():
                logger.warning("계정 설정 완료 실패, 하지만 계정은 생성되었을 수 있습니다.")
            else:
                steps_completed.append("account_setup_completed")
            
            # 11. 계정 생성 확인
            logger.info("11단계: 계정 생성 확인...")
            email = f"{personal_info.username}@gmail.com"
            
            # 성공 결과 반환
            result = AccountCreationResult(
                success=True,
                email=email,
                password=personal_info.password,
                phone_number=personal_info.phone_number,
                creation_time=start_time,
                steps_completed=steps_completed
            )
            
            logger.info(f"Google 계정 생성 성공! 이메일: {email}")
            return result
            
        except Exception as e:
            logger.error(f"Google 계정 생성 중 오류 발생: {e}")
            return AccountCreationResult(
                success=False,
                error_message=str(e),
                steps_completed=steps_completed
            )
    
    async def _open_google_signup_page(self) -> bool:
        """
        Google 계정 생성 페이지를 엽니다.
        
        Returns:
            성공 여부
        """
        try:
            # Chrome 브라우저 열기
            await self.adb.start_app("com.android.chrome")
            await asyncio.sleep(random.uniform(3.0, 5.0))
            
            # Google 계정 생성 URL로 이동
            signup_url = "https://accounts.google.com/signup"
            await self.adb.input_text(signup_url)
            await self.adb.key_event("KEYCODE_ENTER")
            
            # 페이지 로딩 대기
            await asyncio.sleep(random.uniform(5.0, 8.0))
            
            # 페이지가 제대로 로드되었는지 확인
            screenshot_path = await self.adb.capture_screenshot()
            if screenshot_path:
                ocr_results = await self.ocr.extract_text_with_coordinates(screenshot_path)
                page_text = ' '.join([result['text'] for result in ocr_results]).lower()
                
                if any(keyword in page_text for keyword in ['create', 'account', '계정', '만들기', 'sign up']):
                    logger.info("Google 계정 생성 페이지 로드 확인")
                    return True
            
            logger.warning("Google 계정 생성 페이지 로드 확인 실패")
            return False
            
        except Exception as e:
            logger.error(f"Google 계정 생성 페이지 열기 실패: {e}")
            return False
    
    async def _handle_phone_verification(self) -> Dict[str, Any]:
        """
        전화번호 인증을 처리합니다.
        
        Returns:
            인증 결과 딕셔너리
        """
        try:
            logger.info("전화번호 인증 프로세스 시작...")
            
            # 전화번호 구매
            phone_result = await self.phone_verification.get_phone_number("google")
            if not phone_result['success']:
                return {
                    'success': False,
                    'error': f"전화번호 구매 실패: {phone_result['error']}"
                }
            
            phone_number = phone_result['phone_number']
            order_id = phone_result['order_id']
            
            logger.info(f"전화번호 구매 성공: {phone_number}")
            
            # 전화번호 입력
            if not await self.form_filler.find_and_fill_field("Phone", phone_number):
                if not await self.form_filler.find_and_fill_field("전화번호", phone_number):
                    return {
                        'success': False,
                        'error': "전화번호 입력 필드를 찾을 수 없음"
                    }
            
            # 인증 코드 전송 버튼 클릭
            await asyncio.sleep(random.uniform(1.0, 2.0))
            if not await self.form_filler.click_next_button():
                return {
                    'success': False,
                    'error': "인증 코드 전송 버튼 클릭 실패"
                }
            
            # SMS 인증 코드 대기
            logger.info("SMS 인증 코드 대기 중...")
            sms_result = await self.sms_verifier.wait_for_sms(order_id, timeout=300)
            
            if not sms_result['success']:
                return {
                    'success': False,
                    'error': f"SMS 인증 코드 수신 실패: {sms_result['error']}"
                }
            
            verification_code = sms_result['code']
            logger.info(f"인증 코드 수신: {verification_code}")
            
            # 인증 코드 입력
            if not await self.form_filler.find_and_fill_field("Code", verification_code):
                if not await self.form_filler.find_and_fill_field("인증", verification_code):
                    return {
                        'success': False,
                        'error': "인증 코드 입력 필드를 찾을 수 없음"
                    }
            
            # 인증 확인 버튼 클릭
            await asyncio.sleep(random.uniform(1.0, 2.0))
            if not await self.form_filler.click_next_button():
                return {
                    'success': False,
                    'error': "인증 확인 버튼 클릭 실패"
                }
            
            logger.info("전화번호 인증 완료")
            return {
                'success': True,
                'phone_number': phone_number,
                'order_id': order_id
            }
            
        except Exception as e:
            logger.error(f"전화번호 인증 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _complete_account_setup(self) -> bool:
        """
        계정 설정을 완료합니다.
        
        Returns:
            성공 여부
        """
        try:
            logger.info("계정 설정 완료 프로세스 시작...")
            
            # 여러 단계의 설정 페이지를 처리
            max_steps = 5
            for step in range(max_steps):
                logger.info(f"설정 단계 {step + 1}/{max_steps} 처리 중...")
                
                # 화면 캡처 및 분석
                screenshot_path = await self.adb.capture_screenshot()
                if not screenshot_path:
                    continue
                
                ocr_results = await self.ocr.extract_text_with_coordinates(screenshot_path)
                page_text = ' '.join([result['text'] for result in ocr_results]).lower()
                
                # 완료 페이지 확인
                if any(keyword in page_text for keyword in ['welcome', '환영', 'success', '성공', 'complete', '완료']):
                    logger.info("계정 설정 완료 페이지 도달")
                    return True
                
                # 건너뛰기 또는 다음 버튼 찾기
                skip_keywords = ['Skip', '건너뛰기', 'Not now', '나중에', 'Next', '다음']
                button_clicked = False
                
                for result in ocr_results:
                    text = result['text']
                    if any(keyword.lower() in text.lower() for keyword in skip_keywords):
                        await self.form_filler._human_like_tap(result['coordinates'])
                        logger.info(f"버튼 클릭: {text}")
                        button_clicked = True
                        break
                
                if button_clicked:
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                else:
                    # 버튼을 찾지 못한 경우 뒤로 가기 시도
                    logger.warning("설정 버튼을 찾을 수 없음, 뒤로 가기 시도")
                    await self.adb.key_event("KEYCODE_BACK")
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            
            logger.info("계정 설정 단계 완료")
            return True
            
        except Exception as e:
            logger.error(f"계정 설정 완료 실패: {e}")
            return False


# 편의 함수들
async def create_google_account(device_id: Optional[str] = None, 
                              custom_info: Optional[PersonalInfo] = None) -> AccountCreationResult:
    """
    Google 계정을 생성하는 편의 함수
    
    Args:
        device_id: 대상 디바이스 ID
        custom_info: 사용자 지정 개인 정보
    
    Returns:
        계정 생성 결과
    """
    # 필요한 컴포넌트들 초기화
    adb_controller = ADBController(device_id)
    ocr_processor = OCRProcessor()
    device_randomizer = DeviceRandomizer(adb_controller)
    sms_verifier = SMSVerifier()
    phone_verification = PhoneVerification()
    
    # 계정 생성기 생성 및 실행
    creator = GoogleAccountCreator(
        adb_controller=adb_controller,
        ocr_processor=ocr_processor,
        device_randomizer=device_randomizer,
        sms_verifier=sms_verifier,
        phone_verification=phone_verification
    )
    
    return await creator.create_account(custom_info)


if __name__ == "__main__":
    # 테스트 코드
    import asyncio
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def test_account_creation():
        """계정 생성 테스트"""
        try:
            logger.info("Google 계정 생성 테스트 시작...")
            
            result = await create_google_account()
            
            if result.success:
                print(f"✅ 계정 생성 성공!")
                print(f"이메일: {result.email}")
                print(f"비밀번호: {result.password}")
                print(f"전화번호: {result.phone_number}")
                print(f"완료된 단계: {result.steps_completed}")
            else:
                print(f"❌ 계정 생성 실패: {result.error_message}")
                print(f"완료된 단계: {result.steps_completed}")
                
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    asyncio.run(test_account_creation()) 