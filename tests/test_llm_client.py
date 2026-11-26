"""Verify mock selection without making network requests."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import llm_client


@pytest.mark.parametrize("setting, expected", [(None, True), ("true", True), ("  YES ", True), ("1", True), ("false", False), ("0", False)])
def test_mode_is_read_from_environment_on_each_call(monkeypatch, setting, expected):
    monkeypatch.setenv("USE_MOCK", "false" if expected else "true")
    monkeypatch.setattr(llm_client, "_mock_llm_call", lambda prompt: "mock")
    monkeypatch.setattr(llm_client, "_real_llm_call", lambda prompt: "real")
    assert llm_client.llm_call("prompt") == ("real" if expected else "mock")

    if setting is None:
        monkeypatch.delenv("USE_MOCK")
    else:
        monkeypatch.setenv("USE_MOCK", setting)

    assert llm_client.llm_call("prompt") == ("mock" if expected else "real")


@pytest.mark.parametrize("prompt", ["<report_text> 사용자 유형: 예비", "<note_text>demo</note_text>", "<clause_text>demo</clause_text>"])
def test_mock_preserves_existing_json_responses(monkeypatch, prompt):
    monkeypatch.setenv("USE_MOCK", "true")
    result = llm_client.llm_call(prompt)
    assert result == llm_client._mock_llm_call(prompt)
    assert isinstance(json.loads(result), dict)


@pytest.mark.parametrize(
    "prompt, path",
    [
        ("<report_text> 사용자 유형: 예비", ("summary",)),
        ("<clause_text>demo</clause_text>", ("items", 0, "reason")),
    ],
)
def test_mock_free_text_is_marked(prompt, path):
    value = json.loads(llm_client._mock_llm_call(prompt))
    for key in path:
        value = value[key]
    assert value.startswith(llm_client.MOCK_MARKER)


def test_real_mode_requires_api_key_without_mock_fallback(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMCallError, match="ANTHROPIC_API_KEY"):
        llm_client.llm_call("prompt")


def test_real_mode_sends_prompt_and_returns_text(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "false")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "256")
    sdk_factory = Mock()
    create_message = sdk_factory.return_value.messages.create
    create_message.return_value = SimpleNamespace(content=[
        SimpleNamespace(type="text", text=" hello"),
        SimpleNamespace(type="thinking"),
        SimpleNamespace(type="text", text=" world "),
    ])
    monkeypatch.setattr(llm_client.anthropic, "Anthropic", sdk_factory)

    assert llm_client.llm_call("example") == "hello world"
    sdk_factory.assert_called_once_with(api_key="test-key", timeout=30.0)
    create_message.assert_called_once_with(
        model="test-model",
        max_tokens=256,
        messages=[{"role": "user", "content": "example"}],
    )
