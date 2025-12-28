from flask_sqlalchemy import SQLAlchemy
from database import db
from flask_login import UserMixin
from datetime import datetime



class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # (선택 추가) 유저가 가진 결과들을 바로 참조하고 싶을 때
    results = db.relationship('TypingResult', backref='user', lazy=True)

# 구글에서 제공하는 고유 식별자 (Sub 값)
    google_id = db.Column(db.String(200), unique=True, nullable=True)
    # 유저 프로필 이미지 URL (선택사항)
    profile_pic = db.Column(db.String(200))

    def __repr__(self):
        return f'<User {self.username}>'

class TypingText(db.Model):
    __tablename__ = 'typing_texts'

    id = db.Column(db.Integer, primary_key=True)
    genre = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<TypingText {self.title}>'

class TypingResult(db.Model):
    __tablename__ = 'typing_results'

    id = db.Column(db.Integer, primary_key=True)
    
    # [수정] 참조 테이블 이름을 'users'로 변경 (User 모델의 __tablename__과 일치)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # [수정] 참조 테이블 이름을 'typing_texts'로 변경
    text_id = db.Column(db.Integer, db.ForeignKey('typing_texts.id'), nullable=False)
    
    cpm = db.Column(db.Integer, nullable=False)
    wpm = db.Column(db.Integer, nullable=False)
    accuracy = db.Column(db.Float, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # (선택 추가) 결과에서 텍스트 정보를 바로 가져오기 위한 관계 설정
    typing_text = db.relationship('TypingText', backref='results')

    def __repr__(self):
        return f'<Result ID:{self.id} User:{self.user_id} CPM:{self.cpm}>'