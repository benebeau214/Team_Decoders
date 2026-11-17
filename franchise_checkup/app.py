from __future__ import annotations

import hashlib
import html
import math
from typing import Any

import pandas as pd
import streamlit as st
from franchise_checkup.data_loader import validate_user_input
from franchise_checkup.pipeline import (
    CSV_NAMES,
    PAYBACK_SCENARIOS,
    PROJECT_ROOT,
    PipelineError,
    common_brands,
    list_regions,
    load_tables,
    run_checkup,
)


@st.cache_data(show_spinner=False, ttl=300)
def _load_tables(root: str) -> dict[str, pd.DataFrame]:
    return load_tables(root)


def _format_value(value: Any, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "확인 필요"
    if isinstance(value, (int, float)):
        return f"{value:,.1f}{suffix}"
    return f"{value}{suffix}"



_TONE_BY_LEVEL = {"정상": "ok", "주의": "warn", "위험": "danger"}
_SCENARIO_TONES = (("보수", "warn"), ("평균", "primary"), ("낙관", "ok"))
_PERCENT_ITEMS = {"부채비율", "영업이익률", "계약 해지율"}
_USER_TYPE_LABELS = {"예비": "예비 가맹점주", "기존": "기존 가맹점주"}
PAYBACK_LIMIT_MONTHS = 60  # same threshold the existing UI used for "불확실 · 60개월 초과"

_APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
:root{color-scheme:light;--fc-primary:#004ac6;--fc-pc:#2563eb;--fc-text:#191c1e;--fc-var:#434655;--fc-line:#e2e8f0;--fc-low:#f2f4f6;--fc-cont:#eceef0;--fc-err:#ba1a1a;--fc-ter:#006329;--fc-sec:#dae2fd}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#f8fafc;color:var(--fc-text)}
.stApp,.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp button,.stApp input,.stApp textarea,.stApp span:not(.material-symbols-outlined):not([data-testid="stIconMaterial"]){font-family:'Inter','Pretendard','Noto Sans KR',-apple-system,'Segoe UI',sans-serif}
[data-testid="stHeader"]{background:rgba(248,250,252,.85);backdrop-filter:blur(12px)}
.main .block-container,[data-testid="stMainBlockContainer"]{max-width:1160px;padding:5.5rem 2.5rem 4rem}
.stApp h2,.stApp h3{color:var(--fc-text);letter-spacing:-.01em}
.material-symbols-outlined{font-family:'Material Symbols Outlined'!important;font-weight:400;font-style:normal;line-height:1;letter-spacing:normal;text-transform:none;display:inline-block;white-space:nowrap;direction:ltr;vertical-align:middle;-webkit-font-feature-settings:'liga';font-feature-settings:'liga';-webkit-font-smoothing:antialiased}

/* sidebar */
[data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child{background:#fff;border-right:1px solid var(--fc-line)}
@media (min-width:769px){section[data-testid="stSidebar"]{min-width:290px;max-width:310px}}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{padding-bottom:0}
[data-testid="stSidebar"] h2{font-size:1.125rem;font-weight:600;margin:0}
[data-testid="stForm"]{border:none;padding:0}
[data-testid="stSidebar"] [data-baseweb="select"]>div,[data-testid="stSidebar"] [data-baseweb="input"],[data-testid="stSidebar"] [data-baseweb="base-input"]{border-radius:.5rem;border-color:#cbd5e1;background:#fff}
[data-testid="stSidebar"] [data-testid="stNumberInput"] input{text-align:right;font-size:.8125rem}
[data-testid="stSidebar"] label p{font-size:.6875rem;font-weight:600;color:var(--fc-var)}
[data-testid="stSidebar"] [data-testid="stRadio"] label p{font-size:.8125rem;font-weight:500;color:var(--fc-text)}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:var(--fc-pc);border-color:var(--fc-pc);border-radius:.5rem;min-height:42px;font-weight:600}
button[kind="primary"]:hover,button[kind="primaryFormSubmit"]:hover{background:var(--fc-primary);border-color:var(--fc-primary)}
.fc-brand{display:flex;align-items:center;gap:.5rem;padding-bottom:1rem;margin-bottom:.75rem;border-bottom:1px solid var(--fc-line)}
.fc-brand-ico{width:36px;height:36px;border-radius:.5rem;background:var(--fc-pc);color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fc-brand-t{font-size:1rem;font-weight:600;line-height:1.3;color:var(--fc-text)}
.fc-brand-s{font-size:.6875rem;color:var(--fc-var);margin-top:2px}
.fc-side-sec{display:flex;align-items:center;gap:.25rem;font-size:.75rem;font-weight:600;color:var(--fc-text);margin:.25rem 0 .25rem}
.fc-side-sec .material-symbols-outlined{color:var(--fc-primary)}

/* hero */
.fc-eyebrow{display:flex;align-items:center;gap:.4rem;color:var(--fc-pc);font-size:.6875rem;font-weight:600;letter-spacing:.08em}
.fc-eyebrow i{width:8px;height:8px;border-radius:50%;background:var(--fc-pc);display:inline-block}
.fc-title{font-size:2.25rem;line-height:1.2;font-weight:700;letter-spacing:-.02em;color:var(--fc-text);margin:.5rem 0 .25rem;padding:0}
.fc-desc{font-size:.875rem;color:var(--fc-var);margin:.25rem 0 0}
.fc-caption{font-size:.75rem;color:#64748b;margin:.35rem 0 0}
.fc-meta{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;margin-top:1rem;padding:.65rem 1rem;background:rgba(242,244,246,.6);border:1px solid var(--fc-line);border-radius:.5rem}
.fc-meta-item{display:flex;align-items:center;gap:.5rem}
.fc-meta-item+.fc-meta-item{border-left:1px solid #cbd5e1;padding-left:1.5rem}
.fc-meta-item b{font-size:.75rem;font-weight:600;color:var(--fc-text)}
.fc-label{font-size:.6875rem;font-weight:600;color:var(--fc-var)}

/* notice */
.fc-notice{display:flex;align-items:flex-start;gap:.75rem;margin:1.25rem 0 1.5rem;padding:.875rem;border:1px solid rgba(203,213,225,.5);background:rgba(218,226,253,.4);border-radius:.75rem;font-size:.8125rem;line-height:1.5;color:var(--fc-text)}
.fc-notice-ico{width:28px;height:28px;border-radius:.5rem;background:var(--fc-pc);color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.fc-notice-ok{background:rgba(220,252,231,.6);border-color:rgba(22,163,74,.25)}
.fc-notice-ok .fc-notice-ico{background:#16a34a}
.fc-notice p{margin:0 0 .25rem}.fc-notice p:last-child{margin:0}

/* section heads + cards */
.fc-sec-head{display:flex;align-items:center;justify-content:space-between;gap:.75rem;margin:0 0 .75rem}
.fc-sec-head .l{display:flex;align-items:center;gap:.5rem}
.fc-tag{font-size:.6875rem;font-weight:600;background:var(--fc-cont);color:var(--fc-var);padding:2px 8px;border-radius:.5rem}
.fc-h{font-size:1.125rem;font-weight:700;letter-spacing:-.01em;color:var(--fc-text);margin:0}
.fc-small{font-size:.6875rem;color:var(--fc-var)}
.fc-card{background:#fff;border:1px solid var(--fc-line);border-radius:.75rem;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.fc-sumcard{overflow:hidden;margin-bottom:2rem}
.fc-sigs{padding:1rem;border-bottom:1px solid var(--fc-line);background:rgba(242,244,246,.3)}
.fc-sigs-top{display:flex;justify-content:space-between;margin-bottom:.75rem}
.fc-sigs-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}
.fc-sig{padding-right:.75rem;border-right:1px solid rgba(226,232,240,.8)}
.fc-sig:last-child{border-right:none}
.fc-sig-top{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.4rem}
.fc-metric{font-size:1.75rem;line-height:1.2;font-weight:700;letter-spacing:-.02em;color:var(--fc-text)}
.fc-metric-xl{font-size:2.25rem}
.fc-sig-note{font-size:.75rem;line-height:1.45;margin:.4rem 0 0;color:var(--fc-var);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.fc-t-danger{color:var(--fc-err)}.fc-t-warn{color:#d97706}.fc-t-ok{color:#16a34a}.fc-t-primary{color:var(--fc-pc)}.fc-t-muted{color:#64748b}

/* badges */
.fc-badge{display:inline-flex;align-items:center;gap:.3rem;padding:2px 8px;border-radius:999px;font-size:.6875rem;font-weight:600;white-space:nowrap}
.fc-badge i{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.fc-badge.fc-ok{background:#dcfce7;color:#16a34a}.fc-badge.fc-warn{background:#fef3c7;color:#d97706}
.fc-badge.fc-danger{background:#fee2e2;color:#dc2626}.fc-badge.fc-muted{background:#f1f5f9;color:#64748b}.fc-badge.fc-primary{background:var(--fc-sec);color:var(--fc-primary)}

/* payback strip */
.fc-pb{display:flex;flex-wrap:wrap;align-items:center;gap:1rem;padding:1rem}
.fc-pb-title{display:flex;align-items:center;gap:.5rem;flex-shrink:0}
.fc-pb-ico{width:28px;height:28px;border-radius:.5rem;background:var(--fc-cont);display:flex;align-items:center;justify-content:center;color:var(--fc-primary)}
.fc-pb-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.75rem;flex:1}
.fc-scn{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.65rem;border-radius:.5rem;border:1px solid var(--fc-line)}
.fc-scn-danger{border-color:rgba(186,26,26,.3);background:rgba(255,218,214,.2)}.fc-scn-warn{border-color:rgba(217,119,6,.3);background:rgba(254,243,199,.35)}
.fc-scn-primary{border-color:rgba(37,99,235,.3);background:rgba(218,226,253,.2)}.fc-scn-ok{border-color:rgba(0,99,41,.3);background:rgba(0,127,54,.06)}
.fc-scn-muted{background:#f8fafc}
.fc-scn .nm{font-size:.6875rem;font-weight:600;color:var(--fc-var);display:flex;align-items:center;gap:.3rem}
.fc-scn .nm i{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.fc-scn .sub{font-size:.75rem;color:var(--fc-var)}
.fc-scn .big{font-size:1.125rem;font-weight:700;line-height:1.1;text-align:right}
.fc-scn .ym{font-size:.6875rem;font-weight:500;text-align:right;display:block}

/* detail cards */
.fc-grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:1rem;margin-bottom:1.5rem}
.fc-detail{padding:1.25rem;display:flex;flex-direction:column;justify-content:space-between}
.fc-detail-top{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-bottom:.5rem}
.fc-detail-name{font-size:.875rem;font-weight:600;color:var(--fc-text)}
.fc-reason{background:var(--fc-low);border:1px solid var(--fc-line);border-radius:.5rem;padding:.875rem;margin-top:.75rem}
.fc-reason .fc-label{display:block;margin-bottom:.25rem}
.fc-reason p{font-size:.8125rem;line-height:1.6;margin:0;color:var(--fc-text)}

/* payback chart */
.fc-chart{padding:1.5rem;margin-bottom:1rem}
.fc-legend{display:flex;gap:1rem;font-size:.6875rem;color:var(--fc-var);flex-wrap:wrap}
.fc-legend span{display:inline-flex;align-items:center;gap:.4rem}
.fc-legend i{display:inline-block;width:12px;height:12px;border-radius:2px}
.fc-bar-row{display:grid;grid-template-columns:110px 1fr 130px;align-items:center;gap:1rem;padding:.4rem 0}
.fc-bar-label{font-size:.75rem;font-weight:600;text-align:right;color:var(--fc-text)}
.fc-track{position:relative;height:28px;background:var(--fc-low);border-radius:.5rem}
.fc-bar{height:100%;border-radius:.5rem;min-width:2px}
.fc-bar-primary{background:var(--fc-pc)}.fc-bar-ok{background:var(--fc-ter)}.fc-bar-warn{background:#d97706}.fc-bar-danger{background:var(--fc-err)}.fc-bar-muted{background:#94a3b8}
.fc-guide{position:absolute;top:-4px;bottom:-4px;width:0;border-left:2px dashed rgba(186,26,26,.55);z-index:2}
.fc-bar-val{font-size:.8125rem;font-weight:500;text-align:right;color:var(--fc-text)}
.fc-axis{display:grid;grid-template-columns:110px 1fr 130px;gap:1rem;margin-top:.5rem;padding-top:.5rem;border-top:1px solid var(--fc-line)}
.fc-axis-track{position:relative;height:22px;margin-bottom:.5rem}
.fc-axis-track span{position:absolute;top:2px;font-size:.6875rem;color:var(--fc-var);white-space:nowrap}
.fc-axis-track span.lim{color:var(--fc-err);font-weight:600}
.fc-warnbox{display:flex;align-items:flex-start;gap:.6rem;margin-top:1rem;padding:.875rem;border:1px solid rgba(186,26,26,.3);background:rgba(255,218,214,.4);border-radius:.5rem;font-size:.8125rem;line-height:1.6;color:#93000a}
.fc-warnbox p{margin:0}
@media (max-width:760px){.fc-bar-row,.fc-axis{grid-template-columns:80px 1fr 90px;gap:.5rem}}

/* review cards */
.fc-rev{padding:1.25rem;margin-bottom:1rem}
.fc-rev-top{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:.5rem}
.fc-rev-t{display:flex;align-items:center;gap:.6rem}
.fc-rev-t h4{font-size:1rem;font-weight:600;margin:0;color:var(--fc-text);line-height:1.4}
.fc-num{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.6875rem;font-weight:700;flex-shrink:0;background:var(--fc-sec);color:#5c647a}
.fc-num.fc-danger{background:#ffdad6;color:#93000a}
.fc-rev-body{padding-left:2.1rem}
.fc-rev-body p{font-size:.875rem;line-height:1.6;margin:0 0 .5rem;color:var(--fc-text)}
.fc-quote{background:var(--fc-low);border:1px solid var(--fc-line);border-radius:.5rem;padding:.875rem;font-size:.8125rem;font-style:italic;color:var(--fc-text);line-height:1.6}
.fc-note{display:flex;align-items:center;gap:.5rem;padding:.875rem;background:var(--fc-low);border:1px solid var(--fc-line);border-radius:.5rem;font-size:.8125rem;color:var(--fc-var);margin-top:.5rem}
.fc-note .material-symbols-outlined{color:var(--fc-primary)}

/* report */
.fc-report{padding:1.5rem;margin-bottom:1rem}
.fc-report-head{display:flex;align-items:center;gap:.5rem;padding-bottom:.75rem;margin-bottom:1rem;border-bottom:1px solid var(--fc-line)}
.fc-report-head .material-symbols-outlined{color:var(--fc-pc)}
.fc-report p{font-size:.9rem;line-height:1.75;margin:0;color:var(--fc-text)}
[data-testid="stCheckbox"]{background:#fff;border:1px solid var(--fc-line);border-radius:.5rem;padding:.6rem .85rem;margin-bottom:.4rem}
[data-testid="stCheckbox"]:hover{background:rgba(224,227,229,.35)}
.fc-foot{padding:2rem 0 .5rem;margin-top:2.5rem;border-top:1px solid var(--fc-line);text-align:center;font-size:.75rem;color:#64748b}

/* tabs + native widgets */
[data-baseweb="tab-list"]{gap:.5rem;border-bottom:1px solid #cbd5e1}
button[data-baseweb="tab"]{height:auto;padding:.75rem 1.25rem;border-radius:.5rem .5rem 0 0;color:var(--fc-var)}
button[data-baseweb="tab"] p{font-size:.875rem;font-weight:500}
button[data-baseweb="tab"][aria-selected="true"]{background:#fff;color:var(--fc-pc)}
button[data-baseweb="tab"][aria-selected="true"] p{font-weight:600;color:var(--fc-pc)}
[data-baseweb="tab-highlight"]{background:var(--fc-pc);height:2px}
[data-baseweb="tab-border"]{background:transparent}
[data-testid="stExpander"]{background:var(--fc-low);border:1px solid var(--fc-line);border-radius:.5rem}
[data-testid="stDataFrame"],[data-testid="stTable"]{background:#fff;border-radius:.5rem}

/* force readable text colours regardless of Streamlit theme */
[data-testid="stSidebar"] *,[data-testid="stSidebar"] label p,[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:var(--fc-text)}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *{color:var(--fc-var)}
[data-testid="stSidebar"] .fc-brand-s{color:var(--fc-var)}
[data-testid="stSidebar"] .fc-brand-ico,[data-testid="stSidebar"] .fc-brand-ico *{color:#fff}
[data-testid="stSidebar"] button[kind="primaryFormSubmit"],[data-testid="stSidebar"] button[kind="primaryFormSubmit"] *,[data-testid="stSidebar"] button[kind="primary"] *{color:#fff}
[data-testid="stSidebar"] [data-baseweb="select"] *,[data-testid="stSidebar"] input{color:var(--fc-text);-webkit-text-fill-color:var(--fc-text);background-color:#fff}
[data-testid="stSidebar"] [data-baseweb="select"] svg,[data-testid="stSidebar"] [data-testid="stNumberInputContainer"] svg{fill:var(--fc-var);color:var(--fc-var)}
[data-testid="stSidebar"] [data-testid="stNumberInputContainer"],[data-testid="stSidebar"] [data-testid="stNumberInputContainer"] button{background:#fff;border-color:#cbd5e1}
[data-baseweb="popover"] [data-baseweb="menu"],[data-baseweb="popover"] ul,[data-baseweb="popover"] li{background:#fff;color:var(--fc-text)}
[data-baseweb="popover"] li:hover,[data-baseweb="popover"] li[aria-selected="true"]{background:var(--fc-low)}
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] label *,[data-testid="stCheckbox"] p{color:var(--fc-text)!important;font-size:.875rem}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *,[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p{color:var(--fc-text)}
[data-testid="stAlert"] *{color:inherit}
</style>
"""


def _e(value: Any) -> str:
    """Escape any value for safe inclusion in HTML (also collapses newlines)."""
    if value is None:
        return ""
    return html.escape(" ".join(str(value).split()), quote=True)


def _html(markup: str) -> None:
    """Render an HTML block. Lines are joined so Markdown never treats it as code."""
    st.markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def _icon(name: str, size: int = 18) -> str:
    return f'<span class="material-symbols-outlined" style="font-size:{size}px">{name}</span>'


def _badge(label: Any, tone: str) -> str:
    return f'<span class="fc-badge fc-{tone}"><i></i>{_e(label)}</span>'


def _tone(level: Any) -> str:
    return _TONE_BY_LEVEL.get(str(level), "muted")


def _signal_suffix(item: dict[str, Any]) -> str:
    return "%" if item.get("item") in _PERCENT_ITEMS else ""


def _months_text(months: float) -> str:
    years, rest = divmod(int(round(months)), 12)
    if years and rest:
        return f"{years}년 {rest}개월"
    if years:
        return f"{years}년"
    return f"{rest}개월"


def _payback_records(payback_df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(payback_df.to_dict(orient="records")):
        months = row.get("payback_months")
        valid = months is not None and pd.notna(months)
        name = str(row.get("scenario", "시나리오"))
        base = next((tone for key, tone in _SCENARIO_TONES if key in name), ("warn", "primary", "ok")[index % 3])
        over = bool(valid and (bool(row.get("uncertain")) or float(months) > PAYBACK_LIMIT_MONTHS))
        tone = "muted" if not valid else ("danger" if over else base)
        records.append({
            "name": name,
            "months": float(months) if valid else None,
            "profit": row.get("monthly_net_profit"),
            "tone": tone,
            "over": over,
        })
    return records


_REVIEW_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("특수관계자 거래", ("특수관계자 거래 확인:",), ()),
    ("계약 조항", ("점주 확인 조항:",), ()),
    ("자료 누락", (), ("원문 없음", "자료 누락", "값이 누락")),
    ("문서 불일치", (), ("불일치", "다릅", "일치하지", "확인되지 않습니다", "비교 대상이 여러")),
    ("추출·계산 확인", (), ("추출", "실패", "계산", "교차 점검", "제외된")),
)
_DEFAULT_REVIEW_CATEGORY = "기준연도·기타 확인"


def _review_category(flag: dict[str, Any]) -> str:
    """검토 항목의 issue 문구로 화면에 표시할 분류를 정한다."""
    issue = str(flag.get("issue", ""))
    for category, prefixes, keywords in _REVIEW_CATEGORY_RULES:
        if issue.startswith(prefixes) or any(keyword in issue for keyword in keywords):
            return category
    return _DEFAULT_REVIEW_CATEGORY


def _render_review_flags(flags: list[dict[str, Any]]) -> None:
    _html(f"""
<div class="fc-sec-head"><div class="l"><span class="fc-tag">문서 정밀 대조</span>
<h3 class="fc-h">감사보고서 및 정보공개서 대조 발견 사항</h3></div>
<span class="fc-small">확인 필요 {len(flags)}건</span></div>""")
    if not flags:
        st.info(
            "확인 필요 항목이 수집되지 않았습니다. 이는 안전 판정이 아닙니다. "
            "자료 누락이나 추출 결과가 없는 경우에도 목록이 비어 있을 수 있으니 원문과 자료 범위를 확인하세요."
        )
    category_tone = {"계약 조항": "danger", "문서 불일치": "warn", "자료 누락": "warn"}
    cards: list[str] = []
    for number, flag in enumerate(flags, start=1):
        category = _review_category(flag)
        tone = category_tone.get(category, "muted")
        evidence = str(flag.get("evidence") or "")
        quote = flag.get("quote")
        parts = []
        if quote:
            if evidence.startswith("원문 인용"):
                evidence = ""
        elif not evidence:
            evidence = "제공된 근거가 없습니다."
        if evidence:
            parts.append(f"<p>{_e(evidence)}</p>")
        if quote:
            parts.append(f'<span class="fc-label">원문 인용</span><div class="fc-quote">{_e(quote)}</div>')
        num_cls = "fc-num fc-danger" if tone == "danger" else "fc-num"
        cards.append(
            f'<article class="fc-card fc-rev"><div class="fc-rev-top"><div class="fc-rev-t">'
            f'<span class="{num_cls}">{number}</span><h4>{_e(flag.get("issue") or "확인할 사항")}</h4></div>'
            f'{_badge(category, tone)}</div><div class="fc-rev-body">{"".join(parts)}</div></article>'
        )
    if cards:
        _html("".join(cards))
    _html(
        '<div class="fc-note">' + _icon("verified_user") +
        "<span>※ 문서 검토 결과에 언급되지 않은 항목이 있더라도 해당 계약 영역이 전적으로 안전함을 보증하는 것은 아닙니다. "
        "변호사 또는 가맹거래사와의 추가 약관 검토를 권장합니다.</span></div>"
    )


def _render_payback_section(
    payback_df: pd.DataFrame | None,
    avg_sales_info: dict[str, Any] | None,
    year: int,
) -> None:
    if payback_df is None:
        st.warning(
            "회수 기간을 계산하지 못했습니다. 이 영역의 계산에만 영향을 주며 "
            "위의 재무·계약 신호와 문서 검토 결과는 계속 확인할 수 있습니다."
        )
        return

    records = _payback_records(payback_df)
    valid_months = [r["months"] for r in records if r["months"] is not None]
    scale = max(80, int(math.ceil(max(valid_months) * 1.05 / 20) * 20)) if valid_months else 80
    limit_pos = PAYBACK_LIMIT_MONTHS / scale * 100
    ordered = sorted(records, key=lambda r: (r["months"] is None, r["months"] or 0))

    rows = []
    for rec in ordered:
        if rec["months"] is None:
            width, value = 0.0, '<span class="fc-t-muted">산출 불가</span>'
        else:
            width = min(rec["months"] / scale * 100, 100)
            cls = "fc-t-danger" if rec["over"] else ""
            value = f'<span class="{cls}" style="font-weight:600">{rec["months"]:,.1f}개월</span><br><span class="fc-small">{_months_text(rec["months"])}</span>'
        rows.append(
            f'<div class="fc-bar-row"><span class="fc-bar-label">{_e(rec["name"])} 시나리오</span>'
            f'<div class="fc-track"><i class="fc-guide" style="left:{limit_pos:.2f}%"></i>'
            f'<div class="fc-bar fc-bar-{rec["tone"]}" style="width:{width:.2f}%"></div></div>'
            f'<span class="fc-bar-val">{value}</span></div>'
        )
    tick_values = list(range(0, scale + 1, 20))
    tick_html = []
    for t in tick_values:
        shift = "0" if t == 0 else ("-100%" if t == tick_values[-1] else "-50%")
        cls = "lim" if t == PAYBACK_LIMIT_MONTHS else ""
        tick_html.append(f'<span class="{cls}" style="left:{t / scale * 100:.2f}%;transform:translateX({shift})">{t}</span>')
    ticks = "".join(tick_html)

    over_names = [r["name"] for r in records if r["over"] and r["months"] is not None]
    na_names = [r["name"] for r in records if r["months"] is None]
    warns = []
    if over_names:
        warns.append(
            f"<strong>위험 경고:</strong> {_e(', '.join(over_names))} 시나리오는 회수 기간이 "
            f"{PAYBACK_LIMIT_MONTHS}개월(5년)을 초과하거나 불확실로 분류되었습니다. "
            "계약 기간 내 원금 회수가 지연될 수 있으며, 리뉴얼·감가상각 비용이 추가되면 불확실성이 커집니다."
        )
    if na_names:
        warns.append(
            f"<strong>산출 불가:</strong> {_e(', '.join(na_names))} 시나리오는 월 순이익이 0 이하이므로 "
            "회수 기간을 계산할 수 없습니다."
        )
    warn_html = "".join(
        f'<div class="fc-warnbox">{_icon("warning")}<p>{w}</p></div>' for w in warns
    )
    _html(
        '<div class="fc-card fc-chart"><div class="fc-sec-head" style="padding-bottom:.5rem;border-bottom:1px solid #e2e8f0;margin-bottom:1rem">'
        '<div><h3 class="fc-h">시나리오별 원금 회수 소요 기간 비교</h3>'
        f'<p class="fc-small" style="margin:.2rem 0 0">기준연도 {_e(year)}년 · 금액 단위 만원(시연 CSV 기준)</p></div>'
        '<div class="fc-legend"><span><i style="background:#2563eb"></i>회수 기간</span>'
        f'<span><i style="background:transparent;border-left:2px dashed #ba1a1a;border-radius:0;width:0;height:12px"></i>'
        f'<span class="fc-t-danger">계약 갱신선 ({PAYBACK_LIMIT_MONTHS}개월)</span></span></div></div>'
        + "".join(rows)
        + f'<div class="fc-axis"><span></span><div class="fc-axis-track">{ticks}</div><span class="fc-small">(개월)</span></div>'
        + warn_html + "</div>"
    )

    if avg_sales_info is not None:
        basis = str(avg_sales_info.get("basis", "확인 필요"))
        basis_label = "전국 평균" if basis == "전국" else f"{basis} 지역"
        with st.expander("시뮬레이션 산출 가정 및 기준 매출", expanded=False):
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


def _render_summary(signals: list[dict[str, Any]], payback_df: pd.DataFrame | None) -> None:
    flagged = sum(1 for item in signals if str(item.get("level")) in {"주의", "위험"})
    cells = []
    for index, item in enumerate(signals, start=1):
        level = item.get("level", "확인 필요")
        tone = _tone(level)
        value = _format_value(item.get("value"), _signal_suffix(item))
        metric_cls = "fc-metric fc-t-danger" if tone == "danger" else "fc-metric"
        reason = item.get("reason") or "제공된 판정 근거가 없습니다."
        cells.append(
            f'<div class="fc-sig"><div class="fc-sig-top"><span class="fc-label">{index:02d}. {_e(item.get("item", "위험 신호"))}</span>'
            f'{_badge(level, tone)}</div><div class="{metric_cls}">{_e(value)}</div>'
            f'<p class="fc-sig-note">{_e(reason)}</p></div>'
        )
    flag_label = f"{flagged}개 항목 주의·위험 감지" if flagged else "주의·위험 항목 없음"
    flag_cls = "fc-t-danger" if flagged else "fc-t-ok"

    pb_html = ""
    if payback_df is not None:
        scn = []
        for rec in sorted(_payback_records(payback_df), key=lambda r: (r["months"] is None, r["months"] or 0)):
            profit = _format_value(rec["profit"])
            if rec["months"] is None:
                big, sub = "산출 불가", "월 순이익 0 이하"
            else:
                big = f'{rec["months"]:,.1f}개월'
                sub = _months_text(rec["months"]) + (" (60개월 초과)" if rec["over"] else "")
            scn.append(
                f'<div class="fc-scn fc-scn-{rec["tone"]}"><div><span class="nm fc-t-{rec["tone"]}"><i></i>{_e(rec["name"])}</span>'
                f'<span class="sub">월 {_e(profit)}만원</span></div>'
                f'<div><div class="big fc-t-{rec["tone"]}">{_e(big)}</div><span class="ym fc-t-{rec["tone"]}">{_e(sub)}</span></div></div>'
            )
        pb_html = (
            '<div class="fc-pb"><div class="fc-pb-title"><div class="fc-pb-ico">' + _icon("savings", 16) + '</div>'
            '<div><span class="fc-label" style="display:block;color:#191c1e">예상 원금 회수 기간 시나리오</span>'
            '<span class="fc-small">시나리오별 월 순이익 기준</span></div></div>'
            f'<div class="fc-pb-grid">{"".join(scn)}</div></div>'
        )
    else:
        pb_html = '<div class="fc-pb"><span class="fc-small">회수 기간을 계산할 수 없습니다.</span></div>'

    _html(
        '<div class="fc-sec-head"><div class="l">' + _icon("insights", 20).replace("material", "fc-t-primary material") +
        '<h2 class="fc-h">검진 결과 한눈에 보기 (핵심 요약)</h2></div>'
        '<span class="fc-small">공공 데이터 기반 자동 진단</span></div>'
        '<div class="fc-card fc-sumcard"><div class="fc-sigs"><div class="fc-sigs-top">'
        '<span class="fc-label" style="letter-spacing:.04em">본사 재무 및 계약 위험 신호</span>'
        f'<span class="fc-small {flag_cls}" style="font-weight:600">{flag_label}</span></div>'
        f'<div class="fc-sigs-grid">{"".join(cells)}</div></div>{pb_html}</div>'
    )


def _render_signal_details(signals: list[dict[str, Any]]) -> None:
    cards = []
    for index, item in enumerate(signals, start=1):
        level = item.get("level", "확인 필요")
        tone = _tone(level)
        value = _format_value(item.get("value"), _signal_suffix(item))
        metric_cls = "fc-metric fc-metric-xl fc-t-danger" if tone == "danger" else "fc-metric fc-metric-xl"
        cards.append(
            f'<article class="fc-card fc-detail"><div><div class="fc-detail-top">'
            f'<span class="fc-detail-name">지표 {index:02d}. {_e(item.get("item", "지표"))}</span>{_badge(level, tone)}</div>'
            f'<div class="{metric_cls}">{_e(value)}</div></div>'
            f'<div class="fc-reason"><span class="fc-label">상세 판정 근거</span>'
            f'<p>{_e(item.get("reason") or "제공된 판정 근거가 없습니다.")}</p></div></article>'
        )
    _html(
        '<div class="fc-sec-head" style="margin-top:1rem"><div class="l"><span class="fc-tag">상세 판정</span>'
        '<h3 class="fc-h">본사 재무안정성 지표별 정밀 근거</h3></div></div>'
        f'<div class="fc-grid2">{"".join(cards)}</div>'
    )


def _render_notice(freshness: list[str], year: int) -> None:
    if freshness:
        body = "".join(f"<p>{_e(w)}</p>" for w in freshness)
        _html(
            '<aside class="fc-notice"><div class="fc-notice-ico">' + _icon("info", 16) + '</div>'
            f'<div><strong style="color:#003ea8">[자료 최신성 안내]</strong>{body}</div></aside>'
        )
    else:
        _html(
            '<aside class="fc-notice fc-notice-ok"><div class="fc-notice-ico">' + _icon("check", 16) + '</div>'
            f'<div><strong>[자료 최신성 확인]</strong> 본사 재무와 정보공개서의 공통 기준연도 {_e(year)}년 자료로 분석했습니다.</div></aside>'
        )


def _render_dashboard(result: dict[str, Any]) -> None:
    user_input = result["user_input"]
    year = result["year"]
    signals = result["signals"]
    payback_df = result["payback_df"]
    avg_sales_info = result["avg_sales_info"]
    basis = avg_sales_info.get("basis", "확인 필요") if avg_sales_info else "확인 필요"
    basis_label = "전국 평균" if basis == "전국" else f"{basis} 기준"
    user_type = str(user_input["user_type"])

    _render_header([
        ("브랜드", user_input["brand"]),
        ("지역", user_input["region"]),
        ("기준연도", f"{year}년"),
        ("평균매출 기준", basis_label),
        ("사용자 유형", _USER_TYPE_LABELS.get(user_type, user_type)),
    ])
    _render_notice(result["freshness"], year)
    if result.get("warnings"):
        with st.expander("분석 중 확인된 자료 경고", expanded=False):
            for warning in result["warnings"]:
                st.write(warning)
    _render_summary(signals, payback_df)

    tab1, tab2, tab3 = st.tabs(["재무 및 투자 분석", "문서 검토 결과", "종합 리포트 & 체크리스트"])
    with tab1:
        _render_signal_details(signals)
        _render_payback_section(payback_df, avg_sales_info, year)
    with tab2:
        _render_review_flags(result["review_flags"])
        for title, text_value in (("감사보고서 주석 원문", result.get("audit_text")), ("정보공개서 계약 조항 원문", result.get("clause_text"))):
            with st.expander(title, expanded=False):
                st.write(text_value if text_value else "해당 연도 자료가 없습니다.")
    with tab3:
        report = result.get("report") or {}
        summary = report.get("summary") or "리포트 요약을 생성하지 못했습니다. Python 분석 결과와 문서 검토 탭을 확인하세요."
        _html(
            '<div class="fc-sec-head"><div class="l"><span class="fc-tag">AI 리포트</span>'
            '<h3 class="fc-h">AI 종합 진단 리포트</h3></div>'
            f'<span class="fc-small">기준연도 {_e(year)}년</span></div>'
            '<article class="fc-card fc-report"><div class="fc-report-head">' + _icon("summarize", 22) +
            '<h4 class="fc-h" style="font-size:1rem">핵심 검토 브리핑</h4></div>'
            f'<p>{_e(summary)}</p></article>'
        )
        _html(
            '<div class="fc-sec-head" style="margin-top:1rem"><div class="l">' + _icon("checklist", 18).replace("material", "fc-t-primary material") +
            '<h4 class="fc-h" style="font-size:.95rem">추가 확인 체크리스트</h4></div></div>'
        )
        checklist = report.get("checklist", [])
        for position, item in enumerate(checklist):
            digest = hashlib.md5(str(item).encode("utf-8")).hexdigest()[:8]
            st.checkbox(str(item), key=f"report_check_{year}_{position}_{digest}")
        if not checklist:
            st.info("추가 확인 체크리스트가 없습니다.")
    _html(
        '<footer class="fc-foot">본 서비스는 정보 제공 목적이며, 법률·투자 자문이 아닙니다. '
        "가맹 계약 전 가맹거래사 및 법률 전문가와 상담하시기 바랍니다.</footer>"
    )


def _render_header(meta: list[tuple[str, Any]] | None = None) -> None:
    meta_html = ""
    if meta:
        items = "".join(
            f'<span class="fc-meta-item"><span class="fc-label">{_e(label)}</span><b>{_e(value)}</b></span>'
            for label, value in meta
        )
        meta_html = f'<div class="fc-meta">{items}</div>'
    _html(
        '<div class="fc-eyebrow"><i></i>FRANCHISE FINANCIAL CHECKUP</div>'
        '<h1 class="fc-title">프랜차이즈 본사 재무 건강검진</h1>'
        '<p class="fc-desc">공개 자료 기반으로 본사 재무·계약 위험과 예상 투자 회수 기간을 점검합니다.</p>'
        '<p class="fc-caption">이 화면은 제출된 자료와 기존 분석 규칙에 따른 참고 정보입니다. '
        '자료의 범위와 기준연도에 따라 결과가 달라질 수 있으며, 원문 자료를 함께 확인해 주세요.</p>'
        + meta_html
    )


def _render_input_form(brands: list[str], regions: list[str]) -> dict[str, Any] | None:
    with st.sidebar:
        _html(
            '<div class="fc-brand"><div class="fc-brand-ico">' + _icon("verified_user", 20) + '</div>'
            '<div><div class="fc-brand-t">프랜차이즈 재무 건강검진</div>'
            '<div class="fc-brand-s">공정위 정보공개서 정밀진단</div></div></div>'
        )
        st.header("검진 조건 설정")
        st.caption("진단 지표 및 투자 시뮬레이션 매개변수")
        with st.form("health_check_form"):
            _html('<div class="fc-side-sec">' + _icon("corporate_fare", 16) + "검진 대상</div>")
            brand = st.selectbox("대상 가맹본부 브랜드", brands)
            region = st.selectbox("분석 기준 지역 (시도)", regions)

            _html('<div class="fc-side-sec">' + _icon("payments", 16) + "투자 조건</div>")
            st.caption(
                "금액 단위: 만원 (현재 시연 CSV 기준). 실제 자료로 교체할 때는 "
                "원자료 단위를 확인하고 같은 단위로 입력하세요."
            )
            deposit = st.number_input(
                "임차 보증금 (만원)", min_value=0.0, step=100.0, format="%.0f"
            )
            key_money = st.number_input(
                "영업 권리금 (만원)", min_value=0.0, step=100.0, format="%.0f"
            )
            loan_amount = st.number_input(
                "창업 대출금 (만원)", min_value=0.0, step=100.0, format="%.0f"
            )
            loan_rate = st.number_input(
                "대출 금리 (연 %)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                format="%.1f",
            )

            _html('<div class="fc-side-sec">' + _icon("person", 16) + "사용자 유형</div>")
            user_type = st.radio(
                "사용자 유형", ["예비", "기존"], horizontal=True,
                format_func=lambda value: _USER_TYPE_LABELS.get(value, value),
                label_visibility="collapsed",
            )
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
    """Streamlit 앱의 진입점. 입력 폼을 그리고, 제출되면 파이프라인을 실행해 결과를 표시한다."""
    st.set_page_config(
        page_title="프랜차이즈 본사 재무 건강검진",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_APP_CSS, unsafe_allow_html=True)

    try:
        tables = _load_tables(str(PROJECT_ROOT))
    except (FileNotFoundError, OSError, ValueError, ImportError) as error:
        st.error(f"데이터를 불러올 수 없습니다: {error}")
        st.caption("필수 파일: " + ", ".join(CSV_NAMES))
        return

    brands = common_brands(tables["hq_financials.csv"], tables["franchise_disclosure.csv"])
    regions = list_regions(tables["region_sales.csv"])
    if not brands or not regions:
        st.error("브랜드 또는 지역 선택 자료가 없습니다. CSV 내용을 확인하세요.")
        return

    selected = _render_input_form(brands, regions)
    if selected:
        st.session_state.pop("checkup_result", None)
        st.session_state.pop("checkup_input", None)
        result = None
        with st.spinner("재무·계약 분석과 문서 검토를 실행하고 있습니다..."):
            try:
                result = run_checkup(selected, tables)
            except PipelineError as error:
                st.error(str(error))
                for warning in error.warnings:
                    st.warning(warning)
        if result is not None:
            st.session_state["checkup_result"] = result
            st.session_state["checkup_input"] = dict(selected)

    result = st.session_state.get("checkup_result")
    if result is None:
        _render_header()
        st.info("왼쪽 검진 조건을 입력하고 **분석 실행**을 누르면 요약 결과와 상세 근거를 확인할 수 있습니다.")
        return
    if st.session_state.get("checkup_input") != result.get("user_input"):
        st.warning("현재 선택한 조건과 마지막 분석 조건이 다를 수 있습니다. 최신 조건으로 보려면 분석 실행을 눌러 주세요.")
    _render_dashboard(result)


if __name__ == "__main__":
    main()