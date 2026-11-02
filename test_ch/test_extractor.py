import json

from extract_unfavorable_clauses import extract_unfavorable_clauses


ALLOWED_TYPES = {
    "필수품목·구매 강제",
    "위약금·손해배상",
    "계약 해지·갱신",
    "영업지역",
    "광고·판촉비 분담",
    "기타",
}


def test_t11_purchase():
    """구매 강제: 정상 응답을 처리하는지 확인한다."""
    clause_text = (
        "가맹점사업자는 가맹본부가 지정한 업체로부터 "
        "원재료 전량을 구매하여야 한다."
    )

    def mock_llm_call(prompt: str) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "type": "필수품목·구매 강제",
                        "quote": clause_text,
                        "reason": "원재료 구매처 선택이 제한되기 때문이다.",
                    }
                ]
            },
            ensure_ascii=False,
        )

    result = extract_unfavorable_clauses(clause_text, mock_llm_call)

    assert result["status"] == "ok"
    assert len(result["items"]) >= 1
    assert result["dropped"] == 0

    for item in result["items"]:
        assert item["type"] in ALLOWED_TYPES
        assert item["quote"] in clause_text


def test_t12_penalty():
    """위약금: 정상 응답을 처리하는지 확인한다."""
    clause_text = (
        "계약 기간 중 해지 시 가맹점사업자는 "
        "위약금으로 가맹비의 3배를 지급한다."
    )

    def mock_llm_call(prompt: str) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "type": "위약금·손해배상",
                        "quote": clause_text,
                        "reason": "중도 해지 시 금전적 부담이 발생하기 때문이다.",
                    }
                ]
            },
            ensure_ascii=False,
        )

    result = extract_unfavorable_clauses(clause_text, mock_llm_call)

    assert result["status"] == "ok"
    assert len(result["items"]) >= 1
    assert result["dropped"] == 0

    for item in result["items"]:
        assert item["type"] in ALLOWED_TYPES
        assert item["quote"] in clause_text


def test_t13_no_items():
    """추출 결과가 없어도 정상 응답으로 처리한다."""
    clause_text = "가맹본부는 연 2회 위생 교육을 무상으로 제공한다."

    def mock_llm_call(prompt: str) -> str:
        return '{"items": []}'

    result = extract_unfavorable_clauses(clause_text, mock_llm_call)

    assert result == {
        "status": "ok",
        "items": [],
        "dropped": 0,
    }


def test_t14_empty_input():
    """빈 입력이면 LLM을 호출하지 않는다."""
    def mock_llm_call(prompt: str) -> str:
        raise AssertionError("빈 입력에서는 LLM을 호출하면 안 됩니다.")

    result = extract_unfavorable_clauses("", mock_llm_call)

    assert result == {
        "status": "empty",
        "items": [],
        "dropped": 0,
    }


def test_t15_broken_json():
    """잘린 JSON은 parse_error로 처리한다."""
    clause_text = "중도 해지 시 위약금을 지급한다."

    def mock_llm_call(prompt: str) -> str:
        return '{"items": [{"type": "위약'

    result = extract_unfavorable_clauses(clause_text, mock_llm_call)

    assert result == {
        "status": "parse_error",
        "items": [],
        "dropped": 0,
    }


def test_t16_nonexistent_quote():
    """원문에 없는 인용은 제외하고 횟수를 센다."""
    clause_text = "가맹본부는 연 2회 위생 교육을 무상으로 제공한다."

    def mock_llm_call(prompt: str) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "type": "위약금·손해배상",
                        "quote": "중도 해지 시 위약금 1억 원을 지급한다.",
                        "reason": "중도 해지에 따른 금전적 부담이 크기 때문이다.",
                    }
                ]
            },
            ensure_ascii=False,
        )

    result = extract_unfavorable_clauses(clause_text, mock_llm_call)

    assert result == {
        "status": "ok",
        "items": [],
        "dropped": 1,
    }