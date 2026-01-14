import os

from flask import Blueprint, jsonify, request, current_app
from app.models import User, TypingResult, TypingText
from app.utils import api_response
from app.database import db
from flasgger import swag_from


user_blueprint = Blueprint('user', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GET_USER_PROFILE_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_user_profile.yaml')
GET_HISTORY_ALL_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_history_all.yaml')
GET_HISTORY_RECENT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_history_recent.yaml')
GET_HISTORY_GENRE_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_history_genre.yaml')
GET_USER_RANKING_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_user_ranking.yaml')
GET_USER_FAVORITE_IDS_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_user_favorites.yaml')
# 1. 내 프로필 요약 정보
@user_blueprint.route('/profile/<int:user_id>', methods=['GET'])
@swag_from(GET_USER_PROFILE_YAML_PATH)
def get_user_profile(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)

        # 정보를 계정 정보와 상세 통계(stats)로 구조화
        data = {
            "account": {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "profile_pic": user.profile_pic,
                "ranking_score": user.ranking_score  
            },
            "stats": {
                "play_count": user.play_count,
                "max_combo": user.max_combo,
                "avg_accuracy": user.avg_accuracy,
                "best_cpm": user.best_cpm,
                "avg_cpm": user.avg_cpm,
                "best_wpm": user.best_wpm,
                "avg_wpm": user.avg_wpm
            }
        }

        current_app.logger.info(f"👤 [프로필조회] 유저 {user.username}(ID:{user.id})의 모든 정보를 조회했습니다.")

        return api_response(
            success=True, 
            data=data, 
            message="프로필 및 모든 통계 정보를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 프로필 조회 중 서버 에러: {str(e)}")
        return api_response(success=False, error_code=500, message="조회 중 오류가 발생했습니다.", status_code=500)

# 2. 유저 연습 결과 조회 <All>
@user_blueprint.route('/history/all/<int:user_id>', methods=['GET'])
@swag_from(GET_HISTORY_ALL_YAML_PATH)
def get_all_history(user_id):
    
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
@swag_from(GET_HISTORY_RECENT_YAML_PATH)
def get_recent_history(user_id):
    
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
@swag_from(GET_HISTORY_GENRE_YAML_PATH)
def get_history_by_genre(user_id):
   
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
    
# 5. 전체 유저 랭킹 조회 (모든 통계 정보 포함)
@user_blueprint.route('/ranking', methods=['GET'])
@swag_from(GET_USER_RANKING_YAML_PATH)
def get_user_ranking():
  
    try:
        limit_val = request.args.get('limit', default=10, type=int)

        # ranking_score 내림차순 정렬
        top_users = User.query.filter(User.ranking_score != None)\
                        .order_by(User.ranking_score.desc())\
                        .limit(limit_val).all()

        ranking_list = []
        for index, user in enumerate(top_users):
            ranking_list.append({
                "rank": index + 1,
                "account": {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "profile_pic": user.profile_pic,
                    "ranking_score": user.ranking_score
                },
                "stats": {
                    "play_count": user.play_count,
                    "max_combo": user.max_combo,
                    "avg_accuracy": user.avg_accuracy,
                    "best_cpm": user.best_cpm,
                    "avg_cpm": user.avg_cpm,
                    "best_wpm": user.best_wpm,
                    "avg_wpm": user.avg_wpm
                }
            })

        current_app.logger.info(f"🏆 [랭킹조회] TOP {limit_val} 유저 데이터 반환 완료")

        return api_response(
            success=True,
            data=ranking_list,
            message=f"상위 {len(ranking_list)}명의 상세 정보를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 랭킹 조회 에러: {str(e)}")
        return api_response(success=False, error_code=500, message="서버 오류 발생", status_code=500)
    

# 6. 유저가 찜한 글 ID 목록 조회
@user_blueprint.route('/favorites/ids/<int:user_id>', methods=['GET'])
@swag_from(GET_USER_FAVORITE_IDS_YAML_PATH) # 나중에 YAML 연결
def get_favorite_text_ids(user_id):
    try:
        # 1. 유저 존재 여부 확인
        user = User.query.get(user_id)
        if not user:
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)

        favorite_ids = [text.id for text in user.favorite_texts]

        current_app.logger.info(f" [찜ID조회] 유저 {user_id} - 총 {len(favorite_ids)}개의 찜한 글 ID 반환")

        return api_response(
            success=True,
            data={"favorite_text_ids": favorite_ids},
            message=f"유저가 찜한 글 ID {len(favorite_ids)}개를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f" 찜한 ID 조회 에러: {str(e)}")
        return api_response(success=False, error_code=500, message="조회 중 서버 오류가 발생했습니다.", status_code=500)