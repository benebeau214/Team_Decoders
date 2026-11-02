"""LLM 호출 계층. 현재는 데모용 mock을 사용한다."""

import json


class LLMCallError(Exception):
    """LLM 호출 실패. 실제 API 연결 시 SDK 호출 예외를 이 예외로 변환한다."""


def llm_call(prompt: str) -> str:
    """[MOCK] 요청 종류별 데모용 고정 JSON을 반환한다.

    실제 AI 분석은 하지 않는다. 정해진 데모 원문에만 사용하는 mock이다.
    13주차에는 문자열 입력·문자열 출력 형식을 유지하여 실제 API로 교체한다.
    실제 API 연결 시 타임아웃과 제한된 재시도를 설정하고,
    SDK의 호출 예외는 raise LLMCallError(...) from exc로 변환한다.
    """
    if "<note_text>" in prompt:
        return json.dumps(
            {"items": [{
                "related_party": "가상유통",
                "relationship": "종속회사",
                "transaction_type": "매출",
                "amount": "100만원",
                "quote": "당사는 종속회사인 가상유통에 상품 100만원을 매출하였다.",
            }]},
            ensure_ascii=False,
        )
    if "<clause_text>" not in prompt:
        raise ValueError("지원하지 않는 mock 요청입니다.")

    mock_response = {
        "items": [
            {
                "type": "필수품목·구매 강제",
                "quote": "가맹점사업자는 가맹본부가 지정한 업체로부터 원재료 전량을 구매하여야 한다.",
                "reason": "원재료 구매처를 자유롭게 선택하기 어렵기 때문이다.",
            }
        ]
    }

    return json.dumps(mock_response, ensure_ascii=False)
