import random
import string

def random_string(min_len, max_len=None, use_lower=True, use_upper=True, use_special=None):
    """
    범위 기반 길이를 지원하는 유연한 랜덤 문자열 생성 함수
    :param min_len: 최소 길이 (max_len이 없으면 고정 길이로 동작)
    :param max_len: 최대 길이 (이 값이 있으면 min_len ~ max_len 사이에서 랜덤 결정)
    :param use_lower: 소문자 포함 여부
    :param use_upper: 대문자 포함 여부
    :param use_special: False(안씀), True(전체), 또는 "!?@#" (특정 문자열)
    """
    
    # 1. 길이 결정 (두 숫자가 들어오면 그 사이에서 랜덤하게 뽑음)
    if max_len is not None:
        length = random.randint(min_len, max_len)
    else:
        length = min_len
    
    # 2. 기본 문자 세트 (숫자는 기본 포함)
    char_set = string.digits
    
    if use_lower:
        char_set += string.ascii_lowercase
    if use_upper:
        char_set += string.ascii_uppercase
        
    if use_special is True:
        char_set += string.punctuation
    elif isinstance(use_special, str):
        char_set += use_special

    # 3. 문자열 생성
    return ''.join(random.choice(char_set) for _ in range(length))

def pick_random(items):
    """
    배열(List)을 인자로 받아 그 중 하나의 요소를 랜덤하게 반환하는 함수
    :param items: 리스트 또는 튜플 데이터
    """
    # 1. 방어 코드: 배열이 비어있는 경우 None 반환
    if not items:
        return None
        
    # 2. random.choice를 사용하여 하나 추출
    return random.choice(items)

def random_number(min_val, max_val):
    """
    지정한 범위(min_val ~ max_val) 내에서 정수 하나를 무작위로 반환합니다.
    (두 인자값을 모두 포함하는 범위입니다.)
    """
    # random.randint는 양 끝값을 모두 포함하여(inclusive) 랜덤 숫자를 생성합니다.
    return random.randint(min_val, max_val)
