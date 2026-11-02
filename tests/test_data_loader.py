
import pandas as pd
import pytest

from franchise_checkup.data_loader import (
    load_csv_table,
    validate_user_input,
    select_avg_sales,
)


# 1. load_csv_table

def test_load_csv_normal(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(
        "brand,year,revenue\nA,2025,150000\n",
        encoding="utf-8",
    )

    result = load_csv_table(
        str(path), ["brand", "year", "revenue"]
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert list(result.columns) == [
        "brand", "year", "revenue"
    ]


def test_load_csv_boundary(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(
        "brand,year,revenue\n",
        encoding="utf-8",
    )

    result = load_csv_table(
        str(path), ["brand", "year", "revenue"]
    )

    assert result.empty
    assert list(result.columns) == [
        "brand", "year", "revenue"
    ]


def test_load_csv_exception(tmp_path):
    path = tmp_path / "missing.csv"
    path.write_text(
        "brand,year\nA,2025\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_csv_table(
            str(path), ["brand", "year", "revenue"]
        )

# 2. validate_user_input

def test_validate_normal():
    raw = {
        "brand": "A브랜드",
        "region": "서울",
        "deposit": 2000,
        "key_money": 3000,
        "loan_amount": 1000,
        "loan_rate": 5.0,
        "user_type": "예비",
    }

    result = validate_user_input(raw)

    assert result["deposit"] == 2000.0
    assert result["loan_rate"] == 5.0
    assert result["user_type"] == "예비"


def test_validate_boundary():
    raw = {
        "brand": "A브랜드",
        "region": "서울",
        "deposit": 0,
        "key_money": 0,
        "loan_amount": 0,
        "loan_rate": 0,
        "user_type": "예비",
    }

    result = validate_user_input(raw)

    assert result["deposit"] == 0.0
    assert result["key_money"] == 0.0
    assert result["loan_amount"] == 0.0
    assert result["loan_rate"] == 0.0


def test_validate_exception():
    raw = {
        "brand": "A브랜드",
        "region": "서울",
        "deposit": -1000,
        "key_money": 3000,
        "loan_amount": 1000,
        "loan_rate": 5.0,
        "user_type": "예비",
    }

    with pytest.raises(ValueError):
        validate_user_input(raw)

# 3. select_avg_sales

def test_select_sales_normal():
    disc_row = {"avg_annual_sales": 24000}

    region_rows = pd.DataFrame([
        {"region": "서울", "avg_annual_sales": 30000},
        {"region": "경기", "avg_annual_sales": 26000},
    ])

    result = select_avg_sales(
        disc_row, region_rows, "서울"
    )

    assert result["value"] == 30000
    assert result["basis"] == "서울"


def test_select_sales_boundary():
    disc_row = {"avg_annual_sales": 24000}

    region_rows = pd.DataFrame([
        {"region": "경기", "avg_annual_sales": 26000},
    ])

    result = select_avg_sales(
        disc_row, region_rows, "서울"
    )

    assert result["value"] == 24000
    assert result["basis"] == "전국"


def test_select_sales_exception():
    disc_row = {"avg_annual_sales": None}

    region_rows = pd.DataFrame([
        {"region": "경기", "avg_annual_sales": 26000},
    ])

    with pytest.raises(ValueError):
        select_avg_sales(
            disc_row, region_rows, "서울"
        )










