import pytest
import os
from app import create_app
from app.database import db

@pytest.fixture
def app():
    """테스트용 Flask 앱 설정"""
    # 환경 변수를 'testing'으로 설정하여 메모리 DB를 사용하게 함
    os.environ['FLASK_ENV'] = 'testing'
    
    app = create_app(config_mode='testing')
    
    # 테스트에 필요한 컨텍스트 설정
    with app.app_context():
        # 테스트 시작 시 모든 테이블 생성
        db.create_all()
        yield app
        # 테스트 종료 시 세션 제거 및 테이블 삭제
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """테스트용 HTTP 클라이언트 (가상 브라우저)"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Flask CLI 명령 테스트용 러너"""
    return app.test_cli_runner()