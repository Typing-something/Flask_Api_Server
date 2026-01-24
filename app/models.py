from flask_sqlalchemy import SQLAlchemy
from app.database import db
from flask_login import UserMixin
from datetime import datetime, timedelta, timezone

# 한국 시간대 정의
KST = timezone(timedelta(hours=9))

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('text_id', db.Integer, db.ForeignKey('typing_texts.id', ondelete='CASCADE'), primary_key=True),
    db.Column('created_at', db.DateTime, default=lambda: datetime.now(KST))
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_pic = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # 랭킹 시스템의 핵심: 계산된 종합 점수
    ranking_score = db.Column(db.Integer, default=0, nullable=False)

    # 기본 통계 필드
    play_count = db.Column(db.Integer, default=0, nullable=False) 
    max_combo = db.Column(db.Integer, default=0, nullable=False)
    avg_accuracy = db.Column(db.Float, default=0.0, nullable=False)
    best_cpm = db.Column(db.Integer, default=0, nullable=False)   
    avg_cpm = db.Column(db.Float, default=0.0, nullable=False)  
    best_wpm = db.Column(db.Integer, default=0, nullable=False)  
    avg_wpm = db.Column(db.Float, default=0.0, nullable=False)   

    # Relationships
    favorite_texts = db.relationship('TypingText', 
                                    secondary=favorites, 
                                    backref=db.backref('favorited_by', lazy='dynamic'), 
                                    lazy='dynamic')
    results = db.relationship('TypingResult', backref='user', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

    # ✅ [핵심 추가] 실력 기반 점수 산출 로직
    def update_ranking_score(self):
        """
        가중치를 적용하여 유저의 실력 점수를 갱신합니다.
        공식: (최고타수 * 0.5) + (평균정확도 * 5) + (평균타수 * 0.2) + (최고콤보 * 0.1) + 판수보너스
        """
        score = (
            (self.best_cpm * 0.5) +          # 최고 퍼포먼스 비중 높음
            (self.avg_accuracy * 5.0) +     # 정확도 1%당 5점 (변별력 강화)
            (self.avg_cpm * 0.2) +          # 평소 실력 반영
            (self.max_combo * 0.1)          # 집중력 가점
        )
        
        # 성실도 가점: 10판당 1점 (최대 50점)
        play_bonus = min((self.play_count // 10), 50)
        
        self.ranking_score = int(score + play_bonus)

class TypingText(db.Model):
    __tablename__ = 'typing_texts'

    id = db.Column(db.Integer, primary_key=True)
    genre = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)

    results = db.relationship(
        'TypingResult', 
        backref='typing_text', 
        cascade="all, delete-orphan", 
        lazy=True
    )

    def __repr__(self):
        return f'<TypingText {self.title}>'

class TypingResult(db.Model):
    __tablename__ = 'typing_results'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    text_id = db.Column(db.Integer, db.ForeignKey('typing_texts.id', ondelete='CASCADE'), nullable=False)
    
    cpm = db.Column(db.Integer, nullable=False)
    wpm = db.Column(db.Integer, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    combo = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(KST))

    def __repr__(self):
        return f'<Result ID:{self.id} User:{self.user_id} CPM:{self.cpm}>'

class TestReport(db.Model):
    __tablename__ = 'test_reports'
    id = db.Column(db.Integer, primary_key=True)
    test_time = db.Column(db.DateTime, default=lambda: datetime.now(KST))
    git_commit = db.Column(db.String(40))
    total_tests = db.Column(db.Integer, default=0)
    passed_tests = db.Column(db.Integer, default=0)
    failed_tests = db.Column(db.Integer, default=0)
    is_passed = db.Column(db.Boolean, default=False)
    user_count = db.Column(db.Integer, default=0) 

    case_results = db.relationship('TestCaseResult', backref='report', cascade="all, delete-orphan")
    api_performances = db.relationship('ApiPerformance', backref='report', cascade="all, delete-orphan")

class TestCaseResult(db.Model):
    __tablename__ = 'test_case_results'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('test_reports.id', ondelete='CASCADE'), nullable=False)
    test_name = db.Column(db.String(255)) 
    status = db.Column(db.String(50))
    message = db.Column(db.Text)

class ApiPerformance(db.Model):
    __tablename__ = 'api_performances'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('test_reports.id', ondelete='CASCADE'), nullable=False)
    
    # 기본 정보
    method = db.Column(db.String(10))     # GET, POST, DELETE 등
    endpoint = db.Column(db.String(255))   # /text/all, /user/ranking 등
    
    # 핵심 성능 지표 (Latency)
    avg_latency = db.Column(db.Float)      # 평균 응답 시간
    p95_latency = db.Column(db.Float)      # 상위 5% 응답 시간 (가장 중요 🌟)
    p99_latency = db.Column(db.Float)      # 상위 1% 응답 시간 (최악의 케이스)
    max_latency = db.Column(db.Float)      # 최대 응답 시간
    
    # 처리량 및 안정성
    rps = db.Column(db.Float)              # 초당 요청 수
    total_requests = db.Column(db.Integer) # 총 요청 횟수
    fail_count = db.Column(db.Integer, default=0) # 실패 횟수
    error_rate = db.Column(db.Float)       # 에러율 (%)
    
    # 관리자 판단 기준
    # 목표치(SLA)를 넘었는지 여부 (예: p95가 500ms 이하면 True)
    is_satisfied = db.Column(db.Boolean, default=True) 

    def __repr__(self):
        return f'<ApiPerf {self.method} {self.endpoint} RPS:{self.rps}>'