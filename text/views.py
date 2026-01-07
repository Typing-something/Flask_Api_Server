import os
import boto3
import uuid
from flask import Blueprint, jsonify, request, render_template, redirect, url_for, current_app
from database import db
from models import TypingText, TypingResult, User
from datetime import datetime
from utils import api_response
from sqlalchemy import func

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


# 1. 메인용: 랜덤 10개 조회
@text_blueprint.route('/main', methods=['GET'])
def get_main_texts():
    """
    메인 페이지용 랜덤 텍스트 10개 조회
    ---
    tags:
      - Text
    description: |
      **요청 URL:** `GET /text/main`
      - DB에 등록된 전체 텍스트 중 무작위로 10개를 선정하여 반환합니다.
      - 사용자가 페이지를 새로고침할 때마다 새로운 연습 콘텐츠를 추천하는 용도로 사용됩니다.
    responses:
      200:
        description: 랜덤하게 선택된 10개의 글 리스트 반환
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string, example: "랜덤 글 10개를 성공적으로 가져왔습니다."}
            data:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  genre: {type: string}
                  title: {type: string}
                  author: {type: string}
                  content: {type: string}
                  image_url: {type: string}
    """
    try:
        # [핵심 수정] func.rand()를 사용하여 무작위 정렬 후 10개 추출
        texts = TypingText.query.order_by(func.rand()).limit(10).all()
        
        texts_list = [{
            "id": t.id,
            "genre": t.genre,
            "title": t.title,
            "author": t.author,
            "content": t.content,
            "image_url": t.image_url
        } for t in texts]

        current_app.logger.info(f" [랜덤조회] 메인 화면용 텍스트 {len(texts_list)}개를 무작위로 추출했습니다.")

        return api_response(
            success=True, 
            data=texts_list, 
            message="랜덤 글 10개를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"❌ 메인 텍스트 랜덤 조회 중 에러: {str(e)}")
        return api_response(
            success=False, 
            data=[], 
            error_code=500, 
            message="글 목록을 불러오는 중 서버 오류가 발생했습니다.",
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
    글 상세 정보 및 유저별 개인 최고 기록 조회
    ---
    tags:
      - Text
    description: |
      **요청 URL:** `GET /text/{text_id}?user_id={user_id}`
      
      **기능:**
      1. 특정 글의 제목, 작가, 본문 전체, 이미지 URL을 가져옵니다.
      2. `user_id`가 쿼리 파라미터로 전달되면, 해당 글에 대한 유저의 역대 최고 CPM 기록을 함께 반환합니다.
      3. 기록이 없는 유저이거나 `user_id`를 보내지 않은 경우 `my_best`는 `null`로 반환됩니다.
    parameters:
      - name: text_id
        in: path
        type: integer
        required: true
        description: 조회할 글의 고유 ID
      - name: user_id
        in: query
        type: integer
        required: false
        description: 현재 사용자의 최고 기록을 함께 보고 싶을 때 전달
    responses:
      200:
        description: 데이터 조회 성공
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "글 상세 정보와 최고 기록을 성공적으로 가져왔습니다."
            data:
              type: object
              properties:
                text_info:
                  type: object
                  description: 글 상세 정보
                  properties:
                    id: {type: integer, example: 1}
                    genre: {type: string, example: "poem"}
                    title: {type: string, example: "진달래꽃"}
                    author: {type: string, example: "김소월"}
                    content: {type: string, example: "나 보기가 역겨워 가실 때에는..."}
                    image_url: {type: string, example: "https://s3.ap-northeast-2.../image.jpg"}
                my_best:
                  type: object
                  nullable: true
                  description: 해당 유저의 이 글에 대한 최고 기록 (기록 없으면 null)
                  properties:
                    cpm: {type: integer, example: 450}
                    wpm: {type: integer, example: 85}
                    accuracy: {type: number, example: 98.5}
                    combo: {type: integer}
                    date: {type: string, example: "2026-01-05"}
      404:
        description: 존재하지 않는 text_id 요청 시
      500:
        description: 서버 내부 오류
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
                "image_url": t.image_url
            }, 
            "my_best": best_record # 기록이 없으면 None으로 나감
        }

        current_app.logger.info(f"🔍 [상세조회] 유저 {u_id if u_id else '비회원'} - '{t.title}' 조회 완료")

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
    타자 연습 결과 기록 저장 및 유저 통계 갱신
    ---
    tags:
      - Result
    description: |
      **요청 URL:** `POST /text/results`
      
      **기능:**
      1. 새로운 타자 연습 결과를 `typing_result` 테이블에 저장합니다.
      2. 해당 유저의 전체 플레이 횟수(`play_count`)를 1 증가시킵니다.
      3. 유저의 전체 평균 정확도(`avg_accuracy`)를 실시간으로 재계산합니다.
      4. 이번 판의 콤보가 기존 최고 콤보보다 높으면 `max_combo`를 갱신합니다.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - text_id
            - user_id
            - cpm
            - accuracy
            - combo
          properties:
            text_id:
              type: integer
              description: 연습한 글의 ID
            user_id:
              type: integer
              description: 현재 로그인한 유저의 ID
            cpm:
              type: integer
              description: 분당 타자수 (Characters Per Minute)
            wpm:
              type: integer
              description: 분당 단어수 (Words Per Minute), 미입력 시 0
            accuracy:
              type: number
              format: float
              description: 이번 판의 정확도 (0~100)
            combo:
              type: integer
              description: 이번 판에서 달성한 최대 연속 콤보
    responses:
      201:
        description: 저장 및 통계 업데이트 완료
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "연습 결과가 저장되었고 유저 통계가 갱신되었습니다."
            data:
              type: object
              properties:
                result_id:
                  type: integer
                  description: 새로 생성된 결과 기록의 PK
                play_count:
                  type: integer
                  description: 누적 플레이 횟수
                avg_accuracy:
                  type: number
                  description: 갱신된 전체 평균 정확도
                max_combo:
                  type: integer
                  description: 유저의 역대 최고 콤보
                is_new_record:
                  type: boolean
                  description: 이번 판에서 최고 콤보 신기록을 달성했는지 여부
      400:
        description: 필수 파라미터 누락 또는 데이터 형식 오류
      404:
        description: 존재하지 않는 유저 ID
      500:
        description: 서버 내부 오류 (DB 트랜잭션 실패 등)
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

        current_app.logger.error(f"상세 조회 중 서버 에러: {str(e)}")

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



# 6. 글별 최고 점수
@text_blueprint.route('/results/best', methods=['GET'])
def get_global_best_score():
    """
    해당 글의 최고 기록 조회
    ---
    tags:
      - Result
    description: |
      **요청 URL:** `GET /text/results/best?text_id=1`
      - 특정 글에서 가장 높은 타수(CPM)를 기록한 유저의 정보와 성적을 가져옵니다.
      - 랭킹 1위 유저의 닉네임, 타수, 정확도, 최대 콤보를 포함합니다.
    parameters:
      - name: text_id
        in: query
        type: integer
        required: true
        description: 1등 기록을 조회할 글의 ID
    responses:
      200:
        description: 전 세계 1등 기록 조회 성공
        schema:
          type: object
          properties:
            success: {type: boolean, example: true}
            message: {type: string}
            data:
              type: object
              properties:
                top_player: {type: string, description: "1등 유저 닉네임", example: "타자마스터"}
                profile_pic: {type: string, description: "1등 유저 프로필 사진 URL"}
                best_cpm: {type: integer, description: "최고 타수", example: 850}
                best_wpm: {type: integer, description: "최고 WPM", example: 120}
                best_accuracy: {type: number, description: "최고 정확도 (%)", example: 99.8}
                best_combo: {type: integer, description: "최고 콤보", example: 342}
                date: {type: string, description: "달성 일자", example: "2026-01-07"}
      400:
        description: text_id 파라미터 누락
      500:
        description: 서버 내부 오류
    """
    try:
        t_id = request.args.get('text_id')
        if not t_id:
            return api_response(success=False, error_code=400, message="text_id가 필요합니다.", status_code=400)

        # [수정] User.username 뿐만 아니라 profile_pic도 함께 가져오도록 쿼리 보강
        # TypingResult와 User 테이블을 Join하여 CPM 기준 내림차순 정렬 후 최상위 1건 추출
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
            "best_combo": res.combo, # [추가] 콤보 정보 반영
            "date": res.created_at.strftime('%Y-%m-%d')
        }

        # [한글 로그 추가]
        current_app.logger.info(f"👑 [명예의전당] 글 ID:{t_id}의 1등 '{uname}' ({res.cpm}타) 정보를 조회했습니다.")

        return api_response(success=True, data=data, message="전 세계 1등 기록을 성공적으로 가져왔습니다.")

    except Exception as e:
        current_app.logger.error(f"❌ 명예의 전당 조회 오류: {str(e)}")
        return api_response(success=False, error_code=500, message="서버 오류 발생", status_code=500)