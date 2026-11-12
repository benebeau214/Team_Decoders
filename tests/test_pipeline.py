import json

import pandas as pd
import pytest

from franchise_checkup.pipeline import PipelineError, run_checkup


BRAND = "테스트브랜드"
YEAR = 2024


def _tables() -> dict[str, pd.DataFrame]:
    return {
        "hq_financials.csv": pd.DataFrame(
            [
                {
                    "brand": BRAND,
                    "year": YEAR,
                    "total_liabilities": 100.0,
                    "total_equity": 100.0,
                    "capital_stock": 100.0,
                    "revenue": 1000.0,
                    "operating_income": 100.0,
                }
            ]
        ),
        "franchise_disclosure.csv": pd.DataFrame(
            [
                {
                    "brand": BRAND,
                    "year": YEAR,
                    "startup_cost": 10000.0,
                    "avg_annual_sales": 24000.0,
                    "stores_begin": 100.0,
                    "contract_terminated": 1.0,
                    "contract_ended": 1.0,
                    "related_party": "관계사",
                    "relationship": "계열사",
                    "transaction_type": "상품 매입",
                    "amount": "1000만원",
                }
            ]
        ),
        "region_sales.csv": pd.DataFrame(
            [
                {
                    "brand": BRAND,
                    "year": YEAR,
                    "region": "서울",
                    "avg_annual_sales": 24000.0,
                }
            ]
        ),
        "audit_notes.csv": pd.DataFrame(
            [{"brand": BRAND, "year": YEAR, "note_text": "특수관계자 거래 없음"}]
        ),
        "disclosure_clauses.csv": pd.DataFrame(
            [{"brand": BRAND, "year": YEAR, "clause_text": "계약 조항 원문"}]
        ),
    }


def _user_input() -> dict[str, object]:
    return {
        "brand": BRAND,
        "region": "서울",
        "deposit": 2000.0,
        "key_money": 3000.0,
        "loan_amount": 0.0,
        "loan_rate": 0.0,
        "user_type": "예비",
    }


def _mock_llm(prompt: str) -> str:
    if prompt.startswith("당신은 감사보고서 주석을 분석하는 도우미입니다."):
        return json.dumps({"items": []}, ensure_ascii=False)
    if prompt.startswith(
        "당신은 가맹사업 정보공개서의 계약 조항을 검토하는 분석 도우미입니다."
    ):
        return json.dumps({"items": []}, ensure_ascii=False)
    if prompt.startswith("<report_text>"):
        return json.dumps(
            {
                "summary": "통합 테스트 보고서입니다.",
                "checklist": ["계약서를 확인하세요."],
            },
            ensure_ascii=False,
        )
    raise AssertionError("예상하지 못한 LLM 프롬프트가 전달되었습니다.")


def test_run_checkup_normal_path_returns_expected_values_and_keys():
    result = run_checkup(_user_input(), _tables(), _mock_llm)

    assert set(result) == {
        "user_input",
        "year",
        "year_summary",
        "fin_row",
        "disc_row",
        "ratios",
        "termination_rate",
        "signals",
        "freshness",
        "review_flags",
        "audit_text",
        "clause_text",
        "avg_sales_info",
        "payback_df",
        "report",
        "warnings",
    }
    assert result["user_input"] == _user_input()
    assert result["year"] == YEAR
    assert result["year_summary"] == {
        "financial_latest": YEAR,
        "disclosure_latest": YEAR,
        "selected": YEAR,
    }
    assert result["ratios"] == {
        "debt_ratio": pytest.approx(100.0),
        "op_margin": pytest.approx(10.0),
        "capital_status": "정상",
    }
    assert result["termination_rate"] == pytest.approx(2.0)
    assert result["freshness"] == []
    assert result["warnings"] == []
    assert result["audit_text"] == "특수관계자 거래 없음"
    assert result["clause_text"] == "계약 조항 원문"
    assert result["avg_sales_info"] == {"value": 24000.0, "basis": "서울"}
    assert result["payback_df"]["scenario"].tolist() == ["보수", "평균", "낙관"]
    assert result["payback_df"]["monthly_net_profit"].tolist() == [
        80.0,
        200.0,
        360.0,
    ]
    assert set(result["report"]) == {"summary", "checklist"}
    assert result["report"]["summary"] == "통합 테스트 보고서입니다. 법률·투자 자문이 아닙니다."
    assert result["report"]["checklist"] == ["계약서를 확인하세요."]


def test_run_checkup_missing_brand_raises_pipeline_error():
    user_input = {**_user_input(), "brand": "없는브랜드"}

    with pytest.raises(PipelineError, match="브랜드.*자료가 없습니다"):
        run_checkup(user_input, _tables(), _mock_llm)


def test_run_checkup_missing_required_column_raises_pipeline_error():
    tables = _tables()
    tables["hq_financials.csv"] = tables["hq_financials.csv"].drop(
        columns=["operating_income"]
    )

    with pytest.raises(PipelineError, match="hq_financials.csv에 필수 컬럼이 없습니다"):
        run_checkup(_user_input(), tables, _mock_llm)
