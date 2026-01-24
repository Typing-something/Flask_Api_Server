import random
from locust import HttpUser, task, between, tag

class TypingFullCircuitTest(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # 1. 현재 DB에 확실히 존재하는 유저 ID로 설정 (MySQL에서 확인하신 번호)
        self.user_id = 3 
        self.target_text_id = None
        self.target_result_id = None
        
        # 시작하자마자 지문 ID 하나는 무조건 확보하고 시작하게 만듭니다.
        self.ensure_text_id()

    def ensure_text_id(self):
        """target_text_id가 None일 경우 서버에서 하나 가져오는 내부 함수"""
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
    @task(8)
    def text_detail_flow(self):
        # ID가 없으면 실행 안 함 (404 방지)
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
                    self.target_result_id = history[0]['result_id']
                r.success()

        if self.target_result_id:
            self.client.get(f"/text/results/{self.target_text_id}/{self.user_id}/{self.target_result_id}", name="/text/results/[tid]/[uid]/[rid]")

    @tag('user_get')
    @task(6)
    def user_profile_flow(self):
        self.client.get(f"/user/profile/{self.user_id}", name="/user/profile/[id]")
        self.client.get("/user/users", name="/user/users")
        self.client.get("/user/ranking?limit=10", name="/user/ranking")

    @tag('write_heavy')
    @task(3)
    def result_write_and_cleanup(self):
        if not self.target_text_id:
            return

        payload = {
            "user_id": self.user_id, 
            "text_id": self.target_text_id,
            "cpm": random.randint(300, 600), 
            "wpm": 80, 
            "accuracy": 98.0, 
            "combo": 50
        }
        with self.client.post("/text/results", json=payload, name="/text/results", catch_response=True) as r:
            if r.status_code == 201:
                rid = r.json().get('data', {}).get('result_id')
                if rid:
                    # 삭제 시 에러가 나더라도 부하 테스트 전체가 터지지 않게 관리
                    self.client.delete(f"/text/results/{self.target_text_id}/{self.user_id}/{rid}", name="/text/results/[tid]/[uid]/[rid]")
                r.success()
            else:
                r.failure(f"Post failed: {r.status_code}")