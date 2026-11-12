"""LLM 호출 계층. 현재는 데모용 mock을 사용한다."""

import json


class LLMCallError(Exception):
    """LLM 호출 실패. 실제 API 연결 시 SDK 호출 예외를 이 예외로 변환한다."""


def llm_call(prompt: str) -> str:
    """프롬프트를 LLM에 보내고 응답 문자열(JSON)을 받는다.

    현재는 데모용 mock이며 [MOCK] 응답을 반환한다. 13주차에 실제 API로 교체해도
    입력(str)·출력(str) 형식은 유지한다.

    Args:
        prompt: LLM에 전달할 전체 프롬프트.

    Returns:
        JSON 형식의 응답 문자열. 구조는 호출하는 작업(보고서 작성,
        특수관계자 거래 추출, 불리한 조항 추출)마다 다르다.

    Raises:
        LLMCallError: 호출 실패, 또는 지원하지 않는 요청.
    """

    # 1. 보고서 작성 요청
    if prompt.lstrip().startswith("<report_text>"):

        if "사용자 유형: 예비" in prompt:
            checklist = [
                "계약 전 최신 재무자료와 정보공개서의 기재 내용을 확인하세요.",
                "계약 조건과 필수품목 지정·구매 조건을 원문으로 확인하세요.",
                "투자금과 예상 투자 회수 기간의 가정을 점검하세요.",
            ]

        elif "사용자 유형: 기존" in prompt:
            checklist = [
                "최근 재무 신호와 판정 근거의 변화를 확인하세요.",
                "계약 갱신·추가 출점 전에 변경된 조건을 확인하세요.",
                "실제 매출·비용과 투자 회수 시나리오의 차이를 점검하세요.",
            ]

        else:
            raise ValueError("지원하지 않는 사용자 유형입니다.")

        mock_response = {
            "summary": (
                "현재 응답은 보고서 작성 기능의 동작을 확인하기 위한 "
                "데모용 고정 응답입니다. "
                "입력된 재무·문서 자료를 실제로 분석한 결과가 아니므로, "
                "화면에 표시된 분석 결과를 직접 확인해야 합니다."
            ),
            "checklist": checklist,
        }

        return json.dumps(mock_response, ensure_ascii=False)

    # 2. 특수관계자 거래 추출 요청
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

    # 3. 불리한 계약 조항 추출 요청
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
