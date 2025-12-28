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
    # SQLite를 사용하는 경우에만 외래 키 제약 조건을 강제로 켭니다.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()