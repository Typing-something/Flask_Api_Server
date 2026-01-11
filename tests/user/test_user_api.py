import pytest
from app.models import User, TypingText, TypingResult
from app.database import db

class TestUserAPI:
    """유저 프로필, 히스토리 및 랭킹 API 테스트 클래스"""

    @pytest.fixture(autouse=True)
    def setup_method(self, app):
        """매 테스트마다 유저, 텍스트, 기록 데이터 생성"""
        with app.app_context():
            # 1. 테스트 유저 생성 (통계치 포함)
            self.user = User(
                username="tester", 
                email="tester@example.com",
                ranking_score=1500,
                play_count=1,
                best_cpm=500
            )
            
            # 2. 테스트용 텍스트 및 결과 기록 생성
            self.text = TypingText(genre="소설", title="소설 제목", content="본문 내용")
            db.session.add_all([self.user, self.text])
            db.session.commit()

            self.result = TypingResult(
                user_id=self.user.id,
                text_id=self.text.id,
                cpm=500,
                wpm=100,
                accuracy=98.0,
                combo=50
            )
            db.session.add(self.result)
            db.session.commit()

            self.u_id = self.user.id

    # 1. 프로필 조회 테스트
    def test_get_user_profile(self, client):
        response = client.get(f'/user/profile/{self.u_id}')
        res_data = response.get_json()

        assert response.status_code == 200
        assert res_data['success'] is True
        # 구조 검증 (account, stats 분리 여부)
        assert "account" in res_data['data']
        assert "stats" in res_data['data']
        assert res_data['data']['account']['username'] == "tester"
        assert res_data['data']['stats']['best_cpm'] == 500

    # 2. 전체 히스토리 조회 테스트
    def test_get_all_history(self, client):
        response = client.get(f'/user/history/all/{self.u_id}')
        res_data = response.get_json()

        assert response.status_code == 200
        assert len(res_data['data']) >= 1
        # 조인된 텍스트 정보 확인
        assert res_data['data'][0]['text_info']['title'] == "소설 제목"

    # 3. 최근 히스토리 조회 테스트 (Query Parameter 사용)
    def test_get_recent_history(self, client):
        # limit=1로 요청
        response = client.get(f'/user/history/recent/{self.u_id}?limit=1')
        res_data = response.get_json()

        assert response.status_code == 200
        assert len(res_data['data']) == 1
        assert "result_id" in res_data['data'][0]

    # 4. 장르별 히스토리 조회 테스트
    def test_get_history_by_genre(self, client):
        # 존재하는 장르 '소설'로 조회
        response = client.get(f'/user/history/genre/{self.u_id}?genre=소설')
        res_data = response.get_json()

        assert response.status_code == 200
        assert res_data['data'][0]['text_info']['genre'] == "소설"

        # 존재하지 않는 장르 조회 시 빈 배열 확인
        response_empty = client.get(f'/user/history/genre/{self.u_id}?genre=과학')
        assert len(response_empty.get_json()['data']) == 0

    # 5. 유저 랭킹 조회 테스트
    def test_get_user_ranking(self, client):
        response = client.get('/user/ranking?limit=10')
        res_data = response.get_json()

        assert response.status_code == 200
        assert isinstance(res_data['data'], list)
        # 랭킹 순서 및 구조 확인
        if len(res_data['data']) > 0:
            assert res_data['data'][0]['rank'] == 1
            assert "ranking_score" in res_data['data'][0]['account']