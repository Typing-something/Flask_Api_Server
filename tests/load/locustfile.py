import random
import os
from locust import HttpUser, task, between, tag

class TypingFullCircuitTest(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        # 부하테스트용 유저 ID (환경 변수 또는 기본값)
        self.user_id = int(os.getenv('LOCUST_TEST_USER_ID', 3))
        self.target_text_id = None
        self.target_result_id = None
        self.created_result_ids = []  # 생성한 결과 ID 추적
        self.ensure_text_id()

    def ensure_text_id(self):
        """기본 지문 ID 확보"""
        with self.client.get("/text/all", name="[Setup] Get Initial Text", catch_response=True) as r:
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    self.target_text_id = random.choice(data)['id']

    @tag('text_get')
    @task(10)
    def text_list_flow(self):
        with self.client.get("/text/all", name="/text/all", catch_response=True) as r:
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data: 
                    self.target_text_id = random.choice(data)['id']
                r.success()

    @tag('text_get')
    @task(9)
    def text_main_random_flow(self):
        """메인 페이지 랜덤 텍스트 조회"""
        limit = random.choice([5, 10, 15, 20])  # 다양한 limit 값 테스트
        with self.client.get(f"/text/main/{limit}?user_id={self.user_id}", name="/text/main/[limit]", catch_response=True) as r:
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data:
                    # 랜덤 텍스트 중 하나를 target으로 설정
                    self.target_text_id = random.choice(data)['id']
                r.success()

    @tag('text_get')
    @task(8)
    def text_detail_flow(self):
        if not self.target_text_id:
            self.ensure_text_id()
            return
        
        self.client.get(f"/text/{self.target_text_id}?user_id={self.user_id}", name="/text/[id]")
        self.client.get(f"/text/results/best?text_id={self.target_text_id}", name="/text/results/best")

    @tag('text_get')
    @task(5)
    def text_history_flow(self):
        if not self.target_text_id:
            return

        with self.client.get(f"/text/{self.target_text_id}/history/{self.user_id}", name="/text/[id]/history/[uid]", catch_response=True) as r:
            if r.status_code == 200:
                history = r.json().get('data', {}).get('history', [])
                if history: 
                    res_id = history[0]['result_id']
                    self.client.get(f"/text/results/{self.target_text_id}/{self.user_id}/{res_id}", name="/text/results/[tid]/[uid]/[rid]")
                r.success()

    @tag('user_get')
    @task(6)
    def user_profile_flow(self):
        self.client.get(f"/user/profile/{self.user_id}", name="/user/profile/[id]")
        self.client.get("/user/users", name="/user/users")
        self.client.get(f"/user/history/all/{self.user_id}", name="/user/history/all/[id]")
        self.client.get(f"/user/favorite/{self.user_id}", name="/user/favorite/[id]")

    @tag('text_post')
    @task(3)
    def save_result_flow(self):
        """타이핑 결과 저장 (부하테스트용)"""
        if not self.target_text_id:
            self.ensure_text_id()
            if not self.target_text_id:
                return
        
        # 랜덤한 결과 값 생성
        result_data = {
            'text_id': self.target_text_id,
            'user_id': self.user_id,
            'cpm': random.randint(100, 500),
            'wpm': random.randint(20, 100),
            'accuracy': round(random.uniform(80.0, 100.0), 2),
            'combo': random.randint(10, 100)
        }
        
        with self.client.post("/text/results", json=result_data, name="/text/results [POST]", catch_response=True) as r:
            if r.status_code == 201:
                response_data = r.json()
                if response_data.get('success') and 'data' in response_data:
                    result_id = response_data['data'].get('result_id')
                    if result_id:
                        self.created_result_ids.append({
                            'result_id': result_id,
                            'text_id': self.target_text_id,
                            'user_id': self.user_id
                        })
                r.success()
            else:
                r.failure(f"결과 저장 실패: {r.status_code}")