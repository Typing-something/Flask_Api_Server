from flask import Blueprint, jsonify, request, render_template, redirect, url_for
from database import db
from models import TypingText, TypingResult, User
from datetime import datetime

text_blueprint = Blueprint('text', __name__)

# 0. 글쓰기 페이지 (HTML 폼 제공 및 저장)
@text_blueprint.route('/add', methods=['GET', 'POST'])
def add_text():
    """
    새로운 타자 연습 글 추가 페이지/API
    ---
    tags:
      - Text
    description: |
      **사용 방법:**
      - **GET**: `http://localhost:5000/text/add` 접속 시 글쓰기 화면 출력
      - **POST**: HTML 폼 데이터를 전송하여 DB에 저장
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

        new_entry = TypingText(genre=genre, title=title, author=author, content=content)
        db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for('text.get_main_texts')) 
    
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
      **요청 URL:** `GET http://localhost:5000/text/main`
      - 메인 화면에 뿌려줄 요약된 글 목록을 가져옵니다.
    responses:
      200:
        description: 본문 50자 요약이 포함된 리스트 반환
    """
    texts = TypingText.query.limit(10).all()
    return jsonify([{
        "id": t.id,
        "genre": t.genre,
        "title": t.title,
        "author": t.author,
        "content": t.content[:50] + "..."
    } for t in texts]), 200


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
      - K-POP만 조회: `GET /text/?genre=k-pop`
      - 시만 조회: `GET /text/?genre=poem`
    parameters:
      - name: genre
        in: query
        type: string
        description: 필터링할 장르명
    responses:
      200:
        description: 본문을 제외한 제목 위주의 리스트 반환
    """
    genre_param = request.args.get('genre')
    if genre_param:
        texts = TypingText.query.filter_by(genre=genre_param).all()
    else:
        texts = TypingText.query.all()
        
    return jsonify([{
        "id": t.id, "genre": t.genre, "title": t.title, "author": t.author
    } for t in texts]), 200


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
      - 특정 글의 본문 전체와 해당 유저의 최고 기록을 함께 가져옵니다.
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
        description: 글 상세 정보와 기록 데이터
    """
    t = TypingText.query.get_or_404(text_id)
    u_id = request.args.get('user_id')
    best_record = None

    if u_id:
        best = TypingResult.query.filter_by(user_id=u_id, text_id=text_id)\
               .order_by(TypingResult.cpm.desc()).first()
        if best:
            best_record = {
                "cpm": best.cpm, "wpm": best.wpm, 
                "accuracy": best.accuracy, "date": best.created_at.strftime('%Y-%m-%d')
            }
    return jsonify({
        "text_info" : {"id": t.id, "genre": t.genre, "title": t.title, "author": t.author, "content": t.content}, 
        "my_best": best_record
    }), 200


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
    data = request.get_json()
    if not data.get('text_id'):
        return jsonify({"error": "text_id 필수"}), 400

    new_result = TypingResult(
        user_id=data.get('user_id'), text_id=data.get('text_id'),
        cpm=data.get('cpm'), wpm=data.get('wpm'), accuracy=data.get('accuracy')
    )
    db.session.add(new_result)
    db.session.commit()
    return jsonify({"message": "저장 완료", "result_id": new_result.id}), 201


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
    results = TypingResult.query.filter_by(user_id=user_id).order_by(TypingResult.created_at.desc()).all()
    history = []
    for r in results:
        t = TypingText.query.get(r.text_id)
        history.append({
            "title": t.title if t else "삭제된 텍스트",
            "cpm": r.cpm, "wpm": r.wpm, "accuracy": r.accuracy,
            "date": r.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify(history), 200


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
    t_id = request.args.get('text_id')
    if not t_id:
        return jsonify({"error": "text_id 필요"}), 400

    best = db.session.query(TypingResult, User.username)\
            .join(User, TypingResult.user_id == User.id)\
            .filter(TypingResult.text_id == t_id)\
            .order_by(TypingResult.cpm.desc()).first()
    
    if not best:
        return jsonify({"message": "기록 없음", "best_cpm": 0}), 200

    res, uname = best
    return jsonify({
        "top_player": uname, "best_cpm": res.cpm,
        "best_wpm": res.wpm, "best_accuracy": res.accuracy,
        "date": res.created_at.strftime('%Y-%m-%d')
    }), 200