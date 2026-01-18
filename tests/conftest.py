import pytest
import os
from app import create_app
from app.database import db
from app.models import User, TypingText, TypingResult

@pytest.fixture(scope='session')
def app():
    """테스트용 Flask 앱 설정 (세션 동안 1번만 생성)"""
    os.environ['FLASK_ENV'] = 'testing'
    app = create_app(config_mode='testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """테스트용 HTTP 클라이언트"""
    return app.test_client()

@pytest.fixture(autouse=True)
def clear_db(app):
    """모든 테스트 함수 실행 전 DB를 깨끗이 비우는 Fixture (자동 실행)"""
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield  # 여기서 테스트 혹은 다음 Fixture가 실행됩니다.

@pytest.fixture
def setup_data(app, clear_db): 
    """모델의 모든 필드를 활용한 풍성한 기초 데이터 생성"""
    with app.app_context():
        # 1. 상세 유저 데이터 생성
        user = User(
            username="testuser", 
            email="test@test.com",
            ranking_score=1500,
            play_count=1,
            max_combo=50,
            best_cpm=500,
            avg_cpm=450.0,
            avg_accuracy=98.5,
            is_admin=False
        )
        
        # 2. 테스트용 텍스트 생성
        t1 = TypingText(
            genre="소설", 
            title="소설 제목", 
            author="작가1", 
            content="내용1",
            image_url="http://example.com/image1.jpg"
        )
        t2 = TypingText(
            genre="IT", 
            title="IT 제목", 
            author="작가2", 
            content="내용2"
        )
        
        db.session.add_all([user, t1, t2])
        db.session.commit()

        # 3. 찜하기(Favorite) 설정: t1만 찜함
        # 모델의 favorite_texts 관계를 활용합니다.
        user.favorite_texts.append(t1)
        db.session.commit()

        # 4. 타자 결과 기록 생성 (t1에 대한 기록)
        result = TypingResult(
            user_id=user.id, 
            text_id=t1.id, 
            cpm=999, 
            wpm=200, 
            accuracy=100.0, 
            combo=50
        )
        db.session.add(result)
        db.session.commit()

        # [반환] 테스트에서 검증에 필요한 값들을 딕셔너리로 제공
        return {
            "u_id": user.id,
            "t1_id": t1.id,
            "t2_id": t2.id,
            "username": user.username,
            "ranking_score": user.ranking_score,
            "t1_title": t1.title,
            "t1_is_favorite": True,  # 검증 포인트
            "t2_is_favorite": False   # 검증 포인트
        }

@pytest.fixture
def runner(app):
    return app.test_cli_runner()