"""LiteLLM client: config reading and structured-output parsing.

`complete` is bound at import time so these tests exercise the real function even
though the autouse `no_network` fixture replaces the module attribute.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.chat import llm
from app.chat.llm import complete

pytestmark = pytest.mark.usefixtures("no_network")


def _install_fake_litellm(monkeypatch: pytest.MonkeyPatch, content: str | None):
    """Stand in for the litellm module `complete` imports lazily."""
    captured: dict[str, object] = {}

    async def _acompletion(**kwargs: object) -> object:
        captured.update(kwargs)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    module = types.SimpleNamespace(acompletion=_acompletion)
    monkeypatch.setitem(sys.modules, "litellm", module)
    return captured


def test_is_mock_enabled_reads_truthy_values(monkeypatch: pytest.MonkeyPatch):
    for value, expected in [("true", True), ("TRUE", True), ("1", True), ("false", False)]:
        monkeypatch.setenv("LLM_MOCK", value)
        assert llm.is_mock_enabled() is expected

    monkeypatch.delenv("LLM_MOCK")
    assert llm.is_mock_enabled() is False


async def test_complete_parses_valid_structured_output(monkeypatch: pytest.MonkeyPatch):
    captured = _install_fake_litellm(
        monkeypatch,
        '{"message": "hi", "trades": [{"ticker": "aapl", "side": "buy", "quantity": 3}]}',
    )

    output = await complete([{"role": "user", "content": "hi"}])

    assert captured["model"] == llm.MODEL
    assert output.trades[0].ticker == "AAPL"


async def test_complete_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch):
    _install_fake_litellm(monkeypatch, "not json at all")

    with pytest.raises(llm.LlmError):
        await complete([])


async def test_complete_rejects_schema_violations(monkeypatch: pytest.MonkeyPatch):
    _install_fake_litellm(monkeypatch, '{"message": "hi", "trades": [{"ticker": "AAPL"}]}')

    with pytest.raises(llm.LlmError):
        await complete([])


async def test_complete_rejects_empty_content(monkeypatch: pytest.MonkeyPatch):
    _install_fake_litellm(monkeypatch, None)

    with pytest.raises(llm.LlmError):
        await complete([])


async def test_complete_wraps_provider_exceptions(monkeypatch: pytest.MonkeyPatch):
    async def _boom(**kwargs: object) -> None:
        raise TimeoutError("provider timeout")

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(acompletion=_boom))

    with pytest.raises(llm.LlmError):
        await complete([])
