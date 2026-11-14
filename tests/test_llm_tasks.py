import json

import pandas as pd
import pytest

from llm_client import LLMCallError, llm_call as shared_mock_llm_call

from franchise_checkup.llm_tasks import (
    DISCLAIMER,
    _analysis_prompt,
    _fallback_report,
    _json_safe,
    write_report,
    extract_related_party_deals,
    extract_unfavorable_clauses,
)


def _valid_response(summary="검토 결과입니다.", checklist=None):
    return json.dumps(
        {
            "summary": summary,
            "checklist": checklist if checklist is not None else ["계약서를 확인하세요."],
        },
        ensure_ascii=False,
    )


def test_write_report_returns_required_shape():
    result = write_report(
        [{"item": "부채비율", "level": "주의", "value": 250}],
        pd.DataFrame(
            [{"scenario": "평균", "payback_months": 75.0, "uncertain": True}]
        ),
        [{"issue": "기재 차이", "evidence": "자료 간 내용이 다름"}],
        "예비",
        lambda prompt: _valid_response(),
    )

    assert result == {
        "summary": f"검토 결과입니다. {DISCLAIMER}",
        "checklist": ["계약서를 확인하세요."],
    }
    assert isinstance(result["summary"], str)
    assert isinstance(result["checklist"], list)
    assert all(isinstance(item, str) for item in result["checklist"])


def test_prompt_focus_changes_by_user_type():
    prompts = {}
    for user_type in ("예비", "기존"):
        def capture_prompt(prompt, selected_type=user_type):
            prompts[selected_type] = prompt
            return _valid_response()

        write_report(
            [],
            pd.DataFrame(),
            [],
            user_type,
            capture_prompt,
        )

    assert "가맹 계약 전" in prompts["예비"]
    assert "현재 운영과 계약 갱신·추가 출점 전에 확인할 사항" in prompts["기존"]
    assert prompts["예비"] != prompts["기존"]


@pytest.mark.parametrize("user_type", ["invalid", "", None])
def test_unsupported_user_type_raises_value_error(user_type):
    with pytest.raises(ValueError):
        write_report([], pd.DataFrame(), [], user_type, lambda prompt: "{}")


def test_prompt_contains_supplied_financial_payback_and_document_results():
    captured = {}
    signals = [{"item": "영업이익률", "level": "주의", "value": -2.0}]
    payback = pd.DataFrame(
        [{"scenario": "보수", "payback_months": 187.5}]
    )
    flags = [{"issue": "문서 불일치", "evidence": "원문 근거"}]

    def llm_call(prompt):
        captured["prompt"] = prompt
        return _valid_response()

    write_report(signals, payback, flags, "예비", llm_call)

    assert '"level": "주의"' in captured["prompt"]
    assert "187.5" in captured["prompt"]
    assert "문서 불일치" in captured["prompt"]
    assert "원문 근거" in captured["prompt"]


def test_missing_values_are_distinguished_from_empty_results():
    captured = {}

    def llm_call(prompt):
        captured["prompt"] = prompt
        return _valid_response()

    write_report(None, [], None, "예비", llm_call)

    assert '"signals": null' in captured["prompt"]
    assert '"payback": []' in captured["prompt"]
    assert '"document_review": null' in captured["prompt"]


def test_empty_payback_dataframe_is_distinguished_from_nan_scenario():
    captured = {}

    def llm_call(prompt):
        captured["prompt"] = prompt
        return _valid_response()

    write_report(
        [],
        pd.DataFrame(
            [{"scenario": "평균", "payback_months": float("nan")}]
        ),
        [],
        "예비",
        llm_call,
    )

    assert '"empty": false' in captured["prompt"]
    assert '"payback_months": null' in captured["prompt"]
    assert "0개월" in captured["prompt"]


@pytest.mark.parametrize(
    ("llm_call", "safe_reason"),
    [
        (lambda prompt: (_ for _ in ()).throw(RuntimeError("연결 오류")), "LLM 호출에 실패"),
        (lambda prompt: '{"summary":', "LLM 응답을 처리하는 과정에서 오류"),
        (lambda prompt: {"summary": "응답"}, "올바른 형식의 응답을 받지 못했습니다"),
        (lambda prompt: '{"summary": "요약"}', "필요한 보고서 항목이 포함되지 않았습니다"),
        (lambda prompt: '{"summary": "요약", "checklist": "확인"}', "확인 항목이 올바르지 않습니다"),
    ],
)
def test_llm_failures_return_transparent_fallback(llm_call, safe_reason):
    result = write_report([], pd.DataFrame(), [], "기존", llm_call)

    assert safe_reason in result["summary"]
    assert "연결 오류" not in result["summary"]
    assert DISCLAIMER in result["summary"]
    assert "기존 파이썬 분석 결과의 실패를 의미하지 않습니다" in result["summary"]
    assert "화면에 표시된 기존 분석 결과를 직접 확인" in result["summary"]
    assert isinstance(result["checklist"], list)


def test_markdown_fenced_json_is_accepted():
    result = write_report(
        [],
        pd.DataFrame(),
        [],
        "예비",
        lambda prompt: '```json\n{"summary": "요약", "checklist": []}\n```',
    )

    assert result == {"summary": f"요약 {DISCLAIMER}", "checklist": []}


def test_json_safe_converts_nested_values_and_dataframe():
    result = _json_safe(
        {
            "missing": pd.NA,
            "values": (1, 2),
            "frame": pd.DataFrame([{"amount": 10}]),
        }
    )

    assert result == {
        "missing": None,
        "values": [1, 2],
        "frame": {
            "type": "DataFrame",
            "empty": False,
            "columns": ["amount"],
            "rows": [{"amount": 10}],
        },
    }


def test_json_safe_handles_empty_dataframe_boundary():
    assert _json_safe(pd.DataFrame()) == {
        "type": "DataFrame",
        "empty": True,
        "columns": [],
        "rows": [],
    }


def test_json_safe_preserves_value_when_scalar_conversion_raises():
    class InvalidScalar:
        def item(self):
            raise ValueError("cannot convert")

    value = InvalidScalar()

    assert _json_safe(value) is value


def test_analysis_prompt_includes_serialized_analysis_and_audience():
    prompt = _analysis_prompt(
        [{"item": "영업이익률", "value": 2}],
        pd.DataFrame([{"scenario": "평균"}]),
        [{"issue": "문서 확인"}],
        "예비",
    )

    assert prompt.startswith("<report_text>")
    assert "사용자 유형: 예비" in prompt
    assert '"item": "영업이익률"' in prompt
    assert '"scenario": "평균"' in prompt
    assert '"issue": "문서 확인"' in prompt


def test_analysis_prompt_preserves_empty_and_missing_inputs():
    prompt = _analysis_prompt(None, pd.DataFrame(), [], "기존")

    assert '"signals": null' in prompt
    assert '"empty": true' in prompt
    assert '"document_review": []' in prompt


def test_analysis_prompt_rejects_unsupported_user_type():
    with pytest.raises(KeyError):
        _analysis_prompt([], [], [], "unsupported")


def test_fallback_report_returns_user_type_specific_checklist():
    report = _fallback_report("예비", "LLM 호출 실패")

    assert "LLM 호출 실패" in report["summary"]
    assert "본사 신호표의 위험 수준과 판정 근거를 확인하세요." in report["checklist"]
    assert DISCLAIMER in report["summary"]


def test_fallback_report_handles_empty_reason_boundary():
    report = _fallback_report("기존", "")

    assert "실패 원인: ." in report["summary"]
    assert len(report["checklist"]) == 5


def test_fallback_report_propagates_reason_formatting_exception():
    class InvalidReason:
        def __str__(self):
            raise RuntimeError("cannot format reason")

    with pytest.raises(RuntimeError, match="cannot format reason"):
        _fallback_report("예비", InvalidReason())

@pytest.mark.parametrize(
    ("user_type", "expected_checklist"),
    [
        (
            "예비",
            "계약 전 최신 재무자료와 정보공개서의 기재 내용을 확인하세요.",
        ),
        (
            "기존",
            "최근 재무 신호와 판정 근거의 변화를 확인하세요.",
        ),
    ],
)
def test_write_report_with_shared_mock(user_type, expected_checklist):
    result = write_report(
        signals=[
            {
                "item": "부채비율",
                "level": "주의",
                "value": 250,
                "reason": "부채비율이 높은 수준입니다.",
            }
        ],
        payback_df=pd.DataFrame(
            [
                {
                    "scenario": "평균",
                    "monthly_net_profit": 100,
                    "payback_months": 50,
                    "uncertain": False,
                }
            ]
        ),
        flags=[
            {
                "issue": "문서 불일치",
                "evidence": "자료 간 기재 내용이 다름",
            }
        ],
        user_type=user_type,
        llm_call=shared_mock_llm_call,
    )

    assert isinstance(result["summary"], str)
    assert "데모용 고정 응답" in result["summary"]
    assert DISCLAIMER in result["summary"]

    assert isinstance(result["checklist"], list)
    assert expected_checklist in result["checklist"]


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


@pytest.mark.parametrize("error_type", [RuntimeError, TimeoutError, LLMCallError])
@pytest.mark.parametrize("extractor, expected", [
    (extract_related_party_deals, {"status": "llm_error", "items": []}),
    (extract_unfavorable_clauses, {"status": "llm_error", "items": [], "dropped": 0}),
])
def test_extractors_return_llm_error_on_call_failure(extractor, expected, error_type):
    def failing_call(prompt):
        raise error_type("테스트 호출 오류")

    assert extractor("분석할 원문", failing_call) == expected
