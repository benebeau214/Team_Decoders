from __future__ import annotations

import hashlib
import math

import streamlit as st

from franchise_checkup.data_loader import (
    CSV_NAMES,
    DataLoadError,
    load_tables_from_uploads,
)

from franchise_checkup.pipeline import (
    PipelineError,
    common_brands,
    list_regions,
    run_checkup,
)


def get_upload_signature(uploaded_files) -> tuple:
    """업로드 파일의 이름과 내용을 바탕으로 변경 여부를 확인한다."""
    return tuple(
        (
            file.name,
            hashlib.sha256(file.getvalue()).hexdigest(),
        )
        for file in sorted(uploaded_files, key=lambda file: file.name)
    )


def format_percent(value) -> str:
    """화면에 표시할 백분율 값을 포맷한다."""
    if value is None:
        return "확인 필요"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "확인 필요"

    if not math.isfinite(numeric_value):
        return "확인 필요"

    return f"{numeric_value:,.1f}%"


def main() -> None:
    st.set_page_config(
        page_title="프랜차이즈 본사 재무 건강검진 대시보드",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("프랜차이즈 본사 재무 건강검진 대시보드")
    st.markdown(
        "공개 공시 데이터를 활용한 가맹본부 재무 위험 진단 및 "
        "투자 원금 회수 시뮬레이션 서비스입니다."
    )

    # 1. CSV 파일 업로드
    st.sidebar.header("데이터 업로드")
    st.sidebar.markdown(
        "분석에 필요한 CSV 파일 5종을 모두 업로드하세요."
    )

    uploaded_files = st.sidebar.file_uploader(
        "분석용 CSV 파일 업로드",
        type=["csv"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.warning(
            "분석을 시작하려면 사이드바에서 필수 CSV 파일 5종을 업로드해 주세요."
        )

        st.info(
            "**필요한 CSV 파일 목록:**\n"
            + "\n".join(f"- `{name}`" for name in CSV_NAMES)
        )
        st.stop()

    # 2. 업로드 파일 변경 여부 확인 및 데이터 로딩
    upload_signature = get_upload_signature(uploaded_files)

    cached_signature = st.session_state.get("upload_signature")

    if cached_signature != upload_signature:
        # 새로운 파일을 업로드했다면 기존 데이터와 분석 결과 초기화
        for key in (
            "tables",
            "upload_signature",
            "checkup_result",
            "last_input",
        ):
            st.session_state.pop(key, None)

        try:
            tables = load_tables_from_uploads(uploaded_files)

            st.session_state.tables = tables
            st.session_state.upload_signature = upload_signature

        except DataLoadError as error:
            st.error(f"데이터 적재 오류: {error}")
            st.stop()

        except Exception as error:
            st.error(f"예기치 못한 파일 처리 오류가 발생했습니다: {error}")
            st.stop()

    else:
        # 동일한 파일이면 기존에 읽어 둔 DataFrame 재사용
        tables = st.session_state.tables

    # 3. 분석 대상 브랜드 및 지역 선택지 생성
    brands = common_brands(
        tables["hq_financials.csv"],
        tables["franchise_disclosure.csv"],
    )

    regions = list_regions(tables["region_sales.csv"])

    if not brands or not regions:
        st.error(
            "브랜드 또는 지역 목록을 생성할 수 없습니다. "
            "업로드된 CSV 데이터 구조를 확인하세요."
        )
        st.stop()

    # 4. 사이드바 필터 및 투자 조건 설정
    st.sidebar.divider()
    st.sidebar.header("검진 조건 설정")

    brand = st.sidebar.selectbox(
        "대상 가맹본부 브랜드",
        brands,
        key="selected_brand",
    )

    region = st.sidebar.selectbox(
        "분석 기준 지역 (시도)",
        regions,
        key="selected_region",
    )

    st.sidebar.subheader("투자 조건 설정")

    deposit = st.sidebar.number_input(
        "임차 보증금",
        min_value=0.0,
        value=2000.0,
        step=100.0,
    )

    key_money = st.sidebar.number_input(
        "영업 권리금",
        min_value=0.0,
        value=3000.0,
        step=100.0,
    )

    loan_amount = st.sidebar.number_input(
        "창업 대출금",
        min_value=0.0,
        value=5000.0,
        step=100.0,
    )

    loan_rate = st.sidebar.number_input(
        "대출 금리 (연 %)",
        min_value=0.0,
        max_value=100.0,
        value=5.0,
        step=0.1,
    )

    user_type = st.sidebar.radio(
        "사용자 유형",
        ["예비", "기존"],
        horizontal=True,
    )

    current_input = {
        "brand": brand,
        "region": region,
        "deposit": deposit,
        "key_money": key_money,
        "loan_amount": loan_amount,
        "loan_rate": loan_rate,
        "user_type": user_type,
    }

    st.sidebar.caption("조건을 변경하면 분석 결과가 자동으로 갱신됩니다.")

    submitted = st.sidebar.button(
        "현재 조건으로 다시 분석",
        type="primary",
        use_container_width=True,
    )

    # 5. 분석 실행 및 결과 관리
    last_input = st.session_state.get("last_input")

    should_run = (
        submitted
        or st.session_state.get("checkup_result") is None
        or current_input != last_input
    )

    if should_run:
        with st.spinner(
            "백엔드 파이프라인에서 재무·계약 분석 및 시뮬레이션을 실행 중입니다..."
        ):
            try:
                result = run_checkup(current_input, tables)

                st.session_state.checkup_result = result
                st.session_state.last_input = current_input

            except PipelineError as error:
                st.session_state.pop("checkup_result", None)
                st.session_state.pop("last_input", None)

                st.error(f"분석 실행 중 오류 발생: {error}")

                for warning in error.warnings:
                    st.warning(warning)

                return

            except Exception as error:
                st.session_state.pop("checkup_result", None)
                st.session_state.pop("last_input", None)

                st.error(f"예기치 못한 분석 오류가 발생했습니다: {error}")
                return

    result = st.session_state.get("checkup_result")

    if result is None:
        st.info("사이드바에서 분석 조건을 설정해 주세요.")
        return

    # 6. 분석 결과 표시
    year = result["year"]
    signals = result["signals"]
    payback_df = result["payback_df"]

    st.subheader(f"분석 결과: {brand} ({year}년 기준)")

    # 재무 및 계약 지표
    signal_dict = {
        item.get("item"): item
        for item in signals
    }

    debt_item = signal_dict.get("부채비율", {})
    margin_item = signal_dict.get("영업이익률", {})
    term_item = signal_dict.get("계약 해지율", {})

    col1, col2, col3, col4 = st.columns(4)

    debt_level = debt_item.get("level")
    col1.metric(
        label="부채비율",
        value=format_percent(debt_item.get("value")),
        delta=debt_level or "확인 필요",
        delta_color=(
            "inverse"
            if debt_level in ["주의", "위험"]
            else "normal"
        ),
    )

    margin_level = margin_item.get("level")
    col2.metric(
        label="영업이익률",
        value=format_percent(margin_item.get("value")),
        delta=margin_level or "확인 필요",
        delta_color=(
            "inverse"
            if margin_level in ["주의", "위험"]
            else "normal"
        ),
    )

    term_level = term_item.get("level")
    col3.metric(
        label="계약 해지율",
        value=format_percent(term_item.get("value")),
        delta=term_level or "확인 필요",
        delta_color=(
            "inverse"
            if term_level in ["주의", "위험"]
            else "normal"
        ),
    )

    col4.metric(
        label="기준 연도",
        value=f"{year}년",
    )

    st.divider()

    # 7. 탭별 결과 표시
    tab1, tab2, tab3 = st.tabs(
        [
            "투자 회수 시뮬레이션 및 차트",
            "재무 신호 및 문서 검토",
            "업로드 데이터 미리보기",
        ]
    )

    with tab1:
        st.markdown("### 시나리오별 원금 회수 기간 (개월)")

        if payback_df is not None and not payback_df.empty:
            required_columns = {"scenario", "payback_months"}

            if required_columns.issubset(payback_df.columns):
                if payback_df["payback_months"].notna().any():
                    st.bar_chart(
                        payback_df,
                        x="scenario",
                        y="payback_months",
                    )
                else:
                    st.info(
                        "산출 가능한 유효한 회수 기간 데이터가 없습니다."
                    )
            else:
                st.warning("차트에 필요한 데이터 컬럼이 없습니다.")

            st.dataframe(
                payback_df,
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.warning("회수 기간을 산출할 수 없습니다.")

    with tab2:
        st.markdown("### 본사 재무 및 계약 위험 신호 판정")

        if signals:
            st.dataframe(
                signals,
                column_config={
                    "item": st.column_config.TextColumn("항목"),
                    "level": st.column_config.TextColumn("위험 수준"),
                    "value": st.column_config.NumberColumn("값"),
                    "reason": st.column_config.TextColumn(
                        "판정 근거",
                        width="large",
                    ),
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("표시할 재무 신호가 없습니다.")

        st.markdown("### 문서 검토 및 확인 필요 목록")

        review_flags = result.get("review_flags", [])

        if review_flags:
            for flag in review_flags:
                with st.expander(
                    f"[{flag.get('issue', '확인 필요')}]"
                ):
                    st.write(f"**근거:** {flag.get('evidence')}")

                    if flag.get("quote"):
                        st.caption(f"원문 인용: {flag.get('quote')}")

        else:
            st.success("수집된 추가 확인 항목이 없습니다.")

    with tab3:
        st.markdown("### 업로드 데이터 미리보기")

        table_name = st.selectbox(
            "확인할 데이터 테이블 선택",
            list(tables.keys()),
            key="preview_table_name",
        )

        st.dataframe(
            tables[table_name],
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "업로드 데이터와 분석 결과는 현재 세션의 st.session_state에 저장됩니다. "
        "동일한 파일로 화면이 다시 실행되더라도 데이터를 재사용하며, "
        "파일이 변경되면 데이터를 다시 읽고 분석 결과를 갱신합니다."
    )


if __name__ == "__main__":
    main()
