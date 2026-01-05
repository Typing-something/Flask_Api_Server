import os
import boto3
import uuid
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, current_app
from database import db
from models import TypingText, TypingResult, User
from datetime import datetime
from utils import api_response


# S3 클라이언트 설정 (환경변수 로드)
s3 = boto3.client('s3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'ap-northeast-2')
)
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

text_blueprint = Blueprint('text', __name__)

# 0. 글쓰기 페이지 (HTML 폼 제공 및 저장 - 이미지 업로드 기능 추가)
@text_blueprint.route('/add', methods=['GET', 'POST'])
def add_text():
    """
    새로운 타자 연습 글 추가 페이지/API
    ---
    tags:
      - Text
    description: |
      **사용 방법:**
      - **GET**: `/text/add` 접속 시 글쓰기 화면 출력
      - **POST**: HTML 폼 데이터와 이미지 파일을 전송하여 DB 및 S3에 저장
    parameters:
      - name: genre
        in: formData
        type: string
        enum: ['proverb', 'poem', 'novel', 'k-pop']
        description: 글의 장르 선택
      - name: title
        in: formData
        type: string
        required: true
        description: 글의 제목
      - name: author
        in: formData
        type: string
        description: 작가 또는 가수 이름
      - name: content
        in: formData
        type: string
        required: true
        description: 타자 연습용 전체 본문
      - name: image
        in: formData
        type: file
        description: 글과 매칭될 대표 이미지 (S3 업로드)
    responses:
      302:
        description: 저장 후 메인 리다이렉트
      200:
        description: 글쓰기 HTML 폼 반환
    """
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
            if ext not in ['.jpg', '.jpeg', '.png', '.gif']:
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


# 1. 메인용: 상위 10개 조회
@text_blueprint.route('/main', methods=['GET'])
def get_main_texts():
    """
    메인 페이지용 최신 텍스트 10개 조회
    ---
    tags:
      - Text
    description: |
      **요청 URL:** `GET /text/main`
      - 메인 화면에 뿌려줄 요약된 글 목록을 가져옵니다. (이미지 URL 포함)
    responses:
      200:
        description: 본문 요약 및 이미지 URL이 포함된 리스트 반환
    """
    try:
      
        texts = TypingText.query.order_by(TypingText.id.desc()).limit(10).all()
        texts_list = [{
            "id": t.id,
            "genre": t.genre,
            "title": t.title,
            "author": t.author,
            "content": t.content[:50] + "...",
            "image_url": t.image_url
        } for t in texts]

        return api_response(
            success=True, 
            data=texts_list, 
            message="최신 글 10개를 성공적으로 가져왔습니다."
        )

    except Exception as e:

        current_app.logger.error(f"메인 텍스트 조회 중 에러 발생: {str(e)}")
        
        return api_response(
            success=False, 
            data=[],  # 실패했으므로 빈 리스트 전달
            error_code=500, 
            message="서버 내부 문제로 글 목록을 불러오지 못했습니다.",
            status_code=500
        )


# 2. 장르별 목록 필터링
@text_blueprint.route('/', methods=['GET'])
def get_texts_by_genre():
    """
    장르별 목록 필터링 조회
    ---
    tags:
      - Text
    description: |
      **요청 URL 예시:**
      - 전체 조회: `GET /text/`
      - 장르 필터 조회: `GET /text/?genre=k-pop`
    parameters:
      - name: genre
        in: query
        type: string
        description: 필터링할 장르명
    responses:
      200:
        description: 제목 및 이미지 URL 위주의 리스트 반환
    """
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


# 3. 특정 글 상세 조회
@text_blueprint.route('/<int:text_id>', methods=['GET'])
def get_text_by_id(text_id):
    """
    글 상세 정보 및 내 최고 기록 조회
    ---
    tags:
      - Text
    description: |
      **요청 URL 예시:** `GET /text/1?user_id=5`
      - 특정 글의 본문 전체와 이미지 URL, 해당 유저의 최고 기록을 함께 가져옵니다.
    parameters:
      - name: text_id
        in: path
        type: integer
        required: true
      - name: user_id
        in: query
        type: integer
        description: 내 최고기록을 조회하고 싶을 때 포함
    responses:
      200:
        description: 글 상세 정보(이미지 포함)와 기록 데이터
    """
    try:
        # 1. 글 정보 조회 (get_or_404 대신 직접 조회하여 커스텀 에러 처리)
        t = TypingText.query.get(text_id)
        
        # 만약 해당 ID의 글이 DB에 없다면?
        if not t:
            return api_response(
                success=False, 
                error_code=404, 
                message="해당 글을 찾을 수 없습니다.", 
                status_code=404
            )

        # 2. 로그인한 유저의 최고 기록 조회 준비
        u_id = request.args.get('user_id') # 쿼리 스트링에서 user_id 추출
        best_record = None

        # 유저 ID가 전달된 경우에만 기록을 조회함 (로그인 상태 체크)
        if u_id:
            # 해당 유저가 이 글을 연습한 기록 중 CPM(타수)이 가장 높은 1등 기록 가져오기
            best = TypingResult.query.filter_by(user_id=u_id, text_id=text_id)\
                   .order_by(TypingResult.cpm.desc()).first()
            
            if best:
                best_record = {
                    "cpm": best.cpm, 
                    "wpm": best.wpm, 
                    "accuracy": best.accuracy, 
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
                "image_url": t.image_url
            }, 
            "my_best": best_record # 기록이 없으면 None으로 나감
        }

        return api_response(
            success=True, 
            data=data, 
            message="글 상세 정보와 최고 기록을 성공적으로 가져왔습니다."
        )

    except Exception as e:
        # 서버에서 에러가 나면 PM2 로그에 범인을 기록
        current_app.logger.error(f"상세 조회 중 서버 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="데이터를 불러오는 중 서버 내부 오류가 발생했습니다.", 
            status_code=500
        )

# 4. 타자 결과 저장
@text_blueprint.route('/results', methods=['POST'])
def save_typing_result():
    """
    타자 연습 결과 기록 저장
    ---
    tags:
      - Result
    description: |
      **요청 URL:** `POST /text/results`
      **JSON 데이터 형식:**
      ```json
      {
        "text_id": 1,
        "user_id": 5,
        "cpm": 450,
        "wpm": 75,
        "accuracy": 98.5
      }
      ```
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            text_id: {type: integer}
            user_id: {type: integer}
            cpm: {type: integer}
            wpm: {type: integer}
            accuracy: {type: number}
    responses:
      201:
        description: 저장 완료
    """
    try:
        data = request.get_json()
        is_new_record = False
        # 1. 필수 데이터 검증
        if not data:
            return api_response(success=False, error_code=400, message="전송된 데이터가 없습니다.", status_code=400)
        
        required_fields = ['text_id', 'user_id', 'cpm', 'accuracy', 'combo']
        for field in required_fields:
            if data.get(field) is None:
                return api_response(success=False, error_code=400, message=f"{field} 항목은 필수입니다.", status_code=400)

        # 현재 판 정확도 (계산을 위해 변수화)
        current_accuracy = float(data.get('accuracy'))

        # 현재 판 콤보
        current_combo = int(data.get('combo'))

        # 2. 결과 기록(TypingResult) 객체 생성
        new_result = TypingResult(
            user_id=data.get('user_id'),
            text_id=data.get('text_id'),
            cpm=data.get('cpm'),
            wpm=data.get('wpm', 0),
            accuracy=current_accuracy,
            combo = current_combo
        )
        db.session.add(new_result)

        # 3. 유저 통계 업데이트 (횟수 증가 및 평균 정확도 계산)
        user = User.query.get(data.get('user_id'))
        if user:
            # 기본값 방어 코드 (None인 경우 0으로 초기화)
            if user.play_count is None: user.play_count = 0
            if user.avg_accuracy is None: user.avg_accuracy = 0.0
            if user.max_combo is None: user.max_combo = 0

            old_count = user.play_count
            old_avg = user.avg_accuracy

            # [핵심] 플레이 횟수 1 증가
            user.play_count += 1
            new_count = user.play_count

            # [핵심] 새로운 평균 정확도 업데이트
            # 수식: ((기존평균 * 기존횟수) + 이번판정확도) / 새로운횟수
            updated_avg = ((old_avg * old_count) + current_accuracy) / new_count
            user.avg_accuracy = round(updated_avg, 2)
            
            if current_combo > user.max_combo:
                user.max_combo = current_combo
                is_new_record = True

        else:
            # 유저가 없는 경우 처리 (필요시 에러 리턴)
            return api_response(success=False, error_code=404, message="유저를 찾을 수 없습니다.", status_code=404)

        # 4. 최종 DB 반영 (결과 저장 + 유저 통계 갱신을 한 번에)
        db.session.commit()

        return api_response(
            success=True, 
            data={
                "result_id": new_result.id, 
                "play_count": user.play_count,
                "avg_accuracy": user.avg_accuracy,
                "max_combo": user.max_combo,
                "is_new_record": is_new_record # 만일 이번 기록이 최고 기록 갱신이면 true아니면 false
            }, 
            message="연습 결과가 저장되었고 유저 통계가 갱신되었습니다.",
            status_code=201
        )

    except Exception as e:
        db.session.rollback() 
        current_app.logger.error(f"결과 저장 및 유저 업데이트 중 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="서버 내부 문제로 결과를 저장하지 못했습니다.",
            status_code=500
        )


# 5. 유저별 과거 기록 조회
@text_blueprint.route('/results/user/<int:user_id>', methods=['GET'])
def get_user_history(user_id):
    """
    유저의 전체 히스토리 조회 (마이페이지)
    ---
    tags:
      - Result
    description: |
      **요청 URL:** `GET /text/results/user/5`
      - 특정 유저가 지금까지 연습한 모든 기록을 최신순으로 가져옵니다.
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 과거 기록 리스트 반환
    """
    try:
        # 1. 해당 유저의 모든 연습 기록을 최신순으로 가져오기
        results = TypingResult.query.filter_by(user_id=user_id)\
                  .order_by(TypingResult.created_at.desc()).all()
        
        # 2. 기록이 하나도 없을 경우 빈 리스트 응답 (에러는 아님)
        if not results:
            return api_response(
                success=True, 
                data=[], 
                message="아직 연습한 기록이 없습니다."
            )

        # 3. 데이터 가공: 각 결과(r)에 맞는 텍스트 정보 매칭
        history = []
        for r in results:
            # 결과에 저장된 text_id로 해당 글의 제목을 찾아옴
            t = TypingText.query.get(r.text_id)
            history.append({
                "title": t.title if t else "삭제된 텍스트",
                "cpm": r.cpm, 
                "wpm": r.wpm, 
                "accuracy": r.accuracy,
                "date": r.created_at.strftime('%Y-%m-%d %H:%M')
            })

        # 4. 성공 응답
        return api_response(
            success=True, 
            data=history, 
            message=f"유저 {user_id}의 연습 기록을 불러왔습니다."
        )

    except Exception as e:
        # DB 조회 도중 문제 발생 시 로그 기록
        current_app.logger.error(f"유저 히스토리 조회 중 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="과거 기록을 불러오는 중 서버 오류가 발생했습니다.", 
            status_code=500
        )


# 6. 글별 글로벌 최고 점수
@text_blueprint.route('/results/best', methods=['GET'])
def get_global_best_score():
    """
    이 글의 전 세계 1등 기록 조회 (명예의 전당)
    ---
    tags:
      - Result
    description: |
      **요청 URL 예시:** `GET /text/results/best?text_id=1`
      - 특정 글에서 가장 높은 타수(CPM)를 기록한 유저 정보를 가져옵니다.
    parameters:
      - name: text_id
        in: query
        type: integer
        required: true
    responses:
      200:
        description: 1등 유저명과 점수 정보
    """
    try:
        # 1. 쿼리 파라미터에서 text_id 가져오기
        t_id = request.args.get('text_id')
        if not t_id:
            return api_response(
                success=False, 
                error_code=400, 
                message="text_id가 필요합니다.", 
                status_code=400
            )

        # 2. DB 조회: Result와 User 테이블을 조인하여 1등 기록과 유저 이름을 한꺼번에 가져옴
        best = db.session.query(TypingResult, User.username)\
                .join(User, TypingResult.user_id == User.id)\
                .filter(TypingResult.text_id == t_id)\
                .order_by(TypingResult.cpm.desc()).first()
        
        # 3. 기록이 아예 없는 경우
        if not best:
            return api_response(
                success=True, 
                data={
                    "top_player": "No record", 
                    "best_cpm": 0, 
                    "best_wpm": 0, 
                    "best_accuracy": 0
                }, 
                message="아직 등록된 기록이 없습니다."
            )

        # 4. 데이터 언팩 (쿼리 결과에서 객체와 유저명 분리)
        res, uname = best
        data = {
            "top_player": uname, 
            "best_cpm": res.cpm,
            "best_wpm": res.wpm, 
            "best_accuracy": res.accuracy,
            "date": res.created_at.strftime('%Y-%m-%d')
        }

        # 5. 성공 응답
        return api_response(
            success=True, 
            data=data, 
            message="전 세계 1등 기록을 성공적으로 가져왔습니다."
        )

    except Exception as e:
        # 조인 쿼리 등에서 발생할 수 있는 오류 로그 기록
        current_app.logger.error(f"전 세계 1등 조회 중 에러: {str(e)}")
        return api_response(
            success=False, 
            error_code=500, 
            message="서버 오류로 최고 기록을 불러오지 못했습니다.", 
            status_code=500
        )