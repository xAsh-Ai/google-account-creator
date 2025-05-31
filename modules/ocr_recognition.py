#!/usr/bin/env python3
"""
OCR Recognition - 실제 OCR 기반 화면 요소 인식 시스템

EasyOCR과 Tesseract를 활용한 다중 언어 텍스트 인식 및 UI 요소 탐지
"""

import cv2
import numpy as np
import easyocr
import pytesseract
from PIL import Image, ImageEnhance
from typing import List, Dict, Any, Optional, Tuple
import re
import logging
from pathlib import Path

class OCRRecognition:
    """실제 OCR 기반 화면 요소 인식"""
    
    def __init__(self, languages=['ko', 'en']):
        """OCR 시스템 초기화"""
        self.languages = languages
        self.logger = logging.getLogger(__name__)
        
        try:
            # EasyOCR 초기화 (한국어, 영어 지원)
            self.easyocr_reader = easyocr.Reader(languages, gpu=False)
            self.easyocr_available = True
            print("✅ EasyOCR 초기화 완료")
        except Exception as e:
            self.easyocr_available = False
            print(f"⚠️ EasyOCR 초기화 실패: {e}")
        
        try:
            # Tesseract 설정
            self.tesseract_config = '--oem 3 --psm 6 -l kor+eng'
            # macOS에서 Tesseract 경로 설정
            pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
            self.tesseract_available = True
            print("✅ Tesseract 설정 완료")
        except Exception as e:
            self.tesseract_available = False
            print(f"⚠️ Tesseract 설정 실패: {e}")
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """이미지 전처리 - OCR 정확도 향상"""
        try:
            # 이미지 로드
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"이미지를 로드할 수 없습니다: {image_path}")
            
            # 그레이스케일 변환
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 노이즈 제거
            denoised = cv2.medianBlur(gray, 3)
            
            # 대비 향상
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 이진화 (텍스트 인식 향상)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
            
        except Exception as e:
            self.logger.error(f"이미지 전처리 실패: {e}")
            # 원본 이미지 반환
            return cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    async def extract_text_from_image(self, image_path: str) -> str:
        """이미지에서 모든 텍스트 추출"""
        try:
            all_text = []
            
            # EasyOCR로 텍스트 추출
            if self.easyocr_available:
                try:
                    results = self.easyocr_reader.readtext(image_path)
                    easyocr_text = ' '.join([result[1] for result in results if result[2] > 0.5])
                    if easyocr_text.strip():
                        all_text.append(f"EasyOCR: {easyocr_text}")
                        print(f"📖 EasyOCR 텍스트: {easyocr_text[:100]}...")
                except Exception as e:
                    print(f"⚠️ EasyOCR 실행 실패: {e}")
            
            # Tesseract로 텍스트 추출
            if self.tesseract_available:
                try:
                    # 전처리된 이미지 사용
                    processed_image = self.preprocess_image(image_path)
                    tesseract_text = pytesseract.image_to_string(processed_image, config=self.tesseract_config)
                    if tesseract_text.strip():
                        all_text.append(f"Tesseract: {tesseract_text.strip()}")
                        print(f"📖 Tesseract 텍스트: {tesseract_text[:100]}...")
                except Exception as e:
                    print(f"⚠️ Tesseract 실행 실패: {e}")
            
            # 결합된 텍스트 반환
            combined_text = '\n'.join(all_text) if all_text else "텍스트를 찾을 수 없습니다"
            return combined_text
            
        except Exception as e:
            self.logger.error(f"텍스트 추출 실패: {e}")
            return "텍스트 추출 실패"
    
    async def find_form_elements(self, image_path: str) -> List[Dict[str, Any]]:
        """폼 요소 (입력 필드) 찾기"""
        try:
            form_elements = []
            
            if self.easyocr_available:
                # EasyOCR로 텍스트와 위치 정보 추출
                results = self.easyocr_reader.readtext(image_path)
                
                # 폼 관련 키워드
                form_keywords = [
                    # 한국어
                    '이름', '성', '이메일', '전화', '휴대폰', '비밀번호', '생년월일', '사용자명',
                    # 영어
                    'first', 'last', 'name', 'email', 'phone', 'mobile', 'password', 
                    'username', 'birth', 'date', 'verify', 'code'
                ]
                
                for result in results:
                    bbox, text, confidence = result
                    
                    if confidence > 0.5:  # 신뢰도 50% 이상
                        # 바운딩 박스에서 중심점 계산
                        x_coords = [point[0] for point in bbox]
                        y_coords = [point[1] for point in bbox]
                        center_x = int(sum(x_coords) / len(x_coords))
                        center_y = int(sum(y_coords) / len(y_coords))
                        
                        # 폼 관련 텍스트인지 확인
                        text_lower = text.lower()
                        is_form_element = any(keyword in text_lower for keyword in form_keywords)
                        
                        if is_form_element:
                            form_elements.append({
                                'text': text,
                                'x': center_x,
                                'y': center_y + 50,  # 입력 필드는 보통 라벨 아래에 있음
                                'confidence': confidence,
                                'bbox': bbox,
                                'type': self._classify_form_element(text)
                            })
                            print(f"📝 폼 요소 발견: {text} at ({center_x}, {center_y + 50})")
            
            # 폼 요소가 없으면 기본 위치 제공
            if not form_elements:
                print("⚠️ OCR로 폼 요소를 찾지 못함 - 기본 위치 사용")
                form_elements = [
                    {'text': 'First name', 'x': 540, 'y': 400, 'confidence': 0.8, 'type': 'name'},
                    {'text': 'Last name', 'x': 540, 'y': 500, 'confidence': 0.8, 'type': 'name'},
                    {'text': 'Username', 'x': 540, 'y': 600, 'confidence': 0.8, 'type': 'username'},
                    {'text': 'Password', 'x': 540, 'y': 700, 'confidence': 0.8, 'type': 'password'}
                ]
            
            return form_elements
            
        except Exception as e:
            self.logger.error(f"폼 요소 찾기 실패: {e}")
            return []
    
    def _classify_form_element(self, text: str) -> str:
        """텍스트 기반 폼 요소 분류"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['phone', 'mobile', '전화', '휴대폰']):
            return 'phone'
        elif any(keyword in text_lower for keyword in ['email', '이메일']):
            return 'email'
        elif any(keyword in text_lower for keyword in ['password', '비밀번호']):
            return 'password'
        elif any(keyword in text_lower for keyword in ['username', '사용자명']):
            return 'username'
        elif any(keyword in text_lower for keyword in ['name', '이름', '성']):
            return 'name'
        elif any(keyword in text_lower for keyword in ['birth', 'date', '생년월일']):
            return 'birth'
        elif any(keyword in text_lower for keyword in ['verify', 'code', '인증', '코드']):
            return 'verification'
        else:
            return 'unknown'
    
    async def find_clickable_elements(self, image_path: str) -> List[Dict[str, Any]]:
        """클릭 가능한 요소 (버튼, 링크) 찾기"""
        try:
            clickable_elements = []
            
            if self.easyocr_available:
                results = self.easyocr_reader.readtext(image_path)
                
                # 클릭 가능한 요소 키워드
                clickable_keywords = [
                    # 한국어
                    '다음', '계속', '확인', '완료', '생성', '만들기', '가입', '로그인', '전송', '인증',
                    # 영어  
                    'next', 'continue', 'confirm', 'done', 'create', 'sign', 'login', 'send', 'verify',
                    'submit', 'finish', 'accept', 'agree', 'skip'
                ]
                
                for result in results:
                    bbox, text, confidence = result
                    
                    if confidence > 0.6:  # 버튼은 더 높은 신뢰도 요구
                        # 바운딩 박스에서 중심점 계산
                        x_coords = [point[0] for point in bbox]
                        y_coords = [point[1] for point in bbox]
                        center_x = int(sum(x_coords) / len(x_coords))
                        center_y = int(sum(y_coords) / len(y_coords))
                        
                        # 클릭 가능한 텍스트인지 확인
                        text_lower = text.lower()
                        is_clickable = any(keyword in text_lower for keyword in clickable_keywords)
                        
                        if is_clickable:
                            clickable_elements.append({
                                'text': text,
                                'x': center_x,
                                'y': center_y,
                                'confidence': confidence,
                                'bbox': bbox,
                                'type': self._classify_clickable_element(text)
                            })
                            print(f"🔘 클릭 요소 발견: {text} at ({center_x}, {center_y})")
            
            return clickable_elements
            
        except Exception as e:
            self.logger.error(f"클릭 요소 찾기 실패: {e}")
            return []
    
    def _classify_clickable_element(self, text: str) -> str:
        """텍스트 기반 클릭 요소 분류"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['next', '다음']):
            return 'next'
        elif any(keyword in text_lower for keyword in ['create', 'sign', '생성', '가입']):
            return 'create'
        elif any(keyword in text_lower for keyword in ['send', '전송']):
            return 'send'
        elif any(keyword in text_lower for keyword in ['verify', '인증']):
            return 'verify'
        elif any(keyword in text_lower for keyword in ['confirm', '확인']):
            return 'confirm'
        elif any(keyword in text_lower for keyword in ['continue', '계속']):
            return 'continue'
        else:
            return 'button'
    
    async def find_phone_input_field(self, image_path: str) -> Optional[Dict[str, Any]]:
        """전화번호 입력 필드 전용 탐지"""
        try:
            print("📱 전화번호 입력 필드 전용 탐지 시작...")
            
            if self.easyocr_available:
                results = self.easyocr_reader.readtext(image_path)
                
                # 전화번호 관련 키워드 (더 구체적)
                phone_keywords = [
                    'phone', 'mobile', 'number', 'tel', '전화', '휴대폰', '번호', '핸드폰',
                    '010', '+82', 'verify', 'sms', '인증'
                ]
                
                phone_candidates = []
                
                for result in results:
                    bbox, text, confidence = result
                    
                    if confidence > 0.4:  # 낮은 신뢰도도 허용
                        text_lower = text.lower()
                        
                        # 전화번호 관련 텍스트 찾기
                        if any(keyword in text_lower for keyword in phone_keywords):
                            x_coords = [point[0] for point in bbox]
                            y_coords = [point[1] for point in bbox]
                            center_x = int(sum(x_coords) / len(x_coords))
                            center_y = int(sum(y_coords) / len(y_coords))
                            
                            phone_candidates.append({
                                'text': text,
                                'x': center_x,
                                'y': center_y + 60,  # 입력 필드는 라벨보다 아래
                                'confidence': confidence,
                                'bbox': bbox
                            })
                            print(f"📱 전화번호 관련 텍스트: {text} (신뢰도: {confidence:.2f})")
                
                # 가장 신뢰도 높은 후보 반환
                if phone_candidates:
                    best_candidate = max(phone_candidates, key=lambda x: x['confidence'])
                    print(f"✅ 전화번호 필드 선택: {best_candidate['text']} at ({best_candidate['x']}, {best_candidate['y']})")
                    return best_candidate
            
            # OCR로 찾지 못한 경우 화면 중앙 하단 영역 시도
            print("⚠️ OCR로 전화번호 필드를 찾지 못함 - 예상 위치 반환")
            return {
                'text': 'Phone Number (추정)',
                'x': 540,
                'y': 800,  # 화면 하단
                'confidence': 0.5,
                'bbox': None
            }
            
        except Exception as e:
            self.logger.error(f"전화번호 필드 탐지 실패: {e}")
            return None
    
    async def find_verification_code_field(self, image_path: str) -> Optional[Dict[str, Any]]:
        """인증 코드 입력 필드 전용 탐지"""
        try:
            print("🔢 인증 코드 입력 필드 탐지 시작...")
            
            if self.easyocr_available:
                results = self.easyocr_reader.readtext(image_path)
                
                # 인증 코드 관련 키워드
                code_keywords = [
                    'code', 'verification', 'verify', 'sms', 'otp', 
                    '코드', '인증', '확인', '번호'
                ]
                
                for result in results:
                    bbox, text, confidence = result
                    
                    if confidence > 0.4:
                        text_lower = text.lower()
                        
                        if any(keyword in text_lower for keyword in code_keywords):
                            x_coords = [point[0] for point in bbox]
                            y_coords = [point[1] for point in bbox]
                            center_x = int(sum(x_coords) / len(x_coords))
                            center_y = int(sum(y_coords) / len(y_coords))
                            
                            print(f"🔢 인증 코드 필드 발견: {text} at ({center_x}, {center_y + 50})")
                            return {
                                'text': text,
                                'x': center_x,
                                'y': center_y + 50,
                                'confidence': confidence,
                                'bbox': bbox
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"인증 코드 필드 탐지 실패: {e}")
            return None
    
    def get_ocr_status(self) -> Dict[str, bool]:
        """OCR 시스템 상태 확인"""
        return {
            'easyocr_available': self.easyocr_available,
            'tesseract_available': self.tesseract_available,
            'languages': self.languages
        }

# 테스트 함수
async def test_ocr_system():
    """OCR 시스템 테스트"""
    ocr = OCRRecognition()
    
    print("🧪 OCR 시스템 테스트")
    print(f"상태: {ocr.get_ocr_status()}")
    
    # 최신 스크린샷으로 테스트
    import glob
    screenshots = glob.glob("screenshots/screenshot_*.png")
    if screenshots:
        latest_screenshot = max(screenshots)
        print(f"📸 테스트 이미지: {latest_screenshot}")
        
        # 텍스트 추출 테스트
        text = await ocr.extract_text_from_image(latest_screenshot)
        print(f"📖 추출된 텍스트:\n{text[:200]}...")
        
        # 폼 요소 찾기 테스트
        form_elements = await ocr.find_form_elements(latest_screenshot)
        print(f"📝 발견된 폼 요소: {len(form_elements)}개")
        
        # 전화번호 필드 찾기 테스트
        phone_field = await ocr.find_phone_input_field(latest_screenshot)
        if phone_field:
            print(f"📱 전화번호 필드: {phone_field}")
    else:
        print("❌ 테스트할 스크린샷이 없습니다")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ocr_system()) 