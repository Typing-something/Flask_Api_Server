"""
부하테스트로 생성된 데이터 정리 스크립트
특정 유저의 결과만 삭제하여 실제 사용자 데이터는 보호합니다.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app
from app.database import db
from app.models import TypingResult, User
from app.routes.text.helpers import recalculate_user_statistics

# 한국 시간대
KST = timezone(timedelta(hours=9))

def cleanup_locust_results(test_user_id=None, hours_ago=1):
    """
    부하테스트로 생성된 결과 데이터 정리
    
    Args:
        test_user_id: 테스트용 유저 ID (None이면 환경 변수에서 읽음)
        hours_ago: 몇 시간 전부터의 데이터를 삭제할지 (기본 1시간)
    """
    load_dotenv()
    app = create_app(config_mode='production')
    
    with app.app_context():
        # 테스트용 유저 ID 가져오기 (환경 변수 또는 파라미터)
        if not test_user_id:
            test_user_id = int(os.getenv('LOCUST_TEST_USER_ID', 3))  # 기본값: 3
        
        # 유저 존재 확인
        user = User.query.get(test_user_id)
        if not user:
            print(f"❌ 유저 ID {test_user_id}를 찾을 수 없습니다.")
            return
        
        # 삭제할 시간 범위 설정 (기본: 1시간 전부터)
        cutoff_time = datetime.now(KST) - timedelta(hours=hours_ago)
        
        # 해당 유저의 결과 중 최근 N시간 내 생성된 것만 조회
        results_to_delete = TypingResult.query.filter(
            TypingResult.user_id == test_user_id,
            TypingResult.created_at >= cutoff_time
        ).all()
        
        count = len(results_to_delete)
        
        if count == 0:
            print(f"✅ 유저 {test_user_id}의 최근 {hours_ago}시간 내 생성된 결과가 없습니다.")
            return
        
        # 삭제 실행
        try:
            for result in results_to_delete:
                db.session.delete(result)
            
            db.session.commit()
            recalculate_user_statistics(test_user_id)
            print(f"✅ 유저 {test_user_id}의 결과 {count}개를 삭제했습니다.")
            print(f"   삭제 범위: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 이후")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 삭제 중 오류 발생: {str(e)}")
            raise

def cleanup_keep_recent(test_user_id=None, keep_n=100):
    """
    해당 유저의 결과 중 최근 N개만 남기고 나머지 삭제
    부하테스트 기록 폭증 방지용
    """
    load_dotenv()
    app = create_app(config_mode='production')

    with app.app_context():
        if not test_user_id:
            test_user_id = int(os.getenv('LOCUST_TEST_USER_ID', 3))

        user = User.query.get(test_user_id)
        if not user:
            print(f"❌ 유저 ID {test_user_id}를 찾을 수 없습니다.")
            return

        # 유지할 ID (최근 keep_n개)
        ids_to_keep = [
            r.id for r in
            TypingResult.query.filter_by(user_id=test_user_id)
            .order_by(TypingResult.created_at.desc())
            .limit(keep_n)
            .all()
        ]

        if not ids_to_keep:
            print(f"✅ 유저 {test_user_id}의 결과가 없습니다.")
            return

        deleted = TypingResult.query.filter(
            TypingResult.user_id == test_user_id,
            TypingResult.id.notin_(ids_to_keep)
        ).delete(synchronize_session=False)

        db.session.commit()
        if deleted > 0:
            recalculate_user_statistics(test_user_id)
        print(f"✅ 유저 {test_user_id}: 최근 {len(ids_to_keep)}개 유지, {deleted}개 삭제")


def cleanup_by_user_only(test_user_id=None):
    """
    특정 유저의 모든 결과 삭제 (시간 제한 없음)
    주의: 이 함수는 해당 유저의 모든 결과를 삭제합니다.
    """
    load_dotenv()
    app = create_app(config_mode='production')
    
    with app.app_context():
        if not test_user_id:
            test_user_id = int(os.getenv('LOCUST_TEST_USER_ID', 3))
        
        user = User.query.get(test_user_id)
        if not user:
            print(f"❌ 유저 ID {test_user_id}를 찾을 수 없습니다.")
            return
        
        # 해당 유저의 모든 결과 조회
        results_to_delete = TypingResult.query.filter_by(user_id=test_user_id).all()
        count = len(results_to_delete)
        
        if count == 0:
            print(f"✅ 유저 {test_user_id}의 결과가 없습니다.")
            return
        
        try:
            for result in results_to_delete:
                db.session.delete(result)
            
            db.session.commit()
            recalculate_user_statistics(test_user_id)
            print(f"✅ 유저 {test_user_id}의 모든 결과 {count}개를 삭제했습니다.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 삭제 중 오류 발생: {str(e)}")
            raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='부하테스트 데이터 정리 스크립트')
    parser.add_argument('--user-id', type=int, help='테스트용 유저 ID (기본: 환경 변수 또는 3)')
    parser.add_argument('--hours', type=int, default=1, help='몇 시간 전부터 삭제할지 (기본: 1시간)')
    parser.add_argument('--all', action='store_true', help='시간 제한 없이 해당 유저의 모든 결과 삭제')
    parser.add_argument('--keep', type=int, metavar='N', help='최근 N개만 유지하고 나머지 삭제 (예: --keep 100)')
    
    args = parser.parse_args()
    
    if args.keep is not None:
        print(f"🧹 최근 {args.keep}개만 유지, 나머지 삭제")
        cleanup_keep_recent(args.user_id, args.keep)
    elif args.all:
        print("⚠️  경고: 해당 유저의 모든 결과를 삭제합니다.")
        cleanup_by_user_only(args.user_id)
    else:
        print(f"🧹 부하테스트 데이터 정리 시작 (최근 {args.hours}시간)")
        cleanup_locust_results(args.user_id, args.hours)

