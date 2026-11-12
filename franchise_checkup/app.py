"""Streamlit front end for the franchise financial health check."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

import pandas as pd
import streamlit as st
from franchise_checkup.data_loader import load_csv_table, select_avg_sales, validate_user_input
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


@st.cache_data(show_spinner=False, ttl=300)
def _load_tables(root: str) -> dict[str, pd.DataFrame]:
    project_root = Path(root).resolve()
    tables: dict[str, pd.DataFrame] = {}
    for name, columns in REQUIRED_COLUMNS.items():
        path = _find_csv(project_root, name)
        tables[name] = load_csv_table(str(path), columns)
    return tables


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


def _money_input_label(name: str) -> str:
    """Avoid assigning a currency unit until the source CSV units are known."""
    return f"{name} (화폐 단위 확인 필요)"


def _brand_rows(table: pd.DataFrame, brand: str) -> pd.DataFrame:
    return table.loc[table["brand"].astype(str).str.strip() == brand].copy()


def _one_row(table: pd.DataFrame, brand: str, year: int, label: str) -> dict[str, Any] | None:
    rows = _brand_rows(table, brand)
    rows = rows.loc[rows["year"].map(_year_value) == year]
    if rows.empty:
        st.warning(f"{label}: {year}년 자료가 없어 해당 분석은 확인 필요입니다.")
        return None
    if len(rows) > 1:
        st.warning(f"{label}: {year}년 자료가 여러 행입니다. 중복 자료로 분석을 중단합니다.")
        return None
    return rows.iloc[0].to_dict()


def _format_value(value: Any, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "확인 필요"
    if isinstance(value, (int, float)):
        return f"{value:,.1f}{suffix}"
    return f"{value}{suffix}"


def _common_brands(financial: pd.DataFrame, disclosure: pd.DataFrame) -> list[str]:
    financial_brands = set(financial["brand"].dropna().astype(str).str.strip())
    disclosure_brands = set(disclosure["brand"].dropna().astype(str).str.strip())
    return sorted(brand for brand in financial_brands & disclosure_brands if brand)


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


def _render_analysis(user_input: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    if _ANALYSIS_IMPORT_ERROR is not None:
        st.error(
            "분석 모듈을 현재 작업 브랜치에서 불러올 수 없습니다. "
            f"누락된 모듈 또는 의존성을 확인해 주세요: {_ANALYSIS_IMPORT_ERROR}"
        )
        return

    brand = user_input["brand"]
    financial = _brand_rows(tables["hq_financials.csv"], brand)
    disclosure = _brand_rows(tables["franchise_disclosure.csv"], brand)
    if financial.empty or disclosure.empty:
        st.error("선택한 브랜드의 본사 재무 또는 정보공개서 자료가 없습니다.")
        return

    year_summary = _common_year_summary(financial, disclosure)
    year = year_summary["selected"]
    if year is None:
        st.error("선택한 브랜드의 재무 자료와 정보공개서에서 일치하는 기준연도를 찾지 못했습니다.")
        return
    audit_latest = _latest_year(_brand_rows(tables["audit_notes.csv"], brand))
    clauses_latest = _latest_year(_brand_rows(tables["disclosure_clauses.csv"], brand))
    freshness = _freshness_warnings(
        year,
        year_summary["financial_latest"],
        year_summary["disclosure_latest"],
        audit_latest,
        clauses_latest,
    )
    for warning in freshness:
        st.warning(warning)
    st.subheader(f"분석 기준: {brand} · {year}년")

    fin_row = _one_row(tables["hq_financials.csv"], brand, year, "본사 재무")
    disc_row = _one_row(tables["franchise_disclosure.csv"], brand, year, "정보공개서")
    if fin_row is None or disc_row is None:
        return

    # Financial and termination signals are independent of LLM extraction.
    ratios = calc_financial_ratios(fin_row)
    termination_rate = calc_termination_rate(disc_row)
    signals = judge_risk_signals(ratios, termination_rate, RISK_THRESHOLDS)

    st.header("① 본사 재무·계약 신호")
    signal_rows = []
    for item in signals:
        suffix = "%" if item["item"] in {"부채비율", "영업이익률", "계약 해지율"} else ""
        signal_rows.append({
            "항목": item.get("item", "확인 필요"),
            "위험 수준": item.get("level", "확인 필요"),
            "값": _format_value(item.get("value"), suffix),
            "판정 근거": item.get("reason", "판정 근거가 없습니다."),
        })
    st.dataframe(pd.DataFrame(signal_rows), use_container_width=True, hide_index=True)

    review_flags: list[dict[str, Any]] = []
    review_flags.extend(
        {"issue": "기준연도 최신성 확인", "evidence": warning}
        for warning in freshness
    )
    audit = _one_row(tables["audit_notes.csv"], brand, year, "감사보고서 주석")
    clauses = _one_row(tables["disclosure_clauses.csv"], brand, year, "계약 조항")
    if audit is None:
        review_flags.append({"issue": "감사보고서 주석 자료 누락", "evidence": f"{year}년 자료가 없어 특수관계자 거래 추출과 교차 점검을 수행하지 못했습니다."})
    if audit is not None:
        review_flags.extend(_safe_audit_review_flags(
            audit.get("note_text"), disc_row, extract_related_party_deals,
            cross_check_documents, llm_call,
        ))

    if clauses is None:
        review_flags.append({"issue": "정보공개서 계약 조항 자료 누락", "evidence": f"{year}년 자료가 없어 불리한 조항 추출을 수행하지 못했습니다."})
    if clauses is not None:
        review_flags.extend(_safe_clause_review_flags(
            clauses.get("clause_text"), extract_unfavorable_clauses, llm_call
        ))

    st.header("② 원금 회수 기간")
    region_rows = _regional_rows(tables["region_sales.csv"], brand, year)
    avg_sales_info: dict[str, Any] | None = None
    payback_df: pd.DataFrame | None = None
    try:
        avg_sales_info = select_avg_sales(disc_row, region_rows, user_input["region"].strip())
        payback_input = {key: user_input[key] for key in ("deposit", "key_money", "loan_amount", "loan_rate")}
        payback_disc = {**disc_row, "avg_annual_sales": avg_sales_info["value"]}
        payback_df = simulate_payback(payback_disc, payback_input, PAYBACK_SCENARIOS)
    except Exception:
        logger.exception("Payback calculation failed")
        review_flags.append({"issue": "투자 회수 기간 계산 불가", "evidence": "입력 및 매출 자료를 확인해 주세요."})
        st.warning("투자 회수 기간을 계산할 수 없습니다. 입력 및 매출 자료를 확인해 주세요.")

    if avg_sales_info is not None:
        basis = avg_sales_info.get("basis", "확인 필요")
        basis_label = "전국" if basis == "전국" else f"{basis} 지역"
        st.caption(f"회수 기간 가정 · 평균매출 기준: {basis_label} · 기준연도: {year}년")
        assumption_rows = [
            {"시나리오": name, "매출 계수": values["sales_factor"], "순이익률": f"{values['margin']:.0%}"}
            for name, values in PAYBACK_SCENARIOS.items()
        ]
        st.dataframe(pd.DataFrame(assumption_rows), use_container_width=True, hide_index=True)
    if payback_df is not None:
        display_df = payback_df.copy()
        display_df["payback_months"] = display_df["payback_months"].map(
            lambda value: "회수 불가" if pd.isna(value) else f"{value:,.1f}개월"
        )
        display_df["monthly_net_profit"] = payback_df["monthly_net_profit"].map(lambda value: f"{value:,.1f}")
        display_df["uncertain"] = payback_df["uncertain"].map(lambda value: "불확실" if value else "아니오")
        display_df = display_df.rename(columns={
            "scenario": "시나리오", "monthly_net_profit": "월 순이익 (화폐 단위 미확인)", "payback_months": "예상 회수 기간", "uncertain": "불확실 여부",
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        chart_df = payback_df.loc[payback_df["payback_months"].notna(), ["scenario", "payback_months"]].set_index("scenario")
        if not chart_df.empty:
            st.bar_chart(chart_df)
        else:
            st.info("양수 월 순이익이 없어 회수 기간 차트를 표시할 수 없습니다.")
        for row in payback_df.to_dict(orient="records"):
            if row.get("uncertain"):
                period = "회수 불가" if pd.isna(row.get("payback_months")) else f"{row['payback_months']:,.1f}개월"
                st.warning(f"{row['scenario']}: 월 순이익 {row['monthly_net_profit']:,.1f} (화폐 단위 미확인), 회수 기간 {period} — 60개월 초과 또는 회수 불가로 불확실합니다.")

    st.header("③ 확인 필요 목록")
    if not review_flags:
        st.info("추가 확인 항목이 수집되지 않았습니다. 일부 자료가 누락되었거나 추출 결과가 없을 수 있으므로 문서 원문을 별도로 확인하세요.")
    for flag in review_flags:
        with st.container(border=True):
            st.markdown(f"**확인할 사항:** {flag.get('issue', '확인 필요')}")
            st.markdown(f"**근거:** {flag.get('evidence', '자료 또는 근거가 없습니다.')}")
            if flag.get("quote"):
                st.markdown(f"> **원문 인용:** {flag['quote']}")

    st.header("④ 비전문가용 리포트")
    st.caption(f"이 보고서는 {year}년 자료를 기준으로 작성되었습니다.")
    try:
        report = write_report(signals, payback_df, review_flags, user_input["user_type"], llm_call)
        st.write(report.get("summary", "보고서 요약을 제공할 수 없습니다."))
        st.markdown("**추가 확인 체크리스트**")
        for item in report.get("checklist", []):
            st.markdown(f"- {item}")
    except Exception:
        logger.exception("Report generation failed")
        st.warning("보고서 생성에 실패했습니다. 위 파이썬 분석 결과를 확인해 주세요.")

    st.info("본 서비스는 정보 제공 목적이며, 법률·투자 자문이 아닙니다.")


def main() -> None:
    st.set_page_config(page_title="프랜차이즈 본사 재무 건강검진", layout="wide")
    st.title("프랜차이즈 본사 재무 건강검진")
    st.caption("공개 자료 기반의 참고 정보입니다. 분석 결과는 선택한 기준연도에 따라 달라질 수 있습니다.")
    try:
        tables = _load_tables(str(PROJECT_ROOT))
    except (FileNotFoundError, OSError, ValueError, ImportError) as error:
        st.error(f"데이터 파일을 읽을 수 없습니다: {error}")
        st.info("5개 CSV를 프로젝트 루트 또는 data/ 폴더에 두고, 표준 열 이름과 UTF-8/CP949 인코딩을 확인하세요.")
        st.info("필수 CSV: " + ", ".join(CSV_NAMES))
        return

    brands = _common_brands(tables["hq_financials.csv"], tables["franchise_disclosure.csv"])
    region_table = tables["region_sales.csv"]
    regions = sorted(set(value.strip() for value in region_table["region"].dropna().astype(str) if value.strip()))
    if not brands or not regions:
        st.error("브랜드 또는 시도 목록을 만들 수 없습니다. CSV 자료를 확인하세요.")
        return

    with st.form("health_check_form"):
        st.warning(
            "프로젝트 설계 문서와 회수 계산 테스트에는 원·만원 등 화폐 단위가 명시되어 있지 않고, "
            "현재 저장소에도 실제 CSV가 없습니다. 금액 단위를 확인할 때까지 변환하지 않으며, "
            "아래 입력 금액과 CSV 금액이 같은 단위인지 먼저 확인해 주세요."
        )
        col1, col2 = st.columns(2)
        brand = col1.selectbox("브랜드", brands)
        region = col2.selectbox("지역(시도)", regions)
        col3, col4, col5 = st.columns(3)
        deposit = col3.number_input(_money_input_label("보증금"), min_value=0.0, step=100.0)
        key_money = col4.number_input(_money_input_label("권리금"), min_value=0.0, step=100.0)
        loan_amount = col5.number_input(_money_input_label("대출금"), min_value=0.0, step=100.0)
        loan_rate = st.number_input("대출 금리(연 %)", min_value=0.0, max_value=100.0, step=0.1)
        user_type = st.radio("사용자 유형", ["예비", "기존"], horizontal=True)
        submitted = st.form_submit_button("분석 실행", type="primary")

    if submitted:
        try:
            validated = validate_user_input({
                "brand": brand,
                "region": region,
                "deposit": deposit,
                "key_money": key_money,
                "loan_amount": loan_amount,
                "loan_rate": loan_rate,
                "user_type": user_type,
            })
        except (ValueError, ImportError) as error:
            st.error(f"입력값을 확인해 주세요: {error}")
            return
        _render_analysis(validated, tables)


if __name__ == "__main__":
    main()
