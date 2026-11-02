import json

import pandas as pd
import pytest

from franchise_checkup.llm_tasks import write_report


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
        "summary": "검토 결과입니다.",
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
    assert "계약 갱신 및 추가 출점" in prompts["기존"]
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
    ("llm_call", "reason"),
    [
        (lambda prompt: (_ for _ in ()).throw(RuntimeError("연결 오류")), "LLM 호출 실패"),
        (lambda prompt: '{"summary":', "JSON 파싱 실패"),
        (lambda prompt: {"summary": "응답"}, "응답 자료형 오류"),
        (lambda prompt: '{"summary": "요약"}', "필수 필드 누락"),
        (lambda prompt: '{"summary": "요약", "checklist": "확인"}', "자료형 오류"),
    ],
)
def test_llm_failures_return_transparent_fallback(llm_call, reason):
    result = write_report([], pd.DataFrame(), [], "기존", llm_call)

    assert reason in result["summary"]
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

    assert result == {"summary": "요약", "checklist": []}
