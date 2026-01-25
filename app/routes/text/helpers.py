"""
타이핑 결과 저장 관련 헬퍼 함수들
"""
from app.models import User


def validate_result_data(data):
    """
    결과 저장 API의 요청 데이터 검증
    
    Args:
        data: 요청 데이터 (dict)
        
    Returns:
        tuple: (is_valid, error_message, parsed_data)
            - is_valid: 검증 통과 여부 (bool)
            - error_message: 에러 메시지 (str or None)
            - parsed_data: 파싱된 데이터 (dict or None)
    """
    if not data:
        return False, "전송된 데이터가 없습니다.", None
    
    required_fields = ['text_id', 'user_id', 'cpm', 'accuracy', 'combo']
    for field in required_fields:
        if data.get(field) is None:
            return False, f"{field} 항목은 필수입니다.", None
    
    # 수치 변수화 및 검증
    try:
        parsed_data = {
            'text_id': data.get('text_id'),
            'user_id': data.get('user_id'),
            'cpm': int(data.get('cpm')),
            'wpm': int(data.get('wpm', 0)),
            'accuracy': float(data.get('accuracy')),
            'combo': int(data.get('combo'))
        }
        return True, None, parsed_data
    except (ValueError, TypeError) as e:
        return False, f"수치 데이터 형식이 올바르지 않습니다: {str(e)}", None


def update_user_statistics(user, cpm, wpm, accuracy, combo):
    """
    사용자 통계 업데이트 (평균값 계산 및 최고 기록 갱신)
    
    Args:
        user: User 모델 인스턴스
        cpm: 현재 CPM (int)
        wpm: 현재 WPM (int)
        accuracy: 현재 정확도 (float)
        combo: 현재 콤보 (int)
        
    Returns:
        dict: 업데이트 결과 정보
            - is_new_combo_record: 콤보 신기록 여부 (bool)
            - updated_fields: 업데이트된 필드 목록 (list)
    """
    # 플레이 횟수 증가
    old_count = user.play_count
    user.play_count += 1
    new_count = user.play_count
    
    # 평균값 계산 헬퍼 함수
    def calculate_average(old_avg, old_count, new_value, new_count):
        """평균값 계산"""
        return round(((old_avg * old_count) + new_value) / new_count, 2)
    
    # 평균값 갱신
    user.avg_accuracy = calculate_average(user.avg_accuracy, old_count, accuracy, new_count)
    user.avg_cpm = calculate_average(user.avg_cpm, old_count, cpm, new_count)
    user.avg_wpm = calculate_average(user.avg_wpm, old_count, wpm, new_count)
    
    # 최고 기록 갱신
    is_new_combo_record = False
    updated_fields = []
    
    if combo > user.max_combo:
        user.max_combo = combo
        is_new_combo_record = True
        updated_fields.append('max_combo')
    
    if cpm > user.best_cpm:
        user.best_cpm = cpm
        updated_fields.append('best_cpm')
    
    if wpm > user.best_wpm:
        user.best_wpm = wpm
        updated_fields.append('best_wpm')
    
    # 랭킹 점수 갱신
    user.update_ranking_score()
    
    return {
        'is_new_combo_record': is_new_combo_record,
        'updated_fields': updated_fields
    }

