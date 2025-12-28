from flask import Flask, jsonify
import logging
from flask_migrate import Migrate
from flask_login import LoginManager
from flasgger import Swagger

import os
from flask_cors import CORS

from database import db
from models import User, TypingText  # TypingText 모델 추가됨
from auth.views import auth_blueprint
from main.views import main_blueprint
from text.views import text_blueprint

app = Flask(__name__)
ENV = os.getenv('FLASK_ENV', 'development')
swagger = Swagger(app)

if ENV == 'production':
    # 실제 배포 주소를 여기에 적으세요
    CORS(app, resources={r"/*": {"origins": [
            "https://typing-something-fe.vercel.app",
            "https://typing-something-fe.vercel.app/"
        ]}})
else:
    CORS(app)

# 1. 설정 (Configuration) => sqllite로 변환

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 불필요한 오버헤드 방지
# app.secret_key = 'your_secret_key'

# 2. 로깅 설정
app.logger.setLevel(logging.DEBUG)
logging.basicConfig(filename='application.log', level=logging.DEBUG, 
                    format='%(asctime)s:%(levelname)s:%(message)s')



# 3. 확장 도구 초기화
login_manager = LoginManager()
login_manager.init_app(app)
db.init_app(app)
migrate = Migrate(app, db, render_as_batch=True)

# 4. 블루프린트 등록
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(main_blueprint, url_prefix='/')
app.register_blueprint(text_blueprint, url_prefix='/text')

# 5. 사용자 로드 함수 (Flask-Login)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 7. 앱 컨텍스트 초기화
with app.app_context():
    db.create_all()
  
# 8. 공통 에러 및 유틸리티
@app.route('/favicon.ico')
def favicon():
    return ('', 204)

if __name__ == '__main__':
    # 배포 시엔 0.0.0.0으로 열어야 외부에서 접속 가능합니다.
    if ENV == 'production':
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        app.run(port=5000, debug=True)