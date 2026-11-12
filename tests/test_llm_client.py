"""Verify mock selection without making network requests."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import llm_client


@pytest.mark.parametrize("setting, expected", [(None, True), ("true", True), ("  YES ", True), ("1", True), ("false", False), ("0", False)])
def test_mode_is_loaded_from_environment_at_startup(setting, expected):
    env = os.environ.copy()
    if setting is None:
        env.pop("USE_MOCK", None)
    else:
        env["USE_MOCK"] = setting
    result = subprocess.check_output(
        [sys.executable, "-c", "import llm_client; print(llm_client.USE_MOCK)"],
        cwd=Path(llm_client.__file__).parent, env=env, text=True,
    )
    assert result.strip() == str(expected)


@pytest.mark.parametrize("prompt", ["<report_text> 사용자 유형: 예비", "<note_text>demo</note_text>", "<clause_text>demo</clause_text>"])
def test_mock_preserves_existing_json_responses(monkeypatch, prompt):
    monkeypatch.setattr(llm_client, "USE_MOCK", True)
    result = llm_client.llm_call(prompt)
    assert result == llm_client._mock_llm_call(prompt)
    assert isinstance(json.loads(result), dict)


def test_real_mode_reports_unimplemented_api_without_mock_fallback(monkeypatch):
    monkeypatch.setattr(llm_client, "USE_MOCK", False)
    with pytest.raises(llm_client.LLMCallError, match="not connected"):
        llm_client.llm_call("prompt")


def test_real_mode_can_use_future_adapter(monkeypatch):
    monkeypatch.setattr(llm_client, "USE_MOCK", False)
    monkeypatch.setattr(llm_client, "_real_llm_call", lambda prompt: json.dumps({"prompt": prompt}))
    assert json.loads(llm_client.llm_call("example")) == {"prompt": "example"}
