from tokenize import Number, String
import pytest
import io
from unittest.mock import patch
from tests.utils import random_string, pick_random
from app.models import User, TypingText, TypingResult
from app.database import db

@pytest.fixture(scope='class')
def create_user(client):
    def _create_user(email=None, username=None):
        
        # 1. 가짜 이미지 생성
        image_content = b"fake-image-binary-content"
        expect_image_file = (io.BytesIO(image_content), 'test_profile.png')

        expect_username = username or random_string(min_len=8, max_len=12, use_upper=True)
        expect_email = email or f"{expect_username.lower()}@example.com"
       
    
        body = {
            "email": expect_email,
            "username": expect_username,
            "profile_image": expect_image_file
        }

        r = client.post('/auth/test-login', data = body, content_type='multipart/form-data')
        
        # API 응답에서 유저 데이터(user_id, email 등) 추출
        return r, body

    return _create_user


class TestAuthAPI:
    """ Auth 통합 테스트"""
    
    _store = {"user_ids": [], "target_email": ""}

    @property
    def store(self):
        return self.__class__._store
    #   회원 탈퇴 TC 
    # 유저 정보 수정 TC

    def test_TC101_회원가입_추가_확인(self, create_user):

        r, body = create_user()
        assert r.status_code == 201
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        
        result = r_data.get('data')
     
        expect_res_attr = {'email', 'user_id', 'username', "profile_pic", "is_admin"}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0
          
        # sample user 추가 
        for _ in range(5):
            r, body = create_user()
            assert r.status_code == 201
    def test_TC102_회원가입__유저목록_조회_확인(self, client):
        
        r = client.get('/user/users')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        expect_res_attr = {'users', 'users_len'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0
        # user 명단 수 검사
        assert len(result["users"]) == result["users_len"]

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
            self.store["user_ids"].append(account["user_id"])
        if result["users"]:
            self.store["target_email"]= result["users"][-1]["account"]["email"]
    
    def test_TC103_회원가입__유저목록_단일_확인(self, client):
        
        user_id = pick_random(self.store["user_ids"])

        r = client.get(f'/user/profile/{user_id}')

        assert r.status_code == 200
        r_data = r.get_json()

        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

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
    
    def test_TC104_기존_유저_재로그인_확인(self, create_user):
        existing_email = self.store["target_email"]
        assert existing_email != "" # 이메일이 잘 저장되어 있는지 확인

        r, body = create_user(email=existing_email)

        # 3. 검증
        assert r.status_code == 200  # 신규 생성이 아니므로 200이어야 함
        r_data = r.get_json()
        assert r_data['success'] is True

        result = r_data.get('data')
        assert result['email'] == existing_email
    