import os
from flask import Blueprint, request, redirect, url_for, jsonify , current_app
from models import User, db
from flask_login import login_user, logout_user, login_required, current_user
from utils import api_response
import uuid
from google.oauth2 import id_token
from google.auth.transport import requests


auth_blueprint = Blueprint('auth', __name__)
INTERNAL_SYNC_KEY = os.getenv("INTERNAL_SYNC_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# --- 1. 구글 로그인 처리 API ---
@auth_blueprint.route('/google', methods=['POST'])
def google_login():
    """
    구글 소셜 로그인 및 회원가입
    ---
    tags:
      - Auth
    description: |
      **기능:**
      1. 프론트엔드에서 전달받은 구글 ID 토큰을 검증합니다.
      2. 내부 서버 통신용 보안키(X-INTERNAL-KEY)를 확인합니다.
      3. 가입되지 않은 이메일이면 자동으로 회원가입을 진행합니다.
      4. 가입된 유저라면 프로필 사진 등 최신 정보를 업데이트하고 로그인 처리합니다.
      
      **주의사항:** - 헤더에 `Authorization: Bearer <Google_ID_Token>` 형식을 지켜야 합니다.
      - 내부 호출용 `X-INTERNAL-KEY`가 필수입니다.
    parameters:
      - name: X-INTERNAL-KEY
        in: header
        type: string
        required: true
        description: 내부 서버 동기화용 보안키
      - name: Authorization
        in: header
        type: string
        required: true
        description: "Bearer {Google_ID_Token}"
    responses:
      200:
        description: 로그인 성공
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "로그인 성공"}
            data:
              type: object
              properties:
                user_id: {type: integer, description: "DB 내 유저 고유 ID"}
                username: {type: string, description: "유저 닉네임"}
                email: {type: string, description: "구글 이메일"}
                profile_pic: {type: string, description: "구글 프로필 이미지 URL"}
      401:
        description: 구글 토큰이 유효하지 않거나 만료됨
      403:
        description: X-INTERNAL-KEY가 일치하지 않음
      500:
        description: DB 저장 실패 등 서버 내부 오류
    """
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

            user = User(
                username=username,
                email=email,
                profile_pic=profile_pic
            )
            db.session.add(user)
            db.session.commit()
            message = "회원가입 및 로그인 성공"
        else:
            # 기존 유저 정보 업데이트
            user.profile_pic = profile_pic
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
                "profile_pic": user.profile_pic
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

# --- 2. 테스트용 유저 생성 API ---
@auth_blueprint.route('/test_create')
def test_create():
    """
    브라우저 전용 테스트 유저 생성 API
    ---
    tags:
      - Auth
    description: |
      **이 API는 브라우저 주소창에 직접 입력하여 유저를 만드는 용도입니다.**
      
      **사용 방법 (URL 예시):**
      - 기본 생성: `http://localhost:5000/auth/test_create?name=타자왕`
      - 이메일 지정: `http://localhost:5000/auth/test_create?name=철수&email=chul@test.com`
      
      **결과:** 유저가 생성됨과 동시에 해당 유저로 **로그인(세션 생성)** 처리됩니다.
    parameters:
      - name: name
        in: query
        type: string
        required: true
        description: 생성할 유저 이름
      - name: email
        in: query
        type: string
        description: 생성할 유저 이메일 (미입력 시 '이름@test.com'으로 자동생성)
    responses:
      200:
        description: 유저 생성 완료 메시지 반환
    """
    username = request.args.get('name', 'default_user')
    email = request.args.get('email', f'{username}@test.com')
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        login_user(existing_user)
        return f"이미 존재하는 유저입니다. '{existing_user.username}'으로 로그인 되었습니다."

    new_user = User(username=username, email=email)
    db.session.add(new_user)
    db.session.commit()
    
    login_user(new_user)
    return f"유저 '{username}' 생성 및 로그인 완료! (ID: {new_user.id})"


# --- 3. 로그아웃 API ---
@auth_blueprint.route('/logout')
@login_required
def logout():
    """ 현재 사용자 로그아웃 """
    logout_user()
    return api_response(success=True, message="로그아웃 되었습니다.")


