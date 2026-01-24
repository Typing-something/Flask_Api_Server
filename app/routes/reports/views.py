import os
from flask import Blueprint, jsonify, request, current_app
from app.models import TestReport, TestCaseResult, ApiPerformance
from app.utils import api_response
from app.database import db

report_blueprint = Blueprint('report', __name__)

@report_blueprint.route('/report', methods=['POST'])
def receive_test_report():
    try:
        data = request.get_json()
        
        # 1. 메인 리포트 저장
        report = TestReport(
            git_commit=data.get('git_commit'),
            total_tests=data.get('total', 0),
            passed_tests=data.get('passed', 0),
            failed_tests=data.get('failed', 0),
            is_passed=(data.get('failed', 0) == 0),
            user_count=data.get('user_count', 0)
        )
        db.session.add(report)
        db.session.flush() # report.id를 아래에서 쓰기 위해 미리 flush ㅋ

        # 2. Pytest 상세 결과 저장
        for case in data.get('pytest_results', []):
            db.session.add(TestCaseResult(
                report_id=report.id,
                test_name=case.get('test_name'),
                status=case.get('status'),
                message=case.get('message')
            ))

        # 3. Locust 성능 상세 결과 저장 (보강된 필드 반영!)
        for perf in data.get('perf_results', []):
            # p95_latency가 500ms(0.5초)를 넘지 않으면 만족하는 것으로 간주 (기준은 조절 가능 ㅋ)
            p95 = perf.get('p95_latency', 0)
            is_satisfied = p95 < 500 if p95 > 0 else True

            db.session.add(ApiPerformance(
                report_id=report.id,
                method=perf.get('method'),
                endpoint=perf.get('endpoint'),
                avg_latency=perf.get('avg_latency'),
                p95_latency=p95,                # 추가! 🌟
                p99_latency=perf.get('p99_latency'), # 추가! 🌟
                max_latency=perf.get('max_latency'), # 추가! 🌟
                rps=perf.get('rps'),
                total_requests=perf.get('total_requests', 0), # 추가!
                fail_count=perf.get('fail_count', 0),
                error_rate=perf.get('error_rate', 0.0),       # 추가! 🌟
                is_satisfied=is_satisfied                     # 추가!
            ))
        
        db.session.commit()
        return api_response(
            success=True, 
            data={"report_id": report.id}, 
            message="상세 성능 지표를 포함한 통합 리포트 저장 성공 ㅋ", 
            status_code=201
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ [DB 저장 에러 상세]: {str(e)}") 
        return api_response(success=False, message=str(e), status_code=500)

# 1. 전체 리포트 목록 조회 (메인 리포트 정보 요약)
@report_blueprint.route('/reports', methods=['GET'])
def get_reports():
    try:
        # 최신순으로 리포트 목록 조회
        reports = TestReport.query.order_by(TestReport.test_time.desc()).all()
        
        report_list = []
        for r in reports:
            report_list.append({
                "report_id": r.id,
                "test_time": r.test_time.strftime('%Y-%m-%d %H:%M:%S'),
                "git_commit": r.git_commit,
                "summary": {
                    "total": r.total_tests,
                    "passed": r.passed_tests,
                    "failed": r.failed_tests,
                    "is_passed": r.is_passed
                },
                "load_test_info": {
                    "user_count": r.user_count
                }
            })

        return api_response(
            success=True, 
            data=report_list, 
            message=f"총 {len(report_list)}개의 리포트 목록을 가져왔습니다."
        )
    except Exception as e:
        current_app.logger.error(f"리포트 목록 조회 에러: {str(e)}")
        return api_response(success=False, message="목록 조회 실패", status_code=500)


# 2. 특정 리포트 상세 조회 (Pytest 결과 + 상세 성능 지표)
@report_blueprint.route('/reports/<int:report_id>', methods=['GET'])
def get_report_detail(report_id):
    try:
        report = TestReport.query.get(report_id)
        if not report:
            return api_response(success=False, message="리포트를 찾을 수 없습니다.", status_code=404)

        # Pytest 결과 가공
        pytest_details = [{
            "test_name": c.test_name,
            "status": c.status,
            "message": c.message
        } for c in report.case_results]

        # Locust 성능 지표 가공 (중요한 P95, P99 포함!)
        performance_details = [{
            "method": p.method,
            "endpoint": p.endpoint,
            "latency": {
                "avg": p.avg_latency,
                "p95": p.p95_latency,
                "p99": p.p99_latency,
                "max": p.max_latency
            },
            "stats": {
                "rps": p.rps,
                "total_requests": p.total_requests,
                "fail_count": p.fail_count,
                "error_rate": p.error_rate
            },
            "is_satisfied": p.is_satisfied
        } for p in report.api_performances]

        data = {
            "report_info": {
                "id": report.id,
                "date": report.test_time.strftime('%Y-%m-%d %H:%M:%S'),
                "commit": report.git_commit
            },
            "pytest_results": pytest_details,
            "performance_results": performance_details
        }

        return api_response(
            success=True, 
            data=data, 
            message=f"리포트 #{report_id} 상세 정보를 성공적으로 가져왔습니다."
        )

    except Exception as e:
        current_app.logger.error(f"리포트 상세 조회 에러: {str(e)}")
        return api_response(success=False, message="상세 조회 실패", status_code=500)