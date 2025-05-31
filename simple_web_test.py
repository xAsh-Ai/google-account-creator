#!/usr/bin/env python3
"""
Simple Web Test - Chrome FirstRun 우회를 위한 간단한 웹 접근 테스트

Chrome FirstRun 화면을 우회하기 위한 다양한 방법들을 테스트합니다.
"""

import asyncio
import subprocess
import time
import os
from datetime import datetime

class SimpleWebTest:
    """간단한 웹 접근 테스트"""
    
    def __init__(self, device_id="emulator-5554"):
        self.device_id = device_id
        self.adb_exe = "/opt/homebrew/bin/adb"
    
    async def run_command(self, cmd):
        """ADB 명령어 실행"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout.strip()
        except Exception as e:
            print(f"명령어 실행 실패: {e}")
            return ""
    
    async def take_screenshot(self, filename=None):
        """스크린샷 촬영"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simple_test_{timestamp}.png"
        
        try:
            # screenshots 디렉토리 생성
            os.makedirs("screenshots", exist_ok=True)
            
            # 스크린샷 촬영
            await self.run_command([
                self.adb_exe, '-s', self.device_id, 'shell', 'screencap', '/sdcard/temp_screenshot.png'
            ])
            
            # 로컬로 복사
            await self.run_command([
                self.adb_exe, '-s', self.device_id, 'pull', '/sdcard/temp_screenshot.png', f'screenshots/{filename}'
            ])
            
            print(f"📸 스크린샷 저장: screenshots/{filename}")
            return f'screenshots/{filename}'
        except Exception as e:
            print(f"❌ 스크린샷 실패: {e}")
            return None
    
    async def get_current_focus(self):
        """현재 포커스 앱 확인"""
        focus = await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'dumpsys', 'window', '|', 'grep', 'mCurrentFocus'
        ])
        return focus
    
    async def method1_direct_intent(self):
        """방법 1: 직접 Intent로 시스템 브라우저 실행"""
        print("\n🌐 방법 1: 시스템 기본 브라우저로 Google 가입 페이지 접근")
        
        # 홈으로 이동
        await self.run_command([self.adb_exe, '-s', self.device_id, 'shell', 'input', 'keyevent', 'KEYCODE_HOME'])
        await asyncio.sleep(2)
        
        # 시스템 기본 브라우저로 URL 열기
        await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'am', 'start', 
            '-a', 'android.intent.action.VIEW', 
            '-d', 'https://accounts.google.com/signup'
        ])
        
        await asyncio.sleep(5)
        focus = await self.get_current_focus()
        print(f"포커스: {focus}")
        
        screenshot = await self.take_screenshot("method1_result.png")
        return 'chrome' in focus.lower() and 'firstrun' not in focus.lower()
    
    async def method2_settings_intent(self):
        """방법 2: 설정 앱을 통한 계정 추가"""
        print("\n⚙️ 방법 2: Android 설정에서 계정 추가")
        
        # 설정 앱 열기
        await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'am', 'start', 
            '-a', 'android.settings.ADD_ACCOUNT_SETTINGS'
        ])
        
        await asyncio.sleep(3)
        focus = await self.get_current_focus()
        print(f"포커스: {focus}")
        
        screenshot = await self.take_screenshot("method2_result.png")
        return 'settings' in focus.lower()
    
    async def method3_webview_activity(self):
        """방법 3: WebView Activity 직접 실행"""
        print("\n📱 방법 3: WebView Activity로 직접 접근")
        
        # Android System WebView 사용
        await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'am', 'start', 
            '-a', 'android.intent.action.VIEW',
            '-d', 'https://accounts.google.com/signup',
            'com.android.webview'
        ])
        
        await asyncio.sleep(5)
        focus = await self.get_current_focus()
        print(f"포커스: {focus}")
        
        screenshot = await self.take_screenshot("method3_result.png")
        return 'webview' in focus.lower()
    
    async def method4_browser_specific(self):
        """방법 4: 다른 브라우저 앱 찾기"""
        print("\n🔍 방법 4: 설치된 다른 브라우저 확인")
        
        # 설치된 브라우저 패키지 찾기
        packages = await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'pm', 'list', 'packages'
        ])
        
        browser_keywords = ['browser', 'firefox', 'opera', 'edge', 'samsung']
        found_browsers = []
        
        for line in packages.split('\n'):
            for keyword in browser_keywords:
                if keyword in line.lower() and 'chrome' not in line.lower():
                    found_browsers.append(line.strip())
        
        print(f"발견된 브라우저들: {found_browsers}")
        
        if found_browsers:
            # 첫 번째 발견된 브라우저로 시도
            browser_package = found_browsers[0].replace('package:', '')
            await self.run_command([
                self.adb_exe, '-s', self.device_id, 'shell', 'am', 'start',
                '-a', 'android.intent.action.VIEW',
                '-d', 'https://accounts.google.com/signup',
                browser_package
            ])
            
            await asyncio.sleep(5)
            focus = await self.get_current_focus()
            print(f"포커스: {focus}")
            
            screenshot = await self.take_screenshot("method4_result.png")
            return browser_package in focus
        
        return False
    
    async def method5_force_chrome_bypass(self):
        """방법 5: Chrome FirstRun 강제 우회"""
        print("\n💥 방법 5: Chrome FirstRun 강제 우회")
        
        # Chrome 완전 초기화
        await self.run_command([self.adb_exe, '-s', self.device_id, 'shell', 'am', 'force-stop', 'com.android.chrome'])
        await self.run_command([self.adb_exe, '-s', self.device_id, 'shell', 'pm', 'clear', 'com.android.chrome'])
        
        # Chrome FirstRun 플래그 우회 시도
        await self.run_command([
            self.adb_exe, '-s', self.device_id, 'shell', 'am', 'start',
            '-n', 'com.android.chrome/com.google.android.apps.chrome.Main',
            '--ez', 'disable-fre', 'true',
            '--es', 'url', 'https://accounts.google.com/signup'
        ])
        
        await asyncio.sleep(5)
        focus = await self.get_current_focus()
        print(f"포커스: {focus}")
        
        screenshot = await self.take_screenshot("method5_result.png")
        return 'chrome' in focus.lower() and 'firstrun' not in focus.lower()
    
    async def run_all_tests(self):
        """모든 방법 테스트"""
        print("🧪 Simple Web Test - Chrome FirstRun 우회 테스트 시작")
        print("=" * 60)
        
        methods = [
            ("Direct Intent", self.method1_direct_intent),
            ("Settings Intent", self.method2_settings_intent),
            ("WebView Activity", self.method3_webview_activity),
            ("Other Browsers", self.method4_browser_specific),
            ("Force Chrome Bypass", self.method5_force_chrome_bypass),
        ]
        
        results = {}
        
        for method_name, method_func in methods:
            try:
                print(f"\n🔄 {method_name} 테스트 중...")
                success = await method_func()
                results[method_name] = success
                print(f"{'✅' if success else '❌'} {method_name}: {'성공' if success else '실패'}")
                
                # 각 테스트 사이에 잠시 대기
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"❌ {method_name} 테스트 중 오류: {e}")
                results[method_name] = False
        
        print("\n" + "=" * 60)
        print("🏁 테스트 결과 요약:")
        for method_name, success in results.items():
            print(f"   {'✅' if success else '❌'} {method_name}")
        
        successful_methods = [name for name, success in results.items() if success]
        if successful_methods:
            print(f"\n🎉 성공한 방법들: {', '.join(successful_methods)}")
        else:
            print(f"\n😅 모든 방법 실패 - Chrome FirstRun 문제 지속")
        
        return results

async def main():
    """메인 함수"""
    tester = SimpleWebTest()
    results = await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 