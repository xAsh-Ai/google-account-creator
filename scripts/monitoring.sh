#!/bin/bash

# Google Account Creator Monitoring Script
#
# 이 스크립트는 Google Account Creator 시스템의 상태를 모니터링하고
# 문제 발생 시 알림을 전송합니다.
#
# Usage:
#   ./scripts/monitoring.sh [command] [options]
#
# Commands:
#   status      - 시스템 상태 확인
#   health      - 헬스체크 실행
#   metrics     - 성능 메트릭 수집
#   alerts      - 알림 설정 확인
#   watch       - 실시간 모니터링
#   report      - 상태 보고서 생성

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
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
MONITORING_DIR="$PROJECT_ROOT/monitoring"
ALERTS_CONFIG="$MONITORING_DIR/alerts.json"

# 임계값 설정
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
RESPONSE_TIME_THRESHOLD=5000  # ms
ERROR_RATE_THRESHOLD=5        # %

# 알림 설정
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
EMAIL_RECIPIENTS="${EMAIL_RECIPIENTS:-}"

# 디렉토리 생성
mkdir -p "$MONITORING_DIR"

# 시스템 상태 확인
check_system_status() {
    log_info "시스템 상태를 확인합니다..."

    local status_file="$MONITORING_DIR/system_status.json"
    local overall_status="healthy"

    # JSON 시작
    echo "{" > "$status_file"
    echo "  \"timestamp\": \"$TIMESTAMP\"," >> "$status_file"
    echo "  \"system\": {" >> "$status_file"

    # CPU 사용률
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    echo "    \"cpu_usage\": $cpu_usage," >> "$status_file"
    
    if (( $(echo "$cpu_usage > $CPU_THRESHOLD" | bc -l) )); then
        log_warn "CPU 사용률이 높습니다: ${cpu_usage}%"
        overall_status="warning"
    fi

    # 메모리 사용률
    local memory_info=$(free | grep Mem)
    local total_mem=$(echo $memory_info | awk '{print $2}')
    local used_mem=$(echo $memory_info | awk '{print $3}')
    local memory_usage=$(echo "scale=2; $used_mem * 100 / $total_mem" | bc)
    echo "    \"memory_usage\": $memory_usage," >> "$status_file"
    
    if (( $(echo "$memory_usage > $MEMORY_THRESHOLD" | bc -l) )); then
        log_warn "메모리 사용률이 높습니다: ${memory_usage}%"
        overall_status="warning"
    fi

    # 디스크 사용률
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    echo "    \"disk_usage\": $disk_usage," >> "$status_file"
    
    if [ "$disk_usage" -gt "$DISK_THRESHOLD" ]; then
        log_warn "디스크 사용률이 높습니다: ${disk_usage}%"
        overall_status="warning"
    fi

    # 로드 평균
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    echo "    \"load_average\": $load_avg" >> "$status_file"

    echo "  }," >> "$status_file"

    # Docker 컨테이너 상태
    echo "  \"containers\": [" >> "$status_file"
    
    local container_count=0
    local healthy_containers=0
    
    if command -v docker &> /dev/null; then
        while IFS= read -r container; do
            if [ -n "$container" ]; then
                local name=$(echo "$container" | awk '{print $1}')
                local status=$(echo "$container" | awk '{print $2}')
                local health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "unknown")
                
                if [ $container_count -gt 0 ]; then
                    echo "    ," >> "$status_file"
                fi
                
                echo "    {" >> "$status_file"
                echo "      \"name\": \"$name\"," >> "$status_file"
                echo "      \"status\": \"$status\"," >> "$status_file"
                echo "      \"health\": \"$health\"" >> "$status_file"
                echo "    }" >> "$status_file"
                
                container_count=$((container_count + 1))
                
                if [[ "$status" == "Up"* ]] && [[ "$health" == "healthy" || "$health" == "unknown" ]]; then
                    healthy_containers=$((healthy_containers + 1))
                fi
            fi
        done < <(docker ps --format "{{.Names}} {{.Status}}" | grep "$PROJECT_NAME")
    fi
    
    echo "  ]," >> "$status_file"

    # 서비스 상태
    echo "  \"services\": {" >> "$status_file"
    
    # 웹 서비스 확인
    local web_status="down"
    local response_time=0
    
    if curl -f -s -w "%{time_total}" -o /dev/null http://localhost:8080/health 2>/dev/null; then
        web_status="up"
        response_time=$(curl -f -s -w "%{time_total}" -o /dev/null http://localhost:8080/health 2>/dev/null | awk '{print $1 * 1000}')
    fi
    
    echo "    \"web_service\": {" >> "$status_file"
    echo "      \"status\": \"$web_status\"," >> "$status_file"
    echo "      \"response_time_ms\": $response_time" >> "$status_file"
    echo "    }," >> "$status_file"

    # Redis 상태 확인
    local redis_status="down"
    if command -v redis-cli &> /dev/null; then
        if redis-cli ping &> /dev/null; then
            redis_status="up"
        fi
    fi
    
    echo "    \"redis\": {" >> "$status_file"
    echo "      \"status\": \"$redis_status\"" >> "$status_file"
    echo "    }" >> "$status_file"

    echo "  }," >> "$status_file"

    # 전체 상태 결정
    if [ "$container_count" -eq 0 ] || [ "$healthy_containers" -lt "$container_count" ] || [ "$web_status" == "down" ]; then
        overall_status="critical"
    fi

    echo "  \"overall_status\": \"$overall_status\"" >> "$status_file"
    echo "}" >> "$status_file"

    # 상태 출력
    echo ""
    echo "=== 시스템 상태 ==="
    echo "전체 상태: $overall_status"
    echo "CPU 사용률: ${cpu_usage}%"
    echo "메모리 사용률: ${memory_usage}%"
    echo "디스크 사용률: ${disk_usage}%"
    echo "컨테이너: ${healthy_containers}/${container_count} 정상"
    echo "웹 서비스: $web_status (응답시간: ${response_time}ms)"
    echo "Redis: $redis_status"
    echo ""

    return 0
}

# 헬스체크 실행
run_health_check() {
    log_info "헬스체크를 실행합니다..."

    local health_file="$MONITORING_DIR/health_check.json"
    local all_healthy=true

    echo "{" > "$health_file"
    echo "  \"timestamp\": \"$TIMESTAMP\"," >> "$health_file"
    echo "  \"checks\": [" >> "$health_file"

    local check_count=0

    # 웹 서비스 헬스체크
    local web_healthy=false
    local web_response=""
    
    if web_response=$(curl -f -s http://localhost:8080/health 2>/dev/null); then
        web_healthy=true
    fi

    if [ $check_count -gt 0 ]; then
        echo "    ," >> "$health_file"
    fi
    
    echo "    {" >> "$health_file"
    echo "      \"name\": \"web_service\"," >> "$health_file"
    echo "      \"healthy\": $web_healthy," >> "$health_file"
    echo "      \"response\": \"$web_response\"" >> "$health_file"
    echo "    }" >> "$health_file"
    
    check_count=$((check_count + 1))
    
    if [ "$web_healthy" = false ]; then
        all_healthy=false
    fi

    # 데이터베이스 연결 확인
    local db_healthy=false
    
    if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
        db_healthy=true
    fi

    echo "    ," >> "$health_file"
    echo "    {" >> "$health_file"
    echo "      \"name\": \"database\"," >> "$health_file"
    echo "      \"healthy\": $db_healthy," >> "$health_file"
    echo "      \"response\": \"$(redis-cli ping 2>/dev/null || echo 'PONG')\"" >> "$health_file"
    echo "    }" >> "$health_file"
    
    if [ "$db_healthy" = false ]; then
        all_healthy=false
    fi

    # ADB 연결 확인
    local adb_healthy=false
    local device_count=0
    
    if command -v adb &> /dev/null; then
        device_count=$(adb devices | grep -c "device$" || echo "0")
        if [ "$device_count" -gt 0 ]; then
            adb_healthy=true
        fi
    fi

    echo "    ," >> "$health_file"
    echo "    {" >> "$health_file"
    echo "      \"name\": \"adb_devices\"," >> "$health_file"
    echo "      \"healthy\": $adb_healthy," >> "$health_file"
    echo "      \"device_count\": $device_count" >> "$health_file"
    echo "    }" >> "$health_file"

    echo "  ]," >> "$health_file"
    echo "  \"overall_healthy\": $all_healthy" >> "$health_file"
    echo "}" >> "$health_file"

    # 결과 출력
    echo ""
    echo "=== 헬스체크 결과 ==="
    echo "전체 상태: $([ "$all_healthy" = true ] && echo "정상" || echo "비정상")"
    echo "웹 서비스: $([ "$web_healthy" = true ] && echo "정상" || echo "비정상")"
    echo "데이터베이스: $([ "$db_healthy" = true ] && echo "정상" || echo "비정상")"
    echo "ADB 디바이스: $([ "$adb_healthy" = true ] && echo "정상 ($device_count개)" || echo "비정상")"
    echo ""

    if [ "$all_healthy" = false ]; then
        return 1
    fi

    return 0
}

# 성능 메트릭 수집
collect_metrics() {
    log_info "성능 메트릭을 수집합니다..."

    local metrics_file="$MONITORING_DIR/metrics.json"

    echo "{" > "$metrics_file"
    echo "  \"timestamp\": \"$TIMESTAMP\"," >> "$metrics_file"

    # 시스템 메트릭
    echo "  \"system_metrics\": {" >> "$metrics_file"
    
    # CPU 정보
    local cpu_cores=$(nproc)
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    
    echo "    \"cpu\": {" >> "$metrics_file"
    echo "      \"cores\": $cpu_cores," >> "$metrics_file"
    echo "      \"usage_percent\": $cpu_usage" >> "$metrics_file"
    echo "    }," >> "$metrics_file"

    # 메모리 정보
    local memory_info=$(free -b | grep Mem)
    local total_mem=$(echo $memory_info | awk '{print $2}')
    local used_mem=$(echo $memory_info | awk '{print $3}')
    local free_mem=$(echo $memory_info | awk '{print $4}')
    
    echo "    \"memory\": {" >> "$metrics_file"
    echo "      \"total_bytes\": $total_mem," >> "$metrics_file"
    echo "      \"used_bytes\": $used_mem," >> "$metrics_file"
    echo "      \"free_bytes\": $free_mem" >> "$metrics_file"
    echo "    }," >> "$metrics_file"

    # 디스크 정보
    local disk_info=$(df -B1 / | tail -1)
    local total_disk=$(echo $disk_info | awk '{print $2}')
    local used_disk=$(echo $disk_info | awk '{print $3}')
    local free_disk=$(echo $disk_info | awk '{print $4}')
    
    echo "    \"disk\": {" >> "$metrics_file"
    echo "      \"total_bytes\": $total_disk," >> "$metrics_file"
    echo "      \"used_bytes\": $used_disk," >> "$metrics_file"
    echo "      \"free_bytes\": $free_disk" >> "$metrics_file"
    echo "    }" >> "$metrics_file"

    echo "  }," >> "$metrics_file"

    # 애플리케이션 메트릭
    echo "  \"application_metrics\": {" >> "$metrics_file"

    # 웹 서비스 응답 시간
    local response_time=0
    if curl -f -s -w "%{time_total}" -o /dev/null http://localhost:8080/health 2>/dev/null; then
        response_time=$(curl -f -s -w "%{time_total}" -o /dev/null http://localhost:8080/health 2>/dev/null | awk '{print $1 * 1000}')
    fi
    
    echo "    \"web_response_time_ms\": $response_time," >> "$metrics_file"

    # 컨테이너 메트릭
    echo "    \"containers\": [" >> "$metrics_file"
    
    local container_count=0
    if command -v docker &> /dev/null; then
        while IFS= read -r container; do
            if [ -n "$container" ]; then
                local name=$(echo "$container" | awk '{print $1}')
                local stats=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}}" "$name" 2>/dev/null || echo "0%,0B / 0B")
                local cpu_perc=$(echo "$stats" | cut -d',' -f1 | sed 's/%//')
                local mem_usage=$(echo "$stats" | cut -d',' -f2)
                
                if [ $container_count -gt 0 ]; then
                    echo "      ," >> "$metrics_file"
                fi
                
                echo "      {" >> "$metrics_file"
                echo "        \"name\": \"$name\"," >> "$metrics_file"
                echo "        \"cpu_percent\": \"$cpu_perc\"," >> "$metrics_file"
                echo "        \"memory_usage\": \"$mem_usage\"" >> "$metrics_file"
                echo "      }" >> "$metrics_file"
                
                container_count=$((container_count + 1))
            fi
        done < <(docker ps --format "{{.Names}}" | grep "$PROJECT_NAME")
    fi
    
    echo "    ]" >> "$metrics_file"
    echo "  }" >> "$metrics_file"
    echo "}" >> "$metrics_file"

    log_success "메트릭 수집 완료: $metrics_file"
}

# 알림 전송
send_alert() {
    local severity="$1"
    local title="$2"
    local message="$3"
    local color=""

    case "$severity" in
        "critical") color="#FF0000" ;;
        "warning") color="#FFA500" ;;
        "info") color="#00FF00" ;;
        *) color="#808080" ;;
    esac

    log_info "알림을 전송합니다: $severity - $title"

    # Slack 알림
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        local slack_payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "$title",
            "text": "$message",
            "fields": [
                {
                    "title": "Severity",
                    "value": "$severity",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$TIMESTAMP",
                    "short": true
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -X POST -H 'Content-type: application/json' \
             --data "$slack_payload" \
             "$SLACK_WEBHOOK_URL" &> /dev/null || log_warn "Slack 알림 전송 실패"
    fi

    # Discord 알림
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        local discord_payload=$(cat <<EOF
{
    "embeds": [
        {
            "title": "$title",
            "description": "$message",
            "color": $(printf "%d" "0x${color#\#}"),
            "fields": [
                {
                    "name": "Severity",
                    "value": "$severity",
                    "inline": true
                },
                {
                    "name": "Timestamp",
                    "value": "$TIMESTAMP",
                    "inline": true
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -X POST -H 'Content-type: application/json' \
             --data "$discord_payload" \
             "$DISCORD_WEBHOOK_URL" &> /dev/null || log_warn "Discord 알림 전송 실패"
    fi

    # 이메일 알림 (sendmail 사용)
    if [ -n "$EMAIL_RECIPIENTS" ] && command -v sendmail &> /dev/null; then
        local email_subject="[$severity] $title"
        local email_body="$message\n\nTimestamp: $TIMESTAMP"
        
        echo -e "Subject: $email_subject\n\n$email_body" | sendmail "$EMAIL_RECIPIENTS" || log_warn "이메일 알림 전송 실패"
    fi
}

# 실시간 모니터링
watch_system() {
    log_info "실시간 모니터링을 시작합니다... (Ctrl+C로 종료)"

    while true; do
        clear
        echo "🔍 Google Account Creator 실시간 모니터링"
        echo "========================================"
        echo "시간: $TIMESTAMP"
        echo ""

        # 시스템 상태 확인
        check_system_status > /dev/null 2>&1

        # 상태 파일에서 정보 읽기
        if [ -f "$MONITORING_DIR/system_status.json" ]; then
            local overall_status=$(jq -r '.overall_status' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "unknown")
            local cpu_usage=$(jq -r '.system.cpu_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
            local memory_usage=$(jq -r '.system.memory_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
            local disk_usage=$(jq -r '.system.disk_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")

            echo "전체 상태: $overall_status"
            echo "CPU: ${cpu_usage}%"
            echo "메모리: ${memory_usage}%"
            echo "디스크: ${disk_usage}%"
        fi

        echo ""
        echo "다음 업데이트까지 30초..."
        sleep 30
        TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    done
}

# 상태 보고서 생성
generate_report() {
    log_info "상태 보고서를 생성합니다..."

    local report_file="$MONITORING_DIR/status_report_$(date +%Y%m%d_%H%M%S).html"

    cat > "$report_file" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Google Account Creator 상태 보고서</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .status-ok { color: green; }
        .status-warning { color: orange; }
        .status-critical { color: red; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Google Account Creator 상태 보고서</h1>
        <p>생성 시간: TIMESTAMP_PLACEHOLDER</p>
    </div>

    <div class="section">
        <h2>📊 시스템 개요</h2>
        <p>전체 상태: <span id="overall-status">OVERALL_STATUS_PLACEHOLDER</span></p>
    </div>

    <div class="section">
        <h2>💻 시스템 리소스</h2>
        <table>
            <tr><th>항목</th><th>사용률</th><th>상태</th></tr>
            <tr><td>CPU</td><td>CPU_USAGE_PLACEHOLDER%</td><td>CPU_STATUS_PLACEHOLDER</td></tr>
            <tr><td>메모리</td><td>MEMORY_USAGE_PLACEHOLDER%</td><td>MEMORY_STATUS_PLACEHOLDER</td></tr>
            <tr><td>디스크</td><td>DISK_USAGE_PLACEHOLDER%</td><td>DISK_STATUS_PLACEHOLDER</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>🐳 컨테이너 상태</h2>
        <div id="containers">CONTAINERS_PLACEHOLDER</div>
    </div>

    <div class="section">
        <h2>🔧 서비스 상태</h2>
        <table>
            <tr><th>서비스</th><th>상태</th><th>응답시간</th></tr>
            <tr><td>웹 서비스</td><td>WEB_STATUS_PLACEHOLDER</td><td>RESPONSE_TIME_PLACEHOLDER ms</td></tr>
            <tr><td>Redis</td><td>REDIS_STATUS_PLACEHOLDER</td><td>-</td></tr>
        </table>
    </div>
</body>
</html>
EOF

    # 실제 데이터로 플레이스홀더 교체
    check_system_status > /dev/null 2>&1
    
    if [ -f "$MONITORING_DIR/system_status.json" ]; then
        local overall_status=$(jq -r '.overall_status' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "unknown")
        local cpu_usage=$(jq -r '.system.cpu_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
        local memory_usage=$(jq -r '.system.memory_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
        local disk_usage=$(jq -r '.system.disk_usage' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
        local web_status=$(jq -r '.services.web_service.status' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "unknown")
        local response_time=$(jq -r '.services.web_service.response_time_ms' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "0")
        local redis_status=$(jq -r '.services.redis.status' "$MONITORING_DIR/system_status.json" 2>/dev/null || echo "unknown")

        sed -i "s/TIMESTAMP_PLACEHOLDER/$TIMESTAMP/g" "$report_file"
        sed -i "s/OVERALL_STATUS_PLACEHOLDER/$overall_status/g" "$report_file"
        sed -i "s/CPU_USAGE_PLACEHOLDER/$cpu_usage/g" "$report_file"
        sed -i "s/MEMORY_USAGE_PLACEHOLDER/$memory_usage/g" "$report_file"
        sed -i "s/DISK_USAGE_PLACEHOLDER/$disk_usage/g" "$report_file"
        sed -i "s/WEB_STATUS_PLACEHOLDER/$web_status/g" "$report_file"
        sed -i "s/RESPONSE_TIME_PLACEHOLDER/$response_time/g" "$report_file"
        sed -i "s/REDIS_STATUS_PLACEHOLDER/$redis_status/g" "$report_file"
        
        # 상태에 따른 CSS 클래스 적용
        sed -i "s/CPU_STATUS_PLACEHOLDER/$([ $(echo "$cpu_usage > $CPU_THRESHOLD" | bc -l) -eq 1 ] && echo "status-warning" || echo "status-ok")/g" "$report_file"
        sed -i "s/MEMORY_STATUS_PLACEHOLDER/$([ $(echo "$memory_usage > $MEMORY_THRESHOLD" | bc -l) -eq 1 ] && echo "status-warning" || echo "status-ok")/g" "$report_file"
        sed -i "s/DISK_STATUS_PLACEHOLDER/$([ "$disk_usage" -gt "$DISK_THRESHOLD" ] && echo "status-warning" || echo "status-ok")/g" "$report_file"
    fi

    log_success "보고서 생성 완료: $report_file"
    
    # 브라우저에서 열기 (선택사항)
    if command -v xdg-open &> /dev/null; then
        xdg-open "$report_file" &> /dev/null &
    elif command -v open &> /dev/null; then
        open "$report_file" &> /dev/null &
    fi
}

# 도움말 표시
show_help() {
    echo "Google Account Creator Monitoring Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  status      - 시스템 상태 확인"
    echo "  health      - 헬스체크 실행"
    echo "  metrics     - 성능 메트릭 수집"
    echo "  alerts      - 알림 설정 확인"
    echo "  watch       - 실시간 모니터링"
    echo "  report      - 상태 보고서 생성"
    echo "  help        - 이 도움말 표시"
    echo ""
    echo "Environment Variables:"
    echo "  SLACK_WEBHOOK_URL    - Slack 알림용 웹훅 URL"
    echo "  DISCORD_WEBHOOK_URL  - Discord 알림용 웹훅 URL"
    echo "  EMAIL_RECIPIENTS     - 이메일 수신자 목록"
    echo ""
    echo "Examples:"
    echo "  $0 status           # 시스템 상태 확인"
    echo "  $0 health           # 헬스체크 실행"
    echo "  $0 watch            # 실시간 모니터링"
    echo "  $0 report           # HTML 보고서 생성"
}

# 메인 실행 함수
main() {
    local command="${1:-status}"

    case "$command" in
        "status")
            check_system_status
            ;;
        "health")
            if ! run_health_check; then
                send_alert "critical" "Health Check Failed" "One or more health checks failed. Please investigate immediately."
                exit 1
            fi
            ;;
        "metrics")
            collect_metrics
            ;;
        "alerts")
            echo "알림 설정:"
            echo "Slack: $([ -n "$SLACK_WEBHOOK_URL" ] && echo "설정됨" || echo "설정 안됨")"
            echo "Discord: $([ -n "$DISCORD_WEBHOOK_URL" ] && echo "설정됨" || echo "설정 안됨")"
            echo "Email: $([ -n "$EMAIL_RECIPIENTS" ] && echo "설정됨" || echo "설정 안됨")"
            ;;
        "watch")
            watch_system
            ;;
        "report")
            generate_report
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