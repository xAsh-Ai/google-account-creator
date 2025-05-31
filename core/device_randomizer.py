"""
디바이스 랜덤화 모듈

이 모듈은 ADB 명령을 사용하여 디바이스 지문을 랜덤화하는 기능을 제공합니다.
- 화면 해상도 랜덤화
- 화면 밀도 랜덤화  
- 디바이스 언어 랜덤화
- 디바이스 시간대 랜덤화
"""

import random
import logging
from typing import Tuple, List, Optional, Dict
from .adb_controller import ADBController

# 로깅 설정
logger = logging.getLogger(__name__)

class DeviceRandomizer:
    """디바이스 지문 랜덤화를 위한 클래스"""
    
    # 일반적인 Android 화면 해상도 목록 (width, height)
    COMMON_RESOLUTIONS = [
        (720, 1280),   # HD
        (1080, 1920),  # Full HD
        (1440, 2560),  # QHD
        (1080, 2340),  # 18.5:9
        (1080, 2400),  # 20:9
        (720, 1560),   # HD+ 19.5:9
        (828, 1792),   # iPhone XR 해상도
        (750, 1334),   # iPhone 8 해상도
        (1125, 2436),  # iPhone X 해상도
        (1242, 2688),  # iPhone XS Max 해상도
        (1080, 2160),  # 18:9
        (1440, 2960),  # Galaxy S8/S9
        (1440, 3040),  # Galaxy S10
        (1644, 3840),  # 4K
        (900, 1600),   # WUXGA
        (768, 1366),   # WXGA
    ]
    
    # 화면 밀도 값 (DPI)
    SCREEN_DENSITIES = [
        120,  # ldpi
        160,  # mdpi
        213,  # tvdpi
        240,  # hdpi
        320,  # xhdpi
        480,  # xxhdpi
        640,  # xxxhdpi
        280,  # 커스텀
        300,  # 커스텀
        360,  # 커스텀
        400,  # 커스텀
        420,  # 커스텀
        560,  # 커스텀
    ]
    
    # 지원되는 언어 코드
    SUPPORTED_LANGUAGES = [
        'en',    # 영어
        'ko',    # 한국어
        'ja',    # 일본어
        'zh',    # 중국어
        'es',    # 스페인어
        'fr',    # 프랑스어
        'de',    # 독일어
        'it',    # 이탈리아어
        'pt',    # 포르투갈어
        'ru',    # 러시아어
        'ar',    # 아랍어
        'hi',    # 힌디어
        'th',    # 태국어
        'vi',    # 베트남어
        'tr',    # 터키어
    ]
    
    # 시간대 목록
    TIME_ZONES = [
        'Asia/Seoul',
        'Asia/Tokyo',
        'Asia/Shanghai',
        'Asia/Hong_Kong',
        'Asia/Singapore',
        'Asia/Bangkok',
        'Asia/Jakarta',
        'Asia/Manila',
        'Asia/Kolkata',
        'Asia/Dubai',
        'Europe/London',
        'Europe/Paris',
        'Europe/Berlin',
        'Europe/Rome',
        'Europe/Madrid',
        'Europe/Moscow',
        'America/New_York',
        'America/Los_Angeles',
        'America/Chicago',
        'America/Denver',
        'America/Toronto',
        'America/Vancouver',
        'America/Mexico_City',
        'America/Sao_Paulo',
        'America/Buenos_Aires',
        'Australia/Sydney',
        'Australia/Melbourne',
        'Pacific/Auckland',
    ]
    
    def __init__(self, adb_controller: ADBController):
        """
        DeviceRandomizer 초기화
        
        Args:
            adb_controller: ADB 컨트롤러 인스턴스
        """
        self.adb = adb_controller
        self.original_settings = {}
        logger.info("디바이스 랜덤화 모듈이 초기화되었습니다.")
    
    def get_current_resolution(self) -> Optional[Tuple[int, int]]:
        """
        현재 화면 해상도를 가져옵니다.
        
        Returns:
            현재 해상도 (width, height) 또는 None
        """
        try:
            result = self.adb.execute_shell_command("wm size")
            if result and "Physical size:" in result:
                # "Physical size: 1080x1920" 형태에서 해상도 추출
                size_str = result.split("Physical size:")[1].strip()
                width, height = map(int, size_str.split('x'))
                logger.info(f"현재 화면 해상도: {width}x{height}")
                return (width, height)
        except Exception as e:
            logger.error(f"현재 해상도 가져오기 실패: {e}")
        return None
    
    def randomize_screen_resolution(self) -> bool:
        """
        화면 해상도를 랜덤하게 변경합니다.
        
        Returns:
            성공 여부
        """
        try:
            # 현재 해상도 저장 (복원용)
            if 'resolution' not in self.original_settings:
                current_resolution = self.get_current_resolution()
                if current_resolution:
                    self.original_settings['resolution'] = current_resolution
                    logger.info(f"원본 해상도 저장: {current_resolution}")
            
            # 랜덤 해상도 선택
            new_resolution = random.choice(self.COMMON_RESOLUTIONS)
            width, height = new_resolution
            
            logger.info(f"화면 해상도를 {width}x{height}로 변경 시도 중...")
            
            # ADB 명령으로 해상도 변경
            command = f"wm size {width}x{height}"
            result = self.adb.execute_shell_command(command)
            
            # 변경 확인
            import time
            time.sleep(2)  # 변경 적용 대기
            
            current_resolution = self.get_current_resolution()
            if current_resolution == new_resolution:
                logger.info(f"화면 해상도가 성공적으로 {width}x{height}로 변경되었습니다.")
                return True
            else:
                logger.warning(f"해상도 변경이 예상과 다릅니다. 현재: {current_resolution}, 예상: {new_resolution}")
                return False
                
        except Exception as e:
            logger.error(f"화면 해상도 랜덤화 실패: {e}")
            return False
    
    def get_current_density(self) -> Optional[int]:
        """
        현재 화면 밀도를 가져옵니다.
        
        Returns:
            현재 밀도 값 또는 None
        """
        try:
            result = self.adb.execute_shell_command("wm density")
            if result and "Physical density:" in result:
                # "Physical density: 480" 형태에서 밀도 추출
                density_str = result.split("Physical density:")[1].strip()
                density = int(density_str)
                logger.info(f"현재 화면 밀도: {density} DPI")
                return density
        except Exception as e:
            logger.error(f"현재 밀도 가져오기 실패: {e}")
        return None
    
    def randomize_screen_density(self) -> bool:
        """
        화면 밀도를 랜덤하게 변경합니다.
        
        Returns:
            성공 여부
        """
        try:
            # 현재 밀도 저장 (복원용)
            if 'density' not in self.original_settings:
                current_density = self.get_current_density()
                if current_density:
                    self.original_settings['density'] = current_density
                    logger.info(f"원본 밀도 저장: {current_density} DPI")
            
            # 랜덤 밀도 선택
            new_density = random.choice(self.SCREEN_DENSITIES)
            
            logger.info(f"화면 밀도를 {new_density} DPI로 변경 시도 중...")
            
            # ADB 명령으로 밀도 변경
            command = f"wm density {new_density}"
            result = self.adb.execute_shell_command(command)
            
            # 변경 확인
            import time
            time.sleep(2)  # 변경 적용 대기
            
            current_density = self.get_current_density()
            if current_density == new_density:
                logger.info(f"화면 밀도가 성공적으로 {new_density} DPI로 변경되었습니다.")
                return True
            else:
                logger.warning(f"밀도 변경이 예상과 다릅니다. 현재: {current_density}, 예상: {new_density}")
                return False
                
        except Exception as e:
            logger.error(f"화면 밀도 랜덤화 실패: {e}")
            return False
    
    def get_current_language(self) -> Optional[str]:
        """
        현재 디바이스 언어를 가져옵니다.
        
        Returns:
            현재 언어 코드 또는 None
        """
        try:
            result = self.adb.execute_shell_command("getprop persist.sys.language")
            if result:
                language = result.strip()
                logger.info(f"현재 디바이스 언어: {language}")
                return language
        except Exception as e:
            logger.error(f"현재 언어 가져오기 실패: {e}")
        return None
    
    def randomize_device_language(self) -> bool:
        """
        디바이스 언어를 랜덤하게 변경합니다.
        
        Returns:
            성공 여부
        """
        try:
            # 현재 언어 저장 (복원용)
            if 'language' not in self.original_settings:
                current_language = self.get_current_language()
                if current_language:
                    self.original_settings['language'] = current_language
                    logger.info(f"원본 언어 저장: {current_language}")
            
            # 랜덤 언어 선택
            new_language = random.choice(self.SUPPORTED_LANGUAGES)
            
            logger.info(f"디바이스 언어를 {new_language}로 변경 시도 중...")
            
            # ADB 명령으로 언어 변경
            command = f"setprop persist.sys.language {new_language}"
            result = self.adb.execute_shell_command(command)
            
            # 변경 확인
            import time
            time.sleep(3)  # 변경 적용 대기
            
            current_language = self.get_current_language()
            if current_language == new_language:
                logger.info(f"디바이스 언어가 성공적으로 {new_language}로 변경되었습니다.")
                return True
            else:
                logger.warning(f"언어 변경이 예상과 다릅니다. 현재: {current_language}, 예상: {new_language}")
                return False
                
        except Exception as e:
            logger.error(f"디바이스 언어 랜덤화 실패: {e}")
            return False
    
    def get_current_timezone(self) -> Optional[str]:
        """
        현재 디바이스 시간대를 가져옵니다.
        
        Returns:
            현재 시간대 또는 None
        """
        try:
            result = self.adb.execute_shell_command("getprop persist.sys.timezone")
            if result:
                timezone = result.strip()
                logger.info(f"현재 디바이스 시간대: {timezone}")
                return timezone
        except Exception as e:
            logger.error(f"현재 시간대 가져오기 실패: {e}")
        return None
    
    def randomize_device_timezone(self) -> bool:
        """
        디바이스 시간대를 랜덤하게 변경합니다.
        
        Returns:
            성공 여부
        """
        try:
            # 현재 시간대 저장 (복원용)
            if 'timezone' not in self.original_settings:
                current_timezone = self.get_current_timezone()
                if current_timezone:
                    self.original_settings['timezone'] = current_timezone
                    logger.info(f"원본 시간대 저장: {current_timezone}")
            
            # 랜덤 시간대 선택
            new_timezone = random.choice(self.TIME_ZONES)
            
            logger.info(f"디바이스 시간대를 {new_timezone}로 변경 시도 중...")
            
            # ADB 명령으로 시간대 변경
            command = f"setprop persist.sys.timezone {new_timezone}"
            result = self.adb.execute_shell_command(command)
            
            # 변경 확인
            import time
            time.sleep(3)  # 변경 적용 대기
            
            current_timezone = self.get_current_timezone()
            if current_timezone == new_timezone:
                logger.info(f"디바이스 시간대가 성공적으로 {new_timezone}로 변경되었습니다.")
                return True
            else:
                logger.warning(f"시간대 변경이 예상과 다릅니다. 현재: {current_timezone}, 예상: {new_timezone}")
                return False
                
        except Exception as e:
            logger.error(f"디바이스 시간대 랜덤화 실패: {e}")
            return False
    
    def randomize_all(self) -> Dict[str, bool]:
        """
        모든 디바이스 설정을 랜덤화합니다.
        
        Returns:
            각 설정의 성공 여부를 담은 딕셔너리
        """
        logger.info("모든 디바이스 설정 랜덤화를 시작합니다...")
        
        results = {
            'resolution': self.randomize_screen_resolution(),
            'density': self.randomize_screen_density(),
            'language': self.randomize_device_language(),
            'timezone': self.randomize_device_timezone(),
        }
        
        success_count = sum(results.values())
        total_count = len(results)
        
        logger.info(f"디바이스 랜덤화 완료: {success_count}/{total_count} 성공")
        
        return results
    
    def restore_original_settings(self) -> Dict[str, bool]:
        """
        원본 설정으로 복원합니다.
        
        Returns:
            각 설정의 복원 성공 여부를 담은 딕셔너리
        """
        logger.info("원본 디바이스 설정으로 복원을 시작합니다...")
        
        results = {}
        
        # 해상도 복원
        if 'resolution' in self.original_settings:
            try:
                width, height = self.original_settings['resolution']
                command = f"wm size {width}x{height}"
                self.adb.execute_shell_command(command)
                results['resolution'] = True
                logger.info(f"해상도를 원본 {width}x{height}로 복원했습니다.")
            except Exception as e:
                logger.error(f"해상도 복원 실패: {e}")
                results['resolution'] = False
        
        # 밀도 복원
        if 'density' in self.original_settings:
            try:
                density = self.original_settings['density']
                command = f"wm density {density}"
                self.adb.execute_shell_command(command)
                results['density'] = True
                logger.info(f"밀도를 원본 {density} DPI로 복원했습니다.")
            except Exception as e:
                logger.error(f"밀도 복원 실패: {e}")
                results['density'] = False
        
        # 언어 복원
        if 'language' in self.original_settings:
            try:
                language = self.original_settings['language']
                command = f"setprop persist.sys.language {language}"
                self.adb.execute_shell_command(command)
                results['language'] = True
                logger.info(f"언어를 원본 {language}로 복원했습니다.")
            except Exception as e:
                logger.error(f"언어 복원 실패: {e}")
                results['language'] = False
        
        # 시간대 복원
        if 'timezone' in self.original_settings:
            try:
                timezone = self.original_settings['timezone']
                command = f"setprop persist.sys.timezone {timezone}"
                self.adb.execute_shell_command(command)
                results['timezone'] = True
                logger.info(f"시간대를 원본 {timezone}로 복원했습니다.")
            except Exception as e:
                logger.error(f"시간대 복원 실패: {e}")
                results['timezone'] = False
        
        success_count = sum(results.values())
        total_count = len(results)
        
        logger.info(f"원본 설정 복원 완료: {success_count}/{total_count} 성공")
        
        return results
    
    def reset_to_defaults(self) -> Dict[str, bool]:
        """
        디바이스 설정을 기본값으로 재설정합니다.
        
        Returns:
            각 설정의 재설정 성공 여부를 담은 딕셔너리
        """
        logger.info("디바이스 설정을 기본값으로 재설정합니다...")
        
        results = {}
        
        try:
            # 해상도 기본값으로 재설정
            self.adb.execute_shell_command("wm size reset")
            results['resolution'] = True
            logger.info("해상도를 기본값으로 재설정했습니다.")
        except Exception as e:
            logger.error(f"해상도 재설정 실패: {e}")
            results['resolution'] = False
        
        try:
            # 밀도 기본값으로 재설정
            self.adb.execute_shell_command("wm density reset")
            results['density'] = True
            logger.info("밀도를 기본값으로 재설정했습니다.")
        except Exception as e:
            logger.error(f"밀도 재설정 실패: {e}")
            results['density'] = False
        
        # 언어와 시간대는 기본값 재설정이 복잡하므로 원본 설정 복원 사용
        if 'language' in self.original_settings:
            try:
                language = self.original_settings['language']
                command = f"setprop persist.sys.language {language}"
                self.adb.execute_shell_command(command)
                results['language'] = True
                logger.info(f"언어를 {language}로 복원했습니다.")
            except Exception as e:
                logger.error(f"언어 복원 실패: {e}")
                results['language'] = False
        
        if 'timezone' in self.original_settings:
            try:
                timezone = self.original_settings['timezone']
                command = f"setprop persist.sys.timezone {timezone}"
                self.adb.execute_shell_command(command)
                results['timezone'] = True
                logger.info(f"시간대를 {timezone}로 복원했습니다.")
            except Exception as e:
                logger.error(f"시간대 복원 실패: {e}")
                results['timezone'] = False
        
        success_count = sum(results.values())
        total_count = len(results)
        
        logger.info(f"기본값 재설정 완료: {success_count}/{total_count} 성공")
        
        return results


# 편의 함수들
def create_device_randomizer(device_id: Optional[str] = None) -> DeviceRandomizer:
    """
    DeviceRandomizer 인스턴스를 생성합니다.
    
    Args:
        device_id: 대상 디바이스 ID (None이면 첫 번째 연결된 디바이스 사용)
    
    Returns:
        DeviceRandomizer 인스턴스
    """
    adb_controller = ADBController(device_id)
    return DeviceRandomizer(adb_controller)


def quick_randomize(device_id: Optional[str] = None) -> Dict[str, bool]:
    """
    빠른 디바이스 랜덤화를 수행합니다.
    
    Args:
        device_id: 대상 디바이스 ID
    
    Returns:
        각 설정의 성공 여부를 담은 딕셔너리
    """
    randomizer = create_device_randomizer(device_id)
    return randomizer.randomize_all()


if __name__ == "__main__":
    # 테스트 코드
    import sys
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # DeviceRandomizer 생성
        randomizer = create_device_randomizer()
        
        if len(sys.argv) > 1:
            action = sys.argv[1].lower()
            
            if action == "randomize":
                # 모든 설정 랜덤화
                results = randomizer.randomize_all()
                print(f"랜덤화 결과: {results}")
                
            elif action == "restore":
                # 원본 설정 복원
                results = randomizer.restore_original_settings()
                print(f"복원 결과: {results}")
                
            elif action == "reset":
                # 기본값으로 재설정
                results = randomizer.reset_to_defaults()
                print(f"재설정 결과: {results}")
                
            elif action == "resolution":
                # 해상도만 랜덤화
                result = randomizer.randomize_screen_resolution()
                print(f"해상도 랜덤화 결과: {result}")
                
            elif action == "density":
                # 밀도만 랜덤화
                result = randomizer.randomize_screen_density()
                print(f"밀도 랜덤화 결과: {result}")
                
            elif action == "language":
                # 언어만 랜덤화
                result = randomizer.randomize_device_language()
                print(f"언어 랜덤화 결과: {result}")
                
            elif action == "timezone":
                # 시간대만 랜덤화
                result = randomizer.randomize_device_timezone()
                print(f"시간대 랜덤화 결과: {result}")
                
            else:
                print("사용법: python device_randomizer.py [randomize|restore|reset|resolution|density|language|timezone]")
        else:
            # 기본 동작: 현재 설정 확인
            print("현재 디바이스 설정:")
            print(f"해상도: {randomizer.get_current_resolution()}")
            print(f"밀도: {randomizer.get_current_density()}")
            print(f"언어: {randomizer.get_current_language()}")
            print(f"시간대: {randomizer.get_current_timezone()}")
            
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")
        sys.exit(1) 