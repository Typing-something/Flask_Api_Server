import os
import boto3
import uuid
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, current_app
from app.database import db
from app.models import TypingText, TypingResult, User
from datetime import datetime
from app.utils import api_response
from sqlalchemy import func
from flasgger import swag_from
from .helpers import validate_result_data, update_user_statistics, recalculate_user_statistics

# S3 클라이언트 설정 (환경변수 로드)
s3 = boto3.client('s3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'ap-northeast-2')
)
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

text_blueprint = Blueprint('text', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


ADD_TEXT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'add_text.yaml')
GET_RANDOM_TEXTS_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_random_texts.yaml')
GET_BY_GENRE_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_text_by_genre.yaml')
GET_ALL_TEXTS_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_all_texts.yaml')
GET_TEXT_DETAIL_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_text_detail.yaml')
DELETE_TEXT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'delete_text.yaml')
POST_RESULT_YAML_PATH =  os.path.join(BASE_DIR, 'swagger', 'save_result.yaml')
GET_BEST_DATA_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_best_data.yaml')
POST_FAVORITE_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'post_favorite_text.yaml')
GET_USER_TEXT_RESULT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_user_text_result.yaml')
GET_RESULT_DETAIL_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'get_user_detail_result.yaml')
DELETE_RESULT_YAML_PATH = os.path.join(BASE_DIR, 'swagger', 'delete_result.yaml')


# 0. 글쓰기 페이지 (HTML 폼 제공 및 저장 - 이미지 업로드 기능 추가)
@text_blueprint.route('/add', methods=['GET', 'POST'])
@swag_from(ADD_TEXT_YAML_PATH)
def add_text():
  
    if request.method == 'POST':
        genre = request.form.get('genre')
        title = request.form.get('title')
        author = request.form.get('author')
        content = request.form.get('content')
        
        image_file = request.files.get('image')
        image_url = None

        # 1. 이미지 파일 처리 로직 강화
        if image_file and image_file.filename != '':
            # [수정] os.path.splitext를 사용하여 확장자를 안전하게 추출
            # rsplit('.', 1) 방식은 점(.)이 없는 파일에서 IndexError를 유발함
            _, ext = os.path.splitext(image_file.filename)
            ext = ext.lower() # .jpg, .png 등

            # [추가] 허용된 확장자인지 체크하는 로직 (보안 강화)
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                return api_response(success=False, message="지원하지 않는 파일 형식입니다.", status_code=400)

            filename = f"texts/{uuid.uuid4()}{ext}" # texts/uuid.jpg 형태
            
            try:
                # 2. S3 업로드 실행
                s3.upload_fileobj(
                    image_file,
                    BUCKET_NAME,
                    filename,
                    ExtraArgs={
                        "ContentType": image_file.content_type,
                        "ACL": "public-read"
                    }
                )
                # 3. S3 URL 생성 (f-string 가독성 개선)
                region = os.environ.get('AWS_REGION', 'ap-northeast-2')
                image_url = f"https://{BUCKET_NAME}.s3.{region}.amazonaws.com/{filename}"

            except Exception as e:
                current_app.logger.error(f"S3 업로드 에러: {str(e)}") 
                return api_response(success=False, message="이미지 저장 중 오류가 발생했습니다.", status_code=500)

        # 4. DB 저장 (기존 로직 동일)
        try:
            new_entry = TypingText(
                genre=genre, 
                title=title, 
                author=author, 
                content=content,
                image_url=image_url
            )
            db.session.add(new_entry)
            db.session.commit()
            
            current_app.logger.info(f"✅ [{title}] 등록 성공")

            return api_response(
                success=True, 
                message="성공적으로 등록되었습니다.", 
                data={"id": new_entry.id, "image_url": image_url},
                status_code=201
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"DB 저장 에러: {str(e)}")
            return api_response(success=False, message="데이터베이스 저장 실패", status_code=500)
    
    return render_template('add_text.html')

# 1. 메인용: 글 전체 조회
@text_blueprint.route('/all', methods=['GET'])
@swag_from(GET_ALL_TEXTS_YAML_PATH) # YAML 경로 설정 확인하세요!
def get_all_texts():
    try:
        # DB의 모든 텍스트를 ID 순으로 정렬하여 싹 다 가져옴
        texts = TypingText.query.order_by(TypingText.id.asc()).all()
        
        texts_list = [{
            "id": t.id,
            "genre": t.genre,
            "title": t.title,
            "author": t.author,
            "content": t.content,
            "image_url": t.image_url
        } for t in texts]

        current_app.logger.info(f" [전체조회] 총 {len(texts_list)}개의 텍스트를 불러왔습니다.")

        return api_response(
            success=True, 
            data=texts_list, 
            message=f"전체 글 {len(texts_list)}개를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 전체 텍스트 조회 중 에러: {str(e)}")
        return api_response(
            success=False, 
            data=[], 
            error_code=500, 
            message="전체 목록을 불러오는 중 서버 오류가 발생했습니다.",
            status_code=500
        )



# 2. 메인용: 랜덤 <limit>개 조회
@text_blueprint.route('/main/<int:limit_val>', methods=['GET'])
@swag_from(GET_RANDOM_TEXTS_YAML_PATH)
def get_random_texts(limit_val):
    try:
        # 1. 파라미터 추출 및 유효성 검사
        u_id = request.args.get('user_id') # 유저 ID 수신
        limit = request.args.get('limit', default=limit_val, type=int)
        if limit > 50: 
            limit = 50

        # 2. 랜덤 글 데이터 가져오기

        

        if current_app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
            texts = TypingText.query.order_by(func.random()).limit(limit).all()
        else:
            texts = TypingText.query.order_by(func.rand()).limit(limit).all()

        # 3. 유저가 있다면 찜한 글 ID 목록을 Set으로 추출 (성능 최적화)
        favorite_ids = set()
        if u_id:
            user = User.query.get(u_id)
            if user:
                # 유저가 찜한 모든 글의 ID만 모아서 집합으로 만듭니다.
                favorite_ids = {f.id for f in user.favorite_texts}

        # 4. 데이터 가공 (is_favorite 필드 추가)
        texts_list = []
        for t in texts:
            texts_list.append({
                "id": t.id,
                "genre": t.genre,
                "title": t.title,
                "author": t.author,
                "content": t.content,
                "image_url": t.image_url,
                "is_favorite": t.id in favorite_ids # 집합에 ID가 있으면 True, 없으면 False
            })

        current_app.logger.info(f" [랜덤조회] 유저 {u_id if u_id else '비회원'} - {len(texts_list)}개 반환")

        return api_response(
            success=True, 
            data=texts_list, 
            message=f"랜덤 글 {len(texts_list)}개를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 랜덤 조회 에러: {str(e)}")
        return api_response(success=False, data=[], error_code=500, status_code=500)


# 2. 장르별 목록 필터링
@text_blueprint.route('/', methods=['GET'])
@swag_from(GET_BY_GENRE_YAML_PATH)
def get_texts_by_genre():
 
    try:
        genre_param = request.args.get('genre')

        if genre_param:
            texts = TypingText.query.filter_by(genre=genre_param).all()
            message = f"'{genre_param}' 장르의 글 목록을 성공적으로 가져왔습니다."
        else:
            texts = TypingText.query.all()
            message = "전체 글 목록을 성공적으로 가져왔습니다."
        
        texts_list = [{
            "id": t.id, 
            "genre": t.genre, 
            "title": t.title, 
            "author": t.author,
            "content": t.content,
            "image_url": t.image_url
        } for t in texts]

        return api_response(
            success=True, 
            data=texts_list, 
            message=message
        )
    except Exception as e:
        current_app.logger.error(f"장르별 목록 조회 중 오류: {str(e)}")
        return api_response(
            success=False,
            data=[], # 프론트엔드에서 리스트 순회 시 에러 나지 않게 빈 배열 전달
            error_code=500,
            message="글 목록을 불러오는 중 서버 내부 오류가 발생했습니다.",
            status_code=500
        )

@text_blueprint.route('/<int:text_id>', methods=['GET'])
@swag_from(GET_TEXT_DETAIL_YAML_PATH)
def get_text_by_id(text_id):
    try:
        # 1. 글 정보 조회
        t = TypingText.query.get(text_id)
        
        if not t:
            return api_response(
                success=False, 
                error_code=404, 
                message="해당 글을 찾을 수 없습니다.", 
                status_code=404
            )

        # 2. 로그인한 유저 정보 확인 (찜 여부 및 최고 기록 조회용)
        u_id = request.args.get('user_id') 
        best_record = None
        is_favorite = False # 기본값은 False

        if u_id:
            user = User.query.get(u_id)
            if user:
                # 찜 여부 확인
                is_favorite = user.favorite_texts.filter_by(id=text_id).first() is not None

                # 해당 유저의 이 글에 대한 최고 기록 조회
                best = TypingResult.query.filter_by(user_id=u_id, text_id=text_id)\
                       .order_by(TypingResult.cpm.desc()).first()
                
                if best:
                    best_record = {
                        "cpm": best.cpm, 
                        "wpm": best.wpm, 
                        "accuracy": best.accuracy, 
                        "combo": best.combo,
                        "date": best.created_at.strftime('%Y-%m-%d')
                    }

        # 3. 모든 데이터를 규격화된 포맷으로 합치기
        data = {
            "text_info" : {
                "id": t.id, 
                "genre": t.genre, 
                "title": t.title, 
                "author": t.author, 
                "content": t.content,
                "image_url": t.image_url,
                "is_favorite": is_favorite 
            }, 
            "my_best": best_record 
        }

        current_app.logger.info(f"🔍 [상세조회] 유저 {u_id if u_id else '비회원'} - '{t.title}' (찜:{is_favorite}) 조회 완료")

        return api_response(
            success=True, 
            data=data, 
            message="글 상세 정보와 최고 기록을 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"상세 조회 중 서버 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="데이터를 불러오는 중 서버 내부 오류가 발생했습니다.", 
            status_code=500
        )

# 4. 특정 글 삭제
@text_blueprint.route('/<int:text_id>', methods=['DELETE'])
@swag_from(DELETE_TEXT_YAML_PATH)
def delete_text(text_id):
    try:
        # 1. 삭제할 글이 존재하는지 확인
        text = TypingText.query.get(text_id)
        
        if not text:
            return api_response(
                success=False, 
                error_code=404, 
                message="삭제할 글을 찾을 수 없습니다.", 
                status_code=404
            )

        db.session.delete(text)
        db.session.commit()

        current_app.logger.info(f"[글 삭제] ID: {text_id}, 제목: '{text.title}' 삭제 완료")

        return api_response(
            success=True, 
            message=f"ID {text_id}번 글이 성공적으로 삭제되었습니다."
        )

    except Exception as e:
        db.session.rollback() # 오류 발생 시 롤백
        current_app.logger.error(f"❌ 글 삭제 중 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="글 삭제 중 서버 오류가 발생했습니다.",
            status_code=500
        )

# 5. 타자 결과 저장 및 실시간 랭킹 점수 갱신
@text_blueprint.route('/results', methods=['POST'])
@swag_from(POST_RESULT_YAML_PATH)
def save_typing_result():
    try:
        data = request.get_json()
        
        # 1. 데이터 검증
        is_valid, error_message, parsed_data = validate_result_data(data)
        if not is_valid:
            return api_response(success=False, error_code=400, message=error_message, status_code=400)
        
        # 2. 결과 기록(TypingResult) 객체 생성
        new_result = TypingResult(
            user_id=parsed_data['user_id'],
            text_id=parsed_data['text_id'],
            cpm=parsed_data['cpm'],
            wpm=parsed_data['wpm'],
            accuracy=parsed_data['accuracy'],
            combo=parsed_data['combo']
        )
        db.session.add(new_result)

        # 3. 유저 조회 및 통계 업데이트
        user = User.query.get(parsed_data['user_id'])
        if not user:
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)
        
        # 통계 업데이트
        update_result = update_user_statistics(
            user,
            parsed_data['cpm'],
            parsed_data['wpm'],
            parsed_data['accuracy'],
            parsed_data['combo']
        )

        # 4. 최종 DB 반영
        db.session.commit()

        current_app.logger.info(f"🏆 유저 {user.username} 결과 저장 및 랭킹 점수({user.ranking_score}) 갱신 완료")

        return api_response(
            success=True, 
            data={
                "result_id": new_result.id, 
                "play_count": user.play_count,
                "ranking_score": user.ranking_score,
                "avg_accuracy": user.avg_accuracy,
                "best_cpm": user.best_cpm,
                "is_new_record": update_result['is_new_combo_record']
            }, 
            message="연습 결과 저장 및 랭킹 업데이트 성공",
            status_code=201
        )

    except Exception as e:
        db.session.rollback() 
        current_app.logger.error(f"결과 저장 에러: {str(e)}")
        return api_response(success=False, error_code=500, message="서버 오류 발생", status_code=500)

# 6. 글별 최고 점수
@text_blueprint.route('/results/best', methods=['GET'])
@swag_from(GET_BEST_DATA_YAML_PATH)
def get_global_best_score():
    
    try:
        t_id = request.args.get('text_id')
        if not t_id:
            return api_response(success=False, error_code=400, message="text_id가 필요합니다.", status_code=400)

      
        best = db.session.query(TypingResult, User.username, User.profile_pic)\
                .join(User, TypingResult.user_id == User.id)\
                .filter(TypingResult.text_id == t_id)\
                .order_by(TypingResult.cpm.desc()).first()
        
        if not best:
            return api_response(
                success=True, 
                data={
                    "top_player": "No record", 
                    "profile_pic": None,
                    "best_cpm": 0, 
                    "best_wpm": 0, 
                    "best_accuracy": 0,
                    "best_combo": 0
                }, 
                message="아직 등록된 기록이 없습니다."
            )

        # 데이터 언팩 (쿼리 결과에서 객체와 유저 정보 분리)
        res, uname, upic = best
        data = {
            "top_player": uname, 
            "profile_pic": upic,
            "best_cpm": res.cpm,
            "best_wpm": res.wpm, 
            "best_accuracy": res.accuracy,
            "best_combo": res.combo,
            "date": res.created_at.strftime('%Y-%m-%d')
        }

        # [한글 로그 추가]
        current_app.logger.info(f" 글 ID:{t_id}의 1등 '{uname}' ({res.cpm}타) 정보를 조회했습니다.")

        return api_response(success=True, data=data, message="1등 기록을 성공적으로 가져왔습니다.")

    except Exception as e:
        current_app.logger.error(f"❌ 명예의 전당 조회 오류: {str(e)}")
        return api_response(success=False, error_code=500, message="서버 오류 발생", status_code=500)
    

    # 7. 찜하기 토글 (등록/취소)
@text_blueprint.route('/favorite', methods=['POST'])
@swag_from(POST_FAVORITE_YAML_PATH) # 나중에 Swagger 파일 만들면 연결하세요!
def toggle_favorite():
    try:
        data = request.get_json()
        u_id = data.get('user_id')
        t_id = data.get('text_id')

        # 1. 필수값 체크
        if not u_id or not t_id:
            return api_response(success=False, message="user_id와 text_id가 모두 필요합니다.", status_code=400)

        # 2. 유저 및 텍스트 존재 확인
        user = User.query.get(u_id)
        text = TypingText.query.get(t_id)

        if not user or not text:
            return api_response(success=False, message="유저 또는 글을 찾을 수 없습니다.", status_code=404)

        existing_favorite = user.favorite_texts.filter_by(id=t_id).first()

        if existing_favorite:
            user.favorite_texts.remove(text)
            message = f"'{text.title}' 찜하기를 취소했습니다."
            is_favorite = False
        else:
            user.favorite_texts.append(text)
            message = f"'{text.title}' 글을 찜 목록에 추가했습니다."
            is_favorite = True

        db.session.commit()
        
        current_app.logger.info(f" [찜하기 토글] 유저:{u_id}, 글:{t_id}, 결과:{is_favorite}")

        return api_response(
            success=True, 
            message=message,
            data={"is_favorite": is_favorite}
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ 찜하기 에러: {str(e)}")
        return api_response(success=False, message="처리 중 오류가 발생했습니다.", status_code=500)

# 8. 특정 글에 대한 나의 최근 연습 기록 조회
@text_blueprint.route('/<int:text_id>/history/<int:user_id>', methods=['GET'])
@swag_from(GET_USER_TEXT_RESULT_YAML_PATH)
def get_text_history(text_id, user_id):
    """특정 지문에 대해 특정 유저가 연습한 최근 기록들을 가져옵니다."""
    try:
        # 1. 파라미터 확인 (기본 5개)
        limit_val = request.args.get('limit', default=5, type=int)

        # 2. DB 조회: 해당 유저와 해당 텍스트가 일치하는 기록만 최신순 정렬
        results = TypingResult.query.filter_by(user_id=user_id, text_id=text_id)\
                       .order_by(TypingResult.created_at.desc())\
                       .limit(limit_val).all()
        
        # 3. 데이터 가공
        history_list = []
        for r in results:
            history_list.append({
                "result_id": r.id,
                "cpm": r.cpm,
                "wpm": r.wpm,
                "accuracy": r.accuracy,
                "combo": r.combo,
                "date": r.created_at.strftime('%Y-%m-%d %H:%M')
            })

        current_app.logger.info(f"유저 {user_id} - 글 ID {text_id}의 최근 {len(history_list)}개 기록 조회")

        return api_response(
            success=True, 
            data={
                "text_id": text_id,
                "user_id": user_id,
                "history": history_list
            }, 
            message="해당 지문의 연습 이력을 성공적으로 불러왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 지문별 이력 조회 오류: {str(e)}")
        return api_response(success=False, message="이력을 불러오는 중 오류가 발생했습니다.", status_code=500)
    

# 9. 특정 연습 결과 정밀 조회 (지문 + 유저 + 결과 ID 매칭)
@text_blueprint.route('/results/<int:text_id>/<int:user_id>/<int:result_id>', methods=['GET'])
@swag_from(GET_RESULT_DETAIL_YAML_PATH) # 나중에 YAML 추가 시 연결
def get_specific_result(text_id, user_id, result_id):
    """지문, 유저, 결과 ID가 모두 일치하는 단일 기록의 상세 정보를 반환합니다."""
    try:
        # 1. 3가지 ID를 모두 만족하는 기록 조회 (데이터 무결성 검증)
        result = TypingResult.query.filter_by(
            id=result_id, 
            user_id=user_id, 
            text_id=text_id
        ).first()

        if not result:
            return api_response(
                success=False, 
                message="일치하는 연습 기록을 찾을 수 없습니다. (ID 불일치)", 
                status_code=404
            )

        # 2. 결과 가공
        data = {
            "result_id": result.id,
            "text_id": result.text_id,
            "user_id": result.user_id,
            "stats": {
                "cpm": result.cpm,
                "wpm": result.wpm,
                "accuracy": result.accuracy,
                "combo": result.combo,
                "date": result.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        }

        current_app.logger.info(f"🎯 [결과상세] 기록 ID {result_id} 조회 성공")

        return api_response(
            success=True, 
            data=data, 
            message="연습 결과 상세 조회를 완료했습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 결과 상세 조회 에러: {str(e)}")
        return api_response(success=False, message="데이터를 불러오지 못했습니다.", status_code=500)

# 10. 특정 연습 결과 삭제 (Locust 클린업 및 관리용)
@text_blueprint.route('/results/<int:text_id>/<int:user_id>/<int:result_id>', methods=['DELETE'])
@swag_from(DELETE_RESULT_YAML_PATH) # 필요 시 YAML 연결
def delete_specific_result(text_id, user_id, result_id):
    """지문, 유저, 결과 ID가 모두 일치하는 단일 기록을 삭제합니다."""
    try:
        # 1. 3가지 ID를 모두 만족하는 기록 조회
        result = TypingResult.query.filter_by(
            id=result_id, 
            user_id=user_id, 
            text_id=text_id
        ).first()

        if not result:
            return api_response(
                success=False, 
                message="삭제할 기록을 찾을 수 없습니다. (ID 불일치)", 
                status_code=404
            )

        # 2. 삭제 수행
        db.session.delete(result)
        db.session.flush()  # 삭제를 먼저 반영
        
        # 3. 유저 통계 재계산 (SQL 집계 함수 활용)
        recalculated_stats = recalculate_user_statistics(user_id)
        if recalculated_stats:
            db.session.commit()
            current_app.logger.info(f"🗑️ [결과삭제] 유저 {user_id}의 기록 {result_id} 삭제 및 통계 재계산 완료")
        else:
            db.session.rollback()
            return api_response(
                success=False,
                message="유저를 찾을 수 없습니다.",
                status_code=404
            )

        return api_response(
            success=True, 
            data={
                "updated_stats": recalculated_stats
            },
            message="연습 기록이 성공적으로 삭제되었고 유저 통계가 재계산되었습니다."
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ 결과 삭제 에러: {str(e)}")
        return api_response(success=False, message="삭제 처리 중 오류가 발생했습니다.", status_code=500)