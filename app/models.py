from flask_sqlalchemy import SQLAlchemy
from app.database import db
from flask_login import UserMixin
from datetime import datetime

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('text_id', db.Integer, db.ForeignKey('typing_texts.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    favorite_texts = db.relationship('TypingText', 
                                    secondary=favorites,  # 위에서 만든 장부를 중간 매개체로 사용
                                    backref=db.backref('favorited_by', lazy='dynamic'), # 반대로 글에서도 누가 날 찜했는지 확인 가능
                                    lazy='dynamic')


    results = db.relationship('TypingResult', backref='user', lazy=True)

    play_count = db.Column(db.Integer, default=0, nullable=False) 
    max_combo = db.Column(db.Integer, default=0, nullable=False)
    avg_accuracy = db.Column(db.Float, default=0.0, nullable=False)
    profile_pic = db.Column(db.String(200))
    best_cpm = db.Column(db.Integer, default=0, nullable=False)   
    avg_cpm = db.Column(db.Float, default=0.0, nullable=False)  
    best_wpm = db.Column(db.Integer, default=0, nullable=False)  
    avg_wpm = db.Column(db.Float, default=0.0, nullable=False)   

    ranking_score = db.Column(db.Integer, nullable=True)


    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class TypingText(db.Model):
    __tablename__ = 'typing_texts'

    id = db.Column(db.Integer, primary_key=True)
    genre = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)

    # [핵심 수정] 글 삭제 시 해당 글의 모든 연습 결과(TypingResult)를 자동으로 삭제함
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
    
    # 유저 참조
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # [핵심 수정] DB 레벨에서도 글 삭제 시 기록이 삭제되도록 ondelete='CASCADE' 추가
    text_id = db.Column(
        db.Integer, 
        db.ForeignKey('typing_texts.id', ondelete='CASCADE'), 
        nullable=False
    )
    
    cpm = db.Column(db.Integer, nullable=False)
    wpm = db.Column(db.Integer, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    combo = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # TypingText에서 relationship을 설정했으므로 여기서는 중복 정의하지 않아도 됩니다.
    # 만약 기존 코드를 유지하고 싶다면 위 TypingText의 backref 이름과 맞춰주면 됩니다.

    def __repr__(self):
        return f'<Result ID:{self.id} User:{self.user_id} CPM:{self.cpm}>'