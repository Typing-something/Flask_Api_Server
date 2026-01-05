from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine
from flask_sqlalchemy import SQLAlchemy

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# metadata에 naming_convention을 적용하여 db 객체 생성
db = SQLAlchemy(metadata=MetaData(naming_convention=convention))

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # [수정 포인트] 연결된 DB 드라이버 이름을 확인합니다.
    # sqlite3 모듈을 사용하는 경우에만 PRAGMA를 실행합니다.
    if dbapi_connection.__class__.__module__ == 'sqlite3':
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    # MySQL(pymysql)인 경우에는 아무 작업도 하지 않고 넘어갑니다.