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
        
        # 1. 메인 리포트 (필드명: passed_tests, failed_tests 확인! ㅋ)
        report = TestReport(
            git_commit=data.get('git_commit'),
            total_tests=data.get('total', 0),
            passed_tests=data.get('passed', 0), # 스크립트의 'passed' 키와 매칭
            failed_tests=data.get('failed', 0), # 스크립트의 'failed' 키와 매칭
            is_passed=(data.get('failed', 0) == 0),
            user_count=data.get('user_count', 0)
        )
        db.session.add(report)
        db.session.flush() 

        # 2. Pytest 결과 저장
        for case in data.get('pytest_results', []):
            db.session.add(TestCaseResult(
                report_id=report.id,
                test_name=case.get('test_name'),
                status=case.get('status'),
                message=case.get('message') # failed일 때 에러 메시지 저장 ㅋ
            ))

        # 3. Locust 성능 결과 저장
        for perf in data.get('perf_results', []):
            db.session.add(ApiPerformance(
                report_id=report.id,
                method=perf.get('method'),
                endpoint=perf.get('endpoint'),
                avg_latency=perf.get('avg_latency'),
                rps=perf.get('rps'),
                fail_count=perf.get('fail_count', 0)
            ))
        
        db.session.commit()
        return api_response(success=True, data={"report_id": report.id}, message="기능/성능 통합 리포트 저장 성공", status_code=201)

    except Exception as e:
        db.session.rollback()
        # 💡 이 프린트가 서버 터미널에 에러 정체를 확실히 보여줄 거예요!
        print(f"❌ [DB 저장 에러 상세]: {str(e)}") 
        return api_response(success=False, message=str(e), status_code=500)