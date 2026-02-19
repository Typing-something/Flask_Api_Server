"""
Redis 클라이언트 모듈.
REDIS_URL 환경변수가 설정되어 있으면 Redis 캐시를 사용하고,
없으면 None을 반환하여 캐시 없이 DB 직접 조회합니다.
"""
import os
import json

_redis_client = None

# 유저 관련 캐시 TTL (초)
USER_CACHE_TTL = 180  # 3분


def init_redis():
    """환경변수 REDIS_URL이 있으면 Redis 클라이언트를 초기화합니다."""
    global _redis_client
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        _redis_client = None
        return None
    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_client = None
        return None


def get_redis():
    """Redis 클라이언트를 반환합니다. 미설정 시 None."""
    global _redis_client
    if _redis_client is None and os.getenv("REDIS_URL"):
        init_redis()
    return _redis_client


def cache_get(key: str):
    """캐시에서 JSON 데이터를 조회합니다. 없으면 None."""
    r = get_redis()
    if not r:
        return None
    try:
        data = r.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None


def cache_set(key: str, value, ttl: int = USER_CACHE_TTL):
    """캐시에 JSON 데이터를 저장합니다."""
    r = get_redis()
    if not r:
        return False
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def invalidate_user_cache():
    """유저 관련 캐시(랭킹, 전체유저, 프로필)를 전부 삭제합니다."""
    r = get_redis()
    if not r:
        return
    try:
        for key in r.scan_iter("user:*"):
            r.delete(key)
    except Exception:
        pass
