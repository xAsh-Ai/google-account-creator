"""
계정 로깅 및 저장 시스템 모듈

이 모듈은 생성된 Google 계정 정보를 안전하게 로깅하고 저장하는 기능을 제공합니다.
- CSV 형태의 계정 로깅
- JSON 세션 저장소
- 파일 잠금 메커니즘
- 민감 데이터 암호화/복호화
- 백업 및 로테이션
"""

import csv
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import fcntl  # Unix/Linux용 파일 잠금
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .account_creator import AccountCreationResult, PersonalInfo

# 로깅 설정
logger = logging.getLogger(__name__)

@dataclass
class AccountRecord:
    """계정 정보 레코드 데이터 클래스"""
    id: str
    email: str
    password: str
    phone_number: Optional[str]
    first_name: str
    last_name: str
    birth_year: int
    birth_month: int
    birth_day: int
    gender: str
    creation_time: datetime
    status: str  # 'active', 'suspended', 'banned', 'unknown'
    last_login: Optional[datetime] = None
    notes: Optional[str] = None
    device_info: Optional[Dict] = None
    proxy_info: Optional[Dict] = None

@dataclass
class SessionData:
    """세션 데이터 클래스"""
    session_id: str
    account_id: str
    device_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    steps_completed: List[str] = None
    errors: List[str] = None
    metadata: Optional[Dict] = None

class FileLockManager:
    """파일 잠금 관리자"""
    
    _locks = {}
    _lock_mutex = threading.Lock()
    
    @classmethod
    def get_lock(cls, file_path: str) -> threading.Lock:
        """
        파일 경로에 대한 잠금을 가져옵니다.
        
        Args:
            file_path: 잠금할 파일 경로
        
        Returns:
            파일 잠금 객체
        """
        with cls._lock_mutex:
            if file_path not in cls._locks:
                cls._locks[file_path] = threading.Lock()
            return cls._locks[file_path]

class EncryptionManager:
    """데이터 암호화 관리자"""
    
    def __init__(self, password: str = None):
        """
        암호화 관리자 초기화
        
        Args:
            password: 암호화 비밀번호 (None이면 기본값 사용)
        """
        self.password = password or "google-account-creator-2024"
        self.key = self._derive_key(self.password)
        self.cipher = Fernet(self.key)
        logger.info("암호화 관리자가 초기화되었습니다.")
    
    def _derive_key(self, password: str) -> bytes:
        """
        비밀번호로부터 암호화 키를 생성합니다.
        
        Args:
            password: 비밀번호
        
        Returns:
            암호화 키
        """
        salt = b'google_account_salt_2024'  # 고정 솔트 (실제 운영에서는 랜덤 솔트 사용 권장)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: str) -> str:
        """
        데이터를 암호화합니다.
        
        Args:
            data: 암호화할 데이터
        
        Returns:
            암호화된 데이터 (base64 인코딩)
        """
        try:
            encrypted_data = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"데이터 암호화 실패: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        데이터를 복호화합니다.
        
        Args:
            encrypted_data: 암호화된 데이터 (base64 인코딩)
        
        Returns:
            복호화된 데이터
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"데이터 복호화 실패: {e}")
            raise

class CSVLogger:
    """CSV 형태의 계정 로깅 클래스"""
    
    def __init__(self, file_path: str = "data/accounts.csv"):
        """
        CSV 로거 초기화
        
        Args:
            file_path: CSV 파일 경로
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.encryption_manager = EncryptionManager()
        
        # CSV 헤더 정의
        self.headers = [
            'id', 'email', 'password_encrypted', 'phone_number', 'first_name', 'last_name',
            'birth_year', 'birth_month', 'birth_day', 'gender', 'creation_time',
            'status', 'last_login', 'notes', 'device_info', 'proxy_info'
        ]
        
        # 파일이 없으면 헤더 생성
        if not self.file_path.exists():
            self._create_header()
        
        logger.info(f"CSV 로거가 초기화되었습니다: {self.file_path}")
    
    def _create_header(self) -> None:
        """CSV 파일에 헤더를 생성합니다."""
        try:
            with open(self.file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.headers)
            logger.info("CSV 헤더가 생성되었습니다.")
        except Exception as e:
            logger.error(f"CSV 헤더 생성 실패: {e}")
            raise
    
    def log_account(self, account_record: AccountRecord) -> bool:
        """
        계정 정보를 CSV 파일에 로깅합니다.
        
        Args:
            account_record: 계정 레코드
        
        Returns:
            성공 여부
        """
        try:
            # 파일 잠금 획득
            file_lock = FileLockManager.get_lock(str(self.file_path))
            
            with file_lock:
                with open(self.file_path, 'a', newline='', encoding='utf-8') as csvfile:
                    # Unix/Linux 시스템에서 파일 잠금
                    try:
                        fcntl.flock(csvfile.fileno(), fcntl.LOCK_EX)
                    except:
                        pass  # Windows에서는 fcntl을 사용할 수 없음
                    
                    writer = csv.writer(csvfile)
                    
                    # 비밀번호 암호화
                    encrypted_password = self.encryption_manager.encrypt(account_record.password)
                    
                    # 데이터 준비
                    row_data = [
                        account_record.id,
                        account_record.email,
                        encrypted_password,
                        account_record.phone_number,
                        account_record.first_name,
                        account_record.last_name,
                        account_record.birth_year,
                        account_record.birth_month,
                        account_record.birth_day,
                        account_record.gender,
                        account_record.creation_time.isoformat(),
                        account_record.status,
                        account_record.last_login.isoformat() if account_record.last_login else None,
                        account_record.notes,
                        json.dumps(account_record.device_info) if account_record.device_info else None,
                        json.dumps(account_record.proxy_info) if account_record.proxy_info else None
                    ]
                    
                    writer.writerow(row_data)
                    
                    try:
                        fcntl.flock(csvfile.fileno(), fcntl.LOCK_UN)
                    except:
                        pass
            
            logger.info(f"계정 정보가 CSV에 로깅되었습니다: {account_record.email}")
            return True
            
        except Exception as e:
            logger.error(f"CSV 로깅 실패: {e}")
            return False
    
    def read_accounts(self, limit: Optional[int] = None) -> List[AccountRecord]:
        """
        CSV 파일에서 계정 정보를 읽어옵니다.
        
        Args:
            limit: 읽어올 최대 레코드 수
        
        Returns:
            계정 레코드 목록
        """
        try:
            accounts = []
            
            if not self.file_path.exists():
                return accounts
            
            file_lock = FileLockManager.get_lock(str(self.file_path))
            
            with file_lock:
                with open(self.file_path, 'r', encoding='utf-8') as csvfile:
                    try:
                        fcntl.flock(csvfile.fileno(), fcntl.LOCK_SH)
                    except:
                        pass
                    
                    reader = csv.DictReader(csvfile)
                    
                    for i, row in enumerate(reader):
                        if limit and i >= limit:
                            break
                        
                        try:
                            # 비밀번호 복호화
                            decrypted_password = self.encryption_manager.decrypt(row['password_encrypted'])
                            
                            account = AccountRecord(
                                id=row['id'],
                                email=row['email'],
                                password=decrypted_password,
                                phone_number=row['phone_number'] if row['phone_number'] else None,
                                first_name=row['first_name'],
                                last_name=row['last_name'],
                                birth_year=int(row['birth_year']),
                                birth_month=int(row['birth_month']),
                                birth_day=int(row['birth_day']),
                                gender=row['gender'],
                                creation_time=datetime.fromisoformat(row['creation_time']),
                                status=row['status'],
                                last_login=datetime.fromisoformat(row['last_login']) if row['last_login'] else None,
                                notes=row['notes'] if row['notes'] else None,
                                device_info=json.loads(row['device_info']) if row['device_info'] else None,
                                proxy_info=json.loads(row['proxy_info']) if row['proxy_info'] else None
                            )
                            
                            accounts.append(account)
                            
                        except Exception as e:
                            logger.warning(f"레코드 파싱 실패: {e}")
                            continue
                    
                    try:
                        fcntl.flock(csvfile.fileno(), fcntl.LOCK_UN)
                    except:
                        pass
            
            logger.info(f"CSV에서 {len(accounts)}개 계정 정보를 읽어왔습니다.")
            return accounts
            
        except Exception as e:
            logger.error(f"CSV 읽기 실패: {e}")
            return []
    
    def update_account_status(self, account_id: str, status: str, notes: str = None) -> bool:
        """
        계정 상태를 업데이트합니다.
        
        Args:
            account_id: 계정 ID
            status: 새로운 상태
            notes: 추가 노트
        
        Returns:
            성공 여부
        """
        try:
            accounts = self.read_accounts()
            updated = False
            
            for account in accounts:
                if account.id == account_id:
                    account.status = status
                    account.last_login = datetime.now()
                    if notes:
                        account.notes = notes
                    updated = True
                    break
            
            if updated:
                # 파일을 다시 작성
                self._rewrite_csv(accounts)
                logger.info(f"계정 {account_id} 상태가 {status}로 업데이트되었습니다.")
                return True
            else:
                logger.warning(f"계정 {account_id}를 찾을 수 없습니다.")
                return False
                
        except Exception as e:
            logger.error(f"계정 상태 업데이트 실패: {e}")
            return False
    
    def _rewrite_csv(self, accounts: List[AccountRecord]) -> None:
        """
        CSV 파일을 다시 작성합니다.
        
        Args:
            accounts: 계정 목록
        """
        # 백업 생성
        backup_path = f"{self.file_path}.backup.{int(time.time())}"
        shutil.copy2(self.file_path, backup_path)
        
        try:
            # 새로운 파일 작성
            with open(self.file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.headers)
                
                for account in accounts:
                    encrypted_password = self.encryption_manager.encrypt(account.password)
                    
                    row_data = [
                        account.id,
                        account.email,
                        encrypted_password,
                        account.phone_number,
                        account.first_name,
                        account.last_name,
                        account.birth_year,
                        account.birth_month,
                        account.birth_day,
                        account.gender,
                        account.creation_time.isoformat(),
                        account.status,
                        account.last_login.isoformat() if account.last_login else None,
                        account.notes,
                        json.dumps(account.device_info) if account.device_info else None,
                        json.dumps(account.proxy_info) if account.proxy_info else None
                    ]
                    
                    writer.writerow(row_data)
            
            # 백업 파일 삭제
            os.remove(backup_path)
            
        except Exception as e:
            # 오류 발생 시 백업에서 복원
            shutil.copy2(backup_path, self.file_path)
            os.remove(backup_path)
            raise e

class JSONSessionStorage:
    """JSON 세션 저장소 클래스"""
    
    def __init__(self, file_path: str = "data/temp_sessions.json"):
        """
        JSON 세션 저장소 초기화
        
        Args:
            file_path: JSON 파일 경로
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.encryption_manager = EncryptionManager()
        
        # 파일이 없으면 빈 객체 생성
        if not self.file_path.exists():
            self._create_empty_file()
        
        logger.info(f"JSON 세션 저장소가 초기화되었습니다: {self.file_path}")
    
    def _create_empty_file(self) -> None:
        """빈 JSON 파일을 생성합니다."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump({}, jsonfile)
            logger.info("빈 JSON 파일이 생성되었습니다.")
        except Exception as e:
            logger.error(f"JSON 파일 생성 실패: {e}")
            raise
    
    def save_session(self, session_data: SessionData) -> bool:
        """
        세션 데이터를 저장합니다.
        
        Args:
            session_data: 세션 데이터
        
        Returns:
            성공 여부
        """
        try:
            file_lock = FileLockManager.get_lock(str(self.file_path))
            
            with file_lock:
                # 기존 데이터 읽기
                sessions = self._read_sessions_unsafe()
                
                # 민감한 정보 암호화
                session_dict = asdict(session_data)
                if 'metadata' in session_dict and session_dict['metadata']:
                    # 메타데이터에 비밀번호 등 민감 정보가 있으면 암호화
                    if 'password' in session_dict['metadata']:
                        session_dict['metadata']['password'] = self.encryption_manager.encrypt(
                            session_dict['metadata']['password']
                        )
                
                # 날짜 시간을 ISO 형식으로 변환
                session_dict['start_time'] = session_data.start_time.isoformat()
                if session_data.end_time:
                    session_dict['end_time'] = session_data.end_time.isoformat()
                
                # 세션 추가
                sessions[session_data.session_id] = session_dict
                
                # 파일에 저장
                with open(self.file_path, 'w', encoding='utf-8') as jsonfile:
                    try:
                        fcntl.flock(jsonfile.fileno(), fcntl.LOCK_EX)
                    except:
                        pass
                    
                    json.dump(sessions, jsonfile, indent=2, ensure_ascii=False)
                    
                    try:
                        fcntl.flock(jsonfile.fileno(), fcntl.LOCK_UN)
                    except:
                        pass
            
            logger.info(f"세션 {session_data.session_id}가 저장되었습니다.")
            return True
            
        except Exception as e:
            logger.error(f"세션 저장 실패: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[SessionData]:
        """
        세션 데이터를 로드합니다.
        
        Args:
            session_id: 세션 ID
        
        Returns:
            세션 데이터 또는 None
        """
        try:
            sessions = self._read_sessions_unsafe()
            
            if session_id not in sessions:
                return None
            
            session_dict = sessions[session_id]
            
            # 암호화된 정보 복호화
            if 'metadata' in session_dict and session_dict['metadata']:
                if 'password' in session_dict['metadata']:
                    session_dict['metadata']['password'] = self.encryption_manager.decrypt(
                        session_dict['metadata']['password']
                    )
            
            # 날짜 시간 변환
            start_time = datetime.fromisoformat(session_dict['start_time'])
            end_time = datetime.fromisoformat(session_dict['end_time']) if session_dict.get('end_time') else None
            
            session_data = SessionData(
                session_id=session_dict['session_id'],
                account_id=session_dict['account_id'],
                device_id=session_dict['device_id'],
                start_time=start_time,
                end_time=end_time,
                steps_completed=session_dict.get('steps_completed', []),
                errors=session_dict.get('errors', []),
                metadata=session_dict.get('metadata')
            )
            
            logger.info(f"세션 {session_id}가 로드되었습니다.")
            return session_data
            
        except Exception as e:
            logger.error(f"세션 로드 실패: {e}")
            return None
    
    def _read_sessions_unsafe(self) -> Dict:
        """
        잠금 없이 세션 데이터를 읽습니다. (내부 사용)
        
        Returns:
            세션 딕셔너리
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as jsonfile:
                return json.load(jsonfile)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def delete_session(self, session_id: str) -> bool:
        """
        세션을 삭제합니다.
        
        Args:
            session_id: 세션 ID
        
        Returns:
            성공 여부
        """
        try:
            file_lock = FileLockManager.get_lock(str(self.file_path))
            
            with file_lock:
                sessions = self._read_sessions_unsafe()
                
                if session_id in sessions:
                    del sessions[session_id]
                    
                    with open(self.file_path, 'w', encoding='utf-8') as jsonfile:
                        json.dump(sessions, jsonfile, indent=2, ensure_ascii=False)
                    
                    logger.info(f"세션 {session_id}가 삭제되었습니다.")
                    return True
                else:
                    logger.warning(f"세션 {session_id}를 찾을 수 없습니다.")
                    return False
                    
        except Exception as e:
            logger.error(f"세션 삭제 실패: {e}")
            return False
    
    def cleanup_old_sessions(self, days: int = 7) -> int:
        """
        오래된 세션을 정리합니다.
        
        Args:
            days: 보관 기간 (일)
        
        Returns:
            삭제된 세션 수
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            sessions = self._read_sessions_unsafe()
            
            sessions_to_delete = []
            for session_id, session_dict in sessions.items():
                try:
                    start_time = datetime.fromisoformat(session_dict['start_time'])
                    if start_time < cutoff_time:
                        sessions_to_delete.append(session_id)
                except:
                    # 잘못된 형식의 세션도 삭제
                    sessions_to_delete.append(session_id)
            
            # 세션 삭제
            deleted_count = 0
            for session_id in sessions_to_delete:
                if self.delete_session(session_id):
                    deleted_count += 1
            
            logger.info(f"{deleted_count}개의 오래된 세션이 정리되었습니다.")
            return deleted_count
            
        except Exception as e:
            logger.error(f"세션 정리 실패: {e}")
            return 0

class AccountLogger:
    """통합 계정 로깅 시스템"""
    
    def __init__(self, 
                 csv_path: str = "data/accounts.csv",
                 json_path: str = "data/temp_sessions.json",
                 backup_dir: str = "data/backups"):
        """
        계정 로깅 시스템 초기화
        
        Args:
            csv_path: CSV 파일 경로
            json_path: JSON 파일 경로
            backup_dir: 백업 디렉토리
        """
        self.csv_logger = CSVLogger(csv_path)
        self.session_storage = JSONSessionStorage(json_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("통합 계정 로깅 시스템이 초기화되었습니다.")
    
    def log_account_creation_result(self, result: AccountCreationResult, 
                                  personal_info: PersonalInfo,
                                  device_info: Dict = None,
                                  proxy_info: Dict = None) -> Optional[str]:
        """
        계정 생성 결과를 로깅합니다.
        
        Args:
            result: 계정 생성 결과
            personal_info: 개인 정보
            device_info: 디바이스 정보
            proxy_info: 프록시 정보
        
        Returns:
            계정 ID 또는 None
        """
        try:
            if not result.success:
                logger.warning("실패한 계정 생성은 로깅하지 않습니다.")
                return None
            
            # 고유 계정 ID 생성
            account_id = hashlib.md5(f"{result.email}_{int(time.time())}".encode()).hexdigest()[:12]
            
            # 계정 레코드 생성
            account_record = AccountRecord(
                id=account_id,
                email=result.email,
                password=result.password,
                phone_number=result.phone_number,
                first_name=personal_info.first_name,
                last_name=personal_info.last_name,
                birth_year=personal_info.birth_year,
                birth_month=personal_info.birth_month,
                birth_day=personal_info.birth_day,
                gender=personal_info.gender,
                creation_time=result.creation_time or datetime.now(),
                status='active',
                device_info=device_info,
                proxy_info=proxy_info
            )
            
            # CSV에 로깅
            if self.csv_logger.log_account(account_record):
                logger.info(f"계정 {result.email}이 성공적으로 로깅되었습니다. ID: {account_id}")
                return account_id
            else:
                logger.error("계정 로깅 실패")
                return None
                
        except Exception as e:
            logger.error(f"계정 생성 결과 로깅 실패: {e}")
            return None
    
    def start_session(self, account_id: str, device_id: str, metadata: Dict = None) -> str:
        """
        새로운 세션을 시작합니다.
        
        Args:
            account_id: 계정 ID
            device_id: 디바이스 ID
            metadata: 추가 메타데이터
        
        Returns:
            세션 ID
        """
        try:
            session_id = hashlib.md5(f"{account_id}_{device_id}_{int(time.time())}".encode()).hexdigest()[:16]
            
            session_data = SessionData(
                session_id=session_id,
                account_id=account_id,
                device_id=device_id,
                start_time=datetime.now(),
                metadata=metadata
            )
            
            if self.session_storage.save_session(session_data):
                logger.info(f"세션 {session_id}이 시작되었습니다.")
                return session_id
            else:
                logger.error("세션 시작 실패")
                return None
                
        except Exception as e:
            logger.error(f"세션 시작 실패: {e}")
            return None
    
    def end_session(self, session_id: str, steps_completed: List[str] = None, errors: List[str] = None) -> bool:
        """
        세션을 종료합니다.
        
        Args:
            session_id: 세션 ID
            steps_completed: 완료된 단계 목록
            errors: 오류 목록
        
        Returns:
            성공 여부
        """
        try:
            session_data = self.session_storage.load_session(session_id)
            if not session_data:
                logger.warning(f"세션 {session_id}를 찾을 수 없습니다.")
                return False
            
            session_data.end_time = datetime.now()
            session_data.steps_completed = steps_completed or []
            session_data.errors = errors or []
            
            if self.session_storage.save_session(session_data):
                logger.info(f"세션 {session_id}이 종료되었습니다.")
                return True
            else:
                logger.error("세션 종료 실패")
                return False
                
        except Exception as e:
            logger.error(f"세션 종료 실패: {e}")
            return False
    
    def backup_data(self) -> bool:
        """
        데이터를 백업합니다.
        
        Returns:
            성공 여부
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # CSV 백업
            csv_backup_path = self.backup_dir / f"accounts_{timestamp}.csv"
            shutil.copy2(self.csv_logger.file_path, csv_backup_path)
            
            # JSON 백업
            json_backup_path = self.backup_dir / f"sessions_{timestamp}.json"
            shutil.copy2(self.session_storage.file_path, json_backup_path)
            
            logger.info(f"데이터가 백업되었습니다: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"데이터 백업 실패: {e}")
            return False
    
    def cleanup_old_backups(self, days: int = 30) -> int:
        """
        오래된 백업을 정리합니다.
        
        Args:
            days: 보관 기간 (일)
        
        Returns:
            삭제된 파일 수
        """
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            deleted_count = 0
            
            for backup_file in self.backup_dir.glob("*"):
                if backup_file.is_file() and backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    deleted_count += 1
            
            logger.info(f"{deleted_count}개의 오래된 백업이 정리되었습니다.")
            return deleted_count
            
        except Exception as e:
            logger.error(f"백업 정리 실패: {e}")
            return 0
    
    def get_account_statistics(self) -> Dict[str, Any]:
        """
        계정 통계를 가져옵니다.
        
        Returns:
            통계 딕셔너리
        """
        try:
            accounts = self.csv_logger.read_accounts()
            
            total_accounts = len(accounts)
            status_counts = {}
            recent_accounts = 0
            
            week_ago = datetime.now() - timedelta(days=7)
            
            for account in accounts:
                # 상태별 카운트
                status = account.status
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # 최근 일주일 계정
                if account.creation_time > week_ago:
                    recent_accounts += 1
            
            statistics = {
                'total_accounts': total_accounts,
                'status_counts': status_counts,
                'recent_accounts_week': recent_accounts,
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"계정 통계 생성 완료: {total_accounts}개 계정")
            return statistics
            
        except Exception as e:
            logger.error(f"계정 통계 생성 실패: {e}")
            return {}


# 편의 함수들
def create_account_logger() -> AccountLogger:
    """
    기본 설정으로 계정 로거를 생성합니다.
    
    Returns:
        AccountLogger 인스턴스
    """
    return AccountLogger()

def log_account_creation(result: AccountCreationResult, 
                        personal_info: PersonalInfo,
                        device_info: Dict = None,
                        proxy_info: Dict = None) -> Optional[str]:
    """
    계정 생성을 빠르게 로깅하는 편의 함수
    
    Args:
        result: 계정 생성 결과
        personal_info: 개인 정보
        device_info: 디바이스 정보
        proxy_info: 프록시 정보
    
    Returns:
        계정 ID 또는 None
    """
    logger = create_account_logger()
    return logger.log_account_creation_result(result, personal_info, device_info, proxy_info)


if __name__ == "__main__":
    # 테스트 코드
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def test_account_logging():
        """계정 로깅 테스트"""
        try:
            logger.info("계정 로깅 시스템 테스트 시작...")
            
            # AccountLogger 생성
            account_logger = create_account_logger()
            
            # 테스트 데이터 생성
            from .account_creator import PersonalInfo, AccountCreationResult
            
            personal_info = PersonalInfo(
                first_name="테스트",
                last_name="사용자",
                username="testuser123",
                password="testpass123!",
                birth_year=1990,
                birth_month=5,
                birth_day=15,
                gender="male"
            )
            
            result = AccountCreationResult(
                success=True,
                email="testuser123@gmail.com",
                password="testpass123!",
                phone_number="+821012345678",
                creation_time=datetime.now(),
                steps_completed=["device_randomization", "personal_info_filled", "phone_verification_completed"]
            )
            
            # 계정 로깅
            account_id = account_logger.log_account_creation_result(
                result, 
                personal_info,
                device_info={"resolution": "1080x1920", "density": 480},
                proxy_info={"ip": "192.168.1.1", "country": "KR"}
            )
            
            if account_id:
                print(f"✅ 계정 로깅 성공! ID: {account_id}")
                
                # 세션 테스트
                session_id = account_logger.start_session(account_id, "test_device_001")
                if session_id:
                    print(f"✅ 세션 시작 성공! ID: {session_id}")
                    
                    # 세션 종료
                    if account_logger.end_session(session_id, ["login", "profile_setup"], []):
                        print("✅ 세션 종료 성공!")
                
                # 통계 확인
                stats = account_logger.get_account_statistics()
                print(f"📊 계정 통계: {stats}")
                
                # 백업 테스트
                if account_logger.backup_data():
                    print("✅ 백업 성공!")
                
            else:
                print("❌ 계정 로깅 실패")
                
        except Exception as e:
            logger.error(f"테스트 실행 중 오류: {e}")
    
    # 테스트 실행
    test_account_logging() 