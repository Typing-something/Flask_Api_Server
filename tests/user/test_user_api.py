import pytest
from app.models import User, TypingText, TypingResult
from app.database import db

class TestUserAPI:
    """유저 프로필, 히스토리 및 랭킹 API 테스트 클래스"""

    # 1. 프로필 조회 테스트
    def test_get_user_profile(self, client, setup_data):

        user_id = setup_data["u_id"]
        
        response = client.get(f'/user/profile/{user_id}')
        res_data = response.get_json()
        # breakpoint()
        assert response.status_code == 200
        assert res_data['success'] is True
        # 구조 검증 (account, stats 분리 여부)

        result = res_data["data"]
        
        expect_res_attr = {'account', 'stats'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        account = result["account"]

        expect_account_attr = {'email', 'profile_pic', 'ranking_score', 'user_id', 'username'}
        check_account_attr = expect_account_attr.difference(set(account.keys()))
        assert len(check_account_attr) == 0

        stats = result["stats"]

        expect_stats_attr = {'avg_accuracy', 'avg_cpm', 'avg_wpm', 'best_cpm', 'best_wpm', 'max_combo', 'play_count'}
        check_stats_attr = expect_stats_attr.difference(set(stats.keys()))
        assert len(check_stats_attr) == 0



    # 2. 전체 히스토리 조회 테스트
    def test_get_all_history(self, client,setup_data):
        user_id = setup_data["u_id"]
        response = client.get(f'/user/history/all/{user_id}')
        res_data = response.get_json()

        assert response.status_code == 200
        assert 'data' in res_data

        result = res_data["data"]

        expect_res_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'text_info', 'wpm'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

            expect_text_info_attr = {"id", "title", "author", "genre", "image_url"}
            check_text_info_attr = expect_text_info_attr.difference(set(attr["text_info"]))
            assert len(check_text_info_attr) == 0

        # 조인된 텍스트 정보 확인
        

    # 3. 최근 히스토리 조회 테스트 (Query Parameter 사용)
    def test_get_recent_history(self, client, setup_data):
        user_id = setup_data["u_id"]
        response = client.get(f'/user/history/recent/{user_id}?limit=1')
        res_data = response.get_json()

        assert response.status_code == 200
        assert len(res_data['data']) == 1
        assert 'data' in res_data

        result = res_data["data"]

        for attr in result:

            expect_res_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'text_info', 'wpm'}
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

            expect_text_info_attr = {"id", "title", "author", "genre", "image_url", "content_preview"}
            check_text_info_attr = expect_text_info_attr.difference(set(attr["text_info"]))
            assert len(check_text_info_attr) == 0

    # 4. 장르별 히스토리 조회 테스트
    def test_get_history_by_genre(self, client,setup_data):
        user_id = setup_data["u_id"]
        response = client.get(f'/user/history/genre/{user_id}?genre=소설')
        res_data = response.get_json()

        res_data = response.get_json()

        assert response.status_code == 200
        assert 'data' in res_data

        result = res_data["data"]

        expect_res_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'text_info', 'wpm'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

            expect_text_info_attr = {"id", "title", "author", "genre", "image_url"}
            check_text_info_attr = expect_text_info_attr.difference(set(attr["text_info"]))
            assert len(check_text_info_attr) == 0

        # 존재하지 않는 장르 조회 시 빈 배열 확인
        response_empty = client.get(f'/user/history/genre/{user_id}?genre=과학')
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