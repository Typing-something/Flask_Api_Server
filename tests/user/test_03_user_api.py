import pytest
from tests.utils import random_string, pick_random, random_number


@pytest.fixture(scope='class')
def get_users(client):
    """텍스트 생성을 담당하는 팩토리 피스처"""
    def _get_users(genre="IT", title=None, author=None, content=None):
        
        r = client.get('/user/users')

        user_ids = []

        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')
        users = result["users"]
        for attr in users:
                expect_user_attr = {'account', 'stats'}
                check_user_attr = expect_user_attr.difference(set(attr.keys()))
                assert len(check_user_attr) == 0

                stats = attr["stats"]

                expect_stats_attr = {'avg_accuracy', 'avg_cpm', 'avg_wpm', 'best_cpm', 'best_wpm', 'max_combo', 'play_count'}
                check_stats_attr = expect_stats_attr.difference(set(stats.keys()))
                assert len(check_stats_attr) == 0

                account = attr["account"]
                # 여기 email을 저장해놓았다가 나중에 이름에따른 중복검증으로 활용하자. 
                expect_account_attr = {'email', 'profile_pic', 'ranking_score', 'user_id', 'username'}
                check_account_attr = expect_account_attr.difference(set(account.keys()))
                assert len(check_account_attr) == 0
                user_ids.append(account["user_id"])
        

        return user_ids

    return _get_users

class TestUserAPI:
    """유저 프로필, 히스토리, 랭킹 및 찜 목록 API 통합 테스트"""

    _store = {
        "target_user_id": None,
        "history_result_ids": [],
        "user_ids" : []
    }

    @property
    def store(self):
        return self.__class__._store

    def test_TC301_내_프로필_조회_확인(self, client, get_users):
        """특정 유저의 계정 정보 및 통계 데이터 구조 검증"""
        # 1. 테스트용 유저 ID 확보
        user_list = get_users()
        self.store["user_ids"].extend(user_list)
        user_id = pick_random(self.store["user_ids"])

        # 2. API 호출
        r = client.get(f'/user/profile/{user_id}')
        assert r.status_code == 200
        
        r_data = r.get_json()
        assert r_data['success'] is True
        result = r_data['data']  # result 내부에는 {'account': {...}, 'stats': {...}} 가 있음

        # 3. 계정(account) 필드 검증 - result['account']의 키값을 확인해야 함
        expect_account_attr = {'email', 'profile_pic', 'ranking_score', 'user_id', 'username'}
        check_account_attr = expect_account_attr.difference(set(result['account'].keys()))
        assert len(check_account_attr) == 0, f"Account 필드 누락: {check_account_attr}"

        # 4. 통계(stats) 필드 검증 - result['stats']의 키값을 확인해야 함
        expect_stats_attr = {'avg_accuracy', 'avg_cpm', 'avg_wpm', 'best_cpm', 'best_wpm', 'max_combo', 'play_count'}
        # [수정] 변수명 오타 수정 및 stats 키값 접근
        check_stats_attr = expect_stats_attr.difference(set(result['stats'].keys()))
        assert len(check_stats_attr) == 0, f"Stats 필드 누락: {check_stats_attr}"

        # 5. 데이터 값 정합성 추가 확인 (선택 사항이지만 추천)
        assert result['account']['user_id'] == user_id
    def test_TC302_전체_유저_목록_조회_확인(self, client):
        """관리자 혹은 랭킹용 전체 유저 데이터 반환 검증"""
        r = client.get('/user/users')
        assert r.status_code == 200
        
        r_data = r.get_json()
        assert r_data['success'] is True
        assert 'users' in r_data['data']
        assert r_data['data']['users_len'] > 0

        result = r_data['data']

        expect_res_attr = {'users', 'users_len'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        users = result["users"]

        expect_user_attr = {"account", "stats"}

        for attr in users:
            check_user_attr = expect_user_attr.difference(set(attr.keys()))
            assert len(check_user_attr) == 0

            account = attr["account"]

            expect_account_attr = {'email', 'profile_pic', 'ranking_score', 'user_id', 'username'}
            check_account_attr = expect_account_attr.difference(set(account.keys()))
            assert len(check_account_attr) == 0

            stats = attr["stats"]

            expect_stats_attr = {'avg_accuracy', 'avg_cpm', 'avg_wpm', 'best_cpm', 'best_wpm', 'max_combo', 'play_count'}
            check_stats_attr = expect_stats_attr.difference(set(stats.keys()))
            assert len(check_stats_attr) == 0

    

    def test_TC303_유저_전체_연습_기록_조회(self, client):
        """유저의 모든 연습 기록과 연결된 텍스트 정보 검증"""
        user_id = pick_random(self.store["user_ids"])
        

        for user_id in self.store["user_ids"]:

            r = client.get(f'/user/history/all/{user_id}')
            assert r.status_code == 200
            
            r_data = r.get_json()
            history = r_data['data']

   

            if len(history) !=0:
                # 첫 번째 기록의 구조 검증
                item = history[0]
                expect_item_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'text_info', 'wpm'}
                assert expect_item_attr.issubset(item.keys())
                
                # 연결된 텍스트 정보 검증
                expect_text_attr = {'author', 'genre', 'id', 'image_url', 'title'}
                assert expect_text_attr.issubset(item['text_info'].keys())
                self.store["target_user_id"] = user_id
   
    def test_TC304_최근_연습_기록_조회_Limit_확인(self, client):
        """최근 기록 조회 시 limit 파라미터 동작 여부 검증"""
        user_id = self.store["target_user_id"]
        limit = random_number(1,10)
        
        r = client.get(f'/user/history/recent/{user_id}?limit={limit}')
        assert r.status_code == 200
        
        r_data = r.get_json()
        assert r_data['success'] is True
        result = r_data['data']  # result 내부에는 {'account': {...}, 'stats': {...}} 가 있음
        
        expect_res_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'text_info', 'wpm'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

            text_info = attr["text_info"]

            expect_text_info_attr = {'author', 'content_preview', 'genre', 'id', 'image_url', 'title'}
            check_text_info_attr = expect_text_info_attr.difference(set(text_info.keys()))
            assert len(check_text_info_attr) == 0
    

    def test_TC305_장르별_히스토리_필터링_확인(self, client):
        """특정 장르로 필터링된 유저의 기록 조회 검증"""
        user_id = self.store["target_user_id"]
        target_genre = "IT" # 기본값 혹은 생성한 데이터의 장르
        
        r = client.get(f'/user/history/genre/{user_id}?genre={target_genre}')
        assert r.status_code == 200
        
        data = r.get_json()['data']
        for item in data:
            assert item['text_info']['genre'] == target_genre

    def test_TC306_유저_랭킹_목록_조회(self, client):
        """랭킹 스코어 기준 상위 유저 목록 및 순위(rank) 필드 검증"""
        limit = 5
        r = client.get(f'/user/ranking?limit={limit}')
        assert r.status_code == 200
        
        
        r_data = r.get_json()
        assert r_data['success'] is True
        result = r_data['data']


        temp_rank = 9999999

        for rank in result:
            
            assert rank["account"]["ranking_score"] < temp_rank

        
    def test_TC307_내가_찜한_글_메타_정보_조회(self, client):
        """유저가 찜한 글의 메타 데이터 목록 반환 검증 (본문 제외)"""
        user_id = self.store["target_user_id"]
        
        r = client.get(f'/user/favorite/{user_id}')
        assert r.status_code == 200
        
        data = r.get_json()['data']
        if data:
            item = data[0]
            # 메타 정보이므로 content는 없어야 하고 나머지는 있어야 함
            assert 'content' not in item
            expect_meta_attr = {'author', 'genre', 'id', 'image_url', 'title'}
            assert expect_meta_attr.issubset(item.keys())

    def test_TC308_존재하지_않는_유저_프로필_예외처리(self, client):
        """404 에러 시 api_response의 중첩된 에러 구조 검증"""
        invalid_user_id = 99999
        r = client.get(f'/user/profile/{invalid_user_id}')
        
        assert r.status_code == 404
        r_data = r.get_json()
        assert r_data['success'] is False
        # api_response 유틸리티의 중첩 구조 확인
        assert "유저" in r_data['error']['message']