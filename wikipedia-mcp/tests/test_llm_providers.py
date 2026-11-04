import json

import httpx
import pytest
import respx

from llm_providers import ProviderConfig, complete, resolve_provider


# ---------- resolve_provider ----------


def test_only_anthropic_key():
    cfg = resolve_provider({"ANTHROPIC_API_KEY": "a"})
    assert cfg == ProviderConfig("anthropic", "a", "claude-sonnet-4-5")


def test_only_openai_key():
    cfg = resolve_provider({"OPENAI_API_KEY": "o"})
    assert cfg == ProviderConfig("openai", "o", "gpt-4.1-mini")


def test_both_keys_default_to_anthropic():
    cfg = resolve_provider({"ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o"})
    assert cfg.name == "anthropic"


def test_explicit_provider_overrides_autodetect():
    cfg = resolve_provider(
        {"LLM_PROVIDER": "openai", "ANTHROPIC_API_KEY": "a", "OPENAI_API_KEY": "o"}
    )
    assert cfg.name == "openai"
    assert cfg.api_key == "o"


def test_provider_name_is_case_insensitive():
    cfg = resolve_provider({"LLM_PROVIDER": " OpenAI ", "OPENAI_API_KEY": "o"})
    assert cfg.name == "openai"


def test_explicit_provider_without_its_key_fails():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        resolve_provider({"LLM_PROVIDER": "openai", "ANTHROPIC_API_KEY": "a"})


def test_invalid_provider_fails():
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        resolve_provider({"LLM_PROVIDER": "gemini", "ANTHROPIC_API_KEY": "a"})


def test_no_keys_fails():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY or OPENAI_API_KEY"):
        resolve_provider({})


def test_empty_strings_are_treated_as_unset():
    cfg = resolve_provider(
        {
            "LLM_PROVIDER": "",
            "ANTHROPIC_API_KEY": "  ",
            "OPENAI_API_KEY": "o",
            "OPENAI_MODEL": "",
        }
    )
    assert cfg == ProviderConfig("openai", "o", "gpt-4.1-mini")


def test_model_override():
    cfg = resolve_provider({"OPENAI_API_KEY": "o", "OPENAI_MODEL": "gpt-4.1"})
    assert cfg.model == "gpt-4.1"


# ---------- complete ----------


@pytest.mark.asyncio
@respx.mock
async def test_complete_openai_puts_system_first_and_parses_text():
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4.1-mini-2025",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": " Summary "},
                    }
                ],
            },
        )
    )
    cfg = ProviderConfig("openai", "o", "gpt-4.1-mini")

    text, model = await complete(
        cfg, "be careful", [{"role": "user", "content": "hi"}], 100
    )

    assert (text, model) == ("Summary", "gpt-4.1-mini-2025")
    body = json.loads(route.calls.last.request.content)
    assert body["messages"][0] == {"role": "system", "content": "be careful"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert body["max_completion_tokens"] == 100


@pytest.mark.asyncio
@respx.mock
async def test_complete_anthropic_uses_top_level_system_and_parses_text():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-5-2025",
                "content": [{"type": "text", "text": "Summary"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )
    )
    cfg = ProviderConfig("anthropic", "a", "claude-sonnet-4-5")

    text, model = await complete(
        cfg, "be careful", [{"role": "user", "content": "hi"}], 100
    )

    assert (text, model) == ("Summary", "claude-sonnet-4-5-2025")
    body = json.loads(route.calls.last.request.content)
    assert body["system"] == "be careful"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["max_tokens"] == 100


@pytest.mark.asyncio
@respx.mock
async def test_complete_openai_empty_content_returns_empty_text():
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-2",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": None},
                    }
                ],
            },
        )
    )
    cfg = ProviderConfig("openai", "o", "gpt-4.1-mini")

    text, _ = await complete(cfg, "s", [{"role": "user", "content": "hi"}], 10)

    assert text == ""
