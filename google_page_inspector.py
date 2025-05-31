#!/usr/bin/env python3
"""
Google 가입 페이지 구조 검사기

Google의 실제 가입 페이지 구조를 분석하여 올바른 셀렉터를 찾습니다.
"""

import time
import asyncio
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class GooglePageInspector:
    """Google 페이지 구조 검사기"""
    
    def __init__(self):
        self.driver = None
        print("🔍 Google 가입 페이지 구조 검사기")
        print("=" * 50)
    
    def setup_browser(self):
        """브라우저 설정"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # headless 모드 비활성화하여 페이지를 볼 수 있게 함
            # chrome_options.add_argument("--headless")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_window_size(1920, 1080)
            
            # 자동화 감지 방지
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ 브라우저 설정 완료")
            return True
            
        except Exception as e:
            print(f"❌ 브라우저 설정 실패: {e}")
            return False
    
    def inspect_page_structure(self):
        """페이지 구조 검사"""
        try:
            print("🔗 Google 가입 페이지 접속 중...")
            self.driver.get("https://accounts.google.com/signup")
            
            # 페이지 로딩 대기
            time.sleep(5)
            
            print(f"📄 페이지 제목: {self.driver.title}")
            print(f"🌐 현재 URL: {self.driver.current_url}")
            
            print("\n🔍 입력 필드 검사 중...")
            
            # 모든 input 요소 찾기
            input_elements = self.driver.find_elements(By.TAG_NAME, "input")
            
            print(f"📝 총 {len(input_elements)}개의 input 요소 발견:")
            
            for i, element in enumerate(input_elements):
                try:
                    element_info = {
                        'index': i,
                        'name': element.get_attribute('name') or 'N/A',
                        'id': element.get_attribute('id') or 'N/A',
                        'type': element.get_attribute('type') or 'N/A',
                        'placeholder': element.get_attribute('placeholder') or 'N/A',
                        'aria-label': element.get_attribute('aria-label') or 'N/A',
                        'class': element.get_attribute('class') or 'N/A',
                        'visible': element.is_displayed(),
                        'enabled': element.is_enabled()
                    }
                    
                    if element_info['visible'] and element_info['enabled']:
                        print(f"   [{i}] ✅ VISIBLE INPUT:")
                        print(f"       Name: {element_info['name']}")
                        print(f"       ID: {element_info['id']}")
                        print(f"       Type: {element_info['type']}")
                        print(f"       Placeholder: {element_info['placeholder']}")
                        print(f"       Aria-label: {element_info['aria-label']}")
                        print(f"       Class: {element_info['class'][:100]}...")
                        print()
                    
                except Exception as e:
                    print(f"   [{i}] ❌ 오류: {e}")
            
            # 버튼 요소들도 검사
            print("\n🔘 버튼 요소 검사 중...")
            button_elements = self.driver.find_elements(By.TAG_NAME, "button")
            
            for i, element in enumerate(button_elements):
                try:
                    if element.is_displayed():
                        text = element.text or element.get_attribute('aria-label') or 'N/A'
                        print(f"   [{i}] ✅ VISIBLE BUTTON: '{text}'")
                        print(f"       ID: {element.get_attribute('id') or 'N/A'}")
                        print(f"       Class: {element.get_attribute('class') or 'N/A'}")
                        print()
                except Exception as e:
                    print(f"   [{i}] ❌ 버튼 오류: {e}")
            
            # 스크린샷 저장
            screenshot_path = f"google_signup_page_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"📸 페이지 스크린샷 저장: {screenshot_path}")
            
            # 페이지 소스 일부 저장
            page_source_path = f"google_signup_source_{int(time.time())}.html"
            with open(page_source_path, 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print(f"💾 페이지 소스 저장: {page_source_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ 페이지 검사 실패: {e}")
            return False
    
    def test_form_interaction(self):
        """폼 상호작용 테스트"""
        try:
            print("\n🧪 폼 상호작용 테스트...")
            
            # 첫 번째 보이는 텍스트 입력 필드 찾기
            visible_inputs = []
            input_elements = self.driver.find_elements(By.TAG_NAME, "input")
            
            for element in input_elements:
                if element.is_displayed() and element.is_enabled():
                    input_type = element.get_attribute('type')
                    if input_type in ['text', 'email', '']:
                        visible_inputs.append(element)
            
            if visible_inputs:
                print(f"✅ {len(visible_inputs)}개의 입력 가능한 필드 발견")
                
                # 첫 번째 필드에 테스트 입력
                try:
                    test_input = visible_inputs[0]
                    test_input.clear()
                    test_input.send_keys("테스트입력")
                    print("✅ 첫 번째 필드에 테스트 입력 성공")
                    
                    # 잠시 후 지우기
                    time.sleep(2)
                    test_input.clear()
                    print("✅ 입력 내용 삭제 완료")
                    
                except Exception as e:
                    print(f"❌ 입력 테스트 실패: {e}")
            else:
                print("❌ 입력 가능한 필드를 찾을 수 없음")
            
            return True
            
        except Exception as e:
            print(f"❌ 폼 상호작용 테스트 실패: {e}")
            return False
    
    def run_inspection(self):
        """검사 실행"""
        try:
            if not self.setup_browser():
                return False
            
            # 페이지 구조 검사
            if not self.inspect_page_structure():
                return False
            
            # 폼 상호작용 테스트
            if not self.test_form_interaction():
                return False
            
            print("\n🎉 페이지 검사 완료!")
            print("💡 위 정보를 바탕으로 실제 계정 생성 스크립트를 개선할 수 있습니다.")
            
            # 사용자가 페이지를 볼 수 있도록 잠시 대기
            print("\n⏰ 10초 후 브라우저가 닫힙니다. 페이지를 확인해보세요...")
            time.sleep(10)
            
            return True
            
        except Exception as e:
            print(f"❌ 검사 실행 오류: {e}")
            return False
        
        finally:
            if self.driver:
                self.driver.quit()
                print("🧹 브라우저 정리 완료")

def main():
    """메인 함수"""
    inspector = GooglePageInspector()
    
    try:
        print("⚠️ Google 가입 페이지를 검사하시겠습니까? (y/n):", end=" ")
        response = 'y'  # input().strip().lower()
        print('y')
        
        if response == 'y':
            inspector.run_inspection()
        else:
            print("검사가 취소되었습니다.")
            
    except KeyboardInterrupt:
        print("\n\n🛑 검사가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 검사 중 오류 발생: {e}")

if __name__ == "__main__":
    main() 