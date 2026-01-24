import pytest
import os, sys
import io
# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import db
from app.models import User, TypingText, TypingResult

@pytest.fixture(scope='session')
def app():
    """테스트 세션 동안 딱 한 번 앱과 DB 테이블을 생성합니다."""
    os.environ['ENV'] = 'testing'
    app = create_app(config_mode='testing')
    
    with app.app_context():
        db.create_all()  # [핵심] 여기서 테이블을 딱 한 번 만듭니다.
        yield app
        db.session.remove()
        db.drop_all()    # [핵심] 모든 테스트 파일이 다 끝나야 삭제합니다.

@pytest.fixture(scope='session')
def client(app):
    """테스트용 HTTP 클라이언트 (세션 유지)"""
    return app.test_client()

@pytest.fixture(autouse=True)
def cleanup_session():
    """
    매 테스트(함수)가 끝날 때마다 세션을 정리합니다.
    데이터는 삭제하지 않으면서도 DB 연결이 꼬이는 것을 방지합니다.
    """
    yield
    db.session.remove()
    db.session.rollback()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()