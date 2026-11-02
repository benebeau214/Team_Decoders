"""judge_risk_signals 테스트 — 설계 문서 V1 파트 4 (T06~T10) 기준.

구현 전에 작성한 테스트다 (9주차 사이클 ① 논리 설계 산출물).
"""
import pytest

from franchise_checkup.signals import judge_risk_signals


THRESHOLDS = {"debt_warn": 200, "debt_danger": 400, "term_warn": 10, "term_danger": 20}
ITEMS = ["부채비율", "자본잠식", "영업이익률", "계약 해지율"]


def levels(signals: list[dict]) -> list[str]:
    return [s["level"] for s in signals]


def test_t06_normal_all_risky():
    """T06 정상: 모든 지표가 나쁜 본사 → 위험/위험/주의/위험, 항목 4개·순서 고정."""
    ratios = {"debt_ratio": 450.0, "op_margin": -2.0, "capital_status": "완전잠식"}
    result = judge_risk_signals(ratios, 25.0, THRESHOLDS)
    assert [s["item"] for s in result] == ITEMS
    assert levels(result) == ["위험", "위험", "주의", "위험"]
    assert result[0]["value"] == 450.0
    for s in result:  # 반환 형식 계약
        assert set(s.keys()) == {"item", "level", "value", "reason"}


def test_t07_normal_mixed():
    """T07 정상: 주의 수준이 섞인 본사."""
    ratios = {"debt_ratio": 250.0, "op_margin": 3.0, "capital_status": "부분잠식"}
    result = judge_risk_signals(ratios, 12.0, THRESHOLDS)
    assert levels(result) == ["주의", "주의", "정상", "주의"]


def test_t08_boundary_exact_threshold():
    """T08 경계: 부채비율이 임계값과 정확히 같으면(200.0) '주의'."""
    ratios = {"debt_ratio": 200.0, "op_margin": 5.0, "capital_status": "정상"}
    result = judge_risk_signals(ratios, 3.0, THRESHOLDS)
    assert levels(result) == ["주의", "정상", "정상", "정상"]


def test_t09_missing_values_are_check_needed():
    """T09 예외: 값이 없으면 예외 없이 4개 모두 '확인 필요' ('정상'으로 대체 금지)."""
    ratios = {"debt_ratio": None, "op_margin": None, "capital_status": "NA"}
    result = judge_risk_signals(ratios, None, THRESHOLDS)
    assert levels(result) == ["확인 필요"] * 4


def test_t10_empty_ratios_raises():
    """T10 예외: 필수 키가 없는 ratios → ValueError."""
    with pytest.raises(ValueError):
        judge_risk_signals({}, 3.0, THRESHOLDS)
        
def test_t11_nan_is_check_needed():
    """T11 회귀(결함 1): NaN 값은 '정상'이 아니라 '확인 필요'로 판정."""
    nan = float("nan")
    ratios = {"debt_ratio": nan, "op_margin": nan, "capital_status": "정상"}
    result = judge_risk_signals(ratios, nan, THRESHOLDS)
    assert levels(result) == ["확인 필요", "정상", "확인 필요", "확인 필요"]
