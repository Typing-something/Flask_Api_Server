from flask import Blueprint, jsonify, request, current_app
from models import User, TypingResult, TypingText
from utils import api_response
from database import db

user_blueprint = Blueprint('user', __name__)

# 1. 내 프로필 요약 정보
@user_blueprint.route('/profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """
    유저 프로필 상세 정보 조회
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/profile/5`
      - 특정 유저의 계정 정보와 타자 연습 통계(누적 데이터)를 한꺼번에 가져옵니다.
      - 마이페이지 상단 프로필 영역이나 유저 정보 확인용으로 사용됩니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 정보를 조회할 유저의 고유 ID
    responses:
      200:
        description: 유저 프로필 및 통계 정보 반환
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "프로필 조회 성공"}
            data:
              type: object
              properties:
                user_id: {type: integer, example: 5}
                username: {type: string, example: "타자왕민성"}
                email: {type: string, example: "user@example.com"}
                profile_pic: {type: string, example: "https://.../profile.jpg"}
                stats:
                  type: object
                  description: 유저의 누적 연습 통계
                  properties:
                    play_count: {type: integer, description: "총 연습 횟수", example: 120}
                    max_combo: {type: integer, description: "역대 최고 콤보", example: 154}
                    avg_accuracy: {type: number, description: "전체 평균 정확도 (%)", example: 97.5}
      404:
        description: 존재하지 않는 유저 ID 요청 시
      500:
        description: 서버 내부 오류
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)

        # 정보를 계정 정보와 통계(stats)로 분리하여 구조화
        data = {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,  # 누락되었던 이메일 추가
            "profile_pic": user.profile_pic,
            "stats": {
                "play_count": user.play_count,
                "max_combo": user.max_combo,
                "avg_accuracy": user.avg_accuracy
            }
        }

        # [로그 추가]
        current_app.logger.info(f"👤 [프로필조회] 유저 {user.username}(ID:{user.id})의 정보를 조회했습니다.")

        return api_response(success=True, data=data, message="프로필 정보를 성공적으로 가져왔습니다.")

    except Exception as e:
        current_app.logger.error(f"❌ 프로필 조회 중 서버 에러: {str(e)}")
        return api_response(success=False, error_code=500, message="조회 중 오류가 발생했습니다.", status_code=500)

# 2. 나의 연습 결과 조회 <All>
@user_blueprint.route('/history/all/<int:user_id>', methods=['GET'])
def get_all_history(user_id):
    """
    유저의 전체 타자 연습 기록 조회 (상세 정보 포함)
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/history/all/5`
      - 유저의 모든 연습 기록을 최신순으로 가져옵니다.
      - **INNER JOIN**을 통해 원본 글이 삭제된 기록은 결과에서 제외됩니다.
      - 최근 기록 API와 동일한 `text_info` 구조를 반환하여 프론트엔드 컴포넌트 재사용이 가능합니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 기록을 조회할 유저의 ID
    responses:
      200:
        description: 전체 기록 리스트 반환
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "전체 기록 조회 성공"}
            data:
              type: array
              items:
                type: object
                properties:
                  result_id: {type: integer}
                  cpm: {type: integer}
                  wpm: {type: integer}
                  accuracy: {type: number}
                  combo: {type: integer}
                  date: {type: string}
                  text_info:
                    type: object
                    properties:
                      id: {type: integer}
                      title: {type: string}
                      author: {type: string}
                      genre: {type: string}
                      image_url: {type: string}
    """
    try:
        # INNER JOIN을 사용하여 TypingText가 존재하는(삭제되지 않은) 결과만 필터링
        results = db.session.query(TypingResult)\
                  .join(TypingText)\
                  .filter(TypingResult.user_id == user_id)\
                  .order_by(TypingResult.created_at.desc()).all()
        
        history = []
        for r in results:
            t = r.typing_text # join 했으므로 바로 접근 가능
            history.append({
                "result_id": r.id,
                "cpm": r.cpm,
                "wpm": r.wpm,
                "accuracy": r.accuracy,
                "combo": r.combo,
                "date": r.created_at.strftime('%Y-%m-%d %H:%M'),
                "text_info": {
                    "id": t.id,
                    "title": t.title,
                    "author": t.author,
                    "genre": t.genre,
                    "image_url": t.image_url
                }
            })

        # [로그 추가]
        current_app.logger.info(f"📊 [전체조회] 유저 {user_id}의 전체 기록 {len(history)}개를 로드했습니다.")

        return api_response(
            success=True, 
            data=history, 
            message=f"총 {len(history)}개의 기록을 성공적으로 조회했습니다."
        )
    except Exception as e:
        current_app.logger.error(f"❌ 전체 기록 조회 오류: {str(e)}")
        return api_response(success=False, message="전체 기록 조회 중 오류가 발생했습니다.", status_code=500)
    
# 3. 나의 연습 결과 조회 <요청 갯수>
@user_blueprint.route('/history/recent/<int:user_id>', methods=['GET'])
def get_recent_history(user_id):
    """
    유저의 최근 연습 기록 상세 조회 (N개)
    ---
    tags:
      - User
    description: |
      **기능:**
      - 특정 유저가 최근에 연습한 타자 기록을 가져옵니다.
      - 연습 결과뿐만 아니라, 해당 연습에 사용된 글의 상세 정보(제목, 작가, 장르 등)를 포함합니다.
      
      **호출 예시:** `GET /user/history/recent/5?limit=10`
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: 기록을 조회할 유저의 고유 ID
      - name: limit
        in: query
        type: integer
        required: false
        default: 5
        description: 가져올 최신 기록의 개수
    responses:
      200:
        description: 최근 기록 리스트 및 연관 글 정보 반환
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "최근 5개 상세 기록 조회를 완료했습니다."
            data:
              type: array
              items:
                type: object
                properties:
                  result_id:
                    type: integer
                    description: 연습 결과 기록의 고유 ID
                  cpm:
                    type: integer
                    description: 분당 타자수 (Characters Per Minute)
                  wpm:
                    type: integer
                    description: 분당 단어수 (Words Per Minute)
                  accuracy:
                    type: number
                    format: float
                    description: 타자 정확도 (%)
                  combo:
                    type: integer
                    description: 최대 달성 콤보
                  date:
                    type: string
                    description: 연습 일시 (YYYY-MM-DD HH:mm)
                  text_info:
                    type: object
                    description: 연습한 글의 상세 데이터
                    properties:
                      id: {type: integer, description: "글 ID"}
                      title: {type: string, description: "글 제목"}
                      author: {type: string, description: "작가명"}
                      genre: {type: string, description: "장르"}
                      image_url: {type: string, description: "S3 이미지 URL"}
                      content_preview: {type: string, description: "본문 앞부분 요약"}
      500:
        description: 서버 오류 발생
    """
    try:
        limit_val = request.args.get('limit', default=5, type=int)

        # 1. DB 조회 (연관된 TypingText 정보를 한 번에 가져오기 위해 조인 쿼리 고려 가능)
        results = TypingResult.query.filter_by(user_id=user_id)\
                  .order_by(TypingResult.created_at.desc())\
                  .limit(limit_val).all()
        
        # 2. 결과 가공 (모든 정보 포함)
        history = []
        for r in results:
            t = r.typing_text  # 모델의 relationship 활용
            history.append({
                "result_id": r.id,
                "cpm": r.cpm,
                "wpm": r.wpm,
                "accuracy": r.accuracy,
                "combo": r.combo,
                "date": r.created_at.strftime('%Y-%m-%d %H:%M'),
                "text_info": {
                    "id": t.id if t else None,
                    "title": t.title if t else "삭제된 글",
                    "author": t.author if t else "정보 없음",
                    "genre": t.genre if t else "정보 없음",
                    "image_url": t.image_url if t else None,
                    "content_preview": t.content if t else "없음"
                }
            })

        current_app.logger.info(f"📜 [기록조회] 유저 {user_id}의 최근 기록 {len(history)}개를 반환했습니다.")

        return api_response(
            success=True, 
            data=history, 
            message=f"최근 {len(history)}개 상세 기록 조회를 완료했습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 최근 기록 조회 중 오류: {str(e)}")
        return api_response(success=False, message="서버 오류로 기록을 불러오지 못했습니다.", status_code=500)
# 4. 나의 연습 결과 조회 <특정장르>
@user_blueprint.route('/history/genre/<int:user_id>', methods=['GET'])
def get_history_by_genre(user_id):
    """
    유저의 장르별 연습 기록 필터링 조회 (상세 정보 포함)
    ---
    tags:
      - User
    description: |
      **요청 URL:** `GET /user/history/genre/5?genre=k-pop`
      - 특정 유저의 기록 중, 요청한 장르(genre)에 해당하는 데이터만 모아서 반환합니다.
      - 결과 데이터 구조는 전체/최근 기록 API와 동일하게 유지하여 프론트엔드 호환성을 높였습니다.
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
        description: "필터링할 장르명 (예: k-pop, proverb, novel, poem 등)"
    responses:
      200:
        description: 해당 장르의 상세 기록 리스트 반환
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "k-pop 장르 기록 조회 성공"}
            data:
              type: array
              items:
                type: object
                properties:
                  result_id: {type: integer}
                  cpm: {type: integer}
                  wpm: {type: integer}
                  accuracy: {type: number}
                  combo: {type: integer}
                  date: {type: string}
                  text_info:
                    type: object
                    properties:
                      id: {type: integer}
                      title: {type: string}
                      author: {type: string}
                      genre: {type: string}
                      image_url: {type: string}
    """
    try:
        genre_param = request.args.get('genre')
        if not genre_param:
            return api_response(success=False, error_code=400, message="조회할 장르를 지정해주세요.", status_code=400)

        # TypingText 테이블과 JOIN하여 장르 필터링 수행
        results = db.session.query(TypingResult)\
                  .join(TypingText)\
                  .filter(TypingResult.user_id == user_id)\
                  .filter(TypingText.genre == genre_param)\
                  .order_by(TypingResult.created_at.desc()).all()
        
        history = []
        for r in results:
            t = r.typing_text
            history.append({
                "result_id": r.id,
                "cpm": r.cpm,
                "wpm": r.wpm,
                "accuracy": r.accuracy,
                "combo": r.combo,
                "date": r.created_at.strftime('%Y-%m-%d %H:%M'),
                "text_info": {
                    "id": t.id,
                    "title": t.title,
                    "author": t.author,
                    "genre": t.genre,
                    "image_url": t.image_url
                }
            })

        # [로그 추가] 
        current_app.logger.info(f"📂 [장르조회] 유저 {user_id}번이 '{genre_param}' 장르 기록 {len(history)}개를 조회했습니다.")

        return api_response(
            success=True, 
            data=history, 
            message=f"'{genre_param}' 장르 기록 {len(history)}개를 성공적으로 가져왔습니다."
        )
    except Exception as e:
        current_app.logger.error(f"❌ 장르별 조회 오류: {str(e)}")
        return api_response(success=False, error_code=500, message="조회 중 서버 오류가 발생했습니다.", status_code=500)