import pandas as pd
import math
from pandas.errors import EmptyDataError, ParserError


def load_csv_table(filepath: str, required_cols: list[str]) -> pd.DataFrame:
    """Load a comma- or semicolon-delimited CSV and validate required columns."""
    try:
        try:
            data = pd.read_csv(filepath, encoding="utf-8", sep=None, engine="python")
        except UnicodeDecodeError:
            try:
                data = pd.read_csv(
                    filepath,
                    encoding="cp949",
                    sep=None,
                    engine="python",
                )
            except UnicodeDecodeError as cp949_error:
                raise ValueError(
                    f"CSV file could not be decoded as UTF-8 or CP949: {filepath}"
                ) from cp949_error
    except EmptyDataError as error:
        raise ValueError(f"CSV file has no header row: {filepath}") from error
    except ParserError as error:
        raise ValueError(
            f"CSV file could not be parsed as comma- or semicolon-delimited data: "
            f"{filepath}"
        ) from error

    missing_cols = [column for column in required_cols if column not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

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

    if raw["user_type"] not in ("예비", "기존"):
        raise ValueError("user_type must be '예비' or '기존'")

    return {
        "brand": normalized_brand.strip(),
        "region": normalized_region.strip(),
        **normalized_values,
        "user_type": raw["user_type"],
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
    if "avg_annual_sales" not in disc_row:
        raise ValueError("disc_row must contain avg_annual_sales")
    if not {"region", "avg_annual_sales"}.issubset(region_rows.columns):
        raise ValueError(
            "region_rows must contain region and avg_annual_sales columns"
        )

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