#!/usr/bin/env python3
"""
Account Health Checker Demo Script

This script demonstrates how to use the HealthChecker module to monitor
Google account health and receive notifications.
"""

import asyncio
import logging
from pathlib import Path
import sys

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.health_checker import HealthChecker, NotificationConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_basic_health_check():
    """기본 상태 확인 데모"""
    logger.info("=== 기본 상태 확인 데모 ===")
    
    # Health Checker 초기화
    config = {
        'check_timeout': 30,
        'batch_size': 3,
        'headless': True,  # 백그라운드에서 실행
    }
    
    health_checker = HealthChecker(config)
    
    # Selenium 환경 테스트
    if health_checker.setup_selenium_environment():
        logger.info("✅ Selenium 환경 설정 성공")
    else:
        logger.error("❌ Selenium 환경 설정 실패")
        return
    
    # 샘플 계정 데이터
    sample_accounts = [
        {
            'email': 'test1@gmail.com',
            'password': 'password123',
            'created_at': '2024-01-01'
        },
        {
            'email': 'test2@gmail.com', 
            'password': 'password456',
            'created_at': '2024-01-02'
        }
    ]
    
    # 배치 상태 확인 (실제로는 실행하지 않음 - 데모용)
    logger.info("배치 상태 확인 시뮬레이션...")
    # results = await health_checker.run_health_check_batch(sample_accounts)
    
    # 통계 계산
    stats = health_checker.calculate_detailed_survival_stats()
    logger.info(f"통계 계산 완료: {stats}")


async def demo_notification_system():
    """알림 시스템 데모"""
    logger.info("=== 알림 시스템 데모 ===")
    
    # 알림 설정 (실제 웹훅 URL은 환경변수나 설정파일에서 가져오세요)
    config = {
        'slack_webhook_url': None,  # 'https://hooks.slack.com/services/...'
        'discord_webhook_url': None,  # 'https://discord.com/api/webhooks/...'
        'notification_thresholds': {
            'critical_survival_rate': 30.0,
            'warning_survival_rate': 50.0,
            'high_error_rate': 20.0,
            'account_suspension_rate': 10.0
        }
    }
    
    health_checker = HealthChecker(config)
    
    # 샘플 통계 데이터
    sample_stats = {
        'overall': {
            'total_accounts': 100,
            'healthy_accounts': 45,
            'suspended_accounts': 30,
            'locked_accounts': 15,
            'disabled_accounts': 10,
            'unknown_status': 0,
            'survival_rate': 45.0,
            'active_rate': 60.0
        },
        'error_analysis': {
            'error_rate': 25.0,
            'total_errors': 25
        }
    }
    
    # 알림 시스템 테스트
    logger.info("알림 시스템 테스트 중...")
    
    # 경고 알림 테스트
    await health_checker.send_notification(
        "테스트 경고 메시지입니다.",
        'warning',
        sample_stats
    )
    
    # 통계 기반 자동 알림 테스트
    await health_checker.check_and_notify(sample_stats)
    
    # 일일 리포트 테스트
    await health_checker.send_daily_report()


async def demo_survival_analysis():
    """생존율 분석 데모"""
    logger.info("=== 생존율 분석 데모 ===")
    
    health_checker = HealthChecker()
    
    # 상세 통계 계산
    detailed_stats = health_checker.calculate_detailed_survival_stats()
    logger.info("상세 통계:")
    print(f"전체 계정: {detailed_stats['overall']['total_accounts']}개")
    print(f"생존율: {detailed_stats['overall']['survival_rate']:.1f}%")
    
    # 인사이트 생성
    insights = health_checker.get_survival_insights()
    logger.info("생존율 인사이트:")
    for insight in insights:
        print(f"• {insight}")
    
    # 생존율 예측
    forecast = health_checker.generate_survival_forecast(days_ahead=7)
    if forecast and 'forecast' in forecast:
        logger.info("7일 생존율 예측:")
        for day_forecast in forecast['forecast'][:3]:  # 처음 3일만 출력
            print(f"• {day_forecast['date']}: {day_forecast['predicted_survival_rate']:.1f}%")


async def demo_health_report():
    """리포트 생성 데모"""
    logger.info("=== 리포트 생성 데모 ===")
    
    health_checker = HealthChecker()
    
    # 리포트 생성
    report_path = health_checker.export_health_report()
    
    if report_path:
        logger.info(f"✅ 리포트 생성 완료: {report_path}")
        
        # 계정별 상태 조회 예제
        healthy_accounts = health_checker.get_accounts_by_status('healthy')
        suspended_accounts = health_checker.get_accounts_by_status('suspended')
        
        logger.info(f"건강한 계정: {len(healthy_accounts)}개")
        logger.info(f"정지된 계정: {len(suspended_accounts)}개")
    else:
        logger.warning("리포트 생성 실패")


async def main():
    """메인 데모 함수"""
    logger.info("🚀 Account Health Checker 데모 시작")
    
    try:
        # 기본 기능 데모
        await demo_basic_health_check()
        await asyncio.sleep(1)
        
        # 알림 시스템 데모
        await demo_notification_system()
        await asyncio.sleep(1)
        
        # 생존율 분석 데모
        await demo_survival_analysis()
        await asyncio.sleep(1)
        
        # 리포트 생성 데모
        await demo_health_report()
        
        logger.info("✅ 모든 데모 완료")
        
    except Exception as e:
        logger.error(f"❌ 데모 실행 중 오류: {e}")


if __name__ == "__main__":
    # 실제 사용 예제
    print("""
    📋 Health Checker 사용 가이드
    
    1. 기본 사용법:
    ```python
    from core.health_checker import HealthChecker
    
    # 초기화
    checker = HealthChecker({
        'slack_webhook_url': 'YOUR_SLACK_WEBHOOK',
        'batch_size': 5
    })
    
    # CSV에서 계정 로드하여 상태 확인
    await checker.run_periodic_health_check('data/accounts.csv', interval_hours=6)
    ```
    
    2. 개별 계정 확인:
    ```python
    account = {'email': 'test@gmail.com', 'password': 'password'}
    result = checker._check_single_account(account)
    ```
    
    3. 통계 및 리포트:
    ```python
    stats = checker.calculate_detailed_survival_stats()
    insights = checker.get_survival_insights()
    report_path = checker.export_health_report()
    ```
    
    4. 알림 전송:
    ```python
    await checker.send_notification("계정 상태 알림", 'warning', stats)
    await checker.send_daily_report()
    ```
    """)
    
    # 데모 실행
    asyncio.run(main()) 