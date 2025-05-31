"""
계정 로깅 시스템 테스트

이 파일은 core/account_logger.py 모듈의 기능을 테스트합니다.
"""

import unittest
import tempfile
import shutil
import os
import json
import csv
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.account_logger import (
    AccountLogger, CSVLogger, JSONSessionStorage, 
    EncryptionManager, FileLockManager,
    AccountRecord, SessionData,
    create_account_logger, log_account_creation
)
from core.account_creator import AccountCreationResult, PersonalInfo


class TestEncryptionManager(unittest.TestCase):
    """EncryptionManager 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.encryption_manager = EncryptionManager("test_password")
    
    def test_encrypt_decrypt(self):
        """데이터 암호화/복호화 테스트"""
        original_data = "sensitive_password_123"
        
        # 암호화
        encrypted_data = self.encryption_manager.encrypt(original_data)
        self.assertNotEqual(original_data, encrypted_data)
        self.assertIsInstance(encrypted_data, str)
        
        # 복호화
        decrypted_data = self.encryption_manager.decrypt(encrypted_data)
        self.assertEqual(original_data, decrypted_data)
    
    def test_encrypt_empty_string(self):
        """빈 문자열 암호화 테스트"""
        original_data = ""
        encrypted_data = self.encryption_manager.encrypt(original_data)
        decrypted_data = self.encryption_manager.decrypt(encrypted_data)
        self.assertEqual(original_data, decrypted_data)
    
    def test_encrypt_korean_text(self):
        """한국어 텍스트 암호화 테스트"""
        original_data = "안녕하세요 비밀번호입니다"
        encrypted_data = self.encryption_manager.encrypt(original_data)
        decrypted_data = self.encryption_manager.decrypt(encrypted_data)
        self.assertEqual(original_data, decrypted_data)


class TestCSVLogger(unittest.TestCase):
    """CSVLogger 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.csv_file = os.path.join(self.temp_dir, "test_accounts.csv")
        self.csv_logger = CSVLogger(self.csv_file)
        
        # 테스트용 계정 레코드
        self.test_account = AccountRecord(
            id="test123",
            email="test@gmail.com",
            password="testpass123",
            phone_number="+821012345678",
            first_name="테스트",
            last_name="사용자",
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            gender="male",
            creation_time=datetime.now(),
            status="active"
        )
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_create_header(self):
        """CSV 헤더 생성 테스트"""
        self.assertTrue(os.path.exists(self.csv_file))
        
        # 헤더 확인
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            expected_headers = [
                'id', 'email', 'password_encrypted', 'phone_number', 'first_name', 'last_name',
                'birth_year', 'birth_month', 'birth_day', 'gender', 'creation_time',
                'status', 'last_login', 'notes', 'device_info', 'proxy_info'
            ]
            self.assertEqual(headers, expected_headers)
    
    def test_log_account(self):
        """계정 로깅 테스트"""
        result = self.csv_logger.log_account(self.test_account)
        self.assertTrue(result)
        
        # 파일 내용 확인
        accounts = self.csv_logger.read_accounts()
        self.assertEqual(len(accounts), 1)
        
        account = accounts[0]
        self.assertEqual(account.id, self.test_account.id)
        self.assertEqual(account.email, self.test_account.email)
        self.assertEqual(account.password, self.test_account.password)
        self.assertEqual(account.first_name, self.test_account.first_name)
    
    def test_read_accounts_with_limit(self):
        """제한된 수의 계정 읽기 테스트"""
        # 여러 계정 추가
        for i in range(5):
            account = AccountRecord(
                id=f"test{i}",
                email=f"test{i}@gmail.com",
                password="testpass123",
                phone_number="+821012345678",
                first_name="테스트",
                last_name="사용자",
                birth_year=1990,
                birth_month=5,
                birth_day=15,
                gender="male",
                creation_time=datetime.now(),
                status="active"
            )
            self.csv_logger.log_account(account)
        
        # 제한된 수 읽기
        accounts = self.csv_logger.read_accounts(limit=3)
        self.assertEqual(len(accounts), 3)
    
    def test_update_account_status(self):
        """계정 상태 업데이트 테스트"""
        # 계정 로깅
        self.csv_logger.log_account(self.test_account)
        
        # 상태 업데이트
        result = self.csv_logger.update_account_status("test123", "suspended", "테스트 정지")
        self.assertTrue(result)
        
        # 업데이트 확인
        accounts = self.csv_logger.read_accounts()
        account = accounts[0]
        self.assertEqual(account.status, "suspended")
        self.assertEqual(account.notes, "테스트 정지")
        self.assertIsNotNone(account.last_login)


class TestJSONSessionStorage(unittest.TestCase):
    """JSONSessionStorage 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.json_file = os.path.join(self.temp_dir, "test_sessions.json")
        self.session_storage = JSONSessionStorage(self.json_file)
        
        # 테스트용 세션 데이터
        self.test_session = SessionData(
            session_id="session123",
            account_id="account123",
            device_id="device123",
            start_time=datetime.now(),
            metadata={"test": "data"}
        )
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_create_empty_file(self):
        """빈 JSON 파일 생성 테스트"""
        self.assertTrue(os.path.exists(self.json_file))
        
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data, {})
    
    def test_save_and_load_session(self):
        """세션 저장 및 로드 테스트"""
        # 세션 저장
        result = self.session_storage.save_session(self.test_session)
        self.assertTrue(result)
        
        # 세션 로드
        loaded_session = self.session_storage.load_session("session123")
        self.assertIsNotNone(loaded_session)
        self.assertEqual(loaded_session.session_id, self.test_session.session_id)
        self.assertEqual(loaded_session.account_id, self.test_session.account_id)
        self.assertEqual(loaded_session.device_id, self.test_session.device_id)
        self.assertEqual(loaded_session.metadata, self.test_session.metadata)
    
    def test_delete_session(self):
        """세션 삭제 테스트"""
        # 세션 저장
        self.session_storage.save_session(self.test_session)
        
        # 세션 삭제
        result = self.session_storage.delete_session("session123")
        self.assertTrue(result)
        
        # 삭제 확인
        loaded_session = self.session_storage.load_session("session123")
        self.assertIsNone(loaded_session)
    
    def test_cleanup_old_sessions(self):
        """오래된 세션 정리 테스트"""
        # 현재 세션
        current_session = SessionData(
            session_id="current",
            account_id="account123",
            device_id="device123",
            start_time=datetime.now()
        )
        
        # 오래된 세션
        old_session = SessionData(
            session_id="old",
            account_id="account123",
            device_id="device123",
            start_time=datetime.now() - timedelta(days=10)
        )
        
        self.session_storage.save_session(current_session)
        self.session_storage.save_session(old_session)
        
        # 정리 실행 (7일 기준)
        deleted_count = self.session_storage.cleanup_old_sessions(days=7)
        self.assertEqual(deleted_count, 1)
        
        # 확인
        current_loaded = self.session_storage.load_session("current")
        old_loaded = self.session_storage.load_session("old")
        
        self.assertIsNotNone(current_loaded)
        self.assertIsNone(old_loaded)


class TestAccountLogger(unittest.TestCase):
    """AccountLogger 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.csv_file = os.path.join(self.temp_dir, "accounts.csv")
        self.json_file = os.path.join(self.temp_dir, "sessions.json")
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        
        self.account_logger = AccountLogger(
            csv_path=self.csv_file,
            json_path=self.json_file,
            backup_dir=self.backup_dir
        )
        
        # 테스트 데이터
        self.personal_info = PersonalInfo(
            first_name="테스트",
            last_name="사용자",
            username="testuser123",
            password="testpass123",
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            gender="male"
        )
        
        self.account_result = AccountCreationResult(
            success=True,
            email="testuser123@gmail.com",
            password="testpass123",
            phone_number="+821012345678",
            creation_time=datetime.now(),
            steps_completed=["device_randomization", "personal_info_filled"]
        )
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_log_account_creation_result(self):
        """계정 생성 결과 로깅 테스트"""
        account_id = self.account_logger.log_account_creation_result(
            self.account_result,
            self.personal_info,
            device_info={"resolution": "1080x1920"},
            proxy_info={"ip": "192.168.1.1"}
        )
        
        self.assertIsNotNone(account_id)
        self.assertIsInstance(account_id, str)
        
        # CSV에 로깅되었는지 확인
        accounts = self.account_logger.csv_logger.read_accounts()
        self.assertEqual(len(accounts), 1)
        
        account = accounts[0]
        self.assertEqual(account.email, self.account_result.email)
        self.assertEqual(account.first_name, self.personal_info.first_name)
        self.assertIsNotNone(account.device_info)
        self.assertIsNotNone(account.proxy_info)
    
    def test_session_management(self):
        """세션 관리 테스트"""
        # 계정 로깅
        account_id = self.account_logger.log_account_creation_result(
            self.account_result, self.personal_info
        )
        
        # 세션 시작
        session_id = self.account_logger.start_session(
            account_id, "device123", {"test": "metadata"}
        )
        self.assertIsNotNone(session_id)
        
        # 세션 종료
        result = self.account_logger.end_session(
            session_id, ["login", "setup"], ["minor_error"]
        )
        self.assertTrue(result)
        
        # 세션 확인
        session = self.account_logger.session_storage.load_session(session_id)
        self.assertIsNotNone(session)
        self.assertIsNotNone(session.end_time)
        self.assertEqual(session.steps_completed, ["login", "setup"])
        self.assertEqual(session.errors, ["minor_error"])
    
    def test_backup_data(self):
        """데이터 백업 테스트"""
        # 테스트 데이터 생성
        self.account_logger.log_account_creation_result(
            self.account_result, self.personal_info
        )
        
        # 백업 실행
        result = self.account_logger.backup_data()
        self.assertTrue(result)
        
        # 백업 파일 확인
        backup_files = list(os.listdir(self.backup_dir))
        self.assertGreater(len(backup_files), 0)
        
        # CSV 및 JSON 백업 파일 존재 확인
        csv_backup_found = any("accounts_" in f for f in backup_files)
        json_backup_found = any("sessions_" in f for f in backup_files)
        
        self.assertTrue(csv_backup_found)
        self.assertTrue(json_backup_found)
    
    def test_get_account_statistics(self):
        """계정 통계 테스트"""
        # 여러 계정 생성
        for i in range(3):
            result = AccountCreationResult(
                success=True,
                email=f"test{i}@gmail.com",
                password="testpass123",
                creation_time=datetime.now(),
                steps_completed=["completed"]
            )
            
            personal_info = PersonalInfo(
                first_name=f"테스트{i}",
                last_name="사용자",
                username=f"test{i}",
                password="testpass123",
                birth_year=1990,
                birth_month=5,
                birth_day=15,
                gender="male"
            )
            
            self.account_logger.log_account_creation_result(result, personal_info)
        
        # 통계 가져오기
        stats = self.account_logger.get_account_statistics()
        
        self.assertEqual(stats['total_accounts'], 3)
        self.assertIn('status_counts', stats)
        self.assertEqual(stats['status_counts']['active'], 3)
        self.assertEqual(stats['recent_accounts_week'], 3)
        self.assertIn('last_updated', stats)


class TestConvenienceFunctions(unittest.TestCase):
    """편의 함수 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    @patch('core.account_logger.AccountLogger')
    def test_create_account_logger(self, mock_logger_class):
        """create_account_logger 함수 테스트"""
        mock_instance = Mock()
        mock_logger_class.return_value = mock_instance
        
        result = create_account_logger()
        
        mock_logger_class.assert_called_once()
        self.assertEqual(result, mock_instance)
    
    @patch('core.account_logger.create_account_logger')
    def test_log_account_creation_function(self, mock_create_logger):
        """log_account_creation 함수 테스트"""
        # Mock 설정
        mock_logger = Mock()
        mock_logger.log_account_creation_result.return_value = "test_account_id"
        mock_create_logger.return_value = mock_logger
        
        # 테스트 데이터
        personal_info = PersonalInfo(
            first_name="테스트",
            last_name="사용자",
            username="testuser123",
            password="testpass123",
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            gender="male"
        )
        
        result = AccountCreationResult(
            success=True,
            email="testuser123@gmail.com",
            password="testpass123",
            creation_time=datetime.now(),
            steps_completed=["completed"]
        )
        
        # 함수 호출
        account_id = log_account_creation(
            result, personal_info, 
            device_info={"test": "device"}, 
            proxy_info={"test": "proxy"}
        )
        
        # 검증
        mock_create_logger.assert_called_once()
        mock_logger.log_account_creation_result.assert_called_once_with(
            result, personal_info, {"test": "device"}, {"test": "proxy"}
        )
        self.assertEqual(account_id, "test_account_id")


class TestFileLockManager(unittest.TestCase):
    """FileLockManager 테스트"""
    
    def test_get_lock(self):
        """파일 잠금 가져오기 테스트"""
        lock1 = FileLockManager.get_lock("/test/file1.txt")
        lock2 = FileLockManager.get_lock("/test/file1.txt")
        lock3 = FileLockManager.get_lock("/test/file2.txt")
        
        # 같은 파일에 대해서는 같은 잠금 객체
        self.assertIs(lock1, lock2)
        
        # 다른 파일에 대해서는 다른 잠금 객체
        self.assertIsNot(lock1, lock3)


class TestErrorHandling(unittest.TestCase):
    """에러 처리 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """테스트 정리"""
        shutil.rmtree(self.temp_dir)
    
    def test_failed_account_creation_logging(self):
        """실패한 계정 생성 로깅 테스트"""
        csv_file = os.path.join(self.temp_dir, "accounts.csv")
        json_file = os.path.join(self.temp_dir, "sessions.json")
        backup_dir = os.path.join(self.temp_dir, "backups")
        
        account_logger = AccountLogger(csv_file, json_file, backup_dir)
        
        # 실패한 계정 생성 결과
        failed_result = AccountCreationResult(
            success=False,
            error_message="계정 생성 실패",
            steps_completed=["device_randomization"]
        )
        
        personal_info = PersonalInfo(
            first_name="테스트",
            last_name="사용자",
            username="testuser123",
            password="testpass123",
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            gender="male"
        )
        
        # 실패한 결과는 로깅되지 않아야 함
        account_id = account_logger.log_account_creation_result(failed_result, personal_info)
        self.assertIsNone(account_id)
        
        # CSV에 아무것도 로깅되지 않았는지 확인
        accounts = account_logger.csv_logger.read_accounts()
        self.assertEqual(len(accounts), 0)


if __name__ == '__main__':
    # 로깅 설정
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 테스트 실행
    unittest.main(verbosity=2) 