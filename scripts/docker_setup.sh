#!/bin/bash

# Google Account Creator Docker Setup Script
# 
# 이 스크립트는 Docker 환경에서 Google Account Creator를 쉽게 설정하고 실행합니다.
# 
# Usage:
#   ./scripts/docker_setup.sh [command] [options]
#
# Commands:
#   build     - Docker 이미지 빌드
#   run       - 컨테이너 실행
#   dev       - 개발 모드로 실행
#   stop      - 컨테이너 중지
#   logs      - 로그 확인
#   clean     - 정리
#   status    - 상태 확인

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# 프로젝트 루트 디렉토리
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 기본 설정
CONTAINER_NAME="google-account-creator"
IMAGE_NAME="google-account-creator:latest"
COMPOSE_FILE="docker-compose.yml"
COMPOSE_DEV_FILE="docker-compose.override.yml"

# 함수들

# Docker 설치 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        log_info "Docker 설치: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        log_info "Docker Compose 설치: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Docker daemon 확인
    if ! docker info &> /dev/null; then
        log_error "Docker daemon이 실행 중이지 않습니다."
        log_info "Docker를 시작하세요: sudo systemctl start docker"
        exit 1
    fi

    log_info "Docker 환경 확인 완료"
}

# 환경 설정 파일 생성
setup_env() {
    if [ ! -f ".env" ]; then
        log_info "환경 설정 파일(.env)을 생성합니다..."
        cp .env.example .env 2>/dev/null || {
            log_warn ".env.example 파일을 찾을 수 없습니다. 기본 .env 파일을 생성합니다."
            cat > .env << EOF
# Google Account Creator Environment Variables
LOG_LEVEL=INFO
DEBUG=false
ENVIRONMENT=production
WEB_PORT=8080
WEB_HOST=0.0.0.0
MAX_DEVICES=5
SCREENSHOTS_ENABLED=true

# Database
REDIS_PASSWORD=defaultpass
POSTGRES_DB=google_accounts
POSTGRES_USER=postgres
POSTGRES_PASSWORD=defaultpass

# API Keys (설정 필요)
# TWILIO_ACCOUNT_SID=your_sid_here
# TWILIO_AUTH_TOKEN=your_token_here
EOF
        }
        log_info ".env 파일이 생성되었습니다. 필요한 설정을 수정해주세요."
    else
        log_info "기존 .env 파일을 사용합니다."
    fi
}

# 필요한 디렉토리 생성
create_directories() {
    log_info "필요한 디렉토리를 생성합니다..."
    mkdir -p data logs screenshots config
    mkdir -p sql monitoring
    
    # 권한 설정
    chmod 755 data logs screenshots config
    
    log_info "디렉토리 생성 완료"
}

# Docker 이미지 빌드
build_image() {
    log_info "Docker 이미지를 빌드합니다..."
    
    # 캐시 사용 여부
    if [ "$1" = "--no-cache" ]; then
        docker build --no-cache -t "$IMAGE_NAME" .
    else
        docker build -t "$IMAGE_NAME" .
    fi
    
    log_info "Docker 이미지 빌드 완료: $IMAGE_NAME"
}

# 컨테이너 실행
run_container() {
    log_info "Docker 컨테이너를 실행합니다..."
    
    # 기존 컨테이너 중지 및 제거
    docker-compose down 2>/dev/null || true
    
    # 새 컨테이너 실행
    docker-compose up -d
    
    # 시작 대기
    log_info "컨테이너 시작 대기 중..."
    sleep 10
    
    # 상태 확인
    if docker-compose ps | grep -q "Up"; then
        log_info "컨테이너가 성공적으로 실행되었습니다!"
        log_info "웹 대시보드: http://localhost:8080"
        show_status
    else
        log_error "컨테이너 실행에 실패했습니다."
        docker-compose logs
        exit 1
    fi
}

# 개발 모드 실행
run_dev() {
    log_info "개발 모드로 실행합니다..."
    
    # 개발용 환경 변수 설정
    export DEBUG=true
    export LOG_LEVEL=DEBUG
    export ENVIRONMENT=development
    
    # docker-compose.override.yml 사용
    docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
    
    log_info "개발 모드 실행 완료"
    log_info "웹 대시보드: http://localhost:8080"
    log_info "디버깅 포트: 5678"
}

# 컨테이너 중지
stop_container() {
    log_info "컨테이너를 중지합니다..."
    docker-compose down
    log_info "컨테이너 중지 완료"
}

# 로그 확인
show_logs() {
    local service="${1:-google-account-creator}"
    log_info "$service 서비스의 로그를 확인합니다..."
    docker-compose logs -f "$service"
}

# 상태 확인
show_status() {
    log_info "컨테이너 상태:"
    docker-compose ps
    
    echo ""
    log_info "리소스 사용량:"
    docker stats --no-stream $(docker-compose ps -q 2>/dev/null) 2>/dev/null || echo "실행 중인 컨테이너가 없습니다."
    
    echo ""
    log_info "네트워크 포트:"
    echo "- 웹 대시보드: http://localhost:8080"
    echo "- Redis: localhost:6379"
    echo "- PostgreSQL: localhost:5432"
    echo "- Prometheus: http://localhost:9090"
}

# 정리
cleanup() {
    log_info "Docker 리소스를 정리합니다..."
    
    # 컨테이너 중지 및 제거
    docker-compose down -v 2>/dev/null || true
    
    # 이미지 제거 (선택사항)
    read -p "Docker 이미지도 삭제하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi "$IMAGE_NAME" 2>/dev/null || true
        log_info "이미지 삭제 완료"
    fi
    
    # 사용하지 않는 볼륨 정리
    docker volume prune -f
    
    log_info "정리 완료"
}

# 헬프 메시지
show_help() {
    echo "Google Account Creator Docker Setup Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  build [--no-cache]  - Docker 이미지 빌드"
    echo "  run                 - 프로덕션 모드로 실행"
    echo "  dev                 - 개발 모드로 실행"
    echo "  stop                - 컨테이너 중지"
    echo "  logs [service]      - 로그 확인"
    echo "  status              - 상태 확인"
    echo "  clean               - 리소스 정리"
    echo "  help                - 도움말 표시"
    echo ""
    echo "Examples:"
    echo "  $0 build           # 이미지 빌드"
    echo "  $0 run             # 실행"
    echo "  $0 logs            # 모든 로그"
    echo "  $0 logs redis      # Redis 로그만"
    echo "  $0 dev             # 개발 모드"
    echo ""
}

# 메인 실행
main() {
    local command="${1:-help}"
    
    case "$command" in
        "build")
            check_docker
            setup_env
            create_directories
            build_image "$2"
            ;;
        "run")
            check_docker
            setup_env
            create_directories
            run_container
            ;;
        "dev")
            check_docker
            setup_env
            create_directories
            run_dev
            ;;
        "stop")
            check_docker
            stop_container
            ;;
        "logs")
            check_docker
            show_logs "$2"
            ;;
        "status")
            check_docker
            show_status
            ;;
        "clean")
            check_docker
            cleanup
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            log_error "알 수 없는 명령: $command"
            show_help
            exit 1
            ;;
    esac
}

# 스크립트 실행
main "$@" 