from flask import Blueprint, request, redirect, url_for, jsonify
from models import User, db
from flask_login import login_user, logout_user, login_required, current_user



auth_blueprint = Blueprint('auth', __name__)

# --- 1. 구글 로그인 처리 API ---
@auth_blueprint.route('/google', methods=['POST'])
def google_login():
    """
    구글 소셜 로그인 처리 API
    ---
    tags:
      - Auth
    description: |
      **요청 URL:** `POST /auth/google`
      **동작:** 프론트엔드에서 받은 구글 유저 정보를 바탕으로 회원가입 또는 로그인을 처리합니다.
      **JSON Body 예시:**
      ```json
      {
        "google_id": "1029384756",
        "email": "user@gmail.com",
        "username": "홍길동"
      }
      ```
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            google_id: {type: string, example: "1029384756"}
            email: {type: string, example: "user@gmail.com"}
            username: {type: string, example: "홍길동"}
    responses:
      200:
        description: 로그인 성공
      400:
        description: 필수 정보 누락
    """
    data = request.get_json()
    google_id = data.get('google_id')
    email = data.get('email')
    username = data.get('username')

    if not google_id or not email:
        return jsonify({"error": "필수 정보가 누락되었습니다."}), 400

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(username=username, email=email, google_id=google_id)
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return jsonify({
        "message": "구글 로그인 성공",
        "user_id": user.id,
        "username": user.username
    }), 200


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
    """
    현재 사용자 로그아웃
    ---
    tags:
      - Auth
    description: 현재 로그인된 세션을 종료합니다.
    responses:
      200:
        description: 로그아웃 성공 메시지
    """
    logout_user()
    return jsonify({"message": "로그아웃 되었습니다."}), 200


# --- 4. 내 정보 확인 API ---
@auth_blueprint.route('/me')
def get_me():
    """
    현재 로그인된 정보 확인
    ---
    tags:
      - Auth
    description: 세션 정보를 바탕으로 현재 로그인된 유저의 정보를 반환합니다.
    responses:
      200:
        description: 로그인 여부 및 유저 데이터
    """
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email
            }
        })
    return jsonify({"logged_in": False}), 200