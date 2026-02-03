import os
from flask import Blueprint, request, redirect, url_for, jsonify , current_app
from app.models import User
from app.database import db
from flask_login import login_user, logout_user, login_required, current_user
from app.utils import api_response
import uuid
from google.oauth2 import id_token
from google.auth.transport import requests
from flasgger import swag_from



auth_blueprint = Blueprint('auth', __name__)
INTERNAL_SYNC_KEY = os.getenv("INTERNAL_SYNC_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GOOLE_LOGIN_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'google_login.yaml')
USER_OUT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'user_out.yaml')

# --- 1. 구글 로그인 처리 API ---
@auth_blueprint.route('/google', methods=['POST'])
@swag_from(GOOLE_LOGIN_YAML_PATH)
def google_login():
    try:
        # 1. 보안 키 검증 (X-INTERNAL-KEY)
        internal_key = request.headers.get('X-INTERNAL-KEY')
        if internal_key != INTERNAL_SYNC_KEY:
            return api_response(success=False, message="접근 권한이 없습니다.", status_code=403)

        # 2. 헤더에서 구글 ID 토큰 추출
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return api_response(success=False, message="인증 토큰이 없습니다.", status_code=401)
        
        token = auth_header.split(" ")[1]

        # 3. 구글 토큰 검증
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        username = idinfo.get('name', 'User')
        profile_pic = idinfo.get('picture')

        # 4. DB 로직 및 상태 코드 분기
        user = User.query.filter_by(email=email).first()
        status_code = 200 # 기본은 OK

        if not user:
            status_code = 201 # 신규 생성은 Created
            # 닉네임 중복 방지
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                username = f"{username}_{str(uuid.uuid4())[:4]}"

            user = User(
                username=username,
                email=email,
                profile_pic=profile_pic
            )
            db.session.add(user)
            db.session.commit()

            user.ranking_score = 0
            db.session.commit()
            message = "회원가입 및 로그인 성공"
        else:
            user.profile_pic = profile_pic
            if user.ranking_score is None:
                user.ranking_score = 0
            db.session.commit()
            message = "로그인 성공"

        current_app.logger.info(f"✅ [{message}] {user.username} ({user.email}) 님이 접속했습니다.")

        return api_response(
            success=True,
            data={
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "profile_pic": user.profile_pic,
                "is_admin" : user.is_admin # 기존 오타(indinfo) 수정 제안
            },
            message=message,
            status_code=status_code # 201 또는 200 반환
        )

    except ValueError:
        return api_response(success=False, message="유효하지 않은 구글 토큰입니다.", status_code=401)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"로그인 에러: {str(e)}")
        return api_response(success=False, message="서버 오류 발생", status_code=500)
    



@auth_blueprint.route('user_out', methods=['DELETE'])
@swag_from(USER_OUT_YAML_PATH)
def user_out():
    try:
        # 1. 헤더에서 토큰 추출 (로그인 로직과 동일)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return api_response(success=False, message="인증 토큰이 없습니다.", status_code=401)
        
        token = auth_header.split(" ")[1]

        # 2. 토큰 검증 (Google ID Token 검증)
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo['email']

        # 3. 해당 이메일의 유저를 DB에서 찾아 삭제
        user = User.query.filter_by(email=email).first()
        if not user:
            return api_response(success=False, message="유저를 찾을 수 없습니다.", status_code=404)

        db.session.delete(user)
        db.session.commit()
        
        return api_response(success=True, message="회원 탈퇴 및 모든 데이터 삭제가 완료되었습니다.")

    except ValueError:
        return api_response(success=False, message="유효하지 않은 토큰입니다.", status_code=401)
    

if os.getenv('ENV') == 'testing':
    @auth_blueprint.route('/test-login', methods=['POST'])
    def test_login():
        if os.getenv('ENV') != 'testing':
            return api_response(success=False, message="Forbidden", status_code=403)

        if request.is_json:
            data = request.get_json()
        else:
            data = request.form

        email = data.get('email')
        username = data.get('username')
        profile_pic = data.get('profile_pic')
        
        if not email:
            return api_response(success=False, message="이메일이 누락되었습니다.", status_code=400)

        try:
            user = User.query.filter_by(email=email).first()
            status_code = 200

            if not user:
                status_code = 201
                user = User(
                    username=username or f"TestUser_{str(uuid.uuid4())[:4]}", 
                    email=email, 
                    profile_pic=profile_pic
                )
                db.session.add(user)
                db.session.commit()
                
                user.ranking_score = 0
                db.session.commit()
                message = "테스트 회원가입 및 로그인 성공"
            else:
                user.profile_pic = profile_pic # 로그인 시에도 사진 업데이트 로직 동일하게 적용
                db.session.commit()
                message = "테스트 로그인 성공"

            # google_login의 return data 구조와 100% 일치시킴
            return api_response(
                success=True,
                data={
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "profile_pic": user.profile_pic,
                    "is_admin": user.is_admin
                },
                message=message,
                status_code=status_code
            )
        except Exception as e:
            db.session.rollback()
            return api_response(success=False, message=str(e), status_code=500)