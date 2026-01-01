from flask import Blueprint, request, redirect, url_for, jsonify , current_app
from models import User, db
from flask_login import login_user, logout_user, login_required, current_user
from utils import api_response
import uuid

auth_blueprint = Blueprint('auth', __name__)

# --- 1. 구글 로그인 처리 API ---
@auth_blueprint.route('/google', methods=['POST'])
def google_login():
    """
    구글 소셜 로그인/회원가입 API (이메일 기준)
    ---
    tags:
      - Auth
    description: |
      **요청 URL:** `POST /auth/google`
      - 프론트엔드가 보낸 이메일을 기준으로 신규 유저는 가입, 기존 유저는 로그인을 처리합니다.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            email: {type: string, example: "user@gmail.com"}
            username: {type: string, example: "홍길동"}
            profile_pic: {type: string, example: "https://photo.url/..."}
    responses:
      200:
        description: 성공 (user_id 반환)
    """
    try:
        data = request.get_json()
        email = data.get('email')
        username = data.get('username', 'User') # 이름이 없을 경우 기본값
        profile_pic = data.get('profile_pic')

        if not email:
            return api_response(success=False, message="이메일 정보가 누락되었습니다.", status_code=400)

        # 이메일로 기존 유저 찾기
        user = User.query.filter_by(email=email).first()

        if not user:
            # [수정] 닉네임 중복 방지 로직
            # DB에 동일한 username이 있는지 확인
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                # 중복된다면 이름 뒤에 랜덤한 값이나 이메일 앞부분을 붙여 고유하게 만듦
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
            # 정보 업데이트
            user.username = username
            user.profile_pic = profile_pic
            db.session.commit()
            message = "로그인 성공"

        login_user(user)

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

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"로그인 처리 중 에러: {str(e)}")
        return api_response(success=False, message="서버 오류", status_code=500)

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


