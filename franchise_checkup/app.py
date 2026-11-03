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


def _render_signal_cards(signals: list[dict[str, Any]]) -> None:
    st.subheader("03 · 본사 재무·계약 신호")
    st.caption("각 신호는 기존 재무비율 및 위험 판정 결과를 그대로 표시합니다.")
    columns = st.columns(2)
    for index, item in enumerate(signals):
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.markdown(f"**{item.get('item', '지표')}**")
                level = str(item.get("level", "확인 필요"))
                value = item.get("value")
                suffix = "%" if item.get("item") in {"부채비율", "영업이익률", "계약 해지율"} else ""
                st.metric("실제 계산값", _format_value(value, suffix))
                if level == "정상":
                    st.success(f"위험 수준 · {level}")
                elif level == "주의":
                    st.warning(f"위험 수준 · {level}")
                elif level == "위험":
                    st.error(f"위험 수준 · {level}")
                else:
                    st.info(f"위험 수준 · {level}")
                st.caption("판정 근거")
                st.write(item.get("reason") or "제공된 판정 근거가 없습니다.")


def _review_category(flag: dict[str, Any]) -> str:
    issue = str(flag.get("issue", ""))
    if "특수관계자" in issue or "관계자 거래" in issue:
        return "특수관계자 거래"
    if "조항" in issue:
        return "계약 조항"
    if "불일치" in issue or "다릅" in issue or "일치하지" in issue:
        return "문서 불일치"
    if "누락" in issue or "자료" in issue or "문서" in issue:
        return "자료 누락"
    if "추출" in issue or "실패" in issue or "계산" in issue:
        return "추출·계산 확인"
    return "기준연도·기타 확인"


def _render_review_flags(flags: list[dict[str, Any]]) -> None:
    st.subheader("05 · 확인 필요 목록")
    if not flags:
        st.info(
            "확인 필요 항목이 수집되지 않았습니다. 이는 안전 판정이 아닙니다. "
            "자료 누락이나 추출 결과가 없는 경우에도 목록이 비어 있을 수 있으니 원문과 자료 범위를 확인하세요."
        )
        return

    groups: dict[str, list[dict[str, Any]]] = {}
    for flag in flags:
        groups.setdefault(_review_category(flag), []).append(flag)
    for category, items in groups.items():
        st.markdown(f"**{category} · {len(items)}건**")
        for index, flag in enumerate(items, start=1):
            title = str(flag.get("issue") or "확인할 사항")
            with st.expander(f"{index}. {title}", expanded=False):
                st.markdown("**근거**")
                st.write(flag.get("evidence") or "제공된 근거가 없습니다.")
                if flag.get("quote"):
                    st.markdown("**원문 인용**")
                    st.write(flag["quote"])


def _render_payback_section(
    payback_df: pd.DataFrame | None,
    avg_sales_info: dict[str, Any] | None,
    year: int,
) -> None:
    st.subheader("04 · 원금 회수 기간")
    if payback_df is None:
        st.warning(
            "회수 기간을 계산하지 못했습니다. 이 영역의 계산에만 영향을 주며 "
            "위의 재무·계약 신호와 문서 검토 결과는 계속 확인할 수 있습니다."
        )
        return

    columns = st.columns(max(1, min(3, len(payback_df))))
    for index, row in enumerate(payback_df.to_dict(orient="records")):
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.markdown(f"**{row.get('scenario', '시나리오')} 시나리오**")
                profit = row.get("monthly_net_profit")
                st.metric("월 순이익 (만원)", _format_value(profit))
                months = row.get("payback_months")
                if months is None or pd.isna(months):
                    st.metric("예상 회수 기간", "산출 불가")
                    st.warning("불확실 · 월 순이익이 0 이하이므로 회수 기간을 계산할 수 없습니다.")
                else:
                    st.metric("예상 회수 기간", f"{months:,.1f}개월")
                    if bool(row.get("uncertain")):
                        st.warning("불확실 · 60개월을 초과해 장기 가정에 크게 의존합니다.")
                    else:
                        st.success("불확실 여부 · 아니요")
    chart_df = payback_df.loc[
        payback_df["payback_months"].notna(), ["scenario", "payback_months"]
    ].set_index("scenario")
    if chart_df.empty:
        st.info("회수 기간이 계산된 시나리오가 없어 차트에서 표시할 값이 없습니다.")
    else:
        st.markdown("**회수 기간 비교**")
        st.bar_chart(
            chart_df, x_label="시나리오", y_label="회수 기간 (개월)", height=260
        )

    if avg_sales_info is not None:
        basis = str(avg_sales_info.get("basis", "확인 필요"))
        basis_label = "전국 평균" if basis == "전국" else f"{basis} 지역"
        with st.expander("산출 가정 및 기준 매출", expanded=False):
            st.caption(
                f"평균매출 기준: {basis_label} · 기준연도: {year}년 · "
                "시연 CSV 금액 단위: 만원"
            )
            assumption_rows = [
                {
                    "시나리오": name,
                    "매출 계수": values["sales_factor"],
                    "순이익률": f"{values['margin']:.0%}",
                }
                for name, values in PAYBACK_SCENARIOS.items()
            ]
            st.dataframe(
                pd.DataFrame(assumption_rows),
                use_container_width=True,
                hide_index=True,
            )


def _render_report(
    signals: list[dict[str, Any]],
    payback_df: pd.DataFrame | None,
    review_flags: list[dict[str, Any]],
    user_type: str,
    year: int,
) -> None:
    st.subheader("06 · 비전문가용 리포트")
    st.caption(f"보고서 기준연도: {year}년")
    try:
        report = write_report(signals, payback_df, review_flags, user_type, llm_call)
        with st.container(border=True):
            st.markdown("**요약**")
            st.write(report.get("summary", "보고서 요약을 표시할 수 없습니다."))
        st.markdown("**추가 확인 체크리스트**")
        checklist = report.get("checklist", [])
        if checklist:
            for item in checklist:
                st.markdown(f"- {item}")
        else:
            st.info("추가 확인 체크리스트가 생성되지 않았습니다.")
    except Exception:
        logger.exception("Report generation failed")
        st.warning(
            "비전문가용 리포트 생성에 실패했습니다. 기존 Python 분석 결과와 "
            "확인 필요 목록은 계속 확인할 수 있습니다."
        )


def _render_analysis(user_input: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    if _ANALYSIS_IMPORT_ERROR is not None:
        st.error(
            "분석 모듈을 불러오지 못했습니다. 누락된 모듈 또는 의존성을 확인해 주세요: "
            f"{_ANALYSIS_IMPORT_ERROR}"
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
        st.error("본사 재무와 정보공개서에서 일치하는 기준연도를 찾지 못했습니다.")
        return

    fin_row = _one_row(tables["hq_financials.csv"], brand, year, "본사 재무")
    disc_row = _one_row(tables["franchise_disclosure.csv"], brand, year, "정보공개서")
    if fin_row is None or disc_row is None:
        st.warning("기준연도 자료가 불완전해 분석을 진행하지 못했습니다.")
        return

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
    audit = _one_row(tables["audit_notes.csv"], brand, year, "감사보고서 주석")
    clauses = _one_row(tables["disclosure_clauses.csv"], brand, year, "계약 조항")
    if audit is None:
        review_flags.append({
            "issue": "감사보고서 주석 자료 누락",
            "evidence": f"{year}년 자료가 없어 특수관계자 거래 추출과 교차 확인을 수행하지 못했습니다.",
        })
    else:
        review_flags.extend(_safe_audit_review_flags(
            audit.get("note_text"), disc_row, extract_related_party_deals,
            cross_check_documents, llm_call,
        ))
    if clauses is None:
        review_flags.append({
            "issue": "정보공개서 계약 조항 자료 누락",
            "evidence": f"{year}년 자료가 없어 불리한 조항 추출을 수행하지 못했습니다.",
        })
    else:
        review_flags.extend(_safe_clause_review_flags(
            clauses.get("clause_text"), extract_unfavorable_clauses, llm_call,
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
    except Exception as error:
        logger.exception("Payback calculation failed")
        review_flags.append({
            "issue": "투자 회수 기간 계산 확인 필요",
            "evidence": "입력값과 기준연도 매출 자료를 확인해 주세요.",
        })

    basis = avg_sales_info.get("basis", "확인 필요") if avg_sales_info else "확인 필요"
    basis_label = "전국 평균" if basis == "전국" else f"{basis} 기준"
    st.subheader("01 · 검진 대상 요약")
    summary_values = [
        ("브랜드", brand),
        ("지역", user_input["region"]),
        ("분석 기준연도", f"{year}년"),
        ("평균매출 기준", basis_label),
        ("사용자 유형", user_input["user_type"]),
    ]
    for offset, count in ((0, 3), (3, 2)):
        columns = st.columns(count)
        for column, (label, value) in zip(columns, summary_values[offset:offset + count]):
            with column:
                with st.container(border=True):
                    st.caption(label)
                    st.write(value)

    st.subheader("02 · 자료 최신성 및 분석 기준")
    if freshness:
        with st.container(border=True):
            for warning in freshness:
                st.warning(warning)
    else:
        st.caption(
            f"{year}년을 본사 재무와 정보공개서의 공통 기준연도로 사용했습니다. "
            f"평균매출 기준은 {basis_label}입니다."
        )

    st.divider()
    _render_signal_cards(signals)

    st.divider()
    _render_payback_section(payback_df, avg_sales_info, year)

    st.divider()
    _render_review_flags(review_flags)

    st.divider()
    _render_report(
        signals, payback_df, review_flags, user_input["user_type"], year
    )
    st.caption("본 서비스는 정보 제공 목적이며, 법률·투자 자문이 아닙니다.")


def _render_header() -> None:
    st.title("프랜차이즈 본사 재무 건강검진")
    st.markdown(
        "공개 자료 기반으로 본사 재무·계약 위험과 예상 투자 회수 기간을 점검합니다."
    )
    st.caption(
        "이 화면은 제출된 자료와 기존 분석 규칙에 따른 참고 정보입니다. "
        "자료의 범위와 기준연도에 따라 결과가 달라질 수 있으며, 원문 자료를 함께 확인해 주세요."
    )


def _render_input_form(brands: list[str], regions: list[str]) -> dict[str, Any] | None:
    with st.sidebar:
        st.header("검진 조건 설정")
        st.caption("브랜드와 지역, 투자 조건을 선택하세요.")
        with st.form("health_check_form"):
            st.markdown("**검진 대상**")
            brand = st.selectbox("브랜드", brands)
            region = st.selectbox("지역 (시도)", regions)

            st.markdown("**투자 조건**")
            st.caption(
                "금액 단위: 만원 (현재 시연 CSV 기준). 실제 자료로 교체할 때는 "
                "원자료 단위를 확인하고 같은 단위로 입력하세요."
            )
            deposit = st.number_input(
                "보증금", min_value=0.0, step=100.0, format="%.0f"
            )
            key_money = st.number_input(
                "권리금", min_value=0.0, step=100.0, format="%.0f"
            )
            loan_amount = st.number_input(
                "대출금", min_value=0.0, step=100.0, format="%.0f"
            )
            loan_rate = st.number_input(
                "대출 금리 (연 %)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.1f",
            )

            st.markdown("**사용자 유형**")
            user_type = st.radio("사용자 유형", ["예비", "기존"], horizontal=True)
            submitted = st.form_submit_button(
                "분석 실행", type="primary", use_container_width=True
            )

        if not submitted:
            return None
        try:
            return validate_user_input({
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
            return {}


def main() -> None:
    st.set_page_config(
        page_title="프랜차이즈 본사 재무 건강검진",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    st.html(
        """
        <style>
        /* =========================================
           1. 전체 페이지 기본 설정
        ========================================= */

        :root {
            color-scheme: light;
        }

        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background-color: #FFFFFF !important;
            color: #24324A !important;
        }

        /* =========================================
           2. 상단 헤더 및 툴바
        ========================================= */

        header[data-testid="stHeader"],
        [data-testid="stHeader"],
        .stAppHeader {
            background-color: #FFFFFF !important;
            border-bottom: 1px solid #E8ECF2 !important;
            box-shadow: none !important;
        }

        [data-testid="stToolbar"] {
            background-color: transparent !important;
        }

        [data-testid="stDecoration"] {
            background-color: #D95D59 !important;
        }

        /* =========================================
            3. 메인 콘텐츠 영역
        ========================================= */

        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            width: 100%;
            max-width: 1120px;
            margin-left: auto;
            margin-right: auto;
            box-sizing: border-box;

            /* 상단 헤더와 제목이 겹치지 않도록 여백 확보 */
            padding-top: 4rem;
            padding-bottom: 3rem;
            padding-left: 2rem;
            padding-right: 2rem;
        }

        /* =========================================
           4. 사이드바
        ========================================= */

        [data-testid="stSidebar"] {
            background-color: #F8FAFC !important;
            border-right: 1px solid #E2E8F0 !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            background-color: #F8FAFC !important;
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        @media (min-width: 769px) {
            section[data-testid="stSidebar"] {
                width: 310px !important;
                min-width: 310px !important;
                max-width: 310px !important;
            }
        }

        /* =========================================
           5. 제목 및 본문
        ========================================= */

        .stApp h1 {
            color: #172B4D !important;
            font-size: 1.85rem;
            font-weight: 750;
            line-height: 1.35;
            margin-top: 0;
            margin-bottom: 0.5rem;
        }

        .stApp h2 {
            color: #172B4D !important;
            font-size: 1.5rem;
            font-weight: 700;
            margin-top: 1.8rem;
            margin-bottom: 0.8rem;
        }

        .stApp h3 {
            color: #24324A !important;
            font-size: 1.05rem;
            font-weight: 650;
        }

        .stApp p,
        .stApp label,
        .stApp [data-testid="stCaptionContainer"] {
            color: #475569 !important;
            line-height: 1.65;
        }

        /* =========================================
           6. 입력 위젯
        ========================================= */

        .stApp input,
        .stApp textarea,
        .stApp [data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            color: #24324A !important;
            border-color: #CBD5E1 !important;
        }

        [data-testid="stNumberInput"] button {
            background-color: #F1F5F9 !important;
            color: #334155 !important;
            border-color: #CBD5E1 !important;
        }

        [data-testid="stNumberInput"] button:hover {
            background-color: #E2E8F0 !important;
        }

        /* =========================================
           7. 카드 및 컨테이너
        ========================================= */

        .main [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;                
            border-radius: 0.75rem !important;

            /* 카드 내부 여백 */
            padding: 1rem !important;
                                            
            /* 카드 아래쪽 간격 */
            margin-bottom: 0.8rem !important;

            box-shadow: none !important;
        }

        .main [data-testid="stHorizontalBlock"] {
            gap: 1.1rem !important;
        }

        .main [data-testid="stVerticalBlock"] {
            gap: 0.8rem !important;
        }

        .main [data-testid="stAlert"] {
            margin-top: 0.5rem !important;                    
            margin-bottom: 0.7rem !important;
            border-radius: 0.65rem !important;
        }

        /* =========================================
           8. 데이터프레임 및 표
        ========================================= */

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background-color: #FFFFFF !important;
            color: #24324A !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 0.65rem !important;
            overflow: hidden;
        }

        /* =========================================
           9. 차트 영역
            차트 내부 색상은 config.toml 테마를 따름
        ========================================= */

        [data-testid="stVegaLiteChart"],
        [data-testid="stArrowVegaLiteChart"],
        [data-testid="stPlotlyChart"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 0.75rem !important;
            padding: 0.5rem;
        }

        /* =========================================
           10. 구분선 및 안내 문구
        ========================================= */

        .stApp hr {
            border-color: #E8ECF2 !important;
            margin-top: 1rem;
            margin-bottom: 1rem;
        }

        [data-testid="stAlert"] {
            border-radius: 0.65rem !important;
        }

        [data-testid="stCaptionContainer"] {
            font-size: 0.83rem;
        }

        /* =========================================
           11. 버튼
        ========================================= */

        .stApp button[kind="primary"] {
            border-radius: 0.55rem !important;
            font-weight: 650 !important;
            min-height: 2.7rem;
        }

        /* =========================================
           12. 반응형 레이아웃
        ========================================= */

        @media (max-width: 768px) {
            .main .block-container,
            [data-testid="stMainBlockContainer"] {
                max-width: 100%;
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 3rem;
                padding-bottom: 2rem;
            }

            .stApp h1 {
                font-size: 1.5rem;
            }

            .stApp h2 {
                font-size: 1.15rem;
            }
        }
        </style>
        """
    )

    _render_header()

    try:
        tables = _load_tables(str(PROJECT_ROOT))
    except (FileNotFoundError, OSError, ValueError, ImportError) as error:
        st.error(f"데이터를 불러올 수 없습니다: {error}")
        with st.container(border=True):
            st.markdown("**데이터 확인 사항**")
            st.write("필수 CSV를 프로젝트 루트의 data/에 두고, 열 이름과 UTF-8/CP949 인코딩을 확인하세요.")
            st.caption("필수 파일: " + ", ".join(CSV_NAMES))
        return

    brands = _common_brands(
        tables["hq_financials.csv"], tables["franchise_disclosure.csv"]
    )
    regions = sorted({
        value.strip()
        for value in tables["region_sales.csv"]["region"].dropna().astype(str)
        if value.strip()
    })
    if not brands or not regions:
        st.error("브랜드 또는 지역 선택 자료가 없습니다. CSV 내용을 확인하세요.")
        return

    selected = _render_input_form(brands, regions)
    if selected is None:
        st.subheader("분석을 시작하려면")
        st.write(
            "왼쪽 **검진 조건 설정**에서 브랜드와 지역을 고르고 투자 금액을 입력한 뒤 "
            "**분석 실행**을 선택하세요. 결과는 기준연도별 자료와 세 가지 회수 가정으로 표시됩니다."
        )
        return
    if not selected:
        return
    _render_analysis(selected, tables)


if __name__ == "__main__":
    main()
