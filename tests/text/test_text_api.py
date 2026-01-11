import pytest
import io
from unittest.mock import patch
from app.models import User, TypingText, TypingResult
from app.database import db

class TestTextAPI:
    """텍스트 관련 모든 API(누락분 포함) 통합 테스트"""

    @pytest.fixture(autouse=True)
    def setup_method(self, app):
        """매 테스트마다 독립적인 데이터 생성"""
        with app.app_context():
            # 1. 유저 생성
            self.user = User(username="testuser", email="test@test.com")
            
            # 2. 텍스트 샘플 여러 개 생성 (장르별/랜덤 테스트용)
            self.t1 = TypingText(genre="소설", title="소설 제목", author="작가1", content="내용1")
            self.t2 = TypingText(genre="IT", title="IT 제목", author="작가2", content="내용2")
            
            db.session.add_all([self.user, self.t1, self.t2])
            db.session.commit()
            
            self.u_id = self.user.id
            self.t1_id = self.t1.id

    # --- [기존 API 테스트] ---
    def test_get_all_texts(self, client):
        response = client.get('/text/all')
        assert response.status_code == 200
        assert len(response.get_json()['data']) >= 2

    # --- [추가된 API 테스트: 랜덤 조회] ---
    def test_get_random_texts(self, client):
        """랜덤 조회 API 검증 (limit_val 동작 확인)"""
        # limit_val을 1로 설정하여 요청
        response = client.get('/text/main/1')
        res_data = response.get_json()
        print(res_data)
        assert response.status_code == 200
        assert len(res_data['data']) == 1
        assert "is_favorite" in res_data['data'][0]

    # --- [추가된 API 테스트: 장르별 필터링] ---
    def test_get_texts_by_genre(self, client):
        """장르 필터링 API 검증"""
        # 'IT' 장르만 조회
        response = client.get('/text/?genre=IT')
        res_data = response.get_json()
        
        assert response.status_code == 200
        assert len(res_data['data']) == 1
        assert res_data['data'][0]['genre'] == "IT"

    # --- [추가된 API 테스트: 명예의 전당(최고 점수)] ---
    def test_get_global_best_score(self, client, app):
        """특정 글의 1등 기록 조회 검증"""
        # 1. 테스트용 기록 먼저 강제 삽입
        with app.app_context():
            result = TypingResult(
                user_id=self.u_id, 
                text_id=self.t1_id, 
                cpm=999,  # 압도적인 기록
                wpm=200, 
                accuracy=100.0, 
                combo=50
            )
            db.session.add(result)
            db.session.commit()

        # 2. 1등 기록 API 호출
        response = client.get(f'/text/results/best?text_id={self.t1_id}')
        res_data = response.get_json()
        
        assert response.status_code == 200
        assert res_data['data']['top_player'] == "testuser"
        assert res_data['data']['best_cpm'] == 999

    # --- [기존 API 테스트: 결과 저장] ---
    def test_save_typing_result(self, client):
        payload = {
            "user_id": self.u_id,
            "text_id": self.t1_id,
            "cpm": 500,
            "wpm": 100,
            "accuracy": 95.5,
            "combo": 30
        }
        response = client.post('/text/results', json=payload)
        assert response.status_code == 201
        assert response.get_json()['data']['play_count'] == 1

    # --- [기존 API 테스트: 삭제] ---
    def test_delete_text(self, client):
        response = client.delete(f'/text/{self.t1_id}')
        assert response.status_code == 200