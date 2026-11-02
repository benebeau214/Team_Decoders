"""특수관계자 거래 추출의 정상·경계·예외 테스트."""

import json


from extract_related_party_deals import extract_related_party_deals


def test_normal_valid_deal():
    """정상: 유효한 거래 항목의 모든 필드가 보존된다."""
    note_text = "당사는 종속회사인 가상유통에 상품 100만원을 매출하였다."
    expected_item = {
        "related_party": "가상유통",
        "relationship": "종속회사",
        "transaction_type": "매출",
        "amount": "100만원",
        "quote": note_text,
    }

    def mock_llm_call(prompt: str) -> str:
        return json.dumps({"items": [expected_item]}, ensure_ascii=False)

    result = extract_related_party_deals(note_text, mock_llm_call)

    assert result == {"status": "ok", "items": [expected_item]}
    assert result["items"][0]["quote"] in note_text


def test_boundary_no_deals():
    """경계: 거래가 0건인 정상 응답을 오류와 구분한다."""
    note_text = "당기 중 특수관계자와의 거래는 없습니다."

    def mock_llm_call(prompt: str) -> str:
        return '{"items": []}'

    result = extract_related_party_deals(note_text, mock_llm_call)

    assert result == {"status": "ok", "items": []}


def test_exception_broken_json():
    """예외: 잘린 JSON 응답을 parse_error로 처리한다."""
    note_text = "당사는 종속회사인 가상유통에 상품 100만원을 매출하였다."

    def mock_llm_call(prompt: str) -> str:
        return '{"items": [{"related_party": "가상'

    result = extract_related_party_deals(note_text, mock_llm_call)

    assert result == {"status": "parse_error", "items": []}
