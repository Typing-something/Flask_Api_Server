from locust import HttpUser, task, between

class TypingAllTest(HttpUser):
    # 실제 사람처럼 각 조회 사이에 1~2초간 대기합니다.
    # 만약 아주 극한의 부하를 주고 싶다면 between(0.1, 0.5)로 줄여보세요! ㅋ
    wait_time = between(1, 2)

    @task
    def view_all_texts(self):
        """전체 텍스트 목록 조회 API 테스트"""
        # views.py의 @text_blueprint.route('/all') 경로를 호출합니다.
        # Blueprint 이름이 'text'이고 서버 설정에 따라 /text/all 일 수 있으니 확인하세요!
        
        with self.client.get("/text/all", catch_response=True) as response:
            if response.status_code == 200:
                # 응답 성공 시
                response.success()
            else:
                # 응답 실패 시 (500 에러 등 발생 시 로그에 남음)
                response.failure(f"목록 조회 실패! 상태코드: {response.status_code}")