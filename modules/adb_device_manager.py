#!/usr/bin/env python3
"""
ADB Device Manager - Android 디바이스 및 에뮬레이터 관리 시스템

이 모듈은 다음 기능들을 제공합니다:
1. Android 에뮬레이터 자동 생성 및 관리
2. 디바이스 연결 상태 확인 및 복구
3. 에뮬레이터 자동 시작 및 부팅 대기
4. ADB 서버 관리
"""

import os
import asyncio
import subprocess
import time
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
import psutil
import re

class ADBDeviceManager:
    """ADB 디바이스 및 에뮬레이터 관리"""
    
    def __init__(self):
        self.android_home = self._find_android_home()
        self.avd_manager = self._find_avd_manager()
        self.emulator_exe = self._find_emulator()
        self.adb_exe = self._find_adb()
        
        # 기본 에뮬레이터 설정
        self.default_avd_config = {
            'name': 'GoogleAccountCreator_Default',
            'device': 'pixel_7',
            'system_image': 'system-images;android-34;google_apis;x86_64',
            'api_level': '34',
            'target': 'google_apis'
        }
        
        print("🤖 ADB Device Manager 초기화")
        print(f"   Android Home: {self.android_home}")
        print(f"   AVD Manager: {self.avd_manager}")
        print(f"   Emulator: {self.emulator_exe}")
        print(f"   ADB: {self.adb_exe}")
    
    def _find_android_home(self) -> Optional[str]:
        """Android SDK 경로 찾기"""
        # 환경변수 확인
        android_home = os.environ.get('ANDROID_HOME')
        if android_home and os.path.exists(android_home):
            return android_home
        
        # 일반적인 경로들 확인
        possible_paths = [
            os.path.expanduser('~/Library/Android/sdk'),  # macOS
            os.path.expanduser('~/Android/Sdk'),  # Linux
            '/opt/homebrew/share/android-sdk',  # macOS Homebrew
            '/usr/local/share/android-sdk'  # Linux
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _find_avd_manager(self) -> Optional[str]:
        """AVD Manager 실행 파일 찾기"""
        if not self.android_home:
            return None
        
        avdmanager_path = os.path.join(self.android_home, 'cmdline-tools', 'latest', 'bin', 'avdmanager')
        if os.path.exists(avdmanager_path):
            return avdmanager_path
        
        # 다른 버전 확인
        cmdline_tools_dir = os.path.join(self.android_home, 'cmdline-tools')
        if os.path.exists(cmdline_tools_dir):
            for version_dir in os.listdir(cmdline_tools_dir):
                avdmanager_path = os.path.join(cmdline_tools_dir, version_dir, 'bin', 'avdmanager')
                if os.path.exists(avdmanager_path):
                    return avdmanager_path
        
        return None
    
    def _find_emulator(self) -> Optional[str]:
        """Emulator 실행 파일 찾기"""
        if not self.android_home:
            return None
        
        emulator_path = os.path.join(self.android_home, 'emulator', 'emulator')
        if os.path.exists(emulator_path):
            return emulator_path
        
        return None
    
    def _find_adb(self) -> Optional[str]:
        """ADB 실행 파일 찾기"""
        # 시스템 PATH에서 찾기
        try:
            result = subprocess.run(['which', 'adb'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        # Android SDK에서 찾기
        if self.android_home:
            adb_path = os.path.join(self.android_home, 'platform-tools', 'adb')
            if os.path.exists(adb_path):
                return adb_path
        
        return None
    
    async def check_prerequisites(self) -> Dict[str, Any]:
        """시스템 전제 조건 확인"""
        result = {
            'adb_available': bool(self.adb_exe),
            'android_home_found': bool(self.android_home),
            'avd_manager_available': bool(self.avd_manager),
            'emulator_available': bool(self.emulator_exe),
            'connected_devices': [],
            'available_avds': [],
            'recommendations': []
        }
        
        print("🔍 시스템 전제 조건 확인 중...")
        
        # ADB 서버 상태 확인
        if self.adb_exe:
            await self._ensure_adb_server_running()
            result['connected_devices'] = await self.get_connected_devices()
        else:
            result['recommendations'].append("ADB를 설치해야 합니다")
        
        # AVD 목록 확인
        if self.emulator_exe:
            result['available_avds'] = await self.get_available_avds()
        else:
            result['recommendations'].append("Emulator를 설치해야 합니다")
        
        # 권장사항 생성
        if not result['connected_devices'] and not result['available_avds']:
            result['recommendations'].append("Android 에뮬레이터를 생성하거나 실제 디바이스를 연결해야 합니다")
        
        return result
    
    async def _ensure_adb_server_running(self):
        """ADB 서버 실행 확인 및 시작"""
        try:
            # ADB 서버 시작
            await self._run_command([self.adb_exe, 'start-server'])
            print("✅ ADB 서버 실행 중")
        except Exception as e:
            print(f"❌ ADB 서버 시작 실패: {e}")
    
    async def get_connected_devices(self) -> List[str]:
        """연결된 디바이스 목록 가져오기"""
        if not self.adb_exe:
            return []
        
        try:
            result = await self._run_command([self.adb_exe, 'devices'])
            devices = []
            
            for line in result.splitlines()[1:]:  # 첫 번째 줄은 헤더
                if line.strip() and '\t' in line:
                    device_id = line.split('\t')[0]
                    devices.append(device_id)
            
            return devices
        except Exception as e:
            print(f"❌ 디바이스 목록 가져오기 실패: {e}")
            return []
    
    async def get_available_avds(self) -> List[str]:
        """사용 가능한 AVD 목록 가져오기"""
        # AVD Manager 대신 emulator 명령어 직접 사용
        if not self.emulator_exe:
            return []
        
        try:
            result = await self._run_command([self.emulator_exe, '-list-avds'])
            avds = [line.strip() for line in result.splitlines() if line.strip()]
            return avds
        except Exception as e:
            print(f"❌ AVD 목록 가져오기 실패: {e}")
            return []
    
    async def create_default_avd(self) -> bool:
        """기본 AVD 생성"""
        if not self.avd_manager:
            print("❌ AVD Manager를 사용할 수 없습니다")
            return False
        
        config = self.default_avd_config
        print(f"📱 기본 AVD 생성 중: {config['name']}")
        
        try:
            # 시스템 이미지가 설치되어 있는지 확인
            await self._ensure_system_image_installed(config['system_image'])
            
            # AVD 생성 명령
            cmd = [
                self.avd_manager, 'create', 'avd',
                '--name', config['name'],
                '--package', config['system_image'],
                '--device', config['device']
            ]
            
            # 자동으로 "no"를 선택 (기존 AVD 덮어쓰지 않음)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=b'no\n')
            
            if process.returncode == 0:
                print(f"✅ AVD '{config['name']}' 생성 완료")
                return True
            else:
                print(f"❌ AVD 생성 실패: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ AVD 생성 중 오류: {e}")
            return False
    
    async def _ensure_system_image_installed(self, system_image: str):
        """시스템 이미지가 설치되어 있는지 확인하고 설치"""
        # 간단한 구현 - 실제로는 sdkmanager를 사용해서 설치 확인/설치
        print(f"🔍 시스템 이미지 확인: {system_image}")
        # TODO: sdkmanager로 실제 확인 및 설치 구현
    
    async def start_emulator(self, avd_name: Optional[str] = None) -> Optional[str]:
        """에뮬레이터 시작"""
        if not self.emulator_exe:
            print("❌ Emulator 실행 파일을 찾을 수 없습니다")
            return None
        
        # AVD 이름이 지정되지 않으면 기본값 사용
        if not avd_name:
            avds = await self.get_available_avds()
            if not avds:
                print("📱 사용 가능한 AVD가 없어 기본 AVD를 생성합니다")
                if await self.create_default_avd():
                    avd_name = self.default_avd_config['name']
                else:
                    print("❌ 기본 AVD 생성 실패")
                    return None
            else:
                avd_name = avds[0]
        
        print(f"🚀 에뮬레이터 시작 중: {avd_name}")
        
        try:
            # 에뮬레이터를 백그라운드에서 시작
            process = await asyncio.create_subprocess_exec(
                self.emulator_exe, '-avd', avd_name, '-no-audio', '-no-window',
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            print(f"   프로세스 ID: {process.pid}")
            
            # 에뮬레이터 부팅 대기
            device_id = await self._wait_for_emulator_boot()
            
            if device_id:
                print(f"✅ 에뮬레이터 부팅 완료: {device_id}")
                return device_id
            else:
                print("❌ 에뮬레이터 부팅 실패")
                return None
                
        except Exception as e:
            print(f"❌ 에뮬레이터 시작 실패: {e}")
            return None
    
    async def _wait_for_emulator_boot(self, timeout: int = 300) -> Optional[str]:
        """에뮬레이터 부팅 완료 대기"""
        print("⏳ 에뮬레이터 부팅 대기 중...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            devices = await self.get_connected_devices()
            
            for device in devices:
                if await self._is_device_ready(device):
                    return device
            
            await asyncio.sleep(5)
            print("   부팅 중...")
        
        print(f"⏰ 에뮬레이터 부팅 시간 초과 ({timeout}초)")
        return None
    
    async def _is_device_ready(self, device_id: str) -> bool:
        """디바이스가 준비되었는지 확인"""
        try:
            # 부트 완료 확인
            result = await self._run_command([
                self.adb_exe, '-s', device_id, 'shell', 
                'getprop', 'sys.boot_completed'
            ])
            
            if result.strip() == '1':
                return True
            
            return False
            
        except Exception:
            return False
    
    async def ensure_device_available(self) -> Optional[str]:
        """디바이스가 사용 가능한지 확인하고 없으면 에뮬레이터 시작"""
        print("🔍 사용 가능한 디바이스 확인 중...")
        
        # 이미 연결된 디바이스 확인
        devices = await self.get_connected_devices()
        
        for device in devices:
            if await self._is_device_ready(device):
                print(f"✅ 사용 가능한 디바이스 발견: {device}")
                return device
        
        # 연결된 디바이스가 없으면 에뮬레이터 시작
        print("📱 연결된 디바이스가 없어 에뮬레이터를 시작합니다")
        return await self.start_emulator()
    
    async def stop_all_emulators(self):
        """모든 에뮬레이터 종료"""
        devices = await self.get_connected_devices()
        
        for device in devices:
            if 'emulator' in device:
                try:
                    await self._run_command([self.adb_exe, '-s', device, 'emu', 'kill'])
                    print(f"🛑 에뮬레이터 종료: {device}")
                except Exception as e:
                    print(f"❌ 에뮬레이터 종료 실패 {device}: {e}")
    
    async def _run_command(self, cmd: List[str]) -> str:
        """명령어 실행"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Command failed: {stderr.decode()}")
            
            return stdout.decode()
            
        except Exception as e:
            raise Exception(f"Failed to run command {' '.join(cmd)}: {e}")
    
    def get_setup_guide(self) -> str:
        """설정 가이드 반환"""
        guide = """
🔧 ADB 시스템 설정 가이드

1. Android Studio 설치 확인:
   - Android Studio가 설치되어 있는지 확인
   - SDK Manager에서 필요한 컴포넌트 설치

2. 환경 변수 설정:
   export ANDROID_HOME=~/Library/Android/sdk
   export PATH=$PATH:$ANDROID_HOME/platform-tools
   export PATH=$PATH:$ANDROID_HOME/emulator

3. AVD (Android Virtual Device) 생성:
   - Android Studio > AVD Manager에서 가상 디바이스 생성
   - 또는 이 스크립트가 자동으로 생성합니다

4. 실제 디바이스 사용시:
   - 설정 > 개발자 옵션 > USB 디버깅 활성화
   - USB로 컴퓨터와 연결
   - 디버깅 허용 팝업에서 "허용" 선택

🤖 자동 설정:
이 스크립트가 자동으로 다음을 수행합니다:
- ADB 서버 시작
- AVD 생성 (없는 경우)
- 에뮬레이터 시작
- 부팅 완료 대기
        """
        return guide

# 테스트 및 데모 함수
async def main():
    """ADB Device Manager 테스트"""
    print("🤖 ADB Device Manager 테스트")
    print("=" * 50)
    
    manager = ADBDeviceManager()
    
    # 전제 조건 확인
    prerequisites = await manager.check_prerequisites()
    
    print("\n📋 시스템 상태:")
    print(f"   ADB 사용 가능: {'✅' if prerequisites['adb_available'] else '❌'}")
    print(f"   Android Home: {'✅' if prerequisites['android_home_found'] else '❌'}")
    print(f"   AVD Manager: {'✅' if prerequisites['avd_manager_available'] else '❌'}")
    print(f"   Emulator: {'✅' if prerequisites['emulator_available'] else '❌'}")
    print(f"   연결된 디바이스: {len(prerequisites['connected_devices'])}개")
    print(f"   사용 가능한 AVD: {len(prerequisites['available_avds'])}개")
    
    if prerequisites['recommendations']:
        print("\n💡 권장사항:")
        for rec in prerequisites['recommendations']:
            print(f"   - {rec}")
    
    # 디바이스 확보 시도
    print("\n🚀 디바이스 확보 시도...")
    device = await manager.ensure_device_available()
    
    if device:
        print(f"✅ 디바이스 준비 완료: {device}")
        
        # 디바이스 정보 확인
        print(f"📱 디바이스 정보:")
        try:
            result = await manager._run_command([
                manager.adb_exe, '-s', device, 'shell', 'getprop', 'ro.product.model'
            ])
            print(f"   모델: {result.strip()}")
            
            result = await manager._run_command([
                manager.adb_exe, '-s', device, 'shell', 'getprop', 'ro.build.version.release'
            ])
            print(f"   Android 버전: {result.strip()}")
            
        except Exception as e:
            print(f"   정보 가져오기 실패: {e}")
    else:
        print("❌ 디바이스 확보 실패")
        print("\n📖 설정 가이드:")
        print(manager.get_setup_guide())

if __name__ == "__main__":
    asyncio.run(main()) 