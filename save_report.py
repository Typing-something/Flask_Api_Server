import json, requests, os, subprocess, csv, glob, time

def get_git_info():
    try:
        rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        return rev
    except:
        return "unknown"

def check_server_health(target_host, max_retries=10, retry_delay=3):
    """서버가 준비될 때까지 대기"""
    
    print(f"🏥 서버 헬스 체크 시작: {target_host}")
    
    for i in range(max_retries):
        try:
            # 간단한 엔드포인트로 서버 확인
            response = requests.get(f"{target_host}/text/all", timeout=5)
            if response.status_code == 200:
                print(f"✅ 서버 준비 완료! ({i+1}번째 시도)")
                return True
        except Exception as e:
            print(f"⏳ 서버 대기 중... ({i+1}/{max_retries}) - {str(e)[:50]}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
    
    print(f"❌ 서버가 {max_retries * retry_delay}초 내에 응답하지 않았습니다.")
    return False

def run_commands():
    target_host = os.getenv("TARGET_HOST", "http://localhost:5000")
    print(f"🎬 [DEBUG] 테스트 및 부하 측정 시작 (목적지: {target_host})")
    
    # 1. Pytest 실행 (결과 파일이 없을 때만 실행)
    if not os.path.exists("result.json"):
        print(f"🧪 1. Pytest 실행 중...")
        subprocess.run(["pytest", "--json-report", "--json-report-file=result.json"], check=True)
    
    # 1.5. 서버 헬스 체크 (부하테스트 전에 서버가 준비되었는지 확인)
    if not check_server_health(target_host):
        print("⚠️ 서버가 준비되지 않았지만 부하테스트를 계속 진행합니다...")
    
    # 2. Locust 부하 테스트 실행
    print(f"🚀 2. Locust 부하 테스트 실행 중...")
    result = subprocess.run([
        "locust", 
        "-f", "tests/load/locustfile.py",
        "--headless", 
        "-u", "30", 
        "-r", "5", 
        "--run-time", "20s",
        "--csv", "perf",
        "--host", target_host
    ], check=False, capture_output=True, text=True)  # check=False로 변경하여 에러 상세 확인
    
    # Locust 실행 결과 확인
    print(f"📊 Locust 실행 완료 (exit code: {result.returncode})")
    if result.stdout:
        print(f"📝 Locust stdout 전체:\n{result.stdout}")
    if result.stderr:
        print(f"⚠️ Locust stderr:\n{result.stderr}")
    
    # Locust 실패 시 상세 에러 출력
    if result.returncode != 0:
        print(f"❌ Locust 실행 실패 (exit code: {result.returncode})")
        if result.stderr:
            print(f"🔍 상세 에러 메시지:\n{result.stderr}")
        raise Exception(f"Locust 부하 테스트 실패: {result.stderr or '알 수 없는 오류'}")
    
    # 생성된 CSV 파일 확인
    import glob
    csv_files = glob.glob("perf_*.csv")
    print(f"📁 생성된 CSV 파일: {csv_files}")
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            size = os.path.getsize(csv_file)
            print(f"   - {csv_file}: {size} bytes")

def send_combined_report():
    print("📡 [DEBUG] 리포트 데이터 취합 및 전송 준비 중...")
    git_hash = get_git_info()
    
    if not os.path.exists("result.json"):
        print("❌ [WARNING] result.json 파일을 찾을 수 없어 전송을 중단합니다.")
        return

    with open("result.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    perf_results = []
    csv_file_path = "perf_stats.csv"
    
    print(f"🔍 CSV 파일 확인: {csv_file_path}")
    if os.path.exists(csv_file_path):
        file_size = os.path.getsize(csv_file_path)
        print(f"✅ CSV 파일 존재: {file_size} bytes")
        
        with open(csv_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"📄 CSV 파일 내용 (처음 500자):\n{content[:500]}")
            
            f.seek(0)  # 파일 포인터 리셋
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"📊 CSV 행 수: {len(rows)}")
            
            # 랜덤 limit API 데이터를 수집하여 평균 계산
            main_random_data = []
            
            for row in rows:
                print(f"   - 행 데이터: {dict(row)}")
                if row.get('Name') and row['Name'] != 'Aggregated':
                    try:
                        total_req = int(row.get('Request Count', 0) or 0)
                        fail_count = int(row.get('Failure Count', 0) or 0)
                        
                        endpoint_name = row['Name']
                        
                        # 랜덤 limit API인지 확인
                        if '/text/main/' in endpoint_name or endpoint_name == '/text/main/[limit]':
                            # 랜덤 limit API 데이터 수집 (나중에 평균 계산)
                            main_random_data.append({
                                "total_req": total_req,
                                "fail_count": fail_count,
                                "avg_latency": float(row.get('Average Response Time', 0) or 0),
                                "p95_latency": float(row.get('95%', 0) or 0) if row.get('95%', 'N/A') != 'N/A' else 0,
                                "p99_latency": float(row.get('99%', 0) or 0) if row.get('99%', 'N/A') != 'N/A' else 0,
                                "max_latency": float(row.get('Max Response Time', 0) or 0),
                                "rps": float(row.get('Requests/s', 0) or 0),
                            })
                        else:
                            # 일반 API는 그대로 추가
                            perf_results.append({
                                "method": row.get('Type', 'GET'),
                                "endpoint": endpoint_name,
                                "avg_latency": float(row.get('Average Response Time', 0) or 0),
                                "p95_latency": float(row.get('95%', 0) or 0) if row.get('95%', 'N/A') != 'N/A' else 0,
                                "p99_latency": float(row.get('99%', 0) or 0) if row.get('99%', 'N/A') != 'N/A' else 0,
                                "max_latency": float(row.get('Max Response Time', 0) or 0),
                                "rps": float(row.get('Requests/s', 0) or 0),
                                "total_requests": total_req,
                                "fail_count": fail_count,
                                "error_rate": round((fail_count / total_req * 100), 2) if total_req > 0 else 0
                            })
                    except (ValueError, KeyError) as e:
                        print(f"⚠️ CSV 파싱 중 건너뜀: {e}, 행: {row}")
                        continue
            
            # 랜덤 limit API 평균 계산
            if main_random_data:
                total_req_sum = sum(d['total_req'] for d in main_random_data)
                fail_count_sum = sum(d['fail_count'] for d in main_random_data)
                
                # 가중 평균 계산 (요청 수를 가중치로 사용)
                if total_req_sum > 0:
                    weighted_avg_latency = sum(d['avg_latency'] * d['total_req'] for d in main_random_data) / total_req_sum
                    weighted_avg_p95 = sum(d['p95_latency'] * d['total_req'] for d in main_random_data if d['p95_latency'] > 0) / sum(d['total_req'] for d in main_random_data if d['p95_latency'] > 0) if any(d['p95_latency'] > 0 for d in main_random_data) else 0
                    weighted_avg_p99 = sum(d['p99_latency'] * d['total_req'] for d in main_random_data if d['p99_latency'] > 0) / sum(d['total_req'] for d in main_random_data if d['p99_latency'] > 0) if any(d['p99_latency'] > 0 for d in main_random_data) else 0
                    max_latency = max(d['max_latency'] for d in main_random_data)
                    total_rps = sum(d['rps'] for d in main_random_data)
                else:
                    weighted_avg_latency = 0
                    weighted_avg_p95 = 0
                    weighted_avg_p99 = 0
                    max_latency = 0
                    total_rps = 0
                
                perf_results.append({
                    "method": "GET",
                    "endpoint": "/text/main/[limit]",
                    "avg_latency": round(weighted_avg_latency, 2),
                    "p95_latency": round(weighted_avg_p95, 2),
                    "p99_latency": round(weighted_avg_p99, 2),
                    "max_latency": round(max_latency, 2),
                    "rps": round(total_rps, 2),
                    "total_requests": total_req_sum,
                    "fail_count": fail_count_sum,
                    "error_rate": round((fail_count_sum / total_req_sum * 100), 2) if total_req_sum > 0 else 0
                })
                print(f"📊 랜덤 limit API 통합 완료: {len(main_random_data)}개 데이터를 평균화")
    else:
        print(f"❌ CSV 파일이 존재하지 않습니다: {csv_file_path}")
        # 다른 가능한 파일명 확인
        import glob
        all_csv = glob.glob("perf*.csv")
        print(f"🔍 다른 CSV 파일들: {all_csv}")
    
    print(f"📈 수집된 성능 데이터: {len(perf_results)}개")

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