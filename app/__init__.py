import os
import logging
import time
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_login import LoginManager
from flasgger import Swagger
from dotenv import load_dotenv

# 내부 모듈 임포트 (상대 경로 사용)
from .database import db
from .models import User

# 전역 확장 도구 선언
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_mode=None):
    # 1. 환경 변수 로드
    load_dotenv()
    
    app = Flask(__name__)

    # --- 설정 로드 ---
    # 파라미터로 받은 config_mode가 없으면 환경 변수에서 읽어옴
    ENV = config_mode or os.getenv('FLASK_ENV', 'development')
    DATABASE_URL = os.getenv('DATABASE_URL')  # 배포 환경용 (RDS 등)
    LOCAL_MYSQL_URL = os.getenv('LOCAL_MYSQL_URL')  # 로컬 개발용 MySQL
    SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
    
    # 기본 설정
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-1234')

    # 환경별 DB 설정
    if ENV == 'testing':
    # ✅ 테스트: 속도가 빠른 메모리 DB 사용
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    elif ENV == 'production':
    # ✅ 배포: DATABASE_URL (AWS RDS 등) 사용
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

    else:
        # ✅ 로컬 개발 (development)
        if LOCAL_MYSQL_URL:
            # 로컬 MySQL 서버가 켜져 있다면 사용
            app.config['SQLALCHEMY_DATABASE_URI'] = LOCAL_MYSQL_URL
        else:
            # MySQL 설정이 없으면 비상용으로 로컬 SQLite 파일 사용
            basedir = os.path.abspath(os.path.dirname(__file__))
            # 2. 한 단계 위인 루트 폴더(study_flask)로 이동 후 instance 폴더 지정
            instance_path = os.path.abspath(os.path.join(basedir, os.pardir, 'instance'))
            
            # 3. 폴더가 없으면 에러 방지를 위해 생성
            if not os.path.exists(instance_path):
                os.makedirs(instance_path)
                
            db_path = os.path.join(instance_path, 'local.db')
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    
    # CORS 설정
    if ENV == 'production':
        CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
        origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
        CORS(app, resources={r"/*": {"origins": origins_list}})
    else:
        CORS(app)

    # Swagger 설정
    host_only = SERVER_URL.replace('http://', '').replace('https://', '')
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Typing Game API",
            "description": f"Documentation at {SERVER_URL}",
            "version": "1.0.0"
        },
        "host": host_only,
        "schemes": ["http", "https"]
    }
    Swagger(app, template=swagger_template)

    # 3. 블루프린트 등록 (함수 내부에서 임포트하여 순환 참조 방지)
    from .routes.auth.views import auth_blueprint
    from .routes.main.views import main_blueprint
    from .routes.text.views import text_blueprint
    from .routes.user.views import user_blueprint
    from .routes.reports.views import report_blueprint

    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    app.register_blueprint(main_blueprint, url_prefix='/')
    app.register_blueprint(text_blueprint, url_prefix='/text')
    app.register_blueprint(user_blueprint, url_prefix='/user')
    app.register_blueprint(report_blueprint, url_prefix='/admin')
    # 4. 사용자 로더
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 5. 로깅 및 초기화 로그
    setup_logging(app, ENV)

    with app.app_context():
        db.create_all()
        app.logger.info("="*50)
        app.logger.info(f"🚀 타이핑 게임 서버 시작 (모드: {ENV.upper()})")
        
        try:
            from sqlalchemy import text
            # 실제 DB에 신호를 보내서 연결됐는지 확인
            db.session.execute(text('SELECT 1'))
            
            # 주소에서 비밀번호 가리고 출력 (보안)
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            masked_uri = db_uri.split('@')[-1] if '@' in db_uri else db_uri
            
            app.logger.info(f"✅ DB 연결 성공: {masked_uri}")
        except Exception as e:
            app.logger.error(f"❌ DB 연결 실패! 설정을 확인하세요.")
            app.logger.error(f"👉 에러 내용: {str(e)}")

        # Redis 초기화 (선택적 - REDIS_URL 설정 시 캐시 활성화)
        try:
            from app.redis_client import init_redis
            if init_redis():
                app.logger.info("✅ Redis 캐시 연결 성공")
            elif os.getenv("REDIS_URL"):
                app.logger.warning("⚠️ Redis 연결 실패 - 캐시 없이 동작")
            else:
                app.logger.info("ℹ️ Redis 미설정 - 캐시 없이 동작")
        except Exception as e:
            app.logger.warning(f"ℹ️ Redis 초기화 생략: {e}")

        app.logger.info("="*50)

    return app

def setup_logging(app, env):
    if env == 'production':
        app.logger.setLevel(logging.INFO)
    else:
        app.logger.setLevel(logging.DEBUG)
    
    logging.Formatter.converter = lambda *args: time.localtime(time.time() + 32400)
    logging.basicConfig(
        level=logging.INFO, 
        format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )