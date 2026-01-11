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

        # 3. 구글 토큰 검증 및 정보 추출
        # id_token.verify_oauth2_token이 서명, 만료시간 등을 다 체크해줍니다.
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        username = idinfo.get('name', 'User')
        profile_pic = idinfo.get('picture')

        # 4. DB 로직 (기존과 동일)
        user = User.query.filter_by(email=email).first()

       

        if not user:
            # 닉네임 중복 방지
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                username = f"{username}_{str(uuid.uuid4())[:4]}"

            # 신규 유저 객체 생성
            user = User(
                username=username,
                email=email,
                profile_pic=profile_pic
            )
            db.session.add(user)
            db.session.commit()  # 1차 커밋: 여기서 user.id가 생성됩니다.

            # [추가] 생성된 ID를 ranking_score에 초기값으로 할당
            user.ranking_score = user.id
            db.session.commit()  # 2차 커밋: ranking_score 업데이트 반영
            
            message = "회원가입 및 로그인 성공"
        else:
            # 기존 유저 정보 업데이트
            user.profile_pic = profile_pic
            
            # [선택 사항] 만약 기존 유저 중 ranking_score가 비어있는 경우를 대비한 방어 코드
            if user.ranking_score is None:
                user.ranking_score = user.id
                
            db.session.commit()
            message = "로그인 성공"

        current_app.logger.info(f"✅ [{message}] {user.username} ({user.email}) 님이 접속했습니다.")

        # 5. 성공 응답 (프론트엔드 NextAuth가 기대하는 user_id 포함)
        return api_response(
            success=True,
            data={
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "profile_pic": user.profile_pic,
                "indinfo" : user.is_admin
            },
            message=message
        )

    except ValueError:
        # 토큰이 가짜거나 만료되었을 때 발생하는 에러
        return api_response(success=False, message="유효하지 않은 구글 토큰입니다.", status_code=401)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"로그인 에러: {str(e)}")
        return api_response(success=False, message="서버 오류 발생", status_code=500)


