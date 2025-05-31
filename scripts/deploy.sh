#!/bin/bash

# Google Account Creator Deployment Script
#
# 이 스크립트는 Google Account Creator의 배포를 자동화합니다.
# 개발, 스테이징, 프로덕션 환경을 지원합니다.
#
# Usage:
#   ./scripts/deploy.sh [environment] [options]
#
# Environments:
#   dev         - 개발 환경 배포
#   staging     - 스테이징 환경 배포
#   production  - 프로덕션 환경 배포
#
# Options:
#   --build-only    - 빌드만 수행
#   --no-backup     - 백업 생성 안함
#   --force         - 강제 배포
#   --rollback      - 이전 버전으로 롤백

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
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

log_success() {
    echo -e "${CYAN}[SUCCESS]${NC} $1"
}

# 프로젝트 설정
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="google-account-creator"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$PROJECT_ROOT/backups"

# 기본 설정
ENVIRONMENT=""
BUILD_ONLY=false
NO_BACKUP=false
FORCE_DEPLOY=false
ROLLBACK=false

# 환경별 설정
get_compose_files() {
    case "$1" in
        dev)
            echo "docker-compose.yml:docker-compose.dev.yml"
            ;;
        staging)
            echo "docker-compose.yml:docker-compose.staging.yml"
            ;;
        production)
            echo "docker-compose.yml:docker-compose.prod.yml"
            ;;
        *)
            echo "docker-compose.yml"
            ;;
    esac
}

# 파라미터 파싱
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            dev|staging|production)
                ENVIRONMENT="$1"
                shift
                ;;
            --build-only)
                BUILD_ONLY=true
                shift
                ;;
            --no-backup)
                NO_BACKUP=true
                shift
                ;;
            --force)
                FORCE_DEPLOY=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                show_help
                exit 1
                ;;
        esac
    done

    if [[ -z "$ENVIRONMENT" ]]; then
        log_error "환경을 지정해주세요 (dev, staging, production)"
        show_help
        exit 1
    fi
}

# 도움말 표시
show_help() {
    echo "Google Account Creator Deployment Script"
    echo ""
    echo "Usage: $0 [environment] [options]"
    echo ""
    echo "Environments:"
    echo "  dev         - 개발 환경 배포"
    echo "  staging     - 스테이징 환경 배포"
    echo "  production  - 프로덕션 환경 배포"
    echo ""
    echo "Options:"
    echo "  --build-only    - 빌드만 수행하고 배포하지 않음"
    echo "  --no-backup     - 백업을 생성하지 않음"
    echo "  --force         - 확인 없이 강제 배포"
    echo "  --rollback      - 이전 버전으로 롤백"
    echo "  --help, -h      - 이 도움말 표시"
    echo ""
    echo "Examples:"
    echo "  $0 dev                    # 개발 환경 배포"
    echo "  $0 production --force     # 프로덕션 강제 배포"
    echo "  $0 staging --build-only   # 스테이징 빌드만"
    echo "  $0 production --rollback  # 프로덕션 롤백"
}

# 사전 요구사항 확인
check_prerequisites() {
    log_info "사전 요구사항을 확인합니다..."

    # Docker 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다."
        exit 1
    fi

    # Git 확인
    if ! command -v git &> /dev/null; then
        log_error "Git이 설치되지 않았습니다."
        exit 1
    fi

    # 프로젝트 디렉토리 확인
    if [[ ! -f "$PROJECT_ROOT/Dockerfile" ]]; then
        log_error "Dockerfile을 찾을 수 없습니다."
        exit 1
    fi

    # 환경 설정 파일 확인
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        log_warn ".env 파일이 없습니다. 기본 설정을 사용합니다."
    fi

    log_success "사전 요구사항 확인 완료"
}

# Git 상태 확인
check_git_status() {
    log_info "Git 상태를 확인합니다..."

    cd "$PROJECT_ROOT"

    # 변경사항 확인
    if [[ -n $(git status --porcelain) ]] && [[ "$FORCE_DEPLOY" != true ]]; then
        log_warn "커밋되지 않은 변경사항이 있습니다:"
        git status --short
        
        if [[ "$ENVIRONMENT" == "production" ]]; then
            log_error "프로덕션 배포 시 모든 변경사항이 커밋되어야 합니다."
            exit 1
        fi
        
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "배포가 취소되었습니다."
            exit 0
        fi
    fi

    # 현재 브랜치 확인
    CURRENT_BRANCH=$(git branch --show-current)
    log_info "현재 브랜치: $CURRENT_BRANCH"

    # 프로덕션 배포 시 main 브랜치 확인
    if [[ "$ENVIRONMENT" == "production" ]] && [[ "$CURRENT_BRANCH" != "main" ]] && [[ "$FORCE_DEPLOY" != true ]]; then
        log_error "프로덕션 배포는 main 브랜치에서만 가능합니다."
        exit 1
    fi

    # 최신 커밋 정보
    COMMIT_HASH=$(git rev-parse --short HEAD)
    COMMIT_MESSAGE=$(git log -1 --pretty=format:"%s")
    log_info "배포할 커밋: $COMMIT_HASH - $COMMIT_MESSAGE"
}

# 백업 생성
create_backup() {
    if [[ "$NO_BACKUP" == true ]]; then
        log_info "백업 생성을 건너뜁니다."
        return
    fi

    log_info "백업을 생성합니다..."

    mkdir -p "$BACKUP_DIR"

    # 현재 실행 중인 컨테이너 정보 백업
    if docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -q "$PROJECT_NAME"; then
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep "$PROJECT_NAME" > "$BACKUP_DIR/containers_${TIMESTAMP}.txt"
        log_debug "컨테이너 정보 백업 완료"
    fi

    # 데이터 백업 (볼륨)
    if docker volume ls | grep -q "${PROJECT_NAME}"; then
        log_info "데이터 볼륨을 백업합니다..."
        docker run --rm \
            -v "${PROJECT_NAME}_data:/data" \
            -v "$BACKUP_DIR:/backup" \
            alpine tar czf "/backup/data_${TIMESTAMP}.tar.gz" -C /data .
        log_debug "데이터 백업 완료"
    fi

    # 설정 파일 백업
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        cp "$PROJECT_ROOT/.env" "$BACKUP_DIR/env_${TIMESTAMP}.backup"
        log_debug "환경 설정 백업 완료"
    fi

    log_success "백업 생성 완료: $BACKUP_DIR"
}

# 이미지 빌드
build_image() {
    log_info "Docker 이미지를 빌드합니다..."

    cd "$PROJECT_ROOT"

    # 빌드 태그 설정
    BUILD_TAG="${PROJECT_NAME}:${ENVIRONMENT}-${TIMESTAMP}"
    LATEST_TAG="${PROJECT_NAME}:${ENVIRONMENT}-latest"

    # 빌드 실행
    docker build \
        --build-arg ENVIRONMENT="$ENVIRONMENT" \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
        -t "$BUILD_TAG" \
        -t "$LATEST_TAG" \
        .

    log_success "이미지 빌드 완료: $BUILD_TAG"

    # 빌드 정보 저장
    echo "$BUILD_TAG" > "$PROJECT_ROOT/.last_build"
}

# 헬스체크
health_check() {
    local max_attempts=30
    local attempt=1

    log_info "서비스 헬스체크를 시작합니다..."

    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
            log_success "헬스체크 통과 (시도 $attempt/$max_attempts)"
            return 0
        fi

        log_debug "헬스체크 대기 중... (시도 $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    log_error "헬스체크 실패"
    return 1
}

# 배포 실행
deploy() {
    log_info "$ENVIRONMENT 환경에 배포를 시작합니다..."

    cd "$PROJECT_ROOT"

    # Compose 파일 설정
    COMPOSE_FILES=$(get_compose_files "$ENVIRONMENT")
    IFS=':' read -ra FILES <<< "$COMPOSE_FILES"
    
    COMPOSE_CMD="docker-compose"
    for file in "${FILES[@]}"; do
        if [[ -f "$file" ]]; then
            COMPOSE_CMD="$COMPOSE_CMD -f $file"
        fi
    done

    # 기존 서비스 중지
    log_info "기존 서비스를 중지합니다..."
    $COMPOSE_CMD down

    # 새 서비스 시작
    log_info "새 서비스를 시작합니다..."
    $COMPOSE_CMD up -d

    # 헬스체크
    if ! health_check; then
        log_error "배포 실패: 헬스체크 통과하지 못함"
        
        # 롤백 제안
        read -p "이전 버전으로 롤백하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback_deployment
        fi
        exit 1
    fi

    log_success "$ENVIRONMENT 환경 배포 완료"
}

# 롤백
rollback_deployment() {
    log_info "이전 버전으로 롤백합니다..."

    cd "$PROJECT_ROOT"

    # 최신 백업 찾기
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/data_*.tar.gz 2>/dev/null | head -1)
    
    if [[ -n "$LATEST_BACKUP" ]]; then
        log_info "백업에서 데이터를 복원합니다: $LATEST_BACKUP"
        
        # 데이터 복원
        docker run --rm \
            -v "${PROJECT_NAME}_data:/data" \
            -v "$BACKUP_DIR:/backup" \
            alpine sh -c "cd /data && tar xzf /backup/$(basename $LATEST_BACKUP)"
    fi

    # 이전 이미지로 복원 (태그 기반)
    PREVIOUS_TAG="${PROJECT_NAME}:${ENVIRONMENT}-previous"
    if docker images | grep -q "$PREVIOUS_TAG"; then
        docker tag "$PREVIOUS_TAG" "${PROJECT_NAME}:${ENVIRONMENT}-latest"
        log_info "이전 이미지로 복원 완료"
    fi

    # 서비스 재시작
    COMPOSE_FILES=$(get_compose_files "$ENVIRONMENT")
    IFS=':' read -ra FILES <<< "$COMPOSE_FILES"
    
    COMPOSE_CMD="docker-compose"
    for file in "${FILES[@]}"; do
        if [[ -f "$file" ]]; then
            COMPOSE_CMD="$COMPOSE_CMD -f $file"
        fi
    done

    $COMPOSE_CMD down
    $COMPOSE_CMD up -d

    if health_check; then
        log_success "롤백 완료"
    else
        log_error "롤백 실패"
        exit 1
    fi
}

# 배포 후 정리
post_deploy_cleanup() {
    log_info "배포 후 정리를 수행합니다..."

    # 오래된 이미지 정리
    docker image prune -f

    # 오래된 백업 정리 (30일 이상)
    if [[ -d "$BACKUP_DIR" ]]; then
        find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
        find "$BACKUP_DIR" -name "*.backup" -mtime +30 -delete
        log_debug "오래된 백업 파일 정리 완료"
    fi

    log_success "정리 완료"
}

# 배포 상태 확인
check_deployment_status() {
    log_info "배포 상태를 확인합니다..."

    cd "$PROJECT_ROOT"

    # 컨테이너 상태
    echo ""
    echo "=== 컨테이너 상태 ==="
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep "$PROJECT_NAME" || echo "실행 중인 컨테이너가 없습니다."

    # 서비스 로그 (최근 10줄)
    echo ""
    echo "=== 최근 로그 ==="
    docker-compose logs --tail=10 "$PROJECT_NAME" 2>/dev/null || echo "로그를 가져올 수 없습니다."

    # 리소스 사용량
    echo ""
    echo "=== 리소스 사용량 ==="
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep "$PROJECT_NAME" || echo "리소스 정보를 가져올 수 없습니다."

    echo ""
}

# 메인 실행 함수
main() {
    echo "🚀 Google Account Creator 배포 스크립트"
    echo "========================================"
    echo ""

    parse_arguments "$@"

    log_info "배포 환경: $ENVIRONMENT"
    log_info "타임스탬프: $TIMESTAMP"
    echo ""

    # 롤백 모드
    if [[ "$ROLLBACK" == true ]]; then
        rollback_deployment
        exit 0
    fi

    # 사전 확인
    check_prerequisites
    check_git_status

    # 프로덕션 배포 확인
    if [[ "$ENVIRONMENT" == "production" ]] && [[ "$FORCE_DEPLOY" != true ]]; then
        echo ""
        log_warn "⚠️  프로덕션 환경에 배포하려고 합니다!"
        echo "커밋: $COMMIT_HASH - $COMMIT_MESSAGE"
        echo ""
        read -p "계속 진행하시겠습니까? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "배포가 취소되었습니다."
            exit 0
        fi
    fi

    # 백업 생성
    create_backup

    # 이미지 빌드
    build_image

    # 빌드만 수행하는 경우
    if [[ "$BUILD_ONLY" == true ]]; then
        log_success "빌드 완료. 배포는 수행하지 않습니다."
        exit 0
    fi

    # 배포 실행
    deploy

    # 배포 후 정리
    post_deploy_cleanup

    # 상태 확인
    check_deployment_status

    echo ""
    log_success "🎉 배포가 성공적으로 완료되었습니다!"
    echo ""
    echo "📊 대시보드: http://localhost:8080"
    echo "📋 상태 확인: ./scripts/deploy.sh $ENVIRONMENT --status"
    echo "🔄 롤백: ./scripts/deploy.sh $ENVIRONMENT --rollback"
    echo ""
}

# 스크립트 실행
main "$@" 