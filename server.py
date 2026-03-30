"""
Vercel Flask entrypoint.

Vercel은 Flask 배포 시 `app` 인스턴스를 가진 모듈을 엔트리포인트로 사용합니다.
이 파일을 루트에 두면(Zero-config) Vercel이 `app`을 바로 불러올 수 있습니다.
"""

import os

from app import create_app


# Vercel 배포 환경에서는 기본적으로 production 설정을 사용합니다.
os.environ.setdefault("FLASK_ENV", "production")

# WSGI app instance (Vercel이 호출)
app = create_app()

