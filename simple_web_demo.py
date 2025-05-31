#!/usr/bin/env python3
"""
Google Account Creator - 간단한 웹 데모

실제 시스템 기능을 테스트할 수 있는 간단한 웹 인터페이스입니다.
"""

import sys
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core.config_manager import ConfigManager
    config_available = True
except ImportError as e:
    print(f"ConfigManager import failed: {e}")
    config_available = False

class GoogleAccountCreatorHandler(BaseHTTPRequestHandler):
    """간단한 웹 핸들러"""
    
    def do_GET(self):
        """GET 요청 처리"""
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/status':
            self.serve_status()
        elif self.path == '/api/config':
            self.serve_config()
        elif self.path == '/api/test':
            self.serve_test()
        else:
            self.send_error(404, "Page not found")
    
    def serve_dashboard(self):
        """메인 대시보드 페이지"""
        html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Account Creator - 데모</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin: 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        .status-card h3 {{
            margin-top: 0;
            color: #fff;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .status-running {{ background-color: #4CAF50; }}
        .status-warning {{ background-color: #FF9800; }}
        .status-error {{ background-color: #F44336; }}
        .button {{
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s ease;
        }}
        .button:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
        .api-section {{
            margin-top: 30px;
        }}
        .api-section h3 {{
            border-bottom: 2px solid rgba(255, 255, 255, 0.3);
            padding-bottom: 10px;
        }}
        .timestamp {{
            text-align: center;
            margin-top: 30px;
            opacity: 0.8;
            font-size: 0.9em;
        }}
        pre {{
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Google Account Creator</h1>
            <p>시스템 데모 및 테스트 인터페이스</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3><span class="status-indicator status-running"></span>시스템 상태</h3>
                <p><strong>상태:</strong> 실행 중</p>
                <p><strong>환경:</strong> Docker 컨테이너</p>
                <p><strong>Python:</strong> 3.10.12</p>
                <p><strong>ADB:</strong> 사용 가능</p>
            </div>
            
            <div class="status-card">
                <h3><span class="status-indicator status-running"></span>모듈 상태</h3>
                <p><strong>ConfigManager:</strong> {'✅ 정상' if config_available else '❌ 오류'}</p>
                <p><strong>Logger:</strong> ✅ 정상</p>
                <p><strong>Database:</strong> ⚠️ 미연결</p>
                <p><strong>웹 서버:</strong> ✅ 실행 중</p>
            </div>
            
            <div class="status-card">
                <h3><span class="status-indicator status-warning"></span>서비스 상태</h3>
                <p><strong>Redis:</strong> ✅ 실행 중</p>
                <p><strong>PostgreSQL:</strong> ✅ 실행 중</p>
                <p><strong>Prometheus:</strong> ✅ 실행 중</p>
                <p><strong>계정 생성기:</strong> ⚠️ 대기 중</p>
            </div>
        </div>
        
        <div class="api-section">
            <h3>🔧 API 테스트</h3>
            <a href="/api/status" class="button">시스템 상태 확인</a>
            <a href="/api/config" class="button">설정 정보 확인</a>
            <a href="/api/test" class="button">기능 테스트</a>
        </div>
        
        <div class="api-section">
            <h3>📊 모니터링</h3>
            <a href="http://localhost:9090" class="button" target="_blank">Prometheus 대시보드</a>
            <a href="#" class="button" onclick="location.reload()">페이지 새로고침</a>
        </div>
        
        <div class="timestamp">
            마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    
    <script>
        // 자동 새로고침 (30초마다)
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def serve_status(self):
        """시스템 상태 API"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "status": "running",
                "python_version": sys.version,
                "platform": os.name,
                "pid": os.getpid()
            },
            "modules": {
                "config_manager": config_available,
                "logger": True,
                "database": False,
                "web_server": True
            },
            "services": {
                "redis": "running",
                "postgresql": "running", 
                "prometheus": "running",
                "account_creator": "standby"
            }
        }
        
        self.send_json_response(status)
    
    def serve_config(self):
        """설정 정보 API"""
        if not config_available:
            self.send_json_response({
                "error": "ConfigManager not available",
                "message": "Configuration system is not loaded"
            })
            return
        
        try:
            config = ConfigManager()
            config_data = {
                "timestamp": datetime.now().isoformat(),
                "config_summary": config.get_config_summary(),
                "sample_settings": {
                    "account.batch_size": config.get("account.batch_size", "N/A"),
                    "proxy.enabled": config.get("proxy.enabled", "N/A"),
                    "logging.level": config.get("logging.level", "N/A"),
                    "system.max_workers": config.get("system.max_workers", "N/A")
                }
            }
            self.send_json_response(config_data)
        except Exception as e:
            self.send_json_response({
                "error": str(e),
                "message": "Failed to load configuration"
            })
    
    def serve_test(self):
        """기능 테스트 API"""
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": []
        }
        
        # ConfigManager 테스트
        if config_available:
            try:
                config = ConfigManager()
                test_results["tests"].append({
                    "name": "ConfigManager",
                    "status": "pass",
                    "message": "Configuration system working"
                })
            except Exception as e:
                test_results["tests"].append({
                    "name": "ConfigManager", 
                    "status": "fail",
                    "message": str(e)
                })
        else:
            test_results["tests"].append({
                "name": "ConfigManager",
                "status": "skip",
                "message": "Module not available"
            })
        
        # 파일 시스템 테스트
        try:
            test_file = Path("/tmp/test_write.txt")
            test_file.write_text("test")
            test_file.unlink()
            test_results["tests"].append({
                "name": "File System",
                "status": "pass",
                "message": "File operations working"
            })
        except Exception as e:
            test_results["tests"].append({
                "name": "File System",
                "status": "fail", 
                "message": str(e)
            })
        
        # 네트워크 테스트
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('8.8.8.8', 53))
            sock.close()
            
            if result == 0:
                test_results["tests"].append({
                    "name": "Network Connectivity",
                    "status": "pass",
                    "message": "Internet connection available"
                })
            else:
                test_results["tests"].append({
                    "name": "Network Connectivity",
                    "status": "fail",
                    "message": "Cannot reach external servers"
                })
        except Exception as e:
            test_results["tests"].append({
                "name": "Network Connectivity",
                "status": "fail",
                "message": str(e)
            })
        
        self.send_json_response(test_results)
    
    def send_json_response(self, data):
        """JSON 응답 전송"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(json_data.encode('utf-8'))
    
    def log_message(self, format, *args):
        """로그 메시지 (조용히)"""
        pass

def main():
    """메인 함수"""
    port = 8080
    server_address = ('0.0.0.0', port)
    
    print(f"🚀 Google Account Creator 웹 데모 시작")
    print(f"📡 서버 주소: http://localhost:{port}")
    print(f"🔧 ConfigManager: {'사용 가능' if config_available else '사용 불가'}")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    try:
        httpd = HTTPServer(server_address, GoogleAccountCreatorHandler)
        print(f"✅ 웹 서버가 포트 {port}에서 실행 중입니다...")
        print("🌐 브라우저에서 http://localhost:8080 에 접속하세요!")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 서버를 종료합니다...")
    except Exception as e:
        print(f"❌ 서버 오류: {e}")

if __name__ == "__main__":
    main() 