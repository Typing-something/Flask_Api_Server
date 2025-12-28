import os
import logging
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

app = Flask(__name__)
ENV = os.getenv('FLASK_ENV', 'development')

SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
host_only = SERVER_URL.replace('http://', '').replace('https://', '')

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Typing Game API",
        "description": f"Documentation at {SERVER_URL}",
        "version": "1.0.0"
    },
    "host": host_only,  # 이 부분이 핵심!
    "schemes": ["http", "https"]
}

# 2. CORS 설정

CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')

if ENV == 'production':
    # 쉼표로 구분된 문자열을 리스트로 변환
    origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
    CORS(app, resources={r"/*": {"origins": origins_list}})
else:
    CORS(app)


# 3. DB 및 경로 설정
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_PATH = os.path.join(BASE_DIR, 'instance')

if not os.path.exists(INSTANCE_PATH):
    os.makedirs(INSTANCE_PATH)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(INSTANCE_PATH, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# 배포 시엔 반드시 .env의 값을 사용하도록 권장
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-1234')

# 4. 확장 도구 초기화
swagger = Swagger(app, template=swagger_template)
db.init_app(app)
migrate = Migrate(app, db, render_as_batch=True)
login_manager = LoginManager()
login_manager.init_app(app)

# 5. 로깅 설정 (배포 시엔 INFO 레벨 권장)
if ENV == 'production':
    app.logger.setLevel(logging.INFO)
else:
    app.logger.setLevel(logging.DEBUG)

logging.basicConfig(filename='application.log', level=logging.DEBUG, 
                    format='%(asctime)s:%(levelname)s:%(message)s')

# 6. 블루프린트 등록
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(main_blueprint, url_prefix='/')
app.register_blueprint(text_blueprint, url_prefix='/text')

# 7. 사용자 로드 함수
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 8. 공통 유틸리티
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    
    if ENV == 'production':
        # 배포 환경: debug는 반드시 False
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # 로컬 환경
        app.run(host='127.0.0.1', port=port, debug=True)