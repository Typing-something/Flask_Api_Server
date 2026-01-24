import random
from locust import HttpUser, task, between, tag

class TypingFullCircuitTest(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        # MySQL에서 확인된 유효한 유저 ID
        self.user_id = 3 
        self.target_text_id = None
        self.target_result_id = None
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