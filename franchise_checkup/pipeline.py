"""Backend workflow for the franchise financial health check.

This module has no Streamlit dependency. ``app.py`` (UI) and the tests call
``run_checkup`` directly, and ``python pipeline.py`` runs the whole workflow
from the command line.

Workflow (``run_checkup``)::

    user input + CSV tables
      -> common reference year selection
      -> financial ratios / termination rate -> risk signals
      -> data freshness warnings
      -> document review (LLM extraction + cross-check)
      -> payback simulation
      -> non-expert report (LLM)
      -> result dict
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

import pandas as pd
from franchise_checkup.data_loader import load_csv_table, select_avg_sales
from franchise_checkup.llm_tasks import write_report
from llm_client import llm_call

logger = logging.getLogger(__name__)

try:
    from franchise_checkup.llm_tasks import (
        extract_related_party_deals,
        extract_unfavorable_clauses,
    )
    _LLM_EXTRACT_IMPORT_ERROR: ImportError | None = None
except ImportError as error:
    extract_related_party_deals = None
    extract_unfavorable_clauses = None
    _LLM_EXTRACT_IMPORT_ERROR = error

try:
    from franchise_checkup.signals import (
        calc_financial_ratios,
        calc_termination_rate,
        judge_risk_signals,
        cross_check_documents,
    )
    from franchise_checkup.payback import simulate_payback
    _ANALYSIS_IMPORT_ERROR: ImportError | None = None
except ImportError as error:
    # Some working branches do not yet contain these modules. Keep the app
    # importable so it can show a useful message instead of crashing at import.
    simulate_payback = None
    calc_financial_ratios = None
    calc_termination_rate = None
    judge_risk_signals = None
    cross_check_documents = None
    _ANALYSIS_IMPORT_ERROR = error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_NAMES = (
    "hq_financials.csv",
    "franchise_disclosure.csv",
    "region_sales.csv",
    "audit_notes.csv",
    "disclosure_clauses.csv",
)

# These are the V1 reference values documented in design_doc_v1.md and its
# acceptance cases. The existing judge/simulator functions require these as
# arguments and expose no shared constants.
RISK_THRESHOLDS = {
    "debt_warn": 200,
    "debt_danger": 400,
    "term_warn": 10,
    "term_danger": 20,
}
PAYBACK_SCENARIOS = {
    "보수": {"sales_factor": 0.8, "margin": 0.05},
    "평균": {"sales_factor": 1.0, "margin": 0.10},
    "낙관": {"sales_factor": 1.2, "margin": 0.15},
}

REQUIRED_COLUMNS = {
    "hq_financials.csv": [
        "brand", "year", "total_liabilities", "total_equity", "capital_stock",
        "revenue", "operating_income",
    ],
    "franchise_disclosure.csv": [
        "brand", "year", "startup_cost", "avg_annual_sales", "stores_begin",
        "contract_terminated", "contract_ended", "related_party", "relationship",
        "transaction_type", "amount",
    ],
    "region_sales.csv": ["brand", "year", "region", "avg_annual_sales"],
    "audit_notes.csv": ["brand", "year", "note_text"],
    "disclosure_clauses.csv": ["brand", "year", "clause_text"],
}

USER_INPUT_KEYS = (
    "brand", "region", "deposit", "key_money", "loan_amount", "loan_rate", "user_type",
)


class PipelineError(Exception):
    """The workflow cannot continue (missing data, no common year, import failure).

    ``warnings`` carries the non-fatal data notes collected before the failure.
    """

    def __init__(self, message: str, warnings: list[str] | None = None) -> None:
        super().__init__(message)
        self.warnings: list[str] = list(warnings or [])


def _find_csv(root: Path, name: str) -> Path:
    candidates = (
        root / "data" / name,
        root / "franchise_checkup" / "data" / name,
        root / name,
        root / "franchise_checkup" / name,
    )
    matches = list(dict.fromkeys(path.resolve() for path in candidates if path.is_file()))
    if not matches:
        raise FileNotFoundError(f"프로젝트의 표준 데이터 위치에서 {name} 파일을 찾을 수 없습니다.")
    if len(matches) > 1:
        raise ValueError(f"{name} 파일이 여러 허용 위치에 있습니다. 하나만 남겨 주세요: {matches}")
    return matches[0]


def load_tables(root: str) -> dict[str, pd.DataFrame]:
    """Load every required CSV.

    Args:
        root: Project root directory.
    Returns:
        ``{csv file name: DataFrame}`` for each name in ``REQUIRED_COLUMNS``.
    Raises:
        FileNotFoundError / ValueError / OSError: a CSV is missing, duplicated or malformed.
    """
    project_root = Path(root).resolve()
    tables: dict[str, pd.DataFrame] = {}
    for name, columns in REQUIRED_COLUMNS.items():
        path = _find_csv(project_root, name)
        tables[name] = load_csv_table(str(path), columns)
    return tables


def _check_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Fail early when a table is absent or lacks a required column."""
    for name, columns in REQUIRED_COLUMNS.items():
        table = tables.get(name) if isinstance(tables, dict) else None
        if not isinstance(table, pd.DataFrame):
            raise PipelineError(f"{name} 데이터가 없습니다.")
        missing = [column for column in columns if column not in table.columns]
        if missing:
            raise PipelineError(f"{name}에 필수 컬럼이 없습니다: {', '.join(missing)}")


def _year_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value)
    match = re.fullmatch(r"\s*(\d{4})(?:\.0+)?\s*년?\s*", text)
    return int(match.group(1)) if match else None


def _latest_year(table: pd.DataFrame) -> int | None:
    years = [year for year in table["year"].map(_year_value) if year is not None]
    return max(years) if years else None


def _common_year_summary(financial: pd.DataFrame, disclosure: pd.DataFrame) -> dict[str, int | None]:
    financial_years = {year for year in financial["year"].map(_year_value) if year is not None}
    disclosure_years = {year for year in disclosure["year"].map(_year_value) if year is not None}
    common = financial_years & disclosure_years
    return {
        "financial_latest": max(financial_years) if financial_years else None,
        "disclosure_latest": max(disclosure_years) if disclosure_years else None,
        "selected": max(common) if common else None,
    }


def _freshness_warnings(
    selected_year: int,
    financial_latest: int | None,
    disclosure_latest: int | None,
    audit_latest: int | None = None,
    clauses_latest: int | None = None,
) -> list[str]:
    warnings = []
    if financial_latest != selected_year:
        warnings.append(
            f"선택된 공통 기준연도는 {selected_year}년입니다. 본사 재무자료의 최신 연도는 "
            f"{financial_latest if financial_latest is not None else '확인 불가'}년이므로 일부 최신 정보가 분석에 반영되지 않았을 수 있습니다. 자료 누락 여부와 최신 공시 자료를 확인해 주세요."
        )
    if disclosure_latest != selected_year:
        warnings.append(
            f"선택된 공통 기준연도는 {selected_year}년입니다. 정보공개서의 최신 연도는 "
            f"{disclosure_latest if disclosure_latest is not None else '확인 불가'}년이므로 최신 자료 여부를 확인해 주세요."
        )
    for label, latest in (("감사보고서 주석", audit_latest), ("계약 조항", clauses_latest)):
        if latest is not None and latest != selected_year:
            warnings.append(
                f"분석 기준연도는 {selected_year}년이지만 {label}의 최신 자료는 {latest}년입니다. "
                "연도가 다른 자료는 혼합하지 않았으며, 해당 문서의 기준연도를 확인해 주세요."
            )
    return warnings


def _brand_rows(table: pd.DataFrame, brand: str) -> pd.DataFrame:
    return table.loc[table["brand"].astype(str).str.strip() == brand].copy()


def _one_row(
    table: pd.DataFrame, brand: str, year: int, label: str, warnings: list[str],
) -> dict[str, Any] | None:
    """Return the single row for brand/year, or None (reason appended to ``warnings``)."""
    rows = _brand_rows(table, brand)
    rows = rows.loc[rows["year"].map(_year_value) == year]
    if rows.empty:
        warnings.append(f"{label}: {year}년 자료가 없어 해당 분석은 확인 필요입니다.")
        return None
    if len(rows) > 1:
        warnings.append(f"{label}: {year}년 자료가 여러 행입니다. 중복 자료로 분석을 중단합니다.")
        return None
    return rows.iloc[0].to_dict()


def common_brands(financial: pd.DataFrame, disclosure: pd.DataFrame) -> list[str]:
    financial_brands = set(financial["brand"].dropna().astype(str).str.strip())
    disclosure_brands = set(disclosure["brand"].dropna().astype(str).str.strip())
    return sorted(brand for brand in financial_brands & disclosure_brands if brand)


def list_regions(region_table: pd.DataFrame) -> list[str]:
    """Sorted, de-duplicated region names from the region sales table."""
    return sorted({v.strip() for v in region_table["region"].dropna().astype(str) if v.strip()})


def _regional_rows(table: pd.DataFrame, brand: str, year: int) -> pd.DataFrame:
    rows = _brand_rows(table, brand)
    rows = rows.loc[rows["year"].map(_year_value) == year].copy()
    rows["region"] = rows["region"].astype("string").str.strip()
    return rows


def _audit_review_flags(
    note_text: Any,
    disc_row: dict[str, Any],
    extractor,
    cross_checker,
    call_llm,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    result = extractor(note_text if isinstance(note_text, str) else "", call_llm)
    status = result.get("status")
    deals = result.get("items", [])
    if status in {"ok", "partial_error"}:
        if status == "ok" and not deals:
            flags.append({"issue": "특수관계자 거래 추출 결과 없음", "evidence": "정상적으로 검토된 원문에서 추출된 거래가 없습니다."})
        for deal in deals:
            flags.append({
                "issue": f"특수관계자 거래 확인: {deal.get('related_party', '거래처 미상')}",
                "evidence": f"{deal.get('relationship', '')} · {deal.get('transaction_type', '')} · {deal.get('amount', '')}; 원문: {deal.get('quote', '')}",
            })
        if status == "partial_error":
            errors = result.get("errors", [])
            flags.append({
                "issue": "특수관계자 거래 추출 부분 실패 — 일부 결과만 확인됨",
                "evidence": f"정상 추출 {len(deals)}건, 오류 {len(errors)}건. 전체 원문 검토가 완료된 것으로 볼 수 없습니다.",
            })
            for extraction_error in errors:
                flags.append({"issue": "특수관계자 거래 항목 추출 오류", "evidence": str(extraction_error)})
        if status == "ok" or deals:
            cross_disc_row = dict(disc_row)
            for field in ("related_party", "relationship", "transaction_type", "amount"):
                value = cross_disc_row.get(field)
                cross_disc_row[field] = "" if value is None or pd.isna(value) else str(value)
            try:
                flags.extend(cross_checker(deals, cross_disc_row))
            except Exception as error:
                logger.exception("Document cross-check failed")
                flags.append({"issue": "문서 교차 점검 실패", "evidence": "관련 자료를 확인해 주세요."})
    elif status == "empty":
        flags.append({"issue": "감사보고서 주석 원문 없음", "evidence": "특수관계자 거래 추출을 수행하지 않았습니다."})
    else:
        flags.append({"issue": f"특수관계자 거래 추출 확인 필요 ({status})", "evidence": str(result.get("errors", "LLM 응답 또는 검증에 실패했습니다."))})
    return flags


def _clause_review_flags(clause_text: Any, extractor, call_llm) -> list[dict[str, Any]]:
    text = clause_text if isinstance(clause_text, str) else ""
    result = extractor(text, call_llm)
    status = result.get("status")
    flags: list[dict[str, Any]] = []
    if status == "ok":
        items = result.get("items", [])
        if not items:
            flags.append({"issue": "불리한 조항 추출 결과 없음", "evidence": "원문에서 추출된 항목이 없습니다. 문서 전체가 안전하다는 뜻은 아닙니다."})
        for item in items:
            flags.append({
                "issue": f"점주 확인 조항: {item.get('type', '유형 미상')} — {item.get('reason', '')}",
                "evidence": f"원문 인용: {item.get('quote', '')}",
                "quote": item.get("quote", ""),
            })
        if result.get("dropped", 0):
            flags.append({"issue": "원문 근거가 확인되지 않아 제외된 추출 결과", "evidence": f"제외 건수: {result['dropped']}"})
    elif status == "empty":
        flags.append({"issue": "정보공개서 계약 조항 원문 없음", "evidence": "불리한 조항 추출을 수행하지 않았습니다."})
    else:
        flags.append({"issue": f"불리한 조항 추출 확인 필요 ({status})", "evidence": str(result.get("errors", "LLM 응답 또는 검증에 실패했습니다."))})
    return flags


def _safe_audit_review_flags(note_text, disc_row, extractor, cross_checker, call_llm):
    try:
        return _audit_review_flags(note_text, disc_row, extractor, cross_checker, call_llm)
    except Exception:
        logger.exception("Related-party extraction failed")
        return [{"issue": "특수관계자 거래 추출 실패", "evidence": "원문을 확인해 주세요."}]


def _safe_clause_review_flags(clause_text, extractor, call_llm):
    try:
        return _clause_review_flags(clause_text, extractor, call_llm)
    except Exception:
        logger.exception("Unfavorable-clause extraction failed")
        return [{"issue": "불리한 계약 조항 추출 실패", "evidence": "원문을 확인해 주세요."}]


def run_checkup(
    user_input: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    call_llm: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Run the full analysis workflow and return every result the UI shows.

    Args:
        user_input: ``brand, region, deposit, key_money, loan_amount, loan_rate, user_type``
            (already validated by ``validate_user_input``).
        tables: output of ``load_tables``.
        call_llm: ``prompt -> response`` function. Defaults to ``llm_client.llm_call``.
    Returns:
        dict with ``user_input, year, year_summary, fin_row, disc_row, ratios,
        termination_rate, signals, freshness, review_flags, audit_text, clause_text,
        avg_sales_info, payback_df, report, warnings``. ``payback_df`` and ``report``
        are None when that step fails; the other results are still returned.
    Raises:
        PipelineError: input/tables are unusable, the brand has no data, there is no
            common reference year, or the base-year rows are missing/duplicated.
    """
    call_llm = call_llm or llm_call
    warnings: list[str] = []

    if _ANALYSIS_IMPORT_ERROR is not None:
        raise PipelineError(
            "분석 모듈을 불러오지 못했습니다. 누락된 모듈 또는 의존성을 확인해 주세요: "
            f"{_ANALYSIS_IMPORT_ERROR}"
        )
    if not isinstance(user_input, dict):
        raise PipelineError("입력값이 올바르지 않습니다.")
    missing_keys = [key for key in USER_INPUT_KEYS if key not in user_input]
    if missing_keys:
        raise PipelineError(f"입력값이 누락되었습니다: {', '.join(missing_keys)}")
    _check_tables(tables)

    brand = user_input["brand"]
    financial = _brand_rows(tables["hq_financials.csv"], brand)
    disclosure = _brand_rows(tables["franchise_disclosure.csv"], brand)
    if financial.empty or disclosure.empty:
        raise PipelineError("선택한 브랜드의 본사 재무 또는 정보공개서 자료가 없습니다.")

    year_summary = _common_year_summary(financial, disclosure)
    year = year_summary["selected"]
    if year is None:
        raise PipelineError("본사 재무와 정보공개서에서 일치하는 기준연도를 찾지 못했습니다.")

    fin_row = _one_row(tables["hq_financials.csv"], brand, year, "본사 재무", warnings)
    disc_row = _one_row(tables["franchise_disclosure.csv"], brand, year, "정보공개서", warnings)
    if fin_row is None or disc_row is None:
        raise PipelineError("기준연도 자료가 불완전해 분석을 진행하지 못했습니다.", warnings)

    ratios = calc_financial_ratios(fin_row)
    termination_rate = calc_termination_rate(disc_row)
    signals = judge_risk_signals(ratios, termination_rate, RISK_THRESHOLDS)

    freshness = _freshness_warnings(
        year,
        year_summary["financial_latest"],
        year_summary["disclosure_latest"],
        _latest_year(_brand_rows(tables["audit_notes.csv"], brand)),
        _latest_year(_brand_rows(tables["disclosure_clauses.csv"], brand)),
    )

    review_flags: list[dict[str, Any]] = [
        {"issue": "기준연도 최신성 확인", "evidence": warning}
        for warning in freshness
    ]
    audit = _one_row(tables["audit_notes.csv"], brand, year, "감사보고서 주석", warnings)
    clauses = _one_row(tables["disclosure_clauses.csv"], brand, year, "계약 조항", warnings)
    if audit is None:
        review_flags.append({
            "issue": "감사보고서 주석 자료 누락",
            "evidence": f"{year}년 자료가 없어 특수관계자 거래 추출과 교차 확인을 수행하지 못했습니다.",
        })
    else:
        review_flags.extend(_safe_audit_review_flags(
            audit.get("note_text"), disc_row, extract_related_party_deals,
            cross_check_documents, call_llm,
        ))
    if clauses is None:
        review_flags.append({
            "issue": "정보공개서 계약 조항 자료 누락",
            "evidence": f"{year}년 자료가 없어 불리한 조항 추출을 수행하지 못했습니다.",
        })
    else:
        review_flags.extend(_safe_clause_review_flags(
            clauses.get("clause_text"), extract_unfavorable_clauses, call_llm,
        ))

    region_rows = _regional_rows(tables["region_sales.csv"], brand, year)
    avg_sales_info: dict[str, Any] | None = None
    payback_df: pd.DataFrame | None = None
    try:
        avg_sales_info = select_avg_sales(
            disc_row, region_rows, user_input["region"].strip()
        )
        payback_input = {
            key: user_input[key]
            for key in ("deposit", "key_money", "loan_amount", "loan_rate")
        }
        payback_disc = {
            **disc_row,
            "avg_annual_sales": avg_sales_info["value"],
        }
        payback_df = simulate_payback(
            payback_disc, payback_input, PAYBACK_SCENARIOS
        )
    except Exception:
        logger.exception("Payback calculation failed")
        review_flags.append({
            "issue": "투자 회수 기간 계산 확인 필요",
            "evidence": "입력값과 기준연도 매출 자료를 확인해 주세요.",
        })

    report = None
    try:
        report = write_report(signals, payback_df, review_flags, user_input["user_type"], call_llm)
    except Exception:
        logger.exception("Report generation failed")
    return {
        "user_input": dict(user_input), "year": year, "year_summary": year_summary,
        "fin_row": fin_row, "disc_row": disc_row, "ratios": ratios,
        "termination_rate": termination_rate, "signals": signals,
        "freshness": freshness, "review_flags": review_flags,
        "audit_text": audit.get("note_text") if audit is not None else None,
        "clause_text": clauses.get("clause_text") if clauses is not None else None,
        "avg_sales_info": avg_sales_info, "payback_df": payback_df, "report": report,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: run the workflow once and print a summary."""
    parser = argparse.ArgumentParser(description="프랜차이즈 재무 건강검진 파이프라인")
    parser.add_argument("--brand", help="브랜드명 (기본: 공통 브랜드 중 첫 번째)")
    parser.add_argument("--region", help="지역명 (기본: 첫 번째 지역)")
    parser.add_argument("--deposit", type=float, default=2000)
    parser.add_argument("--key-money", type=float, default=3000)
    parser.add_argument("--loan-amount", type=float, default=5000)
    parser.add_argument("--loan-rate", type=float, default=5.2)
    parser.add_argument("--user-type", choices=("예비", "기존"), default="예비")
    args = parser.parse_args(argv)

    try:
        tables = load_tables(str(PROJECT_ROOT))
        brands = common_brands(tables["hq_financials.csv"], tables["franchise_disclosure.csv"])
        regions = list_regions(tables["region_sales.csv"])
        if not brands or not regions:
            raise PipelineError("브랜드 또는 지역 자료가 없습니다.")
        result = run_checkup({
            "brand": args.brand or brands[0],
            "region": args.region or regions[0],
            "deposit": args.deposit,
            "key_money": args.key_money,
            "loan_amount": args.loan_amount,
            "loan_rate": args.loan_rate,
            "user_type": args.user_type,
        }, tables)
    except (PipelineError, FileNotFoundError, OSError, ValueError, ImportError) as error:
        print(f"[실패] {error}")
        return 1

    print(f"브랜드: {result['user_input']['brand']} / 기준연도: {result['year']}")
    print("\n[위험 신호]")
    for item in result["signals"]:
        print(f"- {item.get('item')}: {item.get('value')} ({item.get('level')})")
    print("\n[회수 기간]")
    print(result["payback_df"] if result["payback_df"] is not None else "계산 불가")
    print(f"\n[문서 검토] 확인 필요 {len(result['review_flags'])}건")
    report = result["report"] or {}
    print("\n[리포트]", report.get("summary", "생성 실패"))
    for item in report.get("checklist", []):
        print(f"  - {item}")
    for warning in result["warnings"]:
        print(f"[경고] {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())