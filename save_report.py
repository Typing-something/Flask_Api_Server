import json, requests, os, subprocess, csv, glob

def get_git_info():
    try:
        rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        return rev
    except:
        return "unknown"

def run_commands():
    target_host = os.getenv("TARGET_HOST", "http://localhost:5000")
    
    if not os.path.exists("result.json"):
        print(f"🧪 1. Pytest 실행 중...")
        subprocess.run(["pytest", "--json-report", "--json-report-file=result.json"])
    
    print(f"🚀 2. Locust 부하 테스트 실행 중 (목적지: {target_host})...")
    # 💡 런타임과 유저 수를 상황에 맞게 조절하세요 (예: 5m, -u 50)
    subprocess.run([
        "locust", 
        "-f", "tests/load/locustfile.py",
        "--headless", 
        "-u", "50", 
        "-r", "5", 
        "--run-time", "1m", 
        "--csv", "perf",
        "--host", target_host
    ])

def send_combined_report():
    git_hash = get_git_info()
    
    if not os.path.exists("result.json"):
        print("❌ result.json 파일을 찾을 수 없습니다.")
        return

    with open("result.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    perf_results = []
    # Locust CSV 파일명은 --csv 옵션값 뒤에 _stats.csv가 붙습니다.
    if os.path.exists("perf_stats.csv"):
        with open("perf_stats.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Name'] != 'Aggregated':
                    try:
                        # 💡 관리자 대시보드용 정밀 데이터 추출
                        total_req = int(row.get('Request Count', 0) or 0)
                        fail_count = int(row.get('Failure Count', 0) or 0)
                        
                        perf_results.append({
                            "method": row['Type'],
                            "endpoint": row['Name'],
                            "avg_latency": float(row.get('Average Response Time', 0) or 0),
                            "p95_latency": float(row.get('95%', 0) or 0),     # 상위 5% 지표
                            "p99_latency": float(row.get('99%', 0) or 0),     # 상위 1% 지표
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
        "user_count": 50, # 실행 시 설정한 유저 수
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
    
    try:
        response = requests.post(target_url, json=payload)
        print(f"✅ 리포트 전송 결과: {response.status_code}")
    except Exception as e:
        print(f"❌ 서버 전송 실패: {e}")

# (이하 cleanup_files 및 main은 동일)