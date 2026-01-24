import pytest
import io, random
from tests.utils import random_string, pick_random, random_number
from unittest.mock import patch
from app.models import User, TypingText, TypingResult
from app.database import db

"""
내가 찜한 글 text_id_list 받기받기
텍스트 id_list로 받아서 화면에 그릴 때 쓰는 정보 주기
"""


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

@pytest.fixture(scope='class')
def create_text(client):
    """텍스트 생성을 담당하는 팩토리 피스처"""
    def _create_text(genre="IT", title=None, author=None, content=None):
        # 1. 랜덤 데이터 및 가짜 파일 준비
        expect_title = title or f"Title_{random_string(5, 10)}"
        expect_author = author or f"Author_{random_string(3, 8)}"
        expect_content = content or random_string(50, 100)
        
        img_content = b"fake-image-binary-content"
        img_file = (io.BytesIO(img_content), 'test_profile.png')

        payload = {
            "genre": genre,
            "title": expect_title,
            "author": expect_author,
            "content": expect_content,
            "image": img_file
        }

        # 2. S3 모킹을 유지한 채 API 호출 (이 피스처를 사용하는 곳에서 patch 필요)
        response = client.post(
            '/text/add', 
            data=payload, 
            content_type='multipart/form-data'
        )
        
        return response, payload

    return _create_text

@pytest.fixture(scope='class')
def create_text_result(client):
    """텍스트 생성을 담당하는 팩토리 피스처"""
    def _create_text_result(user_id, text_id, cpm=None, wpm=None, accuracy=None, combo=None):
        # 1. 랜덤 데이터 및 가짜 파일 준비
        body = {
            "user_id": user_id,
            "text_id": text_id,
            "cpm": cpm or random_number(300, 600),
            "wpm": wpm or random_number(60, 120),
            "accuracy": accuracy or round(random.uniform(90.0, 100.0), 1),
            "combo": combo or random_number(10, 50)
        }

        # 2. API 요청
        r = client.post('/text/results', json=body)
        
        return r, body

    return _create_text_result

class TestTextAPI:
    """텍스트 관련 모든 API(누락분 포함) 통합 테스트"""
    
    _store = {
        "user_ids": [],
        "text_ids": [],
        "text_result_ids" : [], 
        "target_text_id": None,
        "target_user_id" : None
    }

    @property
    def store(self):
        return self.__class__._store

    @patch('app.routes.text.views.s3')
    def test_TC201_텍스트_추가_확인(self, mock_s3, create_text):
        """텍스트 추가 팩토리 함수를 이용한 등록 검증"""
        # S3 Mock 설정
        mock_s3.upload_fileobj.return_value = True

        # 1. 팩토리 피스처를 사용하여 텍스트 생성
        response, body = create_text(genre="IT")

        # 2. 검증
        assert response.status_code == 201
        res_data = response.get_json()
        assert res_data['success'] is True
        assert "image_url" in res_data['data']
        
        # 3. ID 저장
        new_text_id = res_data['data']['id']
        self.store["target_text_id"] = new_text_id
        self.store["text_ids"].append(new_text_id)

        # 4. S3 호출 확인
        mock_s3.upload_fileobj.assert_called_once()
        
        # 5. 추가 샘플 텍스트 생성 (필요 시)
        for _ in range(10):
            create_text(genre="IT")



    def test_TC202_전체텍스트_조회_확인(self, client):
        
        r = client.get('/text/all')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')


        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'title'}
        
        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0
            self.store["text_ids"].append(attr["id"])
    
    def test_TC203_텍스트_단일조회_확인(self, client):
        
        text_id = pick_random(self.store["text_ids"])

        r = client.get(f'/text/{text_id}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        expect_res_attr = {'my_best', 'text_info'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        #user_id가 없는 case
        assert result["my_best"] is None

        text_info = result["text_info"]

        expect_text_info_attr = {'author', 'content', 'genre', 'id', 'image_url', 'is_favorite', 'title'}
        check_text_info_attr = expect_text_info_attr.difference(set(text_info.keys()))
        assert len(check_text_info_attr) == 0

    def test_TC204_타이핑__결과_저장_확인(self, client, create_text_result, get_users):
        """타이핑 결과 저장 및 실시간 랭킹 점수 업데이트 검증"""
        user_list = get_users() # 먼저 함수를 실행해서 리스트를 확보
        user_id = pick_random(user_list)
        text_id = pick_random(self.store["text_ids"])

        r, body = create_text_result(user_id, text_id)

        assert r.status_code == 201
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        # [수정] 현재 API 응답 구조와 일치하도록 필드 목록 업데이트
        expect_res_attr = {
            'result_id', 
            'play_count', 
            'ranking_score', # 새로 추가된 랭킹 점수 필드
            'avg_accuracy', 
            'best_cpm', 
            'is_new_record'
        }
        
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        # 데이터 정합성 추가 확인
        assert result['ranking_score'] > 0

        self.store["user_ids"].extend(user_list)
        self.store["target_user_id"] = user_id
        self.store["target_text_id"] = text_id

        for _ in range(5):
            r, body = create_text_result(user_id, text_id)
            assert r.status_code == 201
            
        self.store['target_user_id'] = user_id
        self.store["target_text_id"] = text_id

    def test_TC205_텍스트_및_기록_단일조회_확인(self, client):
        
        user_id = self.store['target_user_id']
        text_id = self.store["target_text_id"]
        q = f'?user_id={user_id}'

        r = client.get(f'/text/{text_id}{q}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        expect_res_attr = {'my_best', 'text_info'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        text_info = result["text_info"]

        expect_text_info_attr = {'author', 'content', 'genre', 'id', 'image_url', 'is_favorite', 'title'}
        check_text_info_attr = expect_text_info_attr.difference(set(text_info.keys()))
        assert len(check_text_info_attr) == 0

        my_best = result["my_best"]

        expect_my_best_attr = {'accuracy', 'combo', 'cpm', 'date', 'wpm'}
        check_my_best_attr = expect_my_best_attr.difference(set(my_best.keys()))
        assert len(check_my_best_attr) == 0
    
    def test_TC206_특정텍스트_유저_기록_전체조회_확인(self, client):
        
        user_id = self.store['target_user_id']
        text_id = self.store["target_text_id"]

        expect_limit = random_number(1,10)

        q = f'?limit={expect_limit}'

        r = client.get(f'/text/{text_id}/history/{user_id}{q}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        expect_res_attr = {'history', 'text_id', 'user_id'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        history = result["history"]

        expect_text_info_attr = {'accuracy', 'combo', 'cpm', 'date', 'result_id', 'wpm'}

        for attr in history:
            check_text_info_attr = expect_text_info_attr.difference(set(attr.keys()))
            assert len(check_text_info_attr) == 0
            self.store["text_result_ids"].append(attr["result_id"])

    def test_TC207_특정텍스트_유저_기록_단일조회_확인(self, client):
        
        user_id = self.store['target_user_id']
        text_id = self.store["target_text_id"]
        result_id = pick_random(self.store["text_result_ids"])
        
        r = client.get(f'/text/results/{text_id}/{user_id}/{result_id}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        expect_res_attr = {'result_id', 'stats', 'text_id', 'user_id'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

        stats = result["stats"]

        expect_text_info_attr = {'accuracy', 'combo', 'cpm', 'date', 'wpm'}
        check_text_info_attr = expect_text_info_attr.difference(set(stats.keys()))
        assert len(check_text_info_attr) == 0
       
    def test_TC208_텍스트_랜덤_조회_확인(self, client):
        """랜덤 조회 API 검증 (limit_val 동작 확인)"""
       
        expect_limit = random_number(1,10)

        r = client.get(f'/text/main/{expect_limit}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')


        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'is_favorite', 'title'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

    def test_TC209_텍스트_장르별_조회_확인(self, client):
        """장르 필터링 API 검증"""
        # 'IT' 장르만 조회

        expect_genre = "IT"

        r = client.get(f'/text/?genre={expect_genre}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')


        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'title'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0
            assert attr["genre"] == expect_genre

   
    def test_TC210_텍스트_찜_추가_확인(self, client):
        """랜덤 조회 시 찜 여부(is_favorite)가 정확히 나오는지 확인"""
        # 찜한 유저의 ID를 쿼리 파라미터로 전달

        user_id = self.store['target_user_id']
        text_id = self.store["target_text_id"]
        q = f'?user_id={user_id}'

        r = client.get(f'/text/{text_id}{q}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        current_is_favorite = result["text_info"]["is_favorite"]

        body = {
            "user_id" : user_id,
            "text_id" : text_id
        }

        r = client.post('/text/favorite', json=body)

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True
        result = r_data.get('data')

        assert current_is_favorite != result["is_favorite"]

    def test_TC211_특정텍스트_1위_조회_확인(self, client):
        """특정 지문의 1등(명예의 전당) 데이터 조회 검증"""
        
        # 1. 기록이 있는 지문 조회
        text_id = self.store["target_text_id"]
        r = client.get(f'/text/results/best?text_id={text_id}')
        
        assert r.status_code == 200
        r_data = r.get_json()
        assert r_data['success'] is True
        
        result = r_data['data']
        # 필드 구조 검증
        expect_attr = {'top_player', 'profile_pic', 'best_cpm', 'best_wpm', 'best_accuracy', 'best_combo', 'date'}
        assert expect_attr.issubset(result.keys())
        
        # 실제 데이터 정합성 (최소 0 이상인지 확인)
        assert result['best_cpm'] > 0
        assert result['top_player'] != "No record"

        # 2. 기록이 없는 새로운 지문 생성 후 조회 (Empty Case)
        # 이전에 삭제되지 않은 ID 중 결과가 아예 없는 것이 있다면 활용하거나, 
        # 여기서는 극단적인 큰 ID값을 넣어 No record 케이스를 확인합니다.
        fake_text_id = 99999
        r_empty = client.get(f'/text/results/best?text_id={fake_text_id}')
        
        assert r_empty.status_code == 200
        empty_data = r_empty.get_json()['data']
        assert empty_data['top_player'] == "No record"
        assert empty_data['best_cpm'] == 0

    def test_TC212_연습결과_단일삭제_확인(self, client):
        """[삭제] 복합 식별자를 이용한 특정 연습 기록 삭제 검증"""
        
        # 1. 삭제할 대상 선정 (기존 store에 저장된 ID 활용)
        user_id = self.store['target_user_id']
        text_id = self.store["target_text_id"]
        
        # 삭제 전, 기록이 존재하는지 먼저 확인하기 위해 하나를 픽합니다.
        result_id = pick_random(self.store["text_result_ids"])

        # 2. 삭제 API 호출 (DELETE /text/results/<tid>/<uid>/<rid>)
        r = client.delete(f'/text/results/{text_id}/{user_id}/{result_id}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert r_data['success'] is True
        

        # 3. 삭제 데이터 확인 (GET으로 다시 조회했을 때 404가 나와야 함)
        r_check = client.get(f'/text/results/{text_id}/{user_id}/{result_id}')
        assert r_check.status_code == 404
        
        # 4. (선택적) 잘못된 ID로 삭제 시도 시 실패 확인
        # 유저 ID만 살짝 바꿔서 호출해봅니다.
        r_fail = client.delete(f'/text/results/{text_id}/99999/{result_id}')
        assert r_fail.status_code == 404

    def test_TC213텍스트_단일삭제_확인(self, client):
        
        text_id = pick_random(self.store["text_ids"])

        r = client.delete(f'/text/{text_id}')

        assert r.status_code == 200
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is True

        #삭제 데이터 확인
        r = client.get(f'/text/{text_id}')
        assert r.status_code == 404


    def test_TC214_존재하지_않는_텍스트_조회_확인(self, client):
        text_id = pick_random(self.store["text_ids"])

        text_id = 999999

        r = client.get(f'/text/{text_id}')

        assert r.status_code == 404
        r_data = r.get_json()
        assert 'data' in r_data
        assert r_data['success'] is False

    def test_TC215_필수값_누락_및_유효성_검사_통합_확인(self, client):
        """API에서 필수 파라미터가 누락되었을 때 400 에러를 반환하는지 확인"""
        
        payload = {
            "genre": "IT",
            "author": "Tester",
            "content": "Sample Content"
        }
        r = client.post('/text/add', data=payload, content_type='multipart/form-data')
        assert r.status_code in [400, 500] 

        # 2. 타자 결과 저장 API 필수값 누락 (JSON)
        # cpm, accuracy 등을 빼고 전송
        incomplete_body = {
            "user_id": self.store['target_user_id'],
            "text_id": self.store["target_text_id"]
            # cpm, accuracy, combo 누락
        }
        r = client.post('/text/results', json=incomplete_body)
        assert r.status_code == 400
        assert r.get_json()['success'] is False

        # 3. 찜하기 토글 API 필수값 누락 (JSON)
        # user_id만 보내고 text_id 누락
        r = client.post('/text/favorite', json={"user_id": self.store['target_user_id']})
        assert r.status_code == 400
        r_data = r.get_json()
        assert r_data['success'] is False
        assert "text_id" in r_data['error']['message']

        # 4. 명예의 전당(Best) 조회 API 필수 쿼리 스트링 누락
        # text_id 없이 호출
        r = client.get('/text/results/best')
        assert r.status_code == 400
        r_data = r.get_json()
        assert r_data['success'] is False
        assert "text_id" in r_data['error']['message']


        # 5. 빈 JSON 본문 전송 테스트
        r = client.post('/text/results', json={})
        assert r.status_code == 400
        
   
      
    
   