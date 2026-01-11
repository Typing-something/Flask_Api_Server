from flask import jsonify

def api_response(success=True, data=None, error_code=None, message=None, status_code=200):
    """
    프론트엔드에게 보낼 공통 응답 규격
    """
    return jsonify({
        "success": success,
        "data": data,         # 성공 시 결과값 (리스트, 딕셔너리 등)
        "error": {            # 실패 시 정보 (성공 시엔 None)
            "code": error_code,
            "message": message
        } if not success else None
    }), status_code