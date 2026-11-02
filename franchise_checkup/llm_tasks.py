"""LLM-backed tasks for explaining existing franchise analysis results."""

import json
from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd


def _json_safe(value: Any) -> Any:
    """Convert analysis values to JSON-compatible values without losing missingness."""
    if isinstance(value, pd.DataFrame):
        return {
            "type": "DataFrame",
            "empty": value.empty,
            "columns": [str(column) for column in value.columns],
            "rows": _json_safe(value.to_dict(orient="records")),
        }

    try:
        missing = pd.isna(value)
        if not hasattr(missing, "__len__") and bool(missing):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass

    return value


def _analysis_prompt(
    signals: object,
    payback_df: object,
    flags: object,
    user_type: str,
) -> str:
    """Build a prompt containing only the supplied analysis results."""
    analysis = {
        "signals": _json_safe(signals),
        "payback": _json_safe(payback_df),
        "document_review": _json_safe(flags),
    }
    audience = (
        "가맹 계약 전 본사 위험 신호, 회수 기간 시나리오, 계약서와 공시의 확인 사항"
        if user_type == "예비"
        else "최근 재무 변화, 운영상 확인 사항, 계약 갱신 및 추가 출점 검토 사항"
    )
    serialized = json.dumps(
        analysis,
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )
    return (
        "당신은 프랜차이즈 재무·계약 분석 결과를 비전문가가 이해하기 쉽게 설명합니다.\n"
        f"사용자 유형: {user_type}\n"
        f"설명 초점: {audience}\n"
        "아래 입력 자료에 이미 포함된 분석 결과만 설명하세요. 계산, 위험 판정, "
        "문서 교차 검증을 새로 하지 마세요. 입력에 없는 수치·사실·법적 판단을 "
        "추가하지 말고, 값이 없거나 null인 항목은 '확인 필요'로 설명하세요. "
        "빈 결과 목록은 입력 누락이나 안전하다는 증거로 단정하지 말고, "
        "표시된 결과가 없다는 점과 확인이 필요한 경우를 구분하세요. "
        "회수 기간 DataFrame 자체가 비어 있는 경우와 행 안의 null 회수 기간을 "
        "구분하세요. null 회수 기간은 계산할 수 없는 결과일 수 있으므로 "
        "0개월 또는 확정적인 회수 불가로 바꾸지 마세요. "
        "법률·투자 자문이나 가맹 여부 권유를 하지 마세요.\n"
        "반환은 JSON 객체 하나만 하세요. 형식은 "
        '{"summary": "한국어 요약", "checklist": ["확인할 사항"]}이며, '
        "summary는 문자열, checklist는 문자열 목록이어야 합니다.\n"
        "입력 분석 결과:\n"
        f"{serialized}"
    )


def _fallback_report(user_type: str, reason: str) -> dict[str, str | list[str]]:
    """Return a transparent report-generation fallback without judging analysis."""
    if user_type == "예비":
        focus = (
            "계약 전 본사 재무 신호, 회수 기간 시나리오, 문서 검토 결과를 "
            "화면의 분석 자료에서 각각 직접 확인하세요."
        )
    else:
        focus = (
            "최근 재무 변화와 운영 관련 신호를 확인하고, 계약 갱신 또는 추가 출점에 "
            "영향을 줄 수 있는 회수 기간·문서 검토 결과를 화면에서 직접 확인하세요."
        )
    return {
        "summary": (
            f"자동 보고서 생성에 실패했습니다. 실패 원인: {reason}. "
            "이는 LLM 보고서 작성 단계의 실패이며, 기존 파이썬 분석 결과의 실패를 "
            "의미하지 않습니다. 화면에 표시된 기존 분석 결과를 직접 확인해 주세요."
        ),
        "checklist": [focus],
    }


def write_report(
    signals: object,
    payback_df: object,
    flags: object,
    user_type: str,
    llm_call: Callable[[str], str],
) -> dict[str, str | list[str]]:
    """Write a Korean non-expert report from existing analysis results.

    The input result schemas are not fixed yet, so the function preserves their
    supplied structure in the prompt rather than interpreting or recalculating it.
    """
    if not isinstance(user_type, str):
        raise ValueError("user_type must be a string")
    user_type = user_type.strip()
    if user_type not in ("예비", "기존"):
        raise ValueError("user_type must be '예비' or '기존'")

    try:
        prompt = _analysis_prompt(signals, payback_df, flags, user_type)
    except Exception as error:
        return _fallback_report(
            user_type,
            f"보고서 입력 자료 구성 실패 ({type(error).__name__}: {error})",
        )

    try:
        response = llm_call(prompt)
    except Exception as error:
        return _fallback_report(
            user_type,
            f"LLM 호출 실패 ({type(error).__name__}: {error})",
        )

    if not isinstance(response, str):
        return _fallback_report(
            user_type,
            f"LLM 응답 자료형 오류 (문자열이 아닌 {type(response).__name__})",
        )

    content = response.strip()
    if content.startswith("```") and content.endswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1]).strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError as error:
        return _fallback_report(
            user_type,
            f"LLM 응답 JSON 파싱 실패 ({error})",
        )

    if not isinstance(result, dict):
        return _fallback_report(
            user_type,
            f"LLM 응답 형식 오류 (JSON 객체가 아닌 {type(result).__name__})",
        )

    missing_fields = [
        field for field in ("summary", "checklist") if field not in result
    ]
    if missing_fields:
        return _fallback_report(
            user_type,
            f"LLM 응답 필수 필드 누락 ({', '.join(missing_fields)})",
        )
    if not isinstance(result["summary"], str) or not result["summary"].strip():
        return _fallback_report(
            user_type,
            "LLM 응답 자료형 오류 (summary는 비어 있지 않은 문자열이어야 함)",
        )
    if not isinstance(result["checklist"], list) or not all(
        isinstance(item, str) and item.strip() for item in result["checklist"]
    ):
        return _fallback_report(
            user_type,
            "LLM 응답 자료형 오류 (checklist는 비어 있지 않은 문자열 목록이어야 함)",
        )

    return {
        "summary": result["summary"].strip(),
        "checklist": [item.strip() for item in result["checklist"]],
    }
