import pytest
import io
from unittest.mock import patch
from app.models import User, TypingText, TypingResult
from app.database import db

class TestTextAPI:
    """텍스트 관련 모든 API(누락분 포함) 통합 테스트"""
   
    def test_TC001_전체텍스트_조회_확인(self, client,setup_data):
        response = client.get('/text/all')
        res_data = response.get_json()
        assert response.status_code == 200
        assert 'data' in res_data
        
        result = res_data["data"] 
        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'title'}
        
        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0
        

    def test_TC002_get_random_texts(self, client, setup_data):
        """랜덤 조회 API 검증 (limit_val 동작 확인)"""
        # limit_val을 1로 설정하여 요청
        response = client.get('/text/main/1')
        res_data = response.get_json()
        
        assert response.status_code == 200
        assert 'data' in res_data
        
        result = res_data["data"]
        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'is_favorite', 'title'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

  
    def test_TC003_get_texts_by_genre(self, client, setup_data):
        """장르 필터링 API 검증"""
        # 'IT' 장르만 조회
        response = client.get('/text/?genre=IT')
        res_data = response.get_json()
        
        assert response.status_code == 200
        assert 'data' in res_data
        
        result = res_data["data"]

        expect_res_attr = {'author', 'content', 'genre', 'id', 'image_url', 'title'}

        for attr in result:
            check_res_attr = expect_res_attr.difference(set(attr.keys()))
            assert len(check_res_attr) == 0

    def test_TC004_get_global_best_score(self, client, setup_data):
        """특정 글의 1등 기록 조회 검증"""
        target_id = setup_data['t1_id']

        response = client.get(f'/text/results/best?text_id={target_id}')
        res_data = response.get_json()
        
        assert response.status_code == 200
        assert 'data' in res_data
        
        result = res_data["data"]
        
        expect_res_attr = {'best_accuracy', 'best_combo', 'best_cpm', 'best_wpm', 'date', 'profile_pic', 'top_player'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

       
    def test_TC005_save_typing_result(self, client, setup_data):
        payload = {
            "user_id": setup_data['u_id'], # self.u_id 대신!
            "text_id": setup_data['t1_id'],
            "cpm": 500,
            "wpm": 100,
            "accuracy": 95.5,
            "combo": 30
        }
        response = client.post('/text/results', json=payload)
        res_data = response.get_json()
        assert response.status_code == 201
        assert 'data' in res_data
        
        result = res_data["data"]

        expect_res_attr = {'avg_accuracy', 'avg_cpm', 'avg_wpm', 'best_cpm', 'best_wpm', 'is_new_record', 'max_combo', 'play_count', 'result_id'}
        check_res_attr = expect_res_attr.difference(set(result.keys()))
        assert len(check_res_attr) == 0

    def test_TC006_get_random_texts_check_favorite(self, client, setup_data):
        """랜덤 조회 시 찜 여부(is_favorite)가 정확히 나오는지 확인"""
        # 찜한 유저의 ID를 쿼리 파라미터로 전달
        u_id = setup_data['u_id']
        response = client.get(f'/text/main/10?user_id={u_id}')
        res_data = response.get_json()
        
        # 응답 데이터에서 t1과 t2를 찾아 찜 여부 검증
        for item in res_data['data']:
            if item['id'] == setup_data['t1_id']:
                assert item['is_favorite'] is True  # 찜한 글은 True여야 함
            if item['id'] == setup_data['t2_id']:
                assert item['is_favorite'] is False # 안 한 글은 False여야 함
        
    def test_TC007_delete_text(self, client, setup_data):
        response = client.delete(f'/text/{setup_data["t1_id"]}')
        target_text_id = setup_data["t1_id"]
        res_data = response.get_json()
        assert response.status_code == 200
        assert res_data['success'] is True
      