import pandas as pd

from franchise_checkup.app import (
    _audit_review_flags,
    _common_brands,
    _common_year_summary,
    _freshness_warnings,
    _money_input_label,
    _safe_audit_review_flags,
    _safe_clause_review_flags,
    _regional_rows,
    _year_value,
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


def test_currency_input_labels_do_not_guess_unit():
    for field in ("보증금", "권리금", "대출금"):
        label = _money_input_label(field)
        assert field in label
        assert "화폐 단위 확인 필요" in label
        assert "원" not in label.replace("화폐 단위 확인 필요", "")


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
    assert _common_brands(financial, disclosure) == ["A"]


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
