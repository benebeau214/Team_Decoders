
from io import BytesIO

import pandas as pd
import pytest

from franchise_checkup.data_loader import (
    CSV_NAMES,
    REQUIRED_COLUMNS,
    DataLoadError,
    load_csv_table,
    load_tables_from_uploads,
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


# 4. load_tables_from_uploads

def _uploaded_csv(name, encoding="utf-8", columns=None):
    columns = columns or REQUIRED_COLUMNS[name]
    content = ",".join(columns) + "\n"
    content += ",".join("값" for _ in columns) + "\n"
    uploaded_file = BytesIO(content.encode(encoding))
    uploaded_file.name = name
    return uploaded_file


def _complete_uploads(encoding="utf-8"):
    return [_uploaded_csv(name, encoding) for name in CSV_NAMES]


def test_load_tables_from_uploads_utf8_returns_expected_tables():
    result = load_tables_from_uploads(_complete_uploads())

    assert list(result) == list(CSV_NAMES)
    assert all(isinstance(table, pd.DataFrame) for table in result.values())
    for name in CSV_NAMES:
        assert set(REQUIRED_COLUMNS[name]).issubset(result[name].columns)


def test_load_tables_from_uploads_cp949_retries_after_utf8_failure():
    result = load_tables_from_uploads(_complete_uploads(encoding="cp949"))

    assert list(result) == list(CSV_NAMES)
    assert result["audit_notes.csv"].iloc[0]["note_text"] == "값"


def test_load_tables_from_uploads_missing_file_raises_data_load_error():
    files = _complete_uploads()[:-1]

    with pytest.raises(DataLoadError, match="disclosure_clauses.csv"):
        load_tables_from_uploads(files)


def test_load_tables_from_uploads_duplicate_file_raises_data_load_error():
    files = _complete_uploads()
    files.append(_uploaded_csv(CSV_NAMES[0]))

    with pytest.raises(DataLoadError, match="중복"):
        load_tables_from_uploads(files)


def test_load_tables_from_uploads_missing_column_names_file_and_column():
    missing_column = REQUIRED_COLUMNS["hq_financials.csv"][0]
    files = [
        _uploaded_csv(
            name,
            columns=(
                [column for column in REQUIRED_COLUMNS[name] if column != missing_column]
                if name == "hq_financials.csv"
                else None
            ),
        )
        for name in CSV_NAMES
    ]

    with pytest.raises(
        DataLoadError,
        match=rf"hq_financials\.csv에 필수 열 '{missing_column}'",
    ):
        load_tables_from_uploads(files)


def test_load_tables_from_uploads_empty_file_raises_data_load_error():
    empty_file = BytesIO()
    empty_file.name = CSV_NAMES[0]
    files = [empty_file, *_complete_uploads()[1:]]

    with pytest.raises(DataLoadError, match="hq_financials.csv"):
        load_tables_from_uploads(files)


def test_load_tables_from_uploads_malformed_csv_raises_data_load_error():
    malformed_file = BytesIO(b'"unterminated\n')
    malformed_file.name = CSV_NAMES[0]
    files = [malformed_file, *_complete_uploads()[1:]]

    with pytest.raises(DataLoadError, match="hq_financials.csv"):
        load_tables_from_uploads(files)










