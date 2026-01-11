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

# 5. 타자 결과 저장
@text_blueprint.route('/results', methods=['POST'])
@swag_from(POST_RESULT_YAML_PATH)
def save_typing_result():
    try:
        data = request.get_json()
        is_new_combo_record = False
        
        # 1. 필수 데이터 검증
        if not data:
            return api_response(success=False, error_code=400, message="전송된 데이터가 없습니다.", status_code=400)
        
        required_fields = ['text_id', 'user_id', 'cpm', 'accuracy', 'combo']
        for field in required_fields:
            if data.get(field) is None:
                return api_response(success=False, error_code=400, message=f"{field} 항목은 필수입니다.", status_code=400)

        # 수치 변수화
        current_cpm = int(data.get('cpm'))
        current_wpm = int(data.get('wpm', 0))
        current_accuracy = float(data.get('accuracy'))
        current_combo = int(data.get('combo'))

        # 2. 결과 기록(TypingResult) 객체 생성
        new_result = TypingResult(
            user_id=data.get('user_id'),
            text_id=data.get('text_id'),
            cpm=current_cpm,
            wpm=current_wpm,
            accuracy=current_accuracy,
            combo=current_combo
        )
        db.session.add(new_result)

        # 3. 유저 통계 업데이트
        user = User.query.get(data.get('user_id'))
        if user:
            # 기본값 방어 코드 (None 방지)
            user.play_count = user.play_count or 0
            user.avg_accuracy = user.avg_accuracy or 0.0
            user.max_combo = user.max_combo or 0
            user.best_cpm = user.best_cpm or 0
            user.avg_cpm = user.avg_cpm or 0.0
            user.best_wpm = user.best_wpm or 0
            user.avg_wpm = user.avg_wpm or 0.0

            old_count = user.play_count
            user.play_count += 1
            new_count = user.play_count

            # --- [핵심] 평균값들 갱신 (누적 평균 공식) ---
            user.avg_accuracy = round(((user.avg_accuracy * old_count) + current_accuracy) / new_count, 2)
            user.avg_cpm = round(((user.avg_cpm * old_count) + current_cpm) / new_count, 2)
            user.avg_wpm = round(((user.avg_wpm * old_count) + current_wpm) / new_count, 2)

            # --- [핵심] 최고 기록들 갱신 (Max 체크) ---
            if current_combo > user.max_combo:
                user.max_combo = current_combo
                is_new_combo_record = True
            
            if current_cpm > user.best_cpm:
                user.best_cpm = current_cpm
            
            if current_wpm > user.best_wpm:
                user.best_wpm = current_wpm

        else:
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)

        # 4. 최종 DB 반영
        db.session.commit()

        return api_response(
            success=True, 
            data={
                "result_id": new_result.id, 
                "play_count": user.play_count,
                "avg_accuracy": user.avg_accuracy,
                "best_cpm": user.best_cpm,
                "avg_cpm": user.avg_cpm,
                "best_wpm": user.best_wpm,
                "avg_wpm": user.avg_wpm,
                "max_combo": user.max_combo,
                "is_new_record": is_new_combo_record 
            }, 
            message="연습 결과 저장 및 통계 갱신 완료",
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