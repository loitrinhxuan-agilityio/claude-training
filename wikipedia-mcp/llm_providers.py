"""Provider selection and completion calls for the MCP sampling client.

The MCP server never talks to an LLM; the client does, on its behalf. This
module lets the client use either Anthropic or OpenAI, chosen from env vars.
"""

import os
from dataclasses import dataclass
from typing import Mapping

PROVIDERS = ("anthropic", "openai")

_KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_MODEL_VARS = {"anthropic": "ANTHROPIC_MODEL", "openai": "OPENAI_MODEL"}
_DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-5", "openai": "gpt-4.1-mini"}


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str
    model: str


def _get(env: Mapping[str, str], key: str) -> str:
    """Return a stripped env value; empty or whitespace-only counts as unset."""
    return (env.get(key) or "").strip()


def _build(name: str, env: Mapping[str, str]) -> ProviderConfig:
    api_key = _get(env, _KEY_VARS[name])
    if not api_key:
        raise ValueError(
            f"{_KEY_VARS[name]} is required when using the {name} provider. "
            "Set it in .env."
        )
    model = _get(env, _MODEL_VARS[name]) or _DEFAULT_MODELS[name]
    return ProviderConfig(name=name, api_key=api_key, model=model)


def resolve_provider(env: Mapping[str, str] | None = None) -> ProviderConfig:
    """Pick the LLM provider.

    Order: explicit LLM_PROVIDER, then ANTHROPIC_API_KEY, then OPENAI_API_KEY.
    Anthropic wins when both keys are set and LLM_PROVIDER is not, which keeps
    the original behaviour.
    """
    env = os.environ if env is None else env

    explicit = _get(env, "LLM_PROVIDER").lower()
    if explicit:
        if explicit not in PROVIDERS:
            raise ValueError(
                f"Unsupported LLM_PROVIDER '{explicit}'. "
                f"Use one of: {', '.join(PROVIDERS)}."
            )
        return _build(explicit, env)

    for name in PROVIDERS:
        if _get(env, _KEY_VARS[name]):
            return _build(name, env)

    raise ValueError(
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
        "(optionally LLM_PROVIDER) in .env before running."
    )


async def _complete_anthropic(
    config: ProviderConfig,
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, str]:
    from anthropic import AsyncAnthropic

    # Anthropic accepts the system prompt separately from conversation messages.
    async with AsyncAnthropic(api_key=config.api_key) as anthropic:
        response = await anthropic.messages.create(
            model=config.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )

    text = "\n".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()
    return text, response.model


async def _complete_openai(
    config: ProviderConfig,
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, str]:
    from openai import AsyncOpenAI

    # OpenAI takes the system prompt as the first chat message.
    # max_completion_tokens is accepted by all current chat models, whereas
    # max_tokens is rejected by newer reasoning models.
    async with AsyncOpenAI(api_key=config.api_key) as openai:
        response = await openai.chat.completions.create(
            model=config.model,
            max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system_prompt}, *messages],
        )

    text = (response.choices[0].message.content or "").strip()
    return text, response.model


async def complete(
    config: ProviderConfig,
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, str]:
    """Run one completion and return (text, model_name). Text may be empty."""
    if config.name == "anthropic":
        return await _complete_anthropic(config, system_prompt, messages, max_tokens)
    if config.name == "openai":
        return await _complete_openai(config, system_prompt, messages, max_tokens)
    raise ValueError(f"Unsupported provider '{config.name}'.")
