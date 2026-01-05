import os
import logging
import time
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_login import LoginManager
from flasgger import Swagger
from dotenv import load_dotenv

# 1. 환경 변수 로드 (가장 먼저 실행)
load_dotenv()

from database import db
from models import User, TypingText
from auth.views import auth_blueprint
from main.views import main_blueprint
from text.views import text_blueprint
from user.views import user_blueprint

app = Flask(__name__)

# --- [수정 포인트 1] 환경 변수 기반 설정 ---
ENV = os.getenv('FLASK_ENV', 'development')
DATABASE_URL = os.getenv('DATABASE_URL') # .env에서 읽어옴

SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
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

# 2. CORS 설정
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
if ENV == 'production':
    origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/*": {"origins": origins_list}})
else:
    CORS(app)

# --- [수정 포인트 2] DB 연결 로직 최적화 ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')

if not os.path.exists(INSTANCE_PATH):
    os.makedirs(INSTANCE_PATH)

if ENV == 'testing':
    # GitHub Actions 전용: 메모리 DB 사용 (속도 최적화)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
elif ENV == 'production' or DATABASE_URL:
    # 로컬 MySQL 또는 AWS RDS 사용
    # MySQL 사용 시 pymysql 드라이버를 명시해야 함
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # 최후의 수단: 로컬 SQLite 파일 사용
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(INSTANCE_PATH, 'local.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-1234')

# 4. 확장 도구 초기화
swagger = Swagger(app, template=swagger_template)
db.init_app(app)
migrate = Migrate(app, db, render_as_batch=True)
login_manager = LoginManager()
login_manager.init_app(app)

# 5. 로깅 설정 (한국 시간 적용 및 포맷 개선)
if ENV == 'production':
    app.logger.setLevel(logging.INFO)
else:
    app.logger.setLevel(logging.DEBUG)

# 로그 시간 한국 시간(KST) 강제 고정
logging.Formatter.converter = lambda *args: time.localtime(time.time() + 32400)

logging.basicConfig(
    level=logging.INFO, 
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 6. 블루프린트 등록
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(main_blueprint, url_prefix='/')
app.register_blueprint(text_blueprint, url_prefix='/text')
app.register_blueprint(user_blueprint, url_prefix='/user')

# 7. 사용자 로드 함수
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 8. 공통 유틸리티
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

@app.route('/crash')
def crash():
    app.logger.info("!!! 사용자가 /crash를 호출함: 서버를 강제 종료합니다 !!!")
    os._exit(1)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    if ENV == 'production':
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        app.run(host='127.0.0.1', port=port, debug=True)