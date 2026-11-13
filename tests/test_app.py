import pandas as pd

from franchise_checkup.app import _review_category
from franchise_checkup.pipeline import (
    _audit_review_flags,
    _clause_review_flags,
    _common_year_summary,
    _freshness_warnings,
    _safe_audit_review_flags,
    _safe_clause_review_flags,
    _regional_rows,
    _year_value,
    common_brands,
)


def test_year_value_accepts_only_finite_integer_values():
    accepted = (2023, "2023", " 2023 ", "2023년", 2023.0, "2023.0")
    rejected = (2023.5, "2023년 1분기", None, float("nan"), float("inf"), "year")
    assert [_year_value(value) for value in accepted] == [2023] * len(accepted)
    assert [_year_value(value) for value in rejected] == [None] * len(rejected)


def test_common_year_selects_latest_shared_year_and_reports_staleness():
    financial = pd.DataFrame({"year": [2022, 2023, 2024]})
    disclosure = pd.DataFrame({"year": [2022, 2023]})
    summary = _common_year_summary(financial, disclosure)
    assert summary == {"financial_latest": 2024, "disclosure_latest": 2023, "selected": 2023}
    warnings = _freshness_warnings(2023, 2024, 2023)
    assert len(warnings) == 1
    assert "2023년" in warnings[0] and "2024년" in warnings[0]


def test_matching_latest_years_have_no_freshness_warning():
    financial = pd.DataFrame({"year": [2023, 2024]})
    disclosure = pd.DataFrame({"year": [2023, 2024]})
    summary = _common_year_summary(financial, disclosure)
    assert summary["selected"] == 2024
    assert _freshness_warnings(2024, 2024, 2024) == []


def test_document_year_mismatch_is_reported_without_mixing_years():
    warnings = _freshness_warnings(2023, 2023, 2023, audit_latest=2024, clauses_latest=2022)
    assert len(warnings) == 2
    assert any("감사보고서 주석" in warning and "2024년" in warning for warning in warnings)
    assert any("계약 조항" in warning and "2022년" in warning for warning in warnings)


def test_partial_audit_extraction_keeps_deals_and_errors_and_cross_checks():
    deal = {"related_party": "A", "relationship": "계열사", "transaction_type": "매출", "amount": "1원", "quote": "근거"}
    called = []

    def cross_checker(deals, disc_row):
        called.append(deals)
        return [{"issue": "교차 결과", "evidence": "근거"}]

    flags = _audit_review_flags(
        "원문",
        {"related_party": "A", "relationship": "계열사", "transaction_type": "매출", "amount": "1원"},
        lambda _text, _llm: {"status": "partial_error", "items": [deal], "errors": [{"index": 1, "reason": "invalid_fields"}]},
        cross_checker,
        lambda _prompt: "{}",
    )

    assert called == [[deal]]
    assert any(flag["issue"].startswith("특수관계자 거래 확인") for flag in flags)
    assert any("부분 실패" in flag["issue"] for flag in flags)
    assert any("항목 추출 오류" in flag["issue"] and "invalid_fields" in flag["evidence"] for flag in flags)
    assert any(flag["issue"] == "교차 결과" for flag in flags)


def test_successful_empty_audit_result_still_cross_checks():
    called = []
    flags = _audit_review_flags(
        "원문",
        {"related_party": "A", "relationship": "계열사", "transaction_type": "매출", "amount": "1원"},
        lambda _text, _llm: {"status": "ok", "items": []},
        lambda deals, _row: called.append(deals) or [{"issue": "미기재 거래", "evidence": "확인"}],
        lambda _prompt: "{}",
    )
    assert called == [[]]
    assert any(flag["issue"] == "미기재 거래" for flag in flags)


def test_incomplete_without_valid_deals_and_parse_error_do_not_cross_check():
    called = []
    cross = lambda deals, row: called.append(deals) or []
    for result in (
        {"status": "partial_error", "items": [], "errors": [{"index": 0}]},
        {"status": "parse_error", "items": []},
        {"status": "empty", "items": []},
    ):
        flags = _audit_review_flags("원문", {}, lambda _text, _llm, r=result: r, cross, lambda _prompt: "{}")
        assert flags
    assert called == []


def test_region_normalization_does_not_mutate_cached_source():
    source = pd.DataFrame([
        {"brand": "A", "year": 2024, "region": "서울특별시 ", "avg_annual_sales": 100},
        {"brand": "A", "year": 2023, "region": "부산광역시", "avg_annual_sales": 200},
    ])
    result = _regional_rows(source, "A", 2024)
    assert result["region"].tolist() == ["서울특별시"]
    assert source.loc[0, "region"] == "서울특별시 "


def test_brand_options_use_financial_and_disclosure_intersection():
    financial = pd.DataFrame({"brand": [" A ", "B", None]})
    disclosure = pd.DataFrame({"brand": ["A", "C", " "]})
    assert common_brands(financial, disclosure) == ["A"]


def test_document_extraction_exceptions_are_logged_and_reported_independently(caplog):
    def fail(*_args):
        raise RuntimeError("mock extraction failure")

    audit_flags = _safe_audit_review_flags("원문", {}, fail, fail, lambda _prompt: "{}")
    clause_flags = _safe_clause_review_flags("원문", fail, lambda _prompt: "{}")
    assert "원문을 확인" in audit_flags[0]["evidence"]
    assert "원문을 확인" in clause_flags[0]["evidence"]
    assert "Related-party extraction failed" in caplog.text
    assert "Unfavorable-clause extraction failed" in caplog.text


def test_cross_check_exception_is_logged_and_returned_as_actionable_flag(caplog):
    deal = {"related_party": "A", "relationship": "관계", "transaction_type": "매출", "amount": "1원", "quote": "근거"}
    flags = _audit_review_flags(
        "원문",
        {"related_party": "A", "relationship": "관계", "transaction_type": "매출", "amount": "1원"},
        lambda _text, _llm: {"status": "ok", "items": [deal]},
        lambda *_args: (_ for _ in ()).throw(RuntimeError("cross failure")),
        lambda _prompt: "{}",
    )
    assert any(flag["issue"] == "문서 교차 점검 실패" for flag in flags)
    assert "Document cross-check failed" in caplog.text


# 검토 항목 분류(_review_category) 회귀 테스트

EXTRACT = "추출·계산 확인"

# (pipeline.py / signals.py가 만드는 issue 문구, 기대 분류)
CASES = (
    ("특수관계자 거래 확인: 가상유통", "특수관계자 거래"),
    ("점주 확인 조항: 필수품목·구매 강제 — 이유", "계약 조항"),
    ("감사보고서 주석 자료 누락", "자료 누락"),
    ("정보공개서 계약 조항 자료 누락", "자료 누락"),
    ("감사보고서 주석 원문 없음", "자료 누락"),
    ("정보공개서 계약 조항 원문 없음", "자료 누락"),
    ("정보공개서의 related_party 값이 누락되었습니다.", "자료 누락"),
    ("감사보고서의 금액 값이 누락되었습니다.", "자료 누락"),
    ("정보공개서에 기재된 특수관계자 거래가 감사보고서 주석에서 확인되지 않습니다.", "문서 불일치"),
    ("정보공개서의 거래처가 감사보고서 주석의 거래처와 일치하지 않습니다.", "문서 불일치"),
    ("'가상유통' 거래의 금액 값이 감사보고서 주석과 정보공개서에서 다릅니다.", "문서 불일치"),
    ("동일 거래처의 비교 대상이 여러 건이므로 개별 거래 또는 합계 기준 확인이 필요합니다.", "문서 불일치"),
    ("특수관계자 거래 추출 결과 없음", EXTRACT),
    ("특수관계자 거래 추출 부분 실패 — 일부 결과만 확인됨", EXTRACT),
    ("특수관계자 거래 항목 추출 오류", EXTRACT),
    ("문서 교차 점검 실패", EXTRACT),
    ("특수관계자 거래 추출 확인 필요 (llm_error)", EXTRACT),
    ("불리한 조항 추출 결과 없음", EXTRACT),
    ("원문 근거가 확인되지 않아 제외된 추출 결과", EXTRACT),
    ("불리한 조항 추출 확인 필요 (parse_error)", EXTRACT),
    ("특수관계자 거래 추출 실패", EXTRACT),
    ("불리한 계약 조항 추출 실패", EXTRACT),
    ("투자 회수 기간 계산 확인 필요", EXTRACT),
    ("기준연도 최신성 확인", "기준연도·기타 확인"),
)

DISC_ROW = {"related_party": "A", "relationship": "계열사", "transaction_type": "매출", "amount": "1원"}
DEAL = {**DISC_ROW, "quote": "근거"}
CLAUSE = {"type": "필수품목·구매 강제", "quote": "q", "reason": "이유"}


def _categories(flags):
    return [_review_category(flag) for flag in flags]


def _audit(result):
    return _audit_review_flags("원문", DISC_ROW, lambda _t, _l: result, lambda _d, _r: [], lambda _p: "{}")


def _clause(result):
    return _clause_review_flags("원문", lambda _t, _l: result, lambda _p: "{}")


def test_known_issue_texts_and_keyword_priority_are_classified_correctly():
    wrong = [
        f"{issue!r}: 기대={expected}, 실제={actual}"
        for issue, expected in CASES
        if (actual := _review_category({"issue": issue})) != expected
    ]
    assert not wrong, f"{len(wrong)}/{len(CASES)}건 오분류\n" + "\n".join(wrong)

    priority_cases = (
        (
            "점주 확인 조항: 계약 해지 — 자료 제공 의무를 누락하면 실패로 본다",
            "계약 조항",
        ),
        ("특수관계자 거래 확인: 원문 없음상사", "특수관계자 거래"),
    )
    for issue, expected in priority_cases:
        assert _review_category({"issue": issue}) == expected


def test_flags_built_by_pipeline_get_the_expected_categories():
    ok_deal = {"status": "ok", "items": [DEAL]}
    assert _categories(_audit(ok_deal)) == ["특수관계자 거래"]
    assert _categories(_audit({"status": "ok", "items": []})) == [EXTRACT]
    assert _categories(_audit({"status": "parse_error", "items": []})) == [EXTRACT]
    assert _categories(_audit({"status": "llm_error", "items": []})) == [EXTRACT]
    assert _categories(_audit({"status": "empty", "items": []})) == ["자료 누락"]
    partial = {"status": "partial_error", "items": [DEAL], "errors": [{"index": 1, "reason": "invalid_fields"}]}
    assert _categories(_audit(partial)) == ["특수관계자 거래", EXTRACT, EXTRACT]

    assert _categories(_clause({"status": "ok", "items": [CLAUSE], "dropped": 0})) == ["계약 조항"]
    assert _categories(_clause({"status": "ok", "items": [], "dropped": 0})) == [EXTRACT]
    assert _categories(_clause({"status": "ok", "items": [CLAUSE], "dropped": 2})) == ["계약 조항", EXTRACT]
    assert _categories(_clause({"status": "parse_error", "items": [], "dropped": 0})) == [EXTRACT]
    assert _categories(_clause({"status": "llm_error", "items": [], "dropped": 0})) == [EXTRACT]


def test_unknown_or_malformed_flags_fall_back_to_the_default_category():
    for flag in ({}, {"issue": None}, {"issue": ""}, {"issue": 123}, {"issue": "처음 보는 문구"}):
        assert _review_category(flag) == "기준연도·기타 확인"