# Google Account Creator Dockerfile
# 
# 이 Dockerfile은 Google 계정 생성 시스템을 컨테이너화하며 다음을 포함합니다:
# - Python 3.10 runtime
# - Android SDK & ADB tools
# - Chrome browser & ChromeDriver
# - OCR dependencies (EasyOCR)
# - OpenCV dependencies
# - VPN/Proxy tools
# - All project dependencies

FROM ubuntu:22.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Seoul

# Android SDK 환경 변수
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/tools

# Chrome 환경 변수
ENV CHROME_BIN=/usr/bin/google-chrome
ENV DISPLAY=:99

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 업데이트 및 기본 도구 설치
RUN apt-get update && apt-get install -y \
    # 기본 시스템 도구
    curl \
    wget \
    unzip \
    git \
    vim \
    htop \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    # Python 관련
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3.10-venv \
    # Android/ADB 관련  
    android-tools-adb \
    android-tools-fastboot \
    # OpenCV & OCR 의존성
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgtk-3-0 \
    # Chrome 의존성
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libu2f-udev \
    # VPN/네트워킹 도구
    openvpn \
    iptables \
    proxychains4 \
    # X11 관련 (Selenium용)
    xvfb \
    x11vnc \
    fluxbox \
    # 기타 유틸리티
    tzdata \
    locales \
    && rm -rf /var/lib/apt/lists/*

# 로케일 설정
RUN locale-gen en_US.UTF-8 ko_KR.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Python 심볼릭 링크 생성
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# pip 업그레이드
RUN python -m pip install --upgrade pip setuptools wheel

# Google Chrome 설치 (amd64에서만)
RUN if [ "$(dpkg --print-architecture)" = "amd64" ]; then \
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-keyring.gpg \
        && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
        && apt-get update \
        && apt-get install -y google-chrome-stable \
        && rm -rf /var/lib/apt/lists/*; \
    else \
        echo "Skipping Chrome installation on non-amd64 architecture"; \
    fi

# ChromeDriver 설치 (Chrome이 설치된 경우에만)
RUN if [ "$(dpkg --print-architecture)" = "amd64" ] && command -v google-chrome >/dev/null 2>&1; then \
        CHROME_VERSION=$(google-chrome --version | grep -oP '\d+\.\d+\.\d+') \
        && DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION%%.*}") \
        && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip" \
        && unzip /tmp/chromedriver.zip -d /tmp/ \
        && mv /tmp/chromedriver /usr/local/bin/chromedriver \
        && chmod +x /usr/local/bin/chromedriver \
        && rm /tmp/chromedriver.zip; \
    else \
        echo "Skipping ChromeDriver installation (Chrome not available)"; \
    fi

# Android SDK 설치 (경량화 버전)
RUN mkdir -p $ANDROID_HOME \
    && wget -O /tmp/platform-tools.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip \
    && unzip /tmp/platform-tools.zip -d $ANDROID_HOME \
    && rm /tmp/platform-tools.zip \
    && chmod +x $ANDROID_HOME/platform-tools/*

# 프로젝트 디렉토리 구조 생성
RUN mkdir -p /app/core \
    && mkdir -p /app/scripts \
    && mkdir -p /app/config \
    && mkdir -p /app/logs \
    && mkdir -p /app/data \
    && mkdir -p /app/screenshots \
    && mkdir -p /app/dashboard \
    && mkdir -p /app/workers \
    && mkdir -p /app/tests \
    && mkdir -p /app/docs \
    && mkdir -p /app/profiling_results

# 먼저 requirements.txt 복사 (Docker layer caching 최적화)
COPY requirements.txt /app/

# Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# EasyOCR 모델 미리 다운로드 (빌드 시간 단축)
RUN python -c "import easyocr; reader = easyocr.Reader(['en', 'ko'])" || echo "EasyOCR models will be downloaded on first run"

# 프로젝트 파일 복사
COPY . /app/

# 실행 권한 설정
RUN find /app -name "*.py" -exec chmod +x {} \; \
    && find /app -name "*.sh" -exec chmod +x {} \;

# 설정 파일 권한 설정
RUN chmod 600 /app/.taskmasterconfig || true \
    && chmod 755 /app/scripts/ \
    && chmod 755 /app/core/

# ADB 연결을 위한 udev 규칙 (선택사항)
RUN mkdir -p /etc/udev/rules.d/

# 포트 노출
EXPOSE 8080 5555 5037

# 헬스체크 스크립트 생성
RUN echo '#!/bin/bash\n\
# 헬스체크 스크립트\n\
python -c "import sys; sys.exit(0)" && \\\n\
adb version > /dev/null && \\\n\
google-chrome --version > /dev/null && \\\n\
echo "All dependencies OK"' > /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD /app/healthcheck.sh

# 엔트리포인트 스크립트 생성
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# X11 가상 디스플레이 시작 (Selenium용)\n\
if [ -z "$DISPLAY" ]; then\n\
    export DISPLAY=:99\n\
    Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &\n\
    echo "Started Xvfb on display :99"\n\
fi\n\
\n\
# ADB 서버 시작\n\
adb start-server || echo "ADB start failed, continuing..."\n\
\n\
# Python 경로 확인\n\
export PYTHONPATH="/app:$PYTHONPATH"\n\
\n\
# 로그 디렉토리 확인\n\
mkdir -p /app/logs /app/screenshots /app/data\n\
\n\
# 설정 파일 확인\n\
if [ ! -f "/app/.taskmasterconfig" ]; then\n\
    echo "Warning: .taskmasterconfig not found"\n\
fi\n\
\n\
echo "Google Account Creator starting..."\n\
echo "Environment: $(python --version)"\n\
echo "ADB version: $(adb version | head -1)"\n\
echo "Chrome version: $(google-chrome --version)"\n\
\n\
# 전달된 명령 실행\n\
exec "$@"' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# 기본 환경 변수 파일 생성
RUN echo '# Google Account Creator Environment Variables\n\
# 이 파일을 복사하여 .env로 사용하세요\n\
\n\
# 기본 설정\n\
LOG_LEVEL=INFO\n\
DEBUG=false\n\
ENVIRONMENT=production\n\
\n\
# 디바이스 설정\n\
DEFAULT_DEVICE_TIMEOUT=30\n\
MAX_DEVICES=5\n\
\n\
# 계정 생성 설정\n\
ACCOUNT_CREATION_TIMEOUT=300\n\
MAX_RETRY_ATTEMPTS=3\n\
\n\
# 스크린샷 설정\n\
SCREENSHOTS_ENABLED=true\n\
SCREENSHOT_DIR=/app/screenshots\n\
\n\
# 데이터베이스 (SQLite 기본)\n\
DATABASE_URL=sqlite:///app/data/accounts.db\n\
\n\
# API 키들 (실제 값으로 교체 필요)\n\
# TWILIO_ACCOUNT_SID=your_twilio_sid\n\
# TWILIO_AUTH_TOKEN=your_twilio_token\n\
# SMS_API_KEY=your_sms_api_key\n\
\n\
# VPN 설정\n\
# VPN_ENABLED=false\n\
# VPN_CONFIG_PATH=/app/config/vpn\n\
\n\
# 프록시 설정\n\
# PROXY_ENABLED=false\n\
# PROXY_HOST=localhost\n\
# PROXY_PORT=8080\n\
\n\
# 웹 대시보드\n\
WEB_PORT=8080\n\
WEB_HOST=0.0.0.0' > /app/.env.example

# 볼륨 마운트 포인트
VOLUME ["/app/data", "/app/logs", "/app/screenshots", "/app/config"]

# 엔트리포인트 설정
ENTRYPOINT ["/app/entrypoint.sh"]

# 기본 명령
CMD ["python", "main.py"]

# 라벨 추가 (메타데이터)
LABEL maintainer="Google Account Creator Team"
LABEL version="1.0.0"
LABEL description="Automated Google Account Creation System"
LABEL org.opencontainers.image.source="https://github.com/your-repo/google-account-creator"
LABEL org.opencontainers.image.documentation="https://github.com/your-repo/google-account-creator/docs"
LABEL org.opencontainers.image.licenses="MIT" 