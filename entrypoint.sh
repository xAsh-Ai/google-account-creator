#!/bin/bash
set -e

# X11 가상 디스플레이 시작 (Selenium용)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:99
    Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &
    echo "Started Xvfb on display :99"
fi

# ADB 서버 시작
adb start-server || echo "ADB start failed, continuing..."

# Python 경로 확인
export PYTHONPATH="/app:$PYTHONPATH"

# 로그 디렉토리 확인
mkdir -p /app/logs /app/screenshots /app/data

# 설정 파일 확인
if [ ! -f "/app/.taskmasterconfig" ]; then
    echo "Warning: .taskmasterconfig not found"
fi

echo "Google Account Creator starting..."
echo "Environment: $(python --version)"
echo "ADB version: $(adb version | head -1)"

# Chrome 버전 확인 (설치되어 있는 경우에만)
if command -v google-chrome >/dev/null 2>&1; then
    echo "Chrome version: $(google-chrome --version)"
else
    echo "Chrome not available (may be running on non-amd64 architecture)"
fi

# 전달된 명령 실행
exec "$@" 