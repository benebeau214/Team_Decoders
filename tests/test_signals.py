"""judge_risk_signals 테스트 — 설계 문서 V1 파트 4 (T06~T10) 기준.

구현 전에 작성한 테스트다 (9주차 사이클 ① 논리 설계 산출물).
"""
import pytest

from franchise_checkup.signals import (
    calc_financial_ratios,
    calc_termination_rate,
    judge_risk_signals,
    cross_check_documents,
)


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


# ---------------------------------------------------------------
# calc_financial_ratios
# ---------------------------------------------------------------
FIN = {
    "total_liabilities": 150.0,
    "total_equity": 50.0,
    "capital_stock": 30.0,
    "revenue": 200.0,
    "operating_income": -10.0,
}


def test_ratios_normal():
    """정상: 부채비율·영업이익률 계산, 출력 키는 judge_risk_signals 입력과 동일."""
    result = calc_financial_ratios(FIN)
    assert set(result.keys()) == {"debt_ratio", "op_margin", "capital_status"}
    assert result["debt_ratio"] == pytest.approx(300.0)
    assert result["op_margin"] == pytest.approx(-5.0)  # 영업손실은 음수 그대로
    assert result["capital_status"] == "정상"


def test_ratios_not_rounded():
    """정상: 판정이 바뀌지 않도록 반올림하지 않은 값을 반환."""
    result = calc_financial_ratios({**FIN, "total_liabilities": 100.0, "total_equity": 30.0})
    assert result["debt_ratio"] == pytest.approx(100.0 / 30.0 * 100)  # 333.33…, 333.3이면 실패


def test_ratios_boundary_capital_impairment():
    """경계: 자본총계 = 자본금이면 정상, 자본금보다 작으면 부분잠식."""
    assert calc_financial_ratios({**FIN, "total_equity": 30.0})["capital_status"] == "정상"
    result = calc_financial_ratios({**FIN, "total_equity": 20.0})
    assert result["capital_status"] == "부분잠식"
    assert result["debt_ratio"] == pytest.approx(750.0)


def test_ratios_boundary_full_impairment():
    """경계: 자본총계 ≤ 0이면 완전잠식(자본금 없어도), 부채비율은 None(N/M), 예외 없음."""
    zero = calc_financial_ratios({**FIN, "total_equity": 0.0})
    assert zero["capital_status"] == "완전잠식"
    assert zero["debt_ratio"] is None  # ZeroDivisionError 없음
    negative = calc_financial_ratios({**FIN, "total_equity": -50.0, "capital_stock": None})
    assert negative["capital_status"] == "완전잠식"
    assert negative["debt_ratio"] is None  # -300%가 '정상'으로 판정되는 것 방지


def test_ratios_missing_values_are_none():
    """예외: 값 없음(None·NaN·키 없음)·매출액 0·부채 음수 → None/'NA', 예외 없음."""
    result = calc_financial_ratios({
        "total_liabilities": -10.0,
        "total_equity": float("nan"),
        "capital_stock": None,
        "revenue": 0.0,
        "operating_income": 5.0,
    })
    assert result == {"debt_ratio": None, "op_margin": None, "capital_status": "NA"}
    assert calc_financial_ratios({}) == {"debt_ratio": None, "op_margin": None, "capital_status": "NA"}


def test_ratios_not_dict_raises():
    """예외: fin_row가 dict가 아니면 ValueError."""
    with pytest.raises(ValueError):
        calc_financial_ratios([])


# ---------------------------------------------------------------
# calc_termination_rate
# ---------------------------------------------------------------
DISC = {"stores_begin": 1000, "contract_terminated": 30, "contract_ended": 20}  # 가상 값


def test_rate_normal():
    """정상: (해지 + 종료) / 연초 가맹점 수 × 100, 반올림 없음."""
    assert calc_termination_rate(DISC) == pytest.approx(5.0)


def test_rate_boundary_zero_stores():
    """경계: 연초 가맹점 수 0이면 None (ZeroDivisionError 없음)."""
    assert calc_termination_rate({**DISC, "stores_begin": 0}) is None


def test_rate_missing_or_negative_is_none():
    """예외: 값 없음(None·NaN·키 없음)·음수 건수 → None, 예외 없음."""
    assert calc_termination_rate({**DISC, "contract_ended": None}) is None
    assert calc_termination_rate({**DISC, "stores_begin": float("nan")}) is None
    assert calc_termination_rate({"stores_begin": 1000}) is None
    assert calc_termination_rate({**DISC, "contract_terminated": -1}) is None


def test_rate_not_dict_raises():
    """예외: disc_row가 dict가 아니면 ValueError."""
    with pytest.raises(ValueError):
        calc_termination_rate("1000")


# ---------------------------------------------------------------
# 연결: 계산 → 판정
# ---------------------------------------------------------------
def test_full_impairment_flows_to_judge():
    """연결: 완전잠식 본사는 부채비율 '확인 필요', 자본잠식 '위험' (부채비율이 '정상'으로 나오면 안 됨)."""
    ratios = calc_financial_ratios({**FIN, "total_equity": -50.0})
    result = judge_risk_signals(ratios, calc_termination_rate(DISC), THRESHOLDS)
    assert levels(result) == ["확인 필요", "위험", "주의", "정상"]


def test_regression_non_numeric_is_none():
    """회귀(결함): 숫자가 아닌 값(쉼표 문자열 등)은 예외 없이 None/'NA'로 처리."""
    # calc_termination_rate: 연초 가맹점 수가 쉼표 문자열
    assert calc_termination_rate({**DISC, "stores_begin": "1,000"}) is None

    # calc_financial_ratios: 부채총계만 문자열, 나머지는 FIN 그대로
    result = calc_financial_ratios({**FIN, "total_liabilities": "150"})
    assert result["debt_ratio"] is None
    assert result["op_margin"] == pytest.approx(-5.0)
    assert result["capital_status"] == "정상"


def _deal():
    return {
        "related_party": "가상유통",
        "relationship": "종속회사",
        "transaction_type": "매출",
        "amount": "100만원",
    }


def test_normal_matching_deal():
    # 정상: 두 문서의 거래가 같으면 문제 없음
    assert cross_check_documents([_deal()], _deal()) == []


def test_boundary_empty_audit_deals():
    # 경계: 감사보고서 거래가 0건이면 확인 불가 문제 1건 반환
    issues = cross_check_documents([], _deal())
    assert len(issues) == 1
    assert "감사보고서 주석에서 확인되지 않습니다" in issues[0]["issue"]
    assert "가상유통" in issues[0]["evidence"]


def test_exception_invalid_deals_type():
    # 예외: 거래 목록에 잘못된 타입을 전달하면 TypeError 발생
    with pytest.raises(TypeError, match="deals"):
        cross_check_documents(None, _deal())


@pytest.mark.parametrize("disc_row", [
    {},
    {field: "" for field in ("related_party", "relationship", "transaction_type", "amount")},
    {"related_party": "  ", "relationship": "\t", "transaction_type": "\n", "amount": " "},
    {"brand": "가상브랜드", "year": 2025},
])
def test_cross_check_both_documents_have_no_deals(disc_row):
    assert cross_check_documents([], disc_row) == []


def test_cross_check_partial_disclosure_keeps_missing_field_warnings():
    issues = cross_check_documents([], {"related_party": "가상유통"})
    assert len(issues) == 3
    for field in ("relationship", "transaction_type", "amount"):
        assert any(field in issue["issue"] for issue in issues)


def test_cross_check_empty_disclosure_with_audit_deal_still_warns():
    assert cross_check_documents([_deal()], {})


def test_cross_check_invalid_empty_field_type_still_raises():
    with pytest.raises(TypeError):
        cross_check_documents([], {"amount": None})


@pytest.mark.parametrize("disclosure", [{}, []])
def test_cross_check_audit_only_party_is_reported(disclosure):
    issues = cross_check_documents([_deal()], disclosure)
    assert len(issues) == 1
    assert "가상유통" in issues[0]["issue"]
    assert "정보공개서" in issues[0]["issue"]
    assert "100만원" in issues[0]["evidence"]


def test_cross_check_extra_audit_party_is_not_lost_after_match():
    extra = {**_deal(), "related_party": "추가거래처", "quote": "추가거래처 원문"}
    issues = cross_check_documents([_deal(), extra], _deal())
    assert len(issues) == 1
    assert "추가거래처" in issues[0]["issue"]
    assert "추가거래처 원문" in issues[0]["evidence"]


def test_cross_check_complete_disclosure_list_avoids_false_missing_party():
    extra = {**_deal(), "related_party": "추가거래처"}
    assert cross_check_documents([_deal(), extra], [_deal(), extra]) == []


def test_cross_check_list_reports_missing_parties_in_both_directions():
    audit_only = {**_deal(), "related_party": "감사전용"}
    disclosure_only = {**_deal(), "related_party": "공개전용"}
    issues = cross_check_documents([_deal(), audit_only], [_deal(), disclosure_only])
    assert len(issues) == 2
    assert any("감사전용" in item["issue"] for item in issues)
    assert any("공개전용" in item["evidence"] for item in issues)


def test_cross_check_party_normalization_and_duplicate_audit_records():
    deal = {**_deal(), "related_party": " Example  Corp "}
    disclosed = {**_deal(), "related_party": "example corp"}
    assert cross_check_documents([deal], [disclosed]) == []
    assert len(cross_check_documents([deal, deal], [])) == 1


@pytest.mark.parametrize("disclosure", [[None], [{"amount": None}]])
def test_cross_check_invalid_disclosure_list_rows_raise(disclosure):
    with pytest.raises(TypeError):
        cross_check_documents([], disclosure)
