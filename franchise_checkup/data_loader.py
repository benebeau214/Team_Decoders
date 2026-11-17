import pandas as pd
import math
from pandas.errors import EmptyDataError, ParserError
import csv
import math
from io import StringIO
from collections.abc import Iterable
from typing import Any

CSV_NAMES = (
    "hq_financials.csv",
    "franchise_disclosure.csv",
    "region_sales.csv",
    "audit_notes.csv",
    "disclosure_clauses.csv",
)

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


class DataLoadError(Exception):
    """업로드 CSV를 읽거나 검증할 수 없을 때 발생하는 예외."""


def load_tables_from_uploads(
    uploaded_files: Iterable[Any],
) -> dict[str, pd.DataFrame]:
    """Load and validate the required CSV tables from uploaded file objects."""
    try:
        files = list(uploaded_files)
    except TypeError as error:
        raise DataLoadError("업로드 파일 목록을 읽을 수 없습니다.") from error

    files_by_name: dict[str, Any] = {}
    for uploaded_file in files:
        name = getattr(uploaded_file, "name", None)
        if not isinstance(name, str) or not name.strip():
            raise DataLoadError("업로드 파일 이름을 확인할 수 없습니다.")
        if name in files_by_name:
            raise DataLoadError(f"{name} 파일이 중복 업로드되었습니다.")
        files_by_name[name] = uploaded_file

    missing_files = [name for name in CSV_NAMES if name not in files_by_name]
    if missing_files:
        raise DataLoadError(
            f"필수 파일이 누락되었습니다: {', '.join(missing_files)}"
        )

    tables: dict[str, pd.DataFrame] = {}
    for name in CSV_NAMES:
        tables[name] = _load_uploaded_csv(
            files_by_name[name],
            name,
            REQUIRED_COLUMNS[name],
        )
    return tables


def _load_uploaded_csv(
    uploaded_file: Any,
    filename: str,
    required_columns: list[str],
) -> pd.DataFrame:
    """Read one uploaded CSV with UTF-8 and CP949 fallback."""
    try:
        uploaded_file.seek(0)
        raw_data = uploaded_file.read()
    except (AttributeError, OSError, TypeError) as error:
        raise DataLoadError(f"{filename} 파일을 읽을 수 없습니다.") from error

    if not raw_data:
        raise DataLoadError(f"{filename} 파일이 비어 있습니다.")
    if isinstance(raw_data, str):
        decoded = raw_data
    elif isinstance(raw_data, bytes):
        try:
            decoded = raw_data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                raw_data = uploaded_file.read()
                decoded = raw_data.decode("cp949")
            except (AttributeError, OSError, TypeError, UnicodeDecodeError) as error:
                raise DataLoadError(
                    f"{filename} 파일을 UTF-8 또는 CP949로 읽을 수 없습니다."
                ) from error
    else:
        raise DataLoadError(f"{filename} 파일 형식을 처리할 수 없습니다.")

    if not decoded.strip():
        raise DataLoadError(f"{filename} 파일이 비어 있습니다.")

    try:
        try:
            dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
        table = pd.read_csv(StringIO(decoded), sep=delimiter)
    except (EmptyDataError, ParserError, UnicodeDecodeError, csv.Error) as error:
        raise DataLoadError(f"{filename} CSV 형식이 올바르지 않습니다.") from error

    missing_columns = [
        column for column in required_columns if column not in table.columns
    ]
    if missing_columns:
        missing = "', '".join(missing_columns)
        raise DataLoadError(
            f"{filename}에 필수 열 '{missing}'가 없습니다."
        )
    return table


def load_csv_table(filepath: str, required_cols: list[str]) -> pd.DataFrame:
    """Load a comma- or semicolon-delimited CSV and validate required columns."""

    # 수정 1: required_cols 자료형 검증
    if not isinstance(required_cols, list) or not all(
        isinstance(col, str) and col.strip() for col in required_cols
    ):
        raise ValueError("required_cols must be a list of non-empty strings")

    # 수정 2: 지원 구분자 확인
    try:
        try:
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                sample = f.read(4096)
            encoding = "utf-8"
        except UnicodeDecodeError:
            with open(filepath, "r", encoding="cp949", newline="") as f:
                sample = f.read(4096)
            encoding = "cp949"

        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            delimiter = dialect.delimiter
        except csv.Error:
            # 단일 열 CSV도 허용
            delimiter = ","

        data = pd.read_csv(
            filepath,
            encoding=encoding,
            sep=delimiter,
        )

    except EmptyDataError as error:
        raise ValueError(
            f"CSV file has no header row: {filepath}"
        ) from error
    except ParserError as error:
        raise ValueError(
            f"CSV file could not be parsed: {filepath}"
        ) from error
    except UnicodeDecodeError as error:
        raise ValueError(
            f"CSV file could not be decoded as UTF-8 or CP949: {filepath}"
        ) from error

    missing_cols = [
        col for col in required_cols
        if col not in data.columns
    ]

    if missing_cols:
        raise ValueError(
            f"Missing required columns: {', '.join(missing_cols)}"
        )

    return data


def validate_user_input(raw: dict) -> dict:
    """Validate and normalize franchise financial health-check user input."""
    required_keys = (
        "brand",
        "region",
        "deposit",
        "key_money",
        "loan_amount",
        "loan_rate",
        "user_type",
    )

    if not isinstance(raw, dict):
        raise ValueError("raw must be a dict")

    missing_keys = [key for key in required_keys if key not in raw]
    if missing_keys:
        raise ValueError(f"Missing required keys: {', '.join(missing_keys)}")

    normalized_brand = raw["brand"]
    normalized_region = raw["region"]
    if not isinstance(normalized_brand, str) or not normalized_brand.strip():
        raise ValueError("brand must be a non-empty string")
    if not isinstance(normalized_region, str) or not normalized_region.strip():
        raise ValueError("region must be a non-empty string")

    normalized_values = {}
    for key in ("deposit", "key_money", "loan_amount", "loan_rate"):
        value = raw[key]
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a finite number")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{key} must be a finite number") from error
        if not math.isfinite(numeric_value):
            raise ValueError(f"{key} must be a finite number")
        normalized_values[key] = numeric_value

    for key in ("deposit", "key_money", "loan_amount"):
        if normalized_values[key] < 0:
            raise ValueError(f"{key} must be at least 0")
    if not 0 <= normalized_values["loan_rate"] <= 100:
        raise ValueError("loan_rate must be between 0 and 100")

    # 수정 1: 사용자 유형 자료형 검증
    if not isinstance(raw["user_type"], str):
        raise ValueError("user_type must be a string")

    # 수정 2: 사용자 유형의 앞뒤 공백 제거
    normalized_user_type = raw["user_type"].strip()

    if normalized_user_type not in ("예비", "기존"):
        raise ValueError("user_type must be '예비' or '기존'")

    return {
        "brand": normalized_brand.strip(),
        "region": normalized_region.strip(),
        **normalized_values,
        "user_type": normalized_user_type,
    }


def select_avg_sales(
    disc_row: dict,
    region_rows: pd.DataFrame,
    region: str
) -> dict:
    """Select a valid regional average sale or fall back to the national value."""
    if not isinstance(region, str) or not region.strip():
        raise ValueError("region must be a non-empty string")
    if not isinstance(disc_row, dict):
        raise ValueError("disc_row must be a dict")
    if not isinstance(region_rows, pd.DataFrame):
        raise ValueError("region_rows must be a pandas DataFrame")
    if not {"region", "avg_annual_sales"}.issubset(region_rows.columns):
        raise ValueError(
            "region_rows must contain region and avg_annual_sales columns"
        )

    # 수정 1: 지역명 앞뒤 공백 제거
    region = region.strip()

    matching_rows = region_rows.loc[region_rows["region"] == region]
    if len(matching_rows) > 1:
        raise ValueError(f"Duplicate regional data found for region: {region}")

    if len(matching_rows) == 1:
        regional_value = matching_rows.iloc[0]["avg_annual_sales"]
        if not isinstance(regional_value, bool):
            try:
                regional_value = float(regional_value)
            except (TypeError, ValueError):
                regional_value = None
            if regional_value is not None and math.isfinite(regional_value):
                if regional_value > 0:
                    return {"value": regional_value, "basis": region}

    # 수정 2: 전국 평균매출이 실제로 필요할 때 검증
    if "avg_annual_sales" not in disc_row:
        raise ValueError("disc_row must contain avg_annual_sales")

    national_value = disc_row["avg_annual_sales"]
    if isinstance(national_value, bool):
        raise ValueError("National average sales must be a positive finite number")
    try:
        national_value = float(national_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "National average sales must be a positive finite number"
        ) from error
    if not math.isfinite(national_value) or national_value <= 0:
        raise ValueError("National average sales must be a positive finite number")

    return {"value": national_value, "basis": "전국"}
