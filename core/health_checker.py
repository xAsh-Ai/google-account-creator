"""
Account Health Checker Module

This module monitors the health and survival rate of created Google accounts.
It performs periodic checks on account status by attempting to login to various Google services.
"""

import time
import json
import pandas as pd
import asyncio
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    WebDriverException, TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)

from .error_recovery import ErrorRecoveryManager
from .account_logger import AccountLogger

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class AccountHealthStatus:
    """계정 상태 정보를 담는 데이터 클래스"""
    email: str
    password: str
    status: str  # 'healthy', 'suspended', 'locked', 'disabled', 'unknown'
    last_checked: str
    gmail_accessible: bool
    youtube_accessible: bool
    error_message: Optional[str] = None
    check_count: int = 0
    first_created: Optional[str] = None
    last_successful_login: Optional[str] = None


@dataclass
class NotificationConfig:
    """알림 설정 클래스"""
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    email_config: Optional[Dict[str, str]] = None
    notification_thresholds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.notification_thresholds is None:
            self.notification_thresholds = {
                'critical_survival_rate': 30.0,  # 30% 이하 생존율
                'warning_survival_rate': 50.0,   # 50% 이하 생존율
                'high_error_rate': 20.0,          # 20% 이상 에러율
                'account_suspension_rate': 10.0    # 10% 이상 정지율
            }


class HealthChecker:
    """Google 계정 상태 모니터링 및 생존율 추적 클래스"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.error_recovery = ErrorRecoveryManager()
        self.account_logger = AccountLogger()
        
        # 설정 변수들
        self.check_timeout = self.config.get('check_timeout', 30)
        self.batch_size = self.config.get('batch_size', 5)
        self.retry_attempts = self.config.get('retry_attempts', 3)
        self.check_interval_hours = self.config.get('check_interval_hours', 24)
        
        # 알림 설정
        self.notification_config = NotificationConfig(
            slack_webhook_url=self.config.get('slack_webhook_url'),
            discord_webhook_url=self.config.get('discord_webhook_url'),
            email_config=self.config.get('email_config'),
            notification_thresholds=self.config.get('notification_thresholds')
        )
        
        # 파일 경로
        self.data_dir = Path("data")
        self.health_log_path = self.data_dir / "account_health.csv"
        self.survival_stats_path = self.data_dir / "survival_stats.json"
        
        # 디렉토리 생성
        self.data_dir.mkdir(exist_ok=True)
        
        # 상태 추적
        self.check_results: List[AccountHealthStatus] = []
        self.survival_stats = {
            'total_checks': 0,
            'healthy_accounts': 0,
            'suspended_accounts': 0,
            'locked_accounts': 0,
            'disabled_accounts': 0,
            'unknown_status': 0,
            'survival_rate': 0.0,
            'last_update': None
        }
        
        logger.info("Health Checker 초기화 완료")
    
    def _create_chrome_driver(self) -> uc.Chrome:
        """Undetected Chrome 드라이버 생성"""
        try:
            options = uc.ChromeOptions()
            
            # 헤드리스 모드 설정 (선택적)
            if self.config.get('headless', False):
                options.add_argument('--headless')
            
            # 기본 Chrome 옵션들
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # User-Agent 설정
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')
            
            # 웹드라이버 생성
            driver = uc.Chrome(options=options, version_main=119)
            
            # 자동화 감지 방지
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome 드라이버 생성 성공")
            return driver
            
        except Exception as e:
            logger.error(f"Chrome 드라이버 생성 실패: {e}")
            raise
    
    def _load_accounts_from_csv(self, csv_path: str) -> List[Dict[str, str]]:
        """CSV 파일에서 계정 정보 로드"""
        try:
            if not Path(csv_path).exists():
                logger.warning(f"계정 CSV 파일이 존재하지 않습니다: {csv_path}")
                return []
            
            df = pd.read_csv(csv_path)
            accounts = []
            
            for _, row in df.iterrows():
                if 'email' in row and 'password' in row:
                    accounts.append({
                        'email': row['email'],
                        'password': row['password'],
                        'created_at': row.get('created_at', ''),
                        'phone': row.get('phone', ''),
                        'recovery_email': row.get('recovery_email', '')
                    })
            
            logger.info(f"CSV에서 {len(accounts)}개 계정 로드 완료")
            return accounts
            
        except Exception as e:
            logger.error(f"계정 CSV 로드 실패: {e}")
            return []
    
    def _save_health_status(self, status_list: List[AccountHealthStatus]):
        """계정 상태를 CSV 파일에 저장"""
        try:
            # 데이터프레임으로 변환
            df_data = [asdict(status) for status in status_list]
            df = pd.DataFrame(df_data)
            
            # 기존 데이터와 병합
            if self.health_log_path.exists():
                existing_df = pd.read_csv(self.health_log_path)
                # 이메일 기준으로 중복 제거 (최신 상태만 유지)
                df = pd.concat([existing_df, df]).drop_duplicates(subset=['email'], keep='last')
            
            df.to_csv(self.health_log_path, index=False)
            logger.info(f"계정 상태 {len(status_list)}개 저장 완료: {self.health_log_path}")
            
        except Exception as e:
            logger.error(f"계정 상태 저장 실패: {e}")
    
    def _calculate_survival_rate(self):
        """생존율 계산 및 통계 업데이트"""
        try:
            if not self.health_log_path.exists():
                return
            
            df = pd.read_csv(self.health_log_path)
            total_accounts = len(df)
            
            if total_accounts == 0:
                return
            
            # 상태별 카운트
            status_counts = df['status'].value_counts()
            
            self.survival_stats.update({
                'total_checks': total_accounts,
                'healthy_accounts': status_counts.get('healthy', 0),
                'suspended_accounts': status_counts.get('suspended', 0),
                'locked_accounts': status_counts.get('locked', 0),
                'disabled_accounts': status_counts.get('disabled', 0),
                'unknown_status': status_counts.get('unknown', 0),
                'survival_rate': (status_counts.get('healthy', 0) / total_accounts) * 100,
                'last_update': datetime.now().isoformat()
            })
            
            # 통계 파일에 저장
            with open(self.survival_stats_path, 'w', encoding='utf-8') as f:
                json.dump(self.survival_stats, f, indent=2, ensure_ascii=False)
            
            logger.info(f"생존율 계산 완료: {self.survival_stats['survival_rate']:.2f}%")
            
        except Exception as e:
            logger.error(f"생존율 계산 실패: {e}")
    
    def setup_selenium_environment(self) -> bool:
        """Selenium 환경 설정 및 테스트"""
        try:
            logger.info("Selenium 환경 설정 시작...")
            
            # 테스트용 드라이버 생성
            test_driver = self._create_chrome_driver()
            
            # Google 페이지로 테스트 접속
            test_driver.get("https://www.google.com")
            
            # 페이지 로드 확인
            WebDriverWait(test_driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            
            test_driver.quit()
            logger.info("Selenium 환경 설정 완료 ✓")
            return True
            
        except Exception as e:
            logger.error(f"Selenium 환경 설정 실패: {e}")
            return False
    
    async def run_health_check_batch(self, accounts: List[Dict[str, str]]) -> List[AccountHealthStatus]:
        """배치 단위로 계정 상태 확인"""
        logger.info(f"배치 상태 확인 시작: {len(accounts)}개 계정")
        
        results = []
        
        # ThreadPoolExecutor를 사용한 병렬 처리
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            future_to_account = {
                executor.submit(self._check_single_account, account): account 
                for account in accounts
            }
            
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result(timeout=self.check_timeout * 2)
                    if result:
                        results.append(result)
                        logger.info(f"계정 확인 완료: {account['email']} - {result.status}")
                except Exception as e:
                    logger.error(f"계정 확인 실패: {account['email']} - {e}")
                    # 실패한 경우에도 결과 기록
                    error_status = AccountHealthStatus(
                        email=account['email'],
                        password=account['password'],
                        status='unknown',
                        last_checked=datetime.now().isoformat(),
                        gmail_accessible=False,
                        youtube_accessible=False,
                        error_message=str(e),
                        check_count=1
                    )
                    results.append(error_status)
        
        logger.info(f"배치 상태 확인 완료: {len(results)}개 결과")
        return results
    
    def get_health_statistics(self) -> Dict[str, Any]:
        """현재 상태 통계 반환"""
        return self.survival_stats.copy()
    
    def get_accounts_by_status(self, status: str) -> List[AccountHealthStatus]:
        """특정 상태의 계정들 반환"""
        try:
            if not self.health_log_path.exists():
                return []
            
            df = pd.read_csv(self.health_log_path)
            filtered_df = df[df['status'] == status]
            
            return [
                AccountHealthStatus(**row.to_dict()) 
                for _, row in filtered_df.iterrows()
            ]
            
        except Exception as e:
            logger.error(f"상태별 계정 조회 실패: {e}")
            return []
    
    def _check_single_account(self, account: Dict[str, str]) -> Optional[AccountHealthStatus]:
        """단일 계정 상태 확인"""
        email = account['email']
        password = account['password']
        driver = None
        
        try:
            logger.info(f"계정 상태 확인 시작: {email}")
            
            # Chrome 드라이버 생성
            driver = self._create_chrome_driver()
            
            # Gmail 로그인 테스트
            gmail_result = self._test_gmail_login(driver, email, password)
            
            # YouTube 로그인 테스트 (Gmail이 성공한 경우만)
            youtube_result = False
            if gmail_result['success']:
                youtube_result = self._test_youtube_access(driver)
            
            # 상태 결정
            status = self._determine_account_status(gmail_result, youtube_result)
            
            return AccountHealthStatus(
                email=email,
                password=password,
                status=status,
                last_checked=datetime.now().isoformat(),
                gmail_accessible=gmail_result['success'],
                youtube_accessible=youtube_result,
                error_message=gmail_result.get('error'),
                check_count=1,
                last_successful_login=datetime.now().isoformat() if gmail_result['success'] else None
            )
            
        except Exception as e:
            logger.error(f"계정 확인 중 오류 발생: {email} - {e}")
            return AccountHealthStatus(
                email=email,
                password=password,
                status='unknown',
                last_checked=datetime.now().isoformat(),
                gmail_accessible=False,
                youtube_accessible=False,
                error_message=str(e),
                check_count=1
            )
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _test_gmail_login(self, driver: uc.Chrome, email: str, password: str) -> Dict[str, Any]:
        """Gmail 로그인 테스트"""
        try:
            logger.info(f"Gmail 로그인 테스트 시작: {email}")
            
            # Gmail 로그인 페이지로 이동
            driver.get("https://accounts.google.com/signin")
            
            # 이메일 입력
            email_input = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.ID, "identifierId"))
            )
            email_input.clear()
            email_input.send_keys(email)
            
            # 다음 버튼 클릭
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "identifierNext"))
            )
            next_button.click()
            
            # 잠시 대기
            time.sleep(2)
            
            # 계정이 존재하지 않는 경우 체크
            try:
                error_element = driver.find_element(By.CSS_SELECTOR, "[data-error-code]")
                if error_element:
                    error_text = error_element.text.lower()
                    if "find your google account" in error_text or "couldn't find" in error_text:
                        return {'success': False, 'error': 'account_not_found', 'message': 'Account does not exist'}
            except NoSuchElementException:
                pass
            
            # 패스워드 입력 필드 대기
            try:
                password_input = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.NAME, "password"))
                )
                password_input.clear()
                password_input.send_keys(password)
                
                # 패스워드 다음 버튼 클릭
                password_next = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "passwordNext"))
                )
                password_next.click()
                
            except TimeoutException:
                # 패스워드 입력 필드가 나타나지 않음 (계정 비활성화 등)
                return {'success': False, 'error': 'password_field_not_found', 'message': 'Password field not available'}
            
            # 로그인 결과 확인을 위해 잠시 대기
            time.sleep(3)
            
            # 로그인 성공 확인
            current_url = driver.current_url
            
            # 2단계 인증이나 추가 보안 확인 페이지 체크
            if "challenge" in current_url or "signin/v2/challenge" in current_url:
                return {'success': False, 'error': '2fa_required', 'message': 'Two-factor authentication required'}
            
            # 계정 복구 페이지 체크
            if "recovery" in current_url or "disabled" in current_url:
                return {'success': False, 'error': 'account_disabled', 'message': 'Account disabled or requires recovery'}
            
            # 잘못된 패스워드 에러 체크
            try:
                password_error = driver.find_element(By.CSS_SELECTOR, "[data-error-code], .LXRPh")
                if password_error and password_error.is_displayed():
                    error_text = password_error.text.lower()
                    if "wrong password" in error_text or "incorrect" in error_text:
                        return {'success': False, 'error': 'wrong_password', 'message': 'Incorrect password'}
            except NoSuchElementException:
                pass
            
            # Gmail 페이지로 리다이렉트 시도
            driver.get("https://mail.google.com")
            
            # Gmail 인터페이스 로드 확인
            try:
                WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-tooltip='Gmail']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".bkK")),  # Gmail logo
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".gb_2")),  # User profile
                        EC.url_contains("mail.google.com")
                    )
                )
                
                # 계정 정지 메시지 확인
                try:
                    suspended_message = driver.find_element(By.XPATH, "//*[contains(text(), 'suspended') or contains(text(), 'disabled')]")
                    if suspended_message and suspended_message.is_displayed():
                        return {'success': False, 'error': 'account_suspended', 'message': 'Account suspended'}
                except NoSuchElementException:
                    pass
                
                logger.info(f"Gmail 로그인 성공: {email}")
                return {'success': True, 'message': 'Gmail login successful'}
                
            except TimeoutException:
                # Gmail 페이지가 로드되지 않음
                current_url = driver.current_url
                if "accounts.google.com" in current_url:
                    return {'success': False, 'error': 'login_failed', 'message': 'Login failed - redirected back to login page'}
                else:
                    return {'success': False, 'error': 'gmail_load_failed', 'message': 'Gmail interface did not load'}
            
        except TimeoutException as e:
            logger.error(f"Gmail 로그인 타임아웃: {email} - {e}")
            return {'success': False, 'error': 'timeout', 'message': 'Login timeout'}
        except Exception as e:
            logger.error(f"Gmail 로그인 오류: {email} - {e}")
            return {'success': False, 'error': 'unknown', 'message': str(e)}
    
    def _test_youtube_access(self, driver: uc.Chrome) -> bool:
        """YouTube 접근 테스트"""
        try:
            logger.info("YouTube 접근 테스트 시작")
            
            # YouTube 페이지로 이동
            driver.get("https://www.youtube.com")
            
            # YouTube 페이지 로드 확인
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.ID, "logo")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#logo-icon")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ytd-topbar-logo-renderer"))
                )
            )
            
            # 로그인 상태 확인 (프로필 아이콘 또는 로그인 버튼)
            try:
                # 프로필 아이콘이 있으면 로그인된 상태
                profile_icon = driver.find_element(By.CSS_SELECTOR, "#avatar-btn, .ytd-topbar-menu-button-renderer")
                if profile_icon:
                    logger.info("YouTube 접근 성공 - 로그인 상태 확인")
                    return True
            except NoSuchElementException:
                pass
            
            # 계정 정지/제한 메시지 확인
            try:
                restriction_message = driver.find_element(By.XPATH, "//*[contains(text(), 'suspended') or contains(text(), 'terminated') or contains(text(), 'disabled')]")
                if restriction_message and restriction_message.is_displayed():
                    logger.warning("YouTube 계정 제한 감지")
                    return False
            except NoSuchElementException:
                pass
            
            # 기본적으로 YouTube 페이지가 로드되면 성공으로 간주
            logger.info("YouTube 접근 성공")
            return True
            
        except TimeoutException:
            logger.error("YouTube 접근 타임아웃")
            return False
        except Exception as e:
            logger.error(f"YouTube 접근 오류: {e}")
            return False
    
    def _determine_account_status(self, gmail_result: Dict[str, Any], youtube_accessible: bool) -> str:
        """계정 상태 결정"""
        if not gmail_result['success']:
            error_type = gmail_result.get('error', 'unknown')
            
            if error_type == 'account_not_found':
                return 'disabled'
            elif error_type == 'account_disabled' or error_type == 'account_suspended':
                return 'suspended'
            elif error_type == 'wrong_password':
                return 'locked'  # 패스워드가 변경되었거나 계정이 잠김
            elif error_type == '2fa_required':
                return 'locked'  # 2단계 인증 활성화로 접근 불가
            else:
                return 'unknown'
        
        # Gmail 로그인은 성공했지만 YouTube에 문제가 있는 경우
        if gmail_result['success'] and not youtube_accessible:
            return 'healthy'  # Gmail만 되어도 일단 건강한 상태로 분류
        
        # 둘 다 성공
        if gmail_result['success'] and youtube_accessible:
            return 'healthy'
        
        return 'unknown'
    
    def update_account_status(self, email: str, new_status: AccountHealthStatus):
        """특정 계정의 상태 업데이트"""
        try:
            logger.info(f"계정 상태 업데이트: {email} -> {new_status.status}")
            
            # 기존 데이터 로드
            existing_data = []
            if self.health_log_path.exists():
                df = pd.read_csv(self.health_log_path)
                existing_data = df.to_dict('records')
            
            # 해당 계정의 기존 기록 찾기
            updated = False
            for record in existing_data:
                if record['email'] == email:
                    # 기존 기록 업데이트
                    record.update({
                        'status': new_status.status,
                        'last_checked': new_status.last_checked,
                        'gmail_accessible': new_status.gmail_accessible,
                        'youtube_accessible': new_status.youtube_accessible,
                        'error_message': new_status.error_message,
                        'check_count': record.get('check_count', 0) + 1,
                        'last_successful_login': new_status.last_successful_login
                    })
                    updated = True
                    break
            
            # 새 계정인 경우 추가
            if not updated:
                new_record = asdict(new_status)
                new_record['check_count'] = 1
                existing_data.append(new_record)
            
            # 데이터프레임으로 변환하여 저장
            df = pd.DataFrame(existing_data)
            df.to_csv(self.health_log_path, index=False)
            
            # 생존율 재계산
            self._calculate_survival_rate()
            
            logger.info(f"계정 상태 업데이트 완료: {email}")
            
        except Exception as e:
            logger.error(f"계정 상태 업데이트 실패: {email} - {e}")
    
    def batch_update_status(self, status_list: List[AccountHealthStatus]):
        """여러 계정의 상태를 일괄 업데이트"""
        try:
            logger.info(f"일괄 상태 업데이트 시작: {len(status_list)}개 계정")
            
            # 기존 데이터 로드
            existing_data = {}
            if self.health_log_path.exists():
                df = pd.read_csv(self.health_log_path)
                existing_data = {row['email']: row.to_dict() for _, row in df.iterrows()}
            
            # 새 상태로 업데이트
            for new_status in status_list:
                email = new_status.email
                
                if email in existing_data:
                    # 기존 기록 업데이트
                    existing_record = existing_data[email]
                    existing_record.update({
                        'status': new_status.status,
                        'last_checked': new_status.last_checked,
                        'gmail_accessible': new_status.gmail_accessible,
                        'youtube_accessible': new_status.youtube_accessible,
                        'error_message': new_status.error_message,
                        'check_count': existing_record.get('check_count', 0) + 1,
                        'last_successful_login': new_status.last_successful_login
                    })
                else:
                    # 새 계정 추가
                    new_record = asdict(new_status)
                    new_record['check_count'] = 1
                    existing_data[email] = new_record
            
            # 데이터프레임으로 변환하여 저장
            df = pd.DataFrame(list(existing_data.values()))
            df.to_csv(self.health_log_path, index=False)
            
            # 생존율 재계산
            self._calculate_survival_rate()
            
            logger.info(f"일괄 상태 업데이트 완료: {len(status_list)}개 계정")
            
        except Exception as e:
            logger.error(f"일괄 상태 업데이트 실패: {e}")
    
    def get_account_history(self, email: str) -> Dict[str, Any]:
        """특정 계정의 이력 조회"""
        try:
            if not self.health_log_path.exists():
                return {}
            
            df = pd.read_csv(self.health_log_path)
            account_data = df[df['email'] == email]
            
            if account_data.empty:
                return {}
            
            latest_record = account_data.iloc[-1].to_dict()
            
            # 추가 통계 계산
            total_checks = latest_record.get('check_count', 0)
            healthy_ratio = 1.0 if latest_record.get('status') == 'healthy' else 0.0
            
            return {
                'email': email,
                'current_status': latest_record.get('status'),
                'last_checked': latest_record.get('last_checked'),
                'total_checks': total_checks,
                'gmail_accessible': latest_record.get('gmail_accessible'),
                'youtube_accessible': latest_record.get('youtube_accessible'),
                'last_error': latest_record.get('error_message'),
                'first_created': latest_record.get('first_created'),
                'last_successful_login': latest_record.get('last_successful_login'),
                'health_score': healthy_ratio
            }
            
        except Exception as e:
            logger.error(f"계정 이력 조회 실패: {email} - {e}")
            return {}
    
    def cleanup_old_records(self, days_to_keep: int = 30):
        """오래된 기록 정리"""
        try:
            if not self.health_log_path.exists():
                return
            
            df = pd.read_csv(self.health_log_path)
            
            # 날짜 변환
            df['last_checked'] = pd.to_datetime(df['last_checked'])
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # 최신 기록만 유지
            df_filtered = df[df['last_checked'] >= cutoff_date]
            
            # 각 계정별로 최신 기록은 반드시 유지
            latest_per_account = df.groupby('email')['last_checked'].idxmax()
            latest_records = df.loc[latest_per_account]
            
            # 필터링된 데이터와 최신 기록 병합
            df_final = pd.concat([df_filtered, latest_records]).drop_duplicates()
            
            # 저장
            df_final.to_csv(self.health_log_path, index=False)
            
            logger.info(f"오래된 기록 정리 완료: {len(df) - len(df_final)}개 기록 제거")
            
        except Exception as e:
            logger.error(f"기록 정리 실패: {e}")
    
    def export_health_report(self, output_path: Optional[str] = None) -> str:
        """상태 리포트를 JSON 형태로 출력"""
        try:
            if output_path is None:
                output_path = self.data_dir / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # 현재 통계
            stats = self.get_health_statistics()
            
            # 계정별 상세 정보
            accounts_detail = []
            if self.health_log_path.exists():
                df = pd.read_csv(self.health_log_path)
                for _, row in df.iterrows():
                    accounts_detail.append({
                        'email': row['email'],
                        'status': row['status'],
                        'last_checked': row['last_checked'],
                        'gmail_accessible': row['gmail_accessible'],
                        'youtube_accessible': row['youtube_accessible'],
                        'check_count': row.get('check_count', 0),
                        'error_message': row.get('error_message')
                    })
            
            # 리포트 구성
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': stats,
                'account_details': accounts_detail,
                'recommendations': self._generate_recommendations(stats)
            }
            
            # 파일로 저장
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"상태 리포트 생성 완료: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"리포트 생성 실패: {e}")
            return ""
    
    def _generate_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """통계를 바탕으로 권장사항 생성"""
        recommendations = []
        
        survival_rate = stats.get('survival_rate', 0)
        total_accounts = stats.get('total_checks', 0)
        
        if survival_rate < 50:
            recommendations.append("생존율이 50% 미만입니다. 계정 생성 과정을 검토해보세요.")
        elif survival_rate < 70:
            recommendations.append("생존율이 평균 이하입니다. 프록시나 디바이스 핑거프린팅을 개선해보세요.")
        elif survival_rate > 90:
            recommendations.append("매우 높은 생존율을 유지하고 있습니다. 현재 전략을 계속 사용하세요.")
        
        if stats.get('suspended_accounts', 0) > total_accounts * 0.2:
            recommendations.append("정지된 계정 비율이 높습니다. 계정 활동 패턴을 다양화하세요.")
        
        if stats.get('locked_accounts', 0) > total_accounts * 0.1:
            recommendations.append("잠긴 계정이 많습니다. 2단계 인증 설정이나 비밀번호 변경을 확인하세요.")
        
        if total_accounts == 0:
            recommendations.append("확인된 계정이 없습니다. 계정 생성을 시작하고 정기적으로 상태를 확인하세요.")
        
        return recommendations
    
    async def run_periodic_health_check(self, csv_path: str, interval_hours: int = 24):
        """주기적인 상태 확인 실행"""
        logger.info(f"주기적 상태 확인 시작: {interval_hours}시간 간격")
        
        while True:
            try:
                # 계정 목록 로드
                accounts = self._load_accounts_from_csv(csv_path)
                
                if not accounts:
                    logger.warning("확인할 계정이 없습니다.")
                    await asyncio.sleep(interval_hours * 3600)
                    continue
                
                logger.info(f"상태 확인 시작: {len(accounts)}개 계정")
                
                # 배치 단위로 확인
                all_results = []
                for i in range(0, len(accounts), self.batch_size):
                    batch = accounts[i:i + self.batch_size]
                    batch_results = await self.run_health_check_batch(batch)
                    all_results.extend(batch_results)
                    
                    # 배치 간 휴식
                    if i + self.batch_size < len(accounts):
                        await asyncio.sleep(10)
                
                # 결과 저장
                if all_results:
                    self.batch_update_status(all_results)
                    
                    # 상세 통계 계산
                    detailed_stats = self.calculate_detailed_survival_stats()
                    
                    # 알림 확인 및 전송
                    await self.check_and_notify(detailed_stats)
                    
                    # 리포트 생성
                    report_path = self.export_health_report()
                    logger.info(f"상태 확인 완료. 리포트: {report_path}")
                
                # 다음 확인까지 대기
                logger.info(f"다음 확인까지 {interval_hours}시간 대기")
                await asyncio.sleep(interval_hours * 3600)
                
            except Exception as e:
                logger.error(f"주기적 상태 확인 중 오류: {e}")
                
                # 오류 발생 시 긴급 알림 전송
                await self.send_emergency_alert(
                    "주기적 상태 확인 중 오류 발생",
                    {'error': str(e), 'timestamp': datetime.now().isoformat()}
                )
                
                await asyncio.sleep(300)  # 5분 후 재시도
    
    def calculate_detailed_survival_stats(self) -> Dict[str, Any]:
        """상세한 생존율 통계 계산"""
        try:
            if not self.health_log_path.exists():
                return self._get_empty_stats()
            
            df = pd.read_csv(self.health_log_path)
            
            if df.empty:
                return self._get_empty_stats()
            
            total_accounts = len(df)
            
            # 상태별 카운트
            status_counts = df['status'].value_counts()
            healthy_count = status_counts.get('healthy', 0)
            suspended_count = status_counts.get('suspended', 0)
            locked_count = status_counts.get('locked', 0)
            disabled_count = status_counts.get('disabled', 0)
            unknown_count = status_counts.get('unknown', 0)
            
            # 기본 생존율
            survival_rate = (healthy_count / total_accounts) * 100 if total_accounts > 0 else 0
            
            # 날짜별 생존율 추이 (최근 30일)
            df['last_checked'] = pd.to_datetime(df['last_checked'])
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_df = df[df['last_checked'] >= thirty_days_ago]
            
            recent_total = len(recent_df)
            recent_healthy = len(recent_df[recent_df['status'] == 'healthy'])
            recent_survival_rate = (recent_healthy / recent_total) * 100 if recent_total > 0 else 0
            
            # 계정 연령별 생존율 (생성일 기준)
            age_stats = self._calculate_age_based_survival(df)
            
            # 체크 횟수별 생존율
            check_stats = self._calculate_check_frequency_stats(df)
            
            # 시간대별 통계
            hourly_stats = self._calculate_hourly_trends(df)
            
            # 에러 패턴 분석
            error_stats = self._analyze_error_patterns(df)
            
            detailed_stats = {
                'overall': {
                    'total_accounts': total_accounts,
                    'healthy_accounts': healthy_count,
                    'suspended_accounts': suspended_count,
                    'locked_accounts': locked_count,
                    'disabled_accounts': disabled_count,
                    'unknown_status': unknown_count,
                    'survival_rate': round(survival_rate, 2),
                    'active_rate': round((healthy_count + locked_count) / total_accounts * 100, 2) if total_accounts > 0 else 0
                },
                'recent_trends': {
                    'last_30_days_total': recent_total,
                    'last_30_days_healthy': recent_healthy,
                    'last_30_days_survival_rate': round(recent_survival_rate, 2),
                    'trend_direction': 'improving' if recent_survival_rate > survival_rate else 'declining' if recent_survival_rate < survival_rate else 'stable'
                },
                'age_based_analysis': age_stats,
                'check_frequency_analysis': check_stats,
                'temporal_patterns': hourly_stats,
                'error_analysis': error_stats,
                'last_update': datetime.now().isoformat()
            }
            
            # 상세 통계 저장
            detailed_stats_path = self.data_dir / "detailed_survival_stats.json"
            with open(detailed_stats_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_stats, f, indent=2, ensure_ascii=False)
            
            # 기본 통계도 업데이트
            self.survival_stats.update(detailed_stats['overall'])
            self.survival_stats['last_update'] = detailed_stats['last_update']
            
            with open(self.survival_stats_path, 'w', encoding='utf-8') as f:
                json.dump(self.survival_stats, f, indent=2, ensure_ascii=False)
            
            logger.info(f"상세 생존율 계산 완료: {survival_rate:.2f}%")
            return detailed_stats
            
        except Exception as e:
            logger.error(f"상세 생존율 계산 실패: {e}")
            return self._get_empty_stats()
    
    def _get_empty_stats(self) -> Dict[str, Any]:
        """빈 통계 반환"""
        return {
            'overall': {
                'total_accounts': 0,
                'healthy_accounts': 0,
                'suspended_accounts': 0,
                'locked_accounts': 0,
                'disabled_accounts': 0,
                'unknown_status': 0,
                'survival_rate': 0.0,
                'active_rate': 0.0
            },
            'recent_trends': {
                'last_30_days_total': 0,
                'last_30_days_healthy': 0,
                'last_30_days_survival_rate': 0.0,
                'trend_direction': 'stable'
            },
            'age_based_analysis': {},
            'check_frequency_analysis': {},
            'temporal_patterns': {},
            'error_analysis': {},
            'last_update': datetime.now().isoformat()
        }
    
    def _calculate_age_based_survival(self, df: pd.DataFrame) -> Dict[str, Any]:
        """계정 연령별 생존율 분석"""
        try:
            if 'first_created' not in df.columns:
                return {}
            
            # 생성일이 있는 계정만 분석
            df_with_age = df[df['first_created'].notna()].copy()
            
            if df_with_age.empty:
                return {}
            
            df_with_age['first_created'] = pd.to_datetime(df_with_age['first_created'])
            df_with_age['age_days'] = (datetime.now() - df_with_age['first_created']).dt.days
            
            # 연령대별 분류
            age_groups = {
                '0-7_days': (0, 7),
                '8-30_days': (8, 30),
                '31-90_days': (31, 90),
                '91-365_days': (91, 365),
                'over_1_year': (366, float('inf'))
            }
            
            age_stats = {}
            for group_name, (min_age, max_age) in age_groups.items():
                if max_age == float('inf'):
                    group_df = df_with_age[df_with_age['age_days'] >= min_age]
                else:
                    group_df = df_with_age[(df_with_age['age_days'] >= min_age) & (df_with_age['age_days'] <= max_age)]
                
                if not group_df.empty:
                    total = len(group_df)
                    healthy = len(group_df[group_df['status'] == 'healthy'])
                    survival_rate = (healthy / total) * 100
                    
                    age_stats[group_name] = {
                        'total_accounts': total,
                        'healthy_accounts': healthy,
                        'survival_rate': round(survival_rate, 2)
                    }
            
            return age_stats
            
        except Exception as e:
            logger.error(f"연령별 생존율 분석 실패: {e}")
            return {}
    
    def _calculate_check_frequency_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """체크 횟수별 통계"""
        try:
            if 'check_count' not in df.columns:
                return {}
            
            # 체크 횟수별 분석
            freq_groups = {
                'single_check': (1, 1),
                'few_checks': (2, 5),
                'regular_checks': (6, 20),
                'frequent_checks': (21, float('inf'))
            }
            
            freq_stats = {}
            for group_name, (min_checks, max_checks) in freq_groups.items():
                if max_checks == float('inf'):
                    group_df = df[df['check_count'] >= min_checks]
                else:
                    group_df = df[(df['check_count'] >= min_checks) & (df['check_count'] <= max_checks)]
                
                if not group_df.empty:
                    total = len(group_df)
                    healthy = len(group_df[group_df['status'] == 'healthy'])
                    survival_rate = (healthy / total) * 100
                    
                    freq_stats[group_name] = {
                        'total_accounts': total,
                        'healthy_accounts': healthy,
                        'survival_rate': round(survival_rate, 2),
                        'avg_checks': round(group_df['check_count'].mean(), 1)
                    }
            
            return freq_stats
            
        except Exception as e:
            logger.error(f"체크 빈도 통계 계산 실패: {e}")
            return {}
    
    def _calculate_hourly_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """시간대별 패턴 분석"""
        try:
            df['last_checked'] = pd.to_datetime(df['last_checked'])
            df['check_hour'] = df['last_checked'].dt.hour
            
            hourly_stats = {}
            for hour in range(24):
                hour_df = df[df['check_hour'] == hour]
                
                if not hour_df.empty:
                    total = len(hour_df)
                    healthy = len(hour_df[hour_df['status'] == 'healthy'])
                    survival_rate = (healthy / total) * 100
                    
                    hourly_stats[f'hour_{hour:02d}'] = {
                        'total_checks': total,
                        'healthy_accounts': healthy,
                        'survival_rate': round(survival_rate, 2)
                    }
            
            # 최적 체크 시간대 찾기
            if hourly_stats:
                best_hour = max(hourly_stats.keys(), key=lambda k: hourly_stats[k]['survival_rate'])
                worst_hour = min(hourly_stats.keys(), key=lambda k: hourly_stats[k]['survival_rate'])
                
                hourly_stats['recommendations'] = {
                    'best_check_hour': best_hour,
                    'worst_check_hour': worst_hour,
                    'best_survival_rate': hourly_stats[best_hour]['survival_rate'],
                    'worst_survival_rate': hourly_stats[worst_hour]['survival_rate']
                }
            
            return hourly_stats
            
        except Exception as e:
            logger.error(f"시간대별 분석 실패: {e}")
            return {}
    
    def _analyze_error_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """에러 패턴 분석"""
        try:
            error_df = df[df['error_message'].notna() & (df['error_message'] != '')]
            
            if error_df.empty:
                return {'total_errors': 0, 'error_types': {}}
            
            # 에러 타입별 분석
            error_counts = error_df['error_message'].value_counts()
            error_types = {}
            
            for error_msg, count in error_counts.items():
                error_types[error_msg] = {
                    'count': count,
                    'percentage': round((count / len(error_df)) * 100, 2)
                }
            
            # 에러 발생률
            total_accounts = len(df)
            error_rate = (len(error_df) / total_accounts) * 100 if total_accounts > 0 else 0
            
            return {
                'total_errors': len(error_df),
                'error_rate': round(error_rate, 2),
                'error_types': error_types,
                'most_common_error': error_counts.index[0] if not error_counts.empty else None
            }
            
        except Exception as e:
            logger.error(f"에러 패턴 분석 실패: {e}")
            return {'total_errors': 0, 'error_types': {}}
    
    def get_survival_insights(self) -> List[str]:
        """생존율 데이터를 바탕으로 인사이트 생성"""
        try:
            detailed_stats = self.calculate_detailed_survival_stats()
            insights = []
            
            overall = detailed_stats['overall']
            trends = detailed_stats['recent_trends']
            
            # 전체 생존율 평가
            survival_rate = overall['survival_rate']
            if survival_rate >= 90:
                insights.append(f"🟢 뛰어난 생존율 ({survival_rate}%)을 기록하고 있습니다.")
            elif survival_rate >= 70:
                insights.append(f"🟡 양호한 생존율 ({survival_rate}%)입니다.")
            else:
                insights.append(f"🔴 생존율이 낮습니다 ({survival_rate}%). 개선이 필요합니다.")
            
            # 트렌드 분석
            if trends['trend_direction'] == 'improving':
                insights.append("📈 최근 30일 동안 생존율이 개선되고 있습니다.")
            elif trends['trend_direction'] == 'declining':
                insights.append("📉 최근 30일 동안 생존율이 하락하고 있습니다.")
            
            # 에러 분석
            error_analysis = detailed_stats.get('error_analysis', {})
            if error_analysis.get('error_rate', 0) > 20:
                insights.append(f"⚠️ 에러 발생률이 높습니다 ({error_analysis['error_rate']}%).")
            
            # 연령별 분석
            age_analysis = detailed_stats.get('age_based_analysis', {})
            if '0-7_days' in age_analysis:
                new_account_survival = age_analysis['0-7_days']['survival_rate']
                if new_account_survival < 50:
                    insights.append("🆕 신규 계정(7일 이내)의 생존율이 낮습니다. 초기 설정을 검토하세요.")
            
            # 시간대 분석
            temporal = detailed_stats.get('temporal_patterns', {})
            if 'recommendations' in temporal:
                best_hour = temporal['recommendations']['best_check_hour']
                insights.append(f"⏰ {best_hour.replace('hour_', '')}시에 체크할 때 생존율이 가장 높습니다.")
            
            return insights
            
        except Exception as e:
            logger.error(f"인사이트 생성 실패: {e}")
            return ["분석 중 오류가 발생했습니다."]
    
    def generate_survival_forecast(self, days_ahead: int = 7) -> Dict[str, Any]:
        """생존율 예측 (간단한 추세 기반)"""
        try:
            if not self.health_log_path.exists():
                return {}
            
            df = pd.read_csv(self.health_log_path)
            df['last_checked'] = pd.to_datetime(df['last_checked'])
            
            # 최근 30일간 일별 생존율 계산
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_df = df[df['last_checked'] >= thirty_days_ago]
            
            if recent_df.empty:
                return {}
            
            # 일별 그룹화
            daily_stats = []
            for i in range(30):
                date = thirty_days_ago + timedelta(days=i)
                day_df = recent_df[recent_df['last_checked'].dt.date == date.date()]
                
                if not day_df.empty:
                    total = len(day_df)
                    healthy = len(day_df[day_df['status'] == 'healthy'])
                    survival_rate = (healthy / total) * 100
                    
                    daily_stats.append({
                        'date': date.date().isoformat(),
                        'survival_rate': survival_rate,
                        'total_accounts': total
                    })
            
            if len(daily_stats) < 3:
                return {'forecast': 'insufficient_data'}
            
            # 간단한 선형 추세 계산
            rates = [stat['survival_rate'] for stat in daily_stats[-7:]]  # 최근 7일
            avg_rate = sum(rates) / len(rates)
            
            # 추세 계산 (최근 3일 vs 이전 3일)
            recent_3_avg = sum(rates[-3:]) / 3
            previous_3_avg = sum(rates[-6:-3]) / 3
            trend = recent_3_avg - previous_3_avg
            
            # 예측
            forecast = []
            for i in range(1, days_ahead + 1):
                future_date = datetime.now() + timedelta(days=i)
                predicted_rate = avg_rate + (trend * i)
                predicted_rate = max(0, min(100, predicted_rate))  # 0-100% 범위로 제한
                
                forecast.append({
                    'date': future_date.date().isoformat(),
                    'predicted_survival_rate': round(predicted_rate, 2)
                })
            
            return {
                'forecast': forecast,
                'current_trend': 'positive' if trend > 0 else 'negative' if trend < 0 else 'stable',
                'trend_strength': abs(trend),
                'confidence': 'low' if len(daily_stats) < 10 else 'medium',
                'base_rate': round(avg_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"생존율 예측 실패: {e}")
            return {}
    
    async def send_notification(self, message: str, severity: str = 'info', stats: Optional[Dict[str, Any]] = None):
        """알림 전송 (Slack, Discord, Email 지원)"""
        try:
            logger.info(f"알림 전송 시작: {severity} - {message[:50]}...")
            
            # 메시지 포맷팅
            formatted_message = self._format_notification_message(message, severity, stats)
            
            # 병렬로 모든 알림 채널에 전송
            tasks = []
            
            if self.notification_config.slack_webhook_url:
                tasks.append(self._send_slack_notification(formatted_message, severity))
            
            if self.notification_config.discord_webhook_url:
                tasks.append(self._send_discord_notification(formatted_message, severity))
            
            if self.notification_config.email_config:
                tasks.append(self._send_email_notification(formatted_message, severity))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for result in results if not isinstance(result, Exception))
                logger.info(f"알림 전송 완료: {success_count}/{len(tasks)}개 성공")
            else:
                logger.warning("설정된 알림 채널이 없습니다.")
                
        except Exception as e:
            logger.error(f"알림 전송 실패: {e}")
    
    def _format_notification_message(self, message: str, severity: str, stats: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """알림 메시지 포맷팅"""
        # 심각도별 이모지 및 색상
        severity_config = {
            'critical': {'emoji': '🚨', 'color': '#FF0000'},
            'warning': {'emoji': '⚠️', 'color': '#FFA500'},
            'info': {'emoji': 'ℹ️', 'color': '#0066CC'},
            'success': {'emoji': '✅', 'color': '#00AA00'}
        }
        
        config = severity_config.get(severity, severity_config['info'])
        
        formatted = {
            'text': f"{config['emoji']} {message}",
            'color': config['color'],
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        
        # 통계 정보 추가
        if stats:
            formatted['stats'] = stats
            
            # 간단한 요약 추가
            if 'overall' in stats:
                overall = stats['overall']
                formatted['summary'] = f"생존율: {overall.get('survival_rate', 0):.1f}% | 총 계정: {overall.get('total_accounts', 0)}개"
        
        return formatted
    
    async def _send_slack_notification(self, formatted_message: Dict[str, Any], severity: str) -> bool:
        """Slack 알림 전송"""
        try:
            webhook_url = self.notification_config.slack_webhook_url
            
            # Slack 메시지 포맷
            slack_payload = {
                "text": formatted_message['text'],
                "attachments": [
                    {
                        "color": formatted_message['color'],
                        "fields": [
                            {
                                "title": "상태 확인 시각",
                                "value": formatted_message['timestamp'],
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            # 통계 정보가 있으면 추가
            if 'summary' in formatted_message:
                slack_payload["attachments"][0]["fields"].append({
                    "title": "현재 상태",
                    "value": formatted_message['summary'],
                    "short": True
                })
            
            # 상세 통계가 있으면 추가
            if 'stats' in formatted_message and 'overall' in formatted_message['stats']:
                stats = formatted_message['stats']['overall']
                stats_text = f"건강: {stats.get('healthy_accounts', 0)}개\n정지: {stats.get('suspended_accounts', 0)}개\n잠금: {stats.get('locked_accounts', 0)}개\n비활성: {stats.get('disabled_accounts', 0)}개"
                
                slack_payload["attachments"][0]["fields"].append({
                    "title": "상세 통계",
                    "value": stats_text,
                    "short": False
                })
            
            response = requests.post(webhook_url, json=slack_payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Slack 알림 전송 성공")
            return True
            
        except Exception as e:
            logger.error(f"Slack 알림 전송 실패: {e}")
            return False
    
    async def _send_discord_notification(self, formatted_message: Dict[str, Any], severity: str) -> bool:
        """Discord 알림 전송"""
        try:
            webhook_url = self.notification_config.discord_webhook_url
            
            # Discord embed 색상
            color_map = {
                '#FF0000': 0xFF0000,  # 빨강
                '#FFA500': 0xFFA500,  # 주황
                '#0066CC': 0x0066CC,  # 파랑
                '#00AA00': 0x00AA00   # 초록
            }
            
            # Discord 메시지 포맷
            discord_payload = {
                "embeds": [
                    {
                        "title": "Account Health Monitor",
                        "description": formatted_message['text'],
                        "color": color_map.get(formatted_message['color'], 0x0066CC),
                        "timestamp": formatted_message['timestamp'],
                        "fields": []
                    }
                ]
            }
            
            # 요약 정보 추가
            if 'summary' in formatted_message:
                discord_payload["embeds"][0]["fields"].append({
                    "name": "현재 상태",
                    "value": formatted_message['summary'],
                    "inline": True
                })
            
            # 상세 통계 추가
            if 'stats' in formatted_message and 'overall' in formatted_message['stats']:
                stats = formatted_message['stats']['overall']
                
                discord_payload["embeds"][0]["fields"].extend([
                    {
                        "name": "건강한 계정",
                        "value": f"{stats.get('healthy_accounts', 0)}개",
                        "inline": True
                    },
                    {
                        "name": "문제 계정",
                        "value": f"{stats.get('suspended_accounts', 0) + stats.get('locked_accounts', 0) + stats.get('disabled_accounts', 0)}개",
                        "inline": True
                    }
                ])
            
            response = requests.post(webhook_url, json=discord_payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Discord 알림 전송 성공")
            return True
            
        except Exception as e:
            logger.error(f"Discord 알림 전송 실패: {e}")
            return False
    
    async def _send_email_notification(self, formatted_message: Dict[str, Any], severity: str) -> bool:
        """이메일 알림 전송 (기본 구현)"""
        try:
            # 이메일 기능은 기본 구현만 제공 (실제 구현은 프로젝트 요구사항에 따라 다름)
            logger.info("이메일 알림 기능은 아직 구현되지 않았습니다.")
            return True
            
        except Exception as e:
            logger.error(f"이메일 알림 전송 실패: {e}")
            return False
    
    async def check_and_notify(self, stats: Dict[str, Any]):
        """통계를 확인하고 필요시 알림 전송"""
        try:
            thresholds = self.notification_config.notification_thresholds
            overall = stats.get('overall', {})
            
            survival_rate = overall.get('survival_rate', 0)
            total_accounts = overall.get('total_accounts', 0)
            suspended_accounts = overall.get('suspended_accounts', 0)
            
            # 생존율 기반 알림
            if survival_rate <= thresholds['critical_survival_rate']:
                await self.send_notification(
                    f"🚨 심각한 상황: 계정 생존율이 {survival_rate:.1f}%로 매우 낮습니다!",
                    'critical',
                    stats
                )
            elif survival_rate <= thresholds['warning_survival_rate']:
                await self.send_notification(
                    f"⚠️ 경고: 계정 생존율이 {survival_rate:.1f}%로 낮습니다.",
                    'warning',
                    stats
                )
            
            # 계정 정지율 알림
            if total_accounts > 0:
                suspension_rate = (suspended_accounts / total_accounts) * 100
                if suspension_rate >= thresholds['account_suspension_rate']:
                    await self.send_notification(
                        f"⚠️ 계정 정지율이 {suspension_rate:.1f}%로 높습니다. ({suspended_accounts}/{total_accounts})",
                        'warning',
                        stats
                    )
            
            # 에러율 알림
            error_stats = stats.get('error_analysis', {})
            error_rate = error_stats.get('error_rate', 0)
            if error_rate >= thresholds['high_error_rate']:
                await self.send_notification(
                    f"⚠️ 에러 발생률이 {error_rate:.1f}%로 높습니다.",
                    'warning',
                    stats
                )
            
            # 긍정적인 알림 (높은 생존율)
            if survival_rate >= 90 and total_accounts >= 10:
                await self.send_notification(
                    f"✅ 우수한 성과: 계정 생존율이 {survival_rate:.1f}%입니다!",
                    'success',
                    stats
                )
                
        except Exception as e:
            logger.error(f"알림 확인 및 전송 실패: {e}")
    
    async def send_daily_report(self):
        """일일 리포트 알림 전송"""
        try:
            # 상세 통계 계산
            detailed_stats = self.calculate_detailed_survival_stats()
            
            # 인사이트 생성
            insights = self.get_survival_insights()
            
            # 리포트 메시지 구성
            report_message = f"📊 일일 계정 상태 리포트\n\n"
            report_message += f"총 계정: {detailed_stats['overall']['total_accounts']}개\n"
            report_message += f"생존율: {detailed_stats['overall']['survival_rate']:.1f}%\n"
            report_message += f"건강: {detailed_stats['overall']['healthy_accounts']}개\n"
            report_message += f"문제: {detailed_stats['overall']['suspended_accounts'] + detailed_stats['overall']['locked_accounts'] + detailed_stats['overall']['disabled_accounts']}개\n\n"
            
            if insights:
                report_message += "🔍 주요 인사이트:\n" + "\n".join(insights[:3])
            
            await self.send_notification(report_message, 'info', detailed_stats)
            
            logger.info("일일 리포트 전송 완료")
            
        except Exception as e:
            logger.error(f"일일 리포트 전송 실패: {e}")
    
    async def send_emergency_alert(self, message: str, additional_info: Optional[Dict] = None):
        """긴급 상황 알림 전송"""
        try:
            emergency_message = f"🚨 긴급 알림: {message}"
            
            if additional_info:
                emergency_message += f"\n\n추가 정보:\n"
                for key, value in additional_info.items():
                    emergency_message += f"• {key}: {value}\n"
            
            await self.send_notification(emergency_message, 'critical')
            
            logger.warning(f"긴급 알림 전송: {message}")
            
        except Exception as e:
            logger.error(f"긴급 알림 전송 실패: {e}") 