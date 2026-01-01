from flask import Blueprint, jsonify, request, current_app
from models import User, TypingResult, TypingText
from utils import api_response
from database import db

user_blueprint = Blueprint('user', __name__)

# 1. 내 프로필 요약 정보
@user_blueprint.route('/profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """
    유저 프로필 요약 정보 조회 (상단 바/마이페이지용)
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/profile/5`
      - 유저의 닉네임, 플레이 횟수, 평균 정확도, 최대 콤보 등 요약 정보를 가져옵니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 정보를 조회할 유저의 ID
    responses:
      200:
        description: 유저 요약 정보 반환
      404:
        description: 유저를 찾을 수 없음
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return api_response(success=False, message="유저를 찾을 수 없습니다.", status_code=404)

        data = {
            "username": user.username,
            "play_count": user.play_count,
            "avg_accuracy": user.avg_accuracy,
            "max_combo": user.max_combo,
            "profile_pic": user.profile_pic
        }
        return api_response(success=True, data=data, message="프로필 조회 성공")
    except Exception as e:
        return api_response(success=False, message="조회 중 오류 발생", status_code=500)

# 2. 나의 연습 결과 조회 <All>
@user_blueprint.route('/history/all/<int:user_id>', methods=['GET'])
def get_all_history(user_id):
    """
    유저의 전체 타자 연습 기록 조회 (삭제된 글 제외)
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/history/all/5`
      - 해당 유저가 연습한 모든 기록을 최신순으로 가져오며, 원본 글이 삭제된 기록은 자동으로 제외됩니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 기록을 조회할 유저의 ID
    responses:
      200:
        description: 전체 기록 리스트 반환
    """
    try:
        results = db.session.query(TypingResult)\
                  .join(TypingText)\
                  .filter(TypingResult.user_id == user_id)\
                  .order_by(TypingResult.created_at.desc()).all()
        
        history = [{
            "text_title": r.typing_text.title,
            "cpm": r.cpm,
            "accuracy": r.accuracy,
            "combo": r.combo,
            "date": r.created_at.strftime('%Y-%m-%d %H:%M')
        } for r in results]

        return api_response(success=True, data=history, message="전체 기록 조회 성공")
    except Exception as e:
        current_app.logger.error(f"전체 기록 조회 오류: {str(e)}")
        return api_response(success=False, message="조회 중 오류 발생", status_code=500)
    
# 3. 나의 연습 결과 조회 <요청 갯수>
@user_blueprint.route('/history/recent/<int:user_id>', methods=['GET'])
def get_recent_history(user_id):
    """
    유저의 최근 연습 기록 N개 조회
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/history/recent/5?limit=10`
      - 지정한 유저의 최신 기록을 요청한 개수(`limit`)만큼 가져옵니다.
      - `limit` 파라미터가 없으면 기본적으로 5개를 가져옵니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 기록을 조회할 유저의 ID
      - name: limit
        in: query
        type: integer
        required: false
        default: 5
        description: 가져올 기록의 개수
    responses:
      200:
        description: 최근 기록 리스트 반환
    """
    try:
        # 1. 쿼리 스트링에서 limit 값을 가져옴 (기본값 5)
        limit_val = request.args.get('limit', default=5, type=int)

        # 2. DB 조회 시 limit_val 적용
        # 삭제된 글을 제외하고 싶다면 여기서 .join(TypingText)를 추가해도 됩니다.
        results = TypingResult.query.filter_by(user_id=user_id)\
                  .order_by(TypingResult.created_at.desc())\
                  .limit(limit_val).all()
        
        history = [{
            "text_title": r.typing_text.title if r.typing_text else "삭제된 글",
            "cpm": r.cpm,
            "accuracy": r.accuracy,
            "combo": r.combo,
            "date": r.created_at.strftime('%Y-%m-%d %H:%M')
        } for r in results]

        return api_response(
            success=True, 
            data=history, 
            message=f"최근 {len(history)}개 기록 조회 성공"
        )
    except Exception as e:
        current_app.logger.error(f"최근 기록 조회 중 오류: {str(e)}")
        return api_response(success=False, message="최근 기록 조회 중 오류", status_code=500)

# 4. 나의 연습 결과 조회 <특정장르>
@user_blueprint.route('/history/genre/<int:user_id>', methods=['GET'])
def get_history_by_genre(user_id):
    """
    유저의 장르별 연습 기록 필터링 조회
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/history/genre/5?genre=k-pop`
      - 특정 장르에 해당하는 연습 기록만 필터링하여 가져옵니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 기록을 조회할 유저의 ID
      - name: genre
        in: query
        type: string
        required: true
        description: 필터링할 장르명 (예: k-pop, proverb 등)
    responses:
      200:
        description: 해당 장르의 기록 리스트 반환
      400:
        description: 장르 파라미터 누락
    """
    try:
        genre_param = request.args.get('genre')
        if not genre_param:
            return api_response(success=False, message="장르를 지정해주세요.", status_code=400)

        results = db.session.query(TypingResult)\
                  .join(TypingText)\
                  .filter(TypingResult.user_id == user_id)\
                  .filter(TypingText.genre == genre_param)\
                  .order_by(TypingResult.created_at.desc()).all()
        
        history = [{
            "text_title": r.typing_text.title,
            "cpm": r.cpm,
            "accuracy": r.accuracy,
            "combo": r.combo,
            "date": r.created_at.strftime('%Y-%m-%d %H:%M')
        } for r in results]

        return api_response(success=True, data=history, message=f"{genre_param} 장르 기록 조회 성공")
    except Exception as e:
        current_app.logger.error(f"장르별 조회 오류: {str(e)}")
        return api_response(success=False, message="장르별 조회 중 오류 발생", status_code=500)