import json, requests, os, subprocess, csv, glob

def get_git_info():
    """현재 Git 커밋 해시 가져오기"""
    try:
        rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        return rev
    except:
        return "unknown"

def run_commands():
    target_host = os.getenv("TARGET_HOST", "http://localhost:5000")
    
    # 💡 수정: Pre-deployment 단계에서 이미 pytest를 돌렸다면 건너뜁니다 ㅋ
    if not os.path.exists("result.json"):
        print(f"🧪 1. Pytest 실행 중...")
        subprocess.run(["pytest", "--json-report", "--json-report-file=result.json"])
    else:
        print(f"✅ 1. 이미 Pytest 결과(result.json)가 존재합니다. 건너뜁니다. ㅋ")
    
    print(f"🚀 2. Locust 부하 테스트 실행 중 (목적지: {target_host})...")
    subprocess.run([
        "locust", 
        "-f", "tests/load/locustfile.py",
        "--headless", 
        "-u", "60", 
        "-r", "2", 
        "--run-time", "10s", 
        "--csv", "perf",
        "--host", target_host
    ])

def send_combined_report():
    git_hash = get_git_info()
    
    if not os.path.exists("result.json"):
        print("❌ result.json 파일을 찾을 수 없어 리포트 전송을 취소합니다.")
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
                        perf_results.append({
                            "method": row['Type'],
                            "endpoint": row['Name'],
                            "avg_latency": float(row.get('Average Response Time', 0) or 0),
                            "rps": float(row.get('Requests/s', 0) or 0),
                            "fail_count": int(row.get('Failure Count', 0) or 0)
                        })
                    except (ValueError, KeyError):
                        continue

    payload = {
        "git_commit": git_hash,
        "total": test_data.get("summary", {}).get("total", 0),
        "passed": test_data.get("summary", {}).get("passed", 0),
        "failed": test_data.get("summary", {}).get("failed", 0),
        "user_count": 60,
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

def cleanup_files():
    """생성된 임시 파일 정리"""
    print("🧹 임시 파일 정리 중...")
    patterns = ["perf_*.csv", "result.json"]
    for pattern in patterns:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                print(f"🗑️ 삭제됨: {f}")
            except Exception as e:
                print(f"⚠️ 삭제 실패 ({f}): {e}")

if __name__ == "__main__":
    try:
        run_commands()
        send_combined_report()
    finally:
        cleanup_files()