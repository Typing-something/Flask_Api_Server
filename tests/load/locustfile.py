import random
from locust import HttpUser, task, between, tag

class TypingFullCircuitTest(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # 💡 MySQL 명단에서 확인된 실제 유저 ID들 중 하나를 랜덤하게 선택합니다.
        # 명단에 1, 2, 3, 4, 5번이 있는 것을 확인했으므로 해당 범위를 사용합니다.
        self.user_id = 3
        self.target_text_id = None
        self.target_result_id = None

    # --- [Text GET API 7종] ---
    @tag('text_get')
    @task(10)
    def text_list_flow(self):
        # 1. 전체 조회 (with 블록 에러 해결을 위해 catch_response=True 추가)
        with self.client.get("/text/all", name="/text/all", catch_response=True) as r:
            if r.status_code == 200:
                data = r.json().get('data', [])
                if data: 
                    self.target_text_id = random.choice(data)['id']
                r.success()
            else:
                r.failure(f"Failed to get texts: {r.status_code}")

        # 2. 랜덤 조회
        self.client.get(f"/text/main/10?user_id={self.user_id}", name="/text/main/[limit]")
        # 3. 장르별 필터링
        self.client.get("/text/?genre=IT", name="/text/?genre=X")

    @tag('text_get')
    @task(8)
    def text_detail_flow(self):
        if self.target_text_id:
            # 4. 글 상세 정보
            self.client.get(f"/text/{self.target_text_id}?user_id={self.user_id}", name="/text/[id]")
            # 5. 명예의 전당
            self.client.get(f"/text/results/best?text_id={self.target_text_id}", name="/text/results/best")

    @tag('text_get')
    @task(5)
    def text_history_flow(self):
        if self.target_text_id:
            # 6. 지문별 내 이력 (catch_response=True 추가)
            with self.client.get(f"/text/{self.target_text_id}/history/{self.user_id}", name="/text/[id]/history/[uid]", catch_response=True) as r:
                if r.status_code == 200:
                    history = r.json().get('data', {}).get('history', [])
                    if history: 
                        self.target_result_id = history[0]['result_id']
                    r.success()
                else:
                    r.failure(f"History fetch failed: {r.status_code}")

            # 7. 정밀 결과 상세
            if self.target_result_id:
                self.client.get(f"/text/results/{self.target_text_id}/{self.user_id}/{self.target_result_id}", name="/text/results/[tid]/[uid]/[rid]")

    # --- [User GET API 7종] ---
    @tag('user_get')
    @task(6)
    def user_profile_flow(self):
        # 8. 내 프로필 요약 (실제 user_id 사용)
        self.client.get(f"/user/profile/{self.user_id}", name="/user/profile/[id]")
        # 9. 전체 유저 리스트
        self.client.get("/user/users", name="/user/users")
        # 10. 전체 랭킹
        self.client.get("/user/ranking?limit=10", name="/user/ranking")

    @tag('user_get')
    @task(4)
    def user_history_flow(self):
        # 11. 유저 전체 이력
        self.client.get(f"/user/history/all/{self.user_id}", name="/user/history/all/[id]")
        # 12. 유저 최근 이력
        self.client.get(f"/user/history/recent/{self.user_id}?limit=5", name="/user/history/recent/[id]")
        # 13. 유저 장르별 이력
        self.client.get(f"/user/history/genre/{self.user_id}?genre=IT", name="/user/history/genre/[id]")
        # 14. 유저 찜 목록
        self.client.get(f"/user/favorite/{self.user_id}", name="/user/favorite/[id]")

    # --- [POST + DELETE 1종] ---
    @tag('write_heavy')
    @task(3)
    def result_write_and_cleanup(self):
        # 15. 결과 저장 후 삭제 (catch_response=True 추가)
        if self.target_text_id:
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
                        self.client.delete(f"/text/results/{self.target_text_id}/{self.user_id}/{rid}", name="/text/results/[tid]/[uid]/[rid]")
                    r.success()
                else:
                    r.failure(f"Post result failed: {r.status_code}")