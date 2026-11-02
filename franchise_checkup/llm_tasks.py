"""LLM-backed tasks for explaining existing franchise analysis results."""

import json
from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

DISCLAIMER = "법률·투자 자문이 아닙니다."

USER_TYPE_FOCUS = {
    "예비": "가맹 계약 전 확인할 사항",
    "기존": "현재 운영과 계약 갱신·추가 출점 전에 확인할 사항",
}

def _json_safe(value: Any) -> Any:
    """Convert analysis values to JSON-compatible values without losing missingness."""
    if isinstance(value, pd.DataFrame):
        return {
            "type": "DataFrame",
            "empty": value.empty,
            "columns": [str(column) for column in value.columns],
            "rows": _json_safe(value.to_dict(orient="records")),
        }

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    try:
        missing = pd.isna(value)
        if not hasattr(missing, "__len__") and bool(missing):
            return None
    except (TypeError, ValueError):
        pass

    item = getattr(value, "item", None)
    if callable(item):
        try:
            converted = item()
            if converted is not value:
                return _json_safe(converted)
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
    serialized = json.dumps(
        analysis,
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )
    audience = USER_TYPE_FOCUS[user_type]

    return (
        "당신은 프랜차이즈 재무·계약 분석 결과를 비전문가가 이해하기 쉽게 설명합니다.\n"
        f"사용자 유형: {user_type}\n"
        f"설명 초점: {audience}\n"
        
        "[입력 자료 설명]\n"
        "- signals: 부채비율, 자본잠식, 영업이익률, 계약 해지율의 "
        "분석 결과입니다. 각 항목의 item, level, value, reason을 "
        "확인하여 설명하세요.\n"
        "- payback: 보수·평균·낙관 시나리오별 월 순이익, 회수 기간, "
        "불확실성 표시가 포함된 DataFrame입니다.\n"
        "- document_review: 정보공개서와 감사보고서의 불일치 및 "
        "확인 사항입니다. issue와 evidence가 제공되면 이를 바탕으로 "
        "설명하세요.\n\n"

        "[작성 원칙]\n"
        "1. 이미 계산·판정된 결과만 설명하세요. 수치 계산, 위험 판정, "
        "문서 교차 검증을 새로 하지 마세요.\n"
        "2. 입력에 없는 수치나 사실, 법적 판단을 만들어 내지 마세요.\n"
        "3. signals의 level과 reason을 임의로 변경하지 마세요.\n"
        "4. payback의 uncertain 표시를 반영하고, 회수 기간을 "
        "임의로 추정하지 마세요.\n"
        "5. 회수 기간이 null이면 0개월로 표현하지 마세요. "
        "월 순이익 등 함께 제공된 결과를 고려해 설명하고, "
        "의미를 판단할 수 없다면 확인 필요로 안내하세요.\n"
        "6. DataFrame 자체가 비어 있는 경우와 특정 시나리오의 "
        "회수 기간만 null인 경우를 구분하세요.\n"
        "7. document_review의 빈 목록은 제공된 결과에 항목이 "
        "없다는 의미로만 설명하세요. 이를 전체 문서가 안전하다는 "
        "뜻으로 확대 해석하지 마세요.\n"
        "8. 기준연도가 제공되면 표시하고, 제공되지 않으면 "
        "기준연도를 확인할 수 없다고 안내하세요.\n"
        "9. 기존 가맹점주에게 최근 재무 변화를 설명할 때는 "
        "여러 연도의 비교 자료가 제공된 경우에만 추세를 설명하세요.\n"
        "10. 계약 조항의 주의 사항은 설명할 수 있지만, "
        "위법 여부나 법적 효력을 확정하지 마세요.\n"
        "11. 법률·투자 자문이나 가맹 여부에 대한 권유를 하지 마세요.\n\n"

        "[출력 형식]\n"
        "반드시 JSON 객체 하나만 반환하세요. Markdown 코드 블록이나 "
        "별도 설명은 포함하지 마세요.\n"
        '{"summary": "한국어 요약", "checklist": ["확인할 사항"]}\n'
        "summary는 문자열, checklist는 문자열 목록이어야 합니다. "
        f"summary에는 '{DISCLAIMER}' 문구를 포함하세요.\n\n"

        f"[입력 분석 결과]\n{serialized}"
    )


def _fallback_report(
    user_type: str, 
    reason: str
) -> dict[str, str | list[str]]:
    """Return a transparent report-generation fallback without judging analysis."""
    if user_type == "예비":
        checklist = [
            "본사 신호표의 위험 수준과 판정 근거를 확인하세요.",
            "보수·평균·낙관 시나리오별 회수 기간과 가정을 확인하세요.",
            "문서 불일치 및 주의 조항의 내용과 원문 근거를 확인하세요.",
            "분석 자료의 기준연도와 최신 여부를 확인하세요.",
        ]
    else:
        checklist = [
            "재무 자료가 여러 연도에 걸쳐 있다면 변화 추이를 확인하세요.",
            "운영상 주의가 필요한 재무·계약 신호를 확인하세요.",
            "회수 기간과 계산 가정이 현재 운영 상황에 적절한지 확인하세요.",
            "계약 갱신 및 추가 출점에 영향을 주는 문서 검토 결과를 확인하세요.",
            "분석 자료의 기준연도와 최신 여부를 확인하세요.",
        ]
    
    summary = (
            f"자동 보고서 생성에 실패했습니다. 실패 원인: {reason}. "
            "이는 LLM 보고서 작성 단계의 실패이며, "
            " 기존 파이썬 분석 결과의 실패를 의미하지 않습니다. "
            "화면에 표시된 기존 분석 결과를 직접 확인해 주세요."
            f"{DISCLAIMER}"    # 실패한 경우의 대체 보고서에도 면책 문구 추가
        )

    return {
        "summary": summary,
        "checklist": checklist,
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
    if user_type not in USER_TYPE_FOCUS:
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

    if set(result.keys()) != {"summary", "checklist"}:
        return _fallback_report(
            user_type,
            "LLM 응답 필수 필드 누락 혹은 불필요한 필드 존재",
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

    summary = result["summary"].strip()

    if DISCLAIMER not in summary:
        summary = f"{summary} {DISCLAIMER}"
    return {
        "summary": summary,
        "checklist": [item.strip() for item in result["checklist"]],
    }
