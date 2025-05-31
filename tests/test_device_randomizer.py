"""
디바이스 랜덤화 모듈 테스트

이 파일은 core/device_randomizer.py 모듈의 기능을 테스트합니다.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.device_randomizer import DeviceRandomizer, create_device_randomizer, quick_randomize
from core.adb_controller import ADBController


class TestDeviceRandomizer(unittest.TestCase):
    """DeviceRandomizer 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # Mock ADB 컨트롤러 생성
        self.mock_adb = Mock(spec=ADBController)
        self.randomizer = DeviceRandomizer(self.mock_adb)
    
    def test_init(self):
        """초기화 테스트"""
        self.assertEqual(self.randomizer.adb, self.mock_adb)
        self.assertEqual(self.randomizer.original_settings, {})
    
    def test_get_current_resolution_success(self):
        """현재 해상도 가져오기 성공 테스트"""
        # Mock ADB 응답
        self.mock_adb.execute_shell_command.return_value = "Physical size: 1080x1920"
        
        result = self.randomizer.get_current_resolution()
        
        self.assertEqual(result, (1080, 1920))
        self.mock_adb.execute_shell_command.assert_called_with("wm size")
    
    def test_get_current_resolution_failure(self):
        """현재 해상도 가져오기 실패 테스트"""
        # Mock ADB 응답 (실패)
        self.mock_adb.execute_shell_command.return_value = None
        
        result = self.randomizer.get_current_resolution()
        
        self.assertIsNone(result)
    
    def test_get_current_density_success(self):
        """현재 밀도 가져오기 성공 테스트"""
        # Mock ADB 응답
        self.mock_adb.execute_shell_command.return_value = "Physical density: 480"
        
        result = self.randomizer.get_current_density()
        
        self.assertEqual(result, 480)
        self.mock_adb.execute_shell_command.assert_called_with("wm density")
    
    def test_get_current_language_success(self):
        """현재 언어 가져오기 성공 테스트"""
        # Mock ADB 응답
        self.mock_adb.execute_shell_command.return_value = "ko"
        
        result = self.randomizer.get_current_language()
        
        self.assertEqual(result, "ko")
        self.mock_adb.execute_shell_command.assert_called_with("getprop persist.sys.language")
    
    def test_get_current_timezone_success(self):
        """현재 시간대 가져오기 성공 테스트"""
        # Mock ADB 응답
        self.mock_adb.execute_shell_command.return_value = "Asia/Seoul"
        
        result = self.randomizer.get_current_timezone()
        
        self.assertEqual(result, "Asia/Seoul")
        self.mock_adb.execute_shell_command.assert_called_with("getprop persist.sys.timezone")
    
    @patch('time.sleep')  # sleep 함수 모킹
    @patch('random.choice')
    def test_randomize_screen_resolution_success(self, mock_choice, mock_sleep):
        """화면 해상도 랜덤화 성공 테스트"""
        # Mock 설정
        mock_choice.return_value = (1080, 1920)
        self.mock_adb.execute_shell_command.side_effect = [
            "Physical size: 720x1280",  # 현재 해상도
            None,  # 변경 명령
            "Physical size: 1080x1920"  # 변경 후 해상도
        ]
        
        result = self.randomizer.randomize_screen_resolution()
        
        self.assertTrue(result)
        self.assertEqual(self.randomizer.original_settings['resolution'], (720, 1280))
        
        # ADB 명령 호출 확인
        calls = self.mock_adb.execute_shell_command.call_args_list
        self.assertEqual(calls[0][0][0], "wm size")  # 현재 해상도 조회
        self.assertEqual(calls[1][0][0], "wm size 1080x1920")  # 해상도 변경
        self.assertEqual(calls[2][0][0], "wm size")  # 변경 후 확인
    
    @patch('time.sleep')
    @patch('random.choice')
    def test_randomize_screen_density_success(self, mock_choice, mock_sleep):
        """화면 밀도 랜덤화 성공 테스트"""
        # Mock 설정
        mock_choice.return_value = 480
        self.mock_adb.execute_shell_command.side_effect = [
            "Physical density: 320",  # 현재 밀도
            None,  # 변경 명령
            "Physical density: 480"  # 변경 후 밀도
        ]
        
        result = self.randomizer.randomize_screen_density()
        
        self.assertTrue(result)
        self.assertEqual(self.randomizer.original_settings['density'], 320)
    
    @patch('time.sleep')
    @patch('random.choice')
    def test_randomize_device_language_success(self, mock_choice, mock_sleep):
        """디바이스 언어 랜덤화 성공 테스트"""
        # Mock 설정
        mock_choice.return_value = "en"
        self.mock_adb.execute_shell_command.side_effect = [
            "ko",  # 현재 언어
            None,  # 변경 명령
            "en"   # 변경 후 언어
        ]
        
        result = self.randomizer.randomize_device_language()
        
        self.assertTrue(result)
        self.assertEqual(self.randomizer.original_settings['language'], "ko")
    
    @patch('time.sleep')
    @patch('random.choice')
    def test_randomize_device_timezone_success(self, mock_choice, mock_sleep):
        """디바이스 시간대 랜덤화 성공 테스트"""
        # Mock 설정
        mock_choice.return_value = "America/New_York"
        self.mock_adb.execute_shell_command.side_effect = [
            "Asia/Seoul",  # 현재 시간대
            None,  # 변경 명령
            "America/New_York"  # 변경 후 시간대
        ]
        
        result = self.randomizer.randomize_device_timezone()
        
        self.assertTrue(result)
        self.assertEqual(self.randomizer.original_settings['timezone'], "Asia/Seoul")
    
    @patch.object(DeviceRandomizer, 'randomize_screen_resolution')
    @patch.object(DeviceRandomizer, 'randomize_screen_density')
    @patch.object(DeviceRandomizer, 'randomize_device_language')
    @patch.object(DeviceRandomizer, 'randomize_device_timezone')
    def test_randomize_all(self, mock_timezone, mock_language, mock_density, mock_resolution):
        """모든 설정 랜덤화 테스트"""
        # Mock 반환값 설정
        mock_resolution.return_value = True
        mock_density.return_value = True
        mock_language.return_value = False  # 하나는 실패로 설정
        mock_timezone.return_value = True
        
        result = self.randomizer.randomize_all()
        
        expected = {
            'resolution': True,
            'density': True,
            'language': False,
            'timezone': True
        }
        self.assertEqual(result, expected)
        
        # 모든 메서드가 호출되었는지 확인
        mock_resolution.assert_called_once()
        mock_density.assert_called_once()
        mock_language.assert_called_once()
        mock_timezone.assert_called_once()
    
    def test_restore_original_settings(self):
        """원본 설정 복원 테스트"""
        # 원본 설정 미리 설정
        self.randomizer.original_settings = {
            'resolution': (720, 1280),
            'density': 320,
            'language': 'ko',
            'timezone': 'Asia/Seoul'
        }
        
        result = self.randomizer.restore_original_settings()
        
        # 모든 복원이 성공했는지 확인
        expected = {
            'resolution': True,
            'density': True,
            'language': True,
            'timezone': True
        }
        self.assertEqual(result, expected)
        
        # ADB 명령이 올바르게 호출되었는지 확인
        calls = self.mock_adb.execute_shell_command.call_args_list
        self.assertIn(('wm size 720x1280',), [call[0] for call in calls])
        self.assertIn(('wm density 320',), [call[0] for call in calls])
        self.assertIn(('setprop persist.sys.language ko',), [call[0] for call in calls])
        self.assertIn(('setprop persist.sys.timezone Asia/Seoul',), [call[0] for call in calls])
    
    def test_reset_to_defaults(self):
        """기본값 재설정 테스트"""
        # 원본 설정 미리 설정
        self.randomizer.original_settings = {
            'language': 'ko',
            'timezone': 'Asia/Seoul'
        }
        
        result = self.randomizer.reset_to_defaults()
        
        # 기본값 재설정 명령이 호출되었는지 확인
        calls = self.mock_adb.execute_shell_command.call_args_list
        self.assertIn(('wm size reset',), [call[0] for call in calls])
        self.assertIn(('wm density reset',), [call[0] for call in calls])


class TestConvenienceFunctions(unittest.TestCase):
    """편의 함수들 테스트"""
    
    @patch('core.device_randomizer.ADBController')
    def test_create_device_randomizer(self, mock_adb_class):
        """DeviceRandomizer 생성 함수 테스트"""
        mock_adb_instance = Mock()
        mock_adb_class.return_value = mock_adb_instance
        
        randomizer = create_device_randomizer("test_device")
        
        self.assertIsInstance(randomizer, DeviceRandomizer)
        mock_adb_class.assert_called_with("test_device")
        self.assertEqual(randomizer.adb, mock_adb_instance)
    
    @patch('core.device_randomizer.create_device_randomizer')
    def test_quick_randomize(self, mock_create):
        """빠른 랜덤화 함수 테스트"""
        mock_randomizer = Mock()
        mock_randomizer.randomize_all.return_value = {'test': True}
        mock_create.return_value = mock_randomizer
        
        result = quick_randomize("test_device")
        
        self.assertEqual(result, {'test': True})
        mock_create.assert_called_with("test_device")
        mock_randomizer.randomize_all.assert_called_once()


class TestConstants(unittest.TestCase):
    """상수 값들 테스트"""
    
    def test_common_resolutions(self):
        """일반적인 해상도 목록 테스트"""
        self.assertIn((720, 1280), DeviceRandomizer.COMMON_RESOLUTIONS)
        self.assertIn((1080, 1920), DeviceRandomizer.COMMON_RESOLUTIONS)
        self.assertIn((1440, 2560), DeviceRandomizer.COMMON_RESOLUTIONS)
        
        # 모든 해상도가 튜플 형태인지 확인
        for resolution in DeviceRandomizer.COMMON_RESOLUTIONS:
            self.assertIsInstance(resolution, tuple)
            self.assertEqual(len(resolution), 2)
            self.assertIsInstance(resolution[0], int)
            self.assertIsInstance(resolution[1], int)
    
    def test_screen_densities(self):
        """화면 밀도 목록 테스트"""
        self.assertIn(160, DeviceRandomizer.SCREEN_DENSITIES)  # mdpi
        self.assertIn(240, DeviceRandomizer.SCREEN_DENSITIES)  # hdpi
        self.assertIn(320, DeviceRandomizer.SCREEN_DENSITIES)  # xhdpi
        self.assertIn(480, DeviceRandomizer.SCREEN_DENSITIES)  # xxhdpi
        
        # 모든 밀도가 정수인지 확인
        for density in DeviceRandomizer.SCREEN_DENSITIES:
            self.assertIsInstance(density, int)
            self.assertGreater(density, 0)
    
    def test_supported_languages(self):
        """지원 언어 목록 테스트"""
        self.assertIn('ko', DeviceRandomizer.SUPPORTED_LANGUAGES)
        self.assertIn('en', DeviceRandomizer.SUPPORTED_LANGUAGES)
        self.assertIn('ja', DeviceRandomizer.SUPPORTED_LANGUAGES)
        self.assertIn('zh', DeviceRandomizer.SUPPORTED_LANGUAGES)
        
        # 모든 언어 코드가 문자열인지 확인
        for lang in DeviceRandomizer.SUPPORTED_LANGUAGES:
            self.assertIsInstance(lang, str)
            self.assertGreater(len(lang), 0)
    
    def test_time_zones(self):
        """시간대 목록 테스트"""
        self.assertIn('Asia/Seoul', DeviceRandomizer.TIME_ZONES)
        self.assertIn('Asia/Tokyo', DeviceRandomizer.TIME_ZONES)
        self.assertIn('America/New_York', DeviceRandomizer.TIME_ZONES)
        self.assertIn('Europe/London', DeviceRandomizer.TIME_ZONES)
        
        # 모든 시간대가 문자열인지 확인
        for tz in DeviceRandomizer.TIME_ZONES:
            self.assertIsInstance(tz, str)
            self.assertIn('/', tz)  # 시간대 형식 확인


if __name__ == '__main__':
    # 로깅 설정 (테스트 중 로그 출력 최소화)
    import logging
    logging.getLogger('core.device_randomizer').setLevel(logging.CRITICAL)
    
    # 테스트 실행
    unittest.main(verbosity=2) 