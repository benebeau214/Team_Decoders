from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

import franchise_checkup.app as app_module
from franchise_checkup.app import format_percent, get_upload_signature


APP_PATH = Path(app_module.__file__).resolve()


def visible_text(at: AppTest) -> str:
    """AppTest 화면에 표시된 주요 텍스트를 하나의 문자열로 모은다."""
    element_names = (
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "text",
        "info",
        "warning",
        "error",
        "success",
    )
    values: list[str] = []

    for element_name in element_names:
        for element in getattr(at, element_name):
            values.append(str(element.value))

    return "\n".join(values)


def test_initial_screen_requests_csv_upload() -> None:
    """업로드 전에는 필수 CSV 안내를 표시하고 앱 오류가 발생하지 않는다."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=10).run()

    assert not at.exception
    assert "필수 CSV 파일 5종" in visible_text(at)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12.345, "12.3%"),
        (0, "0.0%"),
        (None, "확인 필요"),
        ("not-a-number", "확인 필요"),
        (float("nan"), "확인 필요"),
        (float("inf"), "확인 필요"),
    ],
)
def test_format_percent(value: object, expected: str) -> None:
    """백분율 표시 함수가 정상 숫자와 잘못된 값을 구분한다."""
    assert format_percent(value) == expected


def test_upload_signature_is_order_independent_and_content_sensitive() -> None:
    """파일 순서에는 영향받지 않고 파일 내용 변경은 감지한다."""
    file_a = SimpleNamespace(name="a.csv", getvalue=lambda: b"a,1")
    file_b = SimpleNamespace(name="b.csv", getvalue=lambda: b"b,2")
    changed_a = SimpleNamespace(name="a.csv", getvalue=lambda: b"a,changed")

    assert get_upload_signature([file_a, file_b]) == get_upload_signature(
        [file_b, file_a]
    )
    assert get_upload_signature([file_a, file_b]) != get_upload_signature(
        [changed_a, file_b]
    )
