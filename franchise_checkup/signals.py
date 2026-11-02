import math

def judge_risk_signals(
    ratios: dict,
    termination_rate: float | None,
    thresholds: dict,
) -> list[dict]:
    """재무 지표와 계약 해지율의 위험 수준을 판정합니다.

    Args:
        ratios: 부채비율, 영업이익률, 자본잠식 상태를 포함한 지표입니다.
        termination_rate: 계약 해지율(%), 정보가 없으면 None입니다.
        thresholds: 부채비율 및 계약 해지율의 주의·위험 기준값입니다.

    Returns:
        부채비율, 자본잠식, 영업이익률, 계약 해지율 순서의 판정 결과입니다.

    Raises:
        ValueError: ratios가 딕셔너리가 아니거나 필수 지표 키가 없으면 발생합니다.
    """
    required_keys = {"debt_ratio", "op_margin", "capital_status"}
    if not isinstance(ratios, dict) or not required_keys.issubset(ratios):
        raise ValueError("필수 지표 누락")

    debt_ratio = ratios["debt_ratio"]
    op_margin = ratios["op_margin"]
    capital_status = ratios["capital_status"]

    if debt_ratio is None or math.isnan(debt_ratio):
        debt_level = "확인 필요"
        debt_reason = "부채비율 정보가 없어 위험 수준을 확인할 수 없습니다."
    elif debt_ratio >= thresholds["debt_danger"]:
        debt_level = "위험"
        debt_reason = f"부채비율({debt_ratio})이 위험 기준 이상입니다."
    elif debt_ratio >= thresholds["debt_warn"]:
        debt_level = "주의"
        debt_reason = f"부채비율({debt_ratio})이 주의 기준 이상입니다."
    else:
        debt_level = "정상"
        debt_reason = f"부채비율({debt_ratio})이 주의 기준보다 낮습니다."

    if capital_status == "완전잠식":
        capital_level = "위험"
        capital_reason = "자본 상태가 완전잠식입니다."
    elif capital_status == "부분잠식":
        capital_level = "주의"
        capital_reason = "자본 상태가 부분잠식입니다."
    elif capital_status == "정상":
        capital_level = "정상"
        capital_reason = "자본 상태가 정상입니다."
    else:
        capital_level = "확인 필요"
        capital_reason = "자본 상태를 확인할 수 없습니다."

    if op_margin is None or math.isnan(op_margin):
        margin_level = "확인 필요"
        margin_reason = "영업이익률 정보가 없어 위험 수준을 확인할 수 없습니다."
    elif op_margin < 0:
        margin_level = "주의"
        margin_reason = f"영업이익률({op_margin})이 0보다 낮습니다."
    else:
        margin_level = "정상"
        margin_reason = f"영업이익률({op_margin})이 0 이상입니다."

    if termination_rate is None or math.isnan(termination_rate):
        termination_level = "확인 필요"
        termination_reason = "계약 해지율 정보가 없어 위험 수준을 확인할 수 없습니다."
    elif termination_rate >= thresholds["term_danger"]:
        termination_level = "위험"
        termination_reason = f"계약 해지율({termination_rate}%)이 위험 기준 이상입니다."
    elif termination_rate >= thresholds["term_warn"]:
        termination_level = "주의"
        termination_reason = f"계약 해지율({termination_rate}%)이 주의 기준 이상입니다."
    else:
        termination_level = "정상"
        termination_reason = f"계약 해지율({termination_rate}%)이 주의 기준보다 낮습니다."

    return [
        {
            "item": "부채비율",
            "level": debt_level,
            "value": debt_ratio,
            "reason": debt_reason,
        },
        {
            "item": "자본잠식",
            "level": capital_level,
            "value": capital_status,
            "reason": capital_reason,
        },
        {
            "item": "영업이익률",
            "level": margin_level,
            "value": op_margin,
            "reason": margin_reason,
        },
        {
            "item": "계약 해지율",
            "level": termination_level,
            "value": termination_rate,
            "reason": termination_reason,
        },
    ]