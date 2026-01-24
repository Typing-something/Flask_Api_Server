import json, requests, os, subprocess, csv, glob

def get_git_info():
    try:
        rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        return rev
    except:
        return "unknown"

def run_commands():
    target_host = os.getenv("TARGET_HOST", "http://localhost:5000")
    print(f"🎬 [DEBUG] 테스트 및 부하 측정 시작 (목적지: {target_host})")
    
    # 1. Pytest 실행 (결과 파일이 없을 때만 실행)
    if not os.path.exists("result.json"):
        print(f"🧪 1. Pytest 실행 중...")
        subprocess.run(["pytest", "--json-report", "--json-report-file=result.json"], check=True)
    
    # 2. Locust 부하 테스트 실행
    print(f"🚀 2. Locust 부하 테스트 실행 중...")
    subprocess.run([
        "locust", 
        "-f", "tests/load/locustfile.py",
        "--headless", 
        "-u", "50", 
        "-r", "5", 
        "--run-time", "10", 
        "--csv", "perf",
        "--host", target_host
    ], check=True)

def send_combined_report():
    print("📡 [DEBUG] 리포트 데이터 취합 및 전송 준비 중...")
    git_hash = get_git_info()
    
    if not os.path.exists("result.json"):
        print("❌ [ERROR] result.json 파일을 찾을 수 없어 전송을 중단합니다.")
        return

    with open("result.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    perf_results = []
    if os.path.exists("perf_stats.csv"):
        with open("perf_stats.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Name'] != 'Aggregated':
                    try:
                        total_req = int(row.get('Request Count', 0) or 0)
                        fail_count = int(row.get('Failure Count', 0) or 0)
                        
                        perf_results.append({
                            "method": row['Type'],
                            "endpoint": row['Name'],
                            "avg_latency": float(row.get('Average Response Time', 0) or 0),
                            "p95_latency": float(row.get('95%', 0) or 0),
                            "p99_latency": float(row.get('99%', 0) or 0),
                            "max_latency": float(row.get('Max Response Time', 0) or 0),
                            "rps": float(row.get('Requests/s', 0) or 0),
                            "total_requests": total_req,
                            "fail_count": fail_count,
                            "error_rate": round((fail_count / total_req * 100), 2) if total_req > 0 else 0
                        })
                    except (ValueError, KeyError) as e:
                        print(f"⚠️ CSV 파싱 중 건너뜀: {e}")
                        continue

    payload = {
        "git_commit": git_hash,
        "total": test_data.get("summary", {}).get("total", 0),
        "passed": test_data.get("summary", {}).get("passed", 0),
        "failed": test_data.get("summary", {}).get("failed", 0),
        "user_count": 50,
        "pytest_results": [
            {
                "test_name": t['nodeid'].split("::")[-1],
                "status": t['outcome'],
                "message": t.get('call', {}).get('longrepr', "") if t['outcome'] == 'failed' else ""
            } for t in test_data.get("tests", [])
        ],
        "perf_results": perf_results
    }

    base_url = os.getenv("SERVER_URL", "http://localhost:5000")
    target_url = f"{base_url}/admin/report"
    print(f"📤 [DEBUG] 전송 목적지: {target_url}")

    print("-" * 50)
    print(f"🚀 [REAL-TIME CHECK] 전송 시작!")
    print(f"📍 목적지 주소: {target_url}")
    print(f"📦 데이터 크기: {len(json.dumps(payload))} bytes")
    print(f"🔑 환경변수 SERVER_URL 상태: {os.getenv('SERVER_URL')}")
    print("-" * 50)

    
    try:
        response = requests.post(target_url, json=payload, timeout=20)
        print(f"✅ 리포트 전송 결과: {response.status_code}")
        print(f"📝 서버 응답: {response.text}")
    except Exception as e:
        print(f"❌ 서버 전송 실패: {e}")

def cleanup_files():
    print("🧹 [DEBUG] 임시 결과 파일 정리 중...")
    for f in glob.glob("perf_*"):
        try: os.remove(f)
        except: pass
    if os.path.exists("result.json"):
        try: os.remove("result.json")
        except: pass

# 🔥 가장 중요한 실행문 블록!
if __name__ == "__main__":
    print("🏁 스크립트 가동 시작")
    try:
        run_commands()           # 1. 테스트 실행 및 파일 생성
        send_combined_report()    # 2. 결과 전송
        cleanup_files()           # 3. 정리
        print("✅ 모든 작업 완료")
    except Exception as e:
        print(f"🧨 [FATAL] 실행 중 치명적 오류 발생: {e}")