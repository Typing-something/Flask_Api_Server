# Typing Game API

Flask 기반 타이핑 게임 백엔드 API 서버입니다. 사용자 인증, 텍스트 관리, 타이핑 결과 저장 및 랭킹 시스템을 제공합니다.

## 📋 목차

- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [환경 변수 설정](#환경-변수-설정)
- [API 엔드포인트](#api-엔드포인트)
- [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)
- [테스트](#테스트)
- [배포](#배포)

## 🎯 주요 기능

- **인증 시스템**: Google OAuth 2.0 기반 로그인/로그아웃
- **텍스트 관리**: 장르별 타이핑 텍스트 CRUD, 이미지 업로드 (AWS S3)
- **타이핑 결과**: CPM, WPM, 정확도, 콤보 기록 저장 및 조회
- **사용자 프로필**: 통계 정보, 플레이 히스토리, 즐겨찾기 관리
- **랭킹 시스템**: 실력 기반 점수 산출 및 랭킹 조회
- **API 문서화**: Swagger를 통한 자동 API 문서 생성
- **성능 모니터링**: API 응답 시간 및 처리량 추적

## 🛠 기술 스택

- **Framework**: Flask 3.1.2
- **Database**: SQLAlchemy 2.0.45 (SQLite/MySQL 지원)
- **ORM**: Flask-SQLAlchemy
- **Migration**: Flask-Migrate (Alembic)
- **Authentication**: Flask-Login, Google OAuth 2.0
- **API Documentation**: Flasgger (Swagger)
- **CORS**: Flask-CORS
- **Storage**: AWS S3 (이미지 업로드)
- **Testing**: pytest, locust (부하 테스트)
- **Deployment**: Gunicorn

## 📁 프로젝트 구조

```
study_flask/
├── app/
│   ├── __init__.py          # Flask 앱 팩토리 및 초기화
│   ├── database.py          # SQLAlchemy DB 설정
│   ├── models.py            # 데이터베이스 모델 (User, TypingText, TypingResult 등)
│   ├── utils.py             # 유틸리티 함수
│   ├── routes/              # API 라우트
│   │   ├── auth/           # 인증 관련 (Google 로그인)
│   │   ├── main/           # 메인 페이지
│   │   ├── text/           # 텍스트 관리 API
│   │   ├── user/           # 사용자 프로필 및 랭킹
│   │   └── reports/        # 테스트 리포트 관리
│   └── templates/          # HTML 템플릿
├── migrations/              # 데이터베이스 마이그레이션 파일
├── tests/                  # 테스트 코드
│   ├── auth/              # 인증 테스트
│   ├── text/              # 텍스트 API 테스트
│   ├── user/              # 사용자 API 테스트
│   └── load/              # 부하 테스트 (Locust)
├── instance/               # 로컬 데이터베이스 파일
├── config.py              # 설정 파일
├── run.py                 # 애플리케이션 진입점
├── requirements.txt       # Python 패키지 의존성
└── README.md             # 프로젝트 문서
```

## 🚀 설치 및 실행

### 1. 저장소 클론

```bash
git clone <repository-url>
cd study_flask
```

### 2. 가상 환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env` 파일을 생성하고 필요한 환경 변수를 설정합니다. (자세한 내용은 [환경 변수 설정](#환경-변수-설정) 참조)

### 5. 데이터베이스 초기화

```bash
# 마이그레이션 초기화 (최초 1회)
flask db init

# 마이그레이션 생성
flask db migrate -m "Initial migration"

# 마이그레이션 적용
flask db upgrade
```

### 6. 서버 실행

```bash
# 개발 모드
python run.py

# 또는 Flask CLI 사용
flask run
```

서버는 기본적으로 `http://127.0.0.1:5000`에서 실행됩니다.

## ⚙️ 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
# Flask 환경 설정
FLASK_ENV=development  # development, testing, production
PORT=5000
SECRET_KEY=your-secret-key-here

# 데이터베이스 설정
# 로컬 개발용 MySQL (선택사항)
LOCAL_MYSQL_URL=mysql+pymysql://user:password@localhost:3306/dbname

# 프로덕션용 데이터베이스 (AWS RDS 등)
DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname

# 서버 URL
SERVER_URL=http://localhost:5000

# Google OAuth 설정
GOOGLE_CLIENT_ID=your-google-client-id
INTERNAL_SYNC_KEY=your-internal-sync-key

# AWS S3 설정 (이미지 업로드용)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your-bucket-name

# CORS 설정 (프로덕션)
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

## 📡 API 엔드포인트

### 인증 (Auth)

- `POST /auth/google` - Google OAuth 로그인
- `POST /auth/logout` - 로그아웃

### 텍스트 관리 (Text)

- `GET /text/all` - 모든 텍스트 목록 조회
- `GET /text/random` - 랜덤 텍스트 조회
- `GET /text/genre/<genre>` - 장르별 텍스트 조회
- `GET /text/<int:text_id>` - 텍스트 상세 조회
- `POST /text/add` - 텍스트 추가 (이미지 업로드 포함)
- `DELETE /text/<int:text_id>` - 텍스트 삭제
- `POST /text/<int:text_id>/favorite` - 즐겨찾기 추가/제거
- `POST /text/result` - 타이핑 결과 저장
- `GET /text/<int:text_id>/result` - 사용자별 텍스트 결과 조회
- `GET /text/<int:text_id>/result/<int:result_id>` - 결과 상세 조회
- `GET /text/<int:text_id>/best` - 최고 기록 조회
- `DELETE /text/<int:text_id>/result/<int:result_id>` - 결과 삭제

### 사용자 (User)

- `GET /user/profile/<int:user_id>` - 사용자 프로필 조회
- `GET /user/all` - 모든 사용자 프로필 조회
- `GET /user/ranking` - 랭킹 조회
- `GET /user/<int:user_id>/history/all` - 전체 플레이 히스토리
- `GET /user/<int:user_id>/history/recent` - 최근 플레이 히스토리
- `GET /user/<int:user_id>/history/genre/<genre>` - 장르별 히스토리
- `GET /user/<int:user_id>/favorites` - 즐겨찾기 목록

### 관리자 (Admin)

- `GET /admin/reports` - 테스트 리포트 조회

### API 문서

서버 실행 후 다음 URL에서 Swagger API 문서를 확인할 수 있습니다:

```
http://localhost:5000/apispec_1.json
http://localhost:5000/apidocs
```

## 🗄 데이터베이스 마이그레이션

### 마이그레이션 생성

모델 변경 후 마이그레이션 파일 생성:

```bash
flask db migrate -m "설명 메시지"
```

### 마이그레이션 적용

```bash
flask db upgrade
```

### 마이그레이션 롤백

```bash
flask db downgrade
```

## 🧪 테스트

### 단위 테스트 실행

```bash
# 모든 테스트 실행
pytest

# 커버리지 포함
pytest --cov=app

# 특정 테스트 파일 실행
pytest tests/auth/test_01_login_out.py
```

### 부하 테스트 (Locust)

```bash
# Locust 서버 시작
locust -f tests/load/locustfile.py

# 브라우저에서 http://localhost:8089 접속하여 테스트 실행
```

## 🚢 배포

### 프로덕션 모드 실행

```bash
# 환경 변수 설정
export FLASK_ENV=production

# Gunicorn으로 실행
gunicorn -w 4 -b 0.0.0.0:5000 "run:app"
```

### 주요 배포 고려사항

1. **환경 변수**: 프로덕션 환경의 모든 민감한 정보는 환경 변수로 관리
2. **데이터베이스**: AWS RDS 등 프로덕션 데이터베이스 사용
3. **CORS**: 허용된 도메인만 설정
4. **로깅**: 프로덕션 모드에서는 INFO 레벨 이상만 로깅
5. **보안**: SECRET_KEY는 반드시 강력한 랜덤 문자열 사용

## 📊 데이터베이스 모델

### User
- 사용자 정보 및 통계 (CPM, WPM, 정확도, 콤보 등)
- 랭킹 점수 (ranking_score)

### TypingText
- 타이핑 텍스트 정보 (장르, 제목, 내용, 이미지)

### TypingResult
- 타이핑 결과 기록 (CPM, WPM, 정확도, 콤보)

### TestReport / TestCaseResult / ApiPerformance
- 테스트 리포트 및 API 성능 모니터링 데이터

## 📝 라이선스

이 프로젝트는 학습 목적으로 제작되었습니다.

## 👥 기여

이슈 및 풀 리퀘스트를 환영합니다!

