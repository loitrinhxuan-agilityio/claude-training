import asyncio
import os
import sys

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    LoggingMessageNotificationParams,
    ProgressNotificationParams,
    TextContent,
)
from anthropic import AsyncAnthropic

load_dotenv()


def sampling_messages(params: CreateMessageRequestParams) -> list[dict[str, str]]:
    """Convert MCP sampling messages into Anthropic Messages API messages."""
    converted: list[dict[str, str]] = []
    for item in params.messages:
        if not isinstance(item.content, TextContent):
            raise ValueError("This demo supports text-only sampling messages.")
        role = "assistant" if item.role == "assistant" else "user"
        converted.append({"role": role, "content": item.content.text})
    return converted


async def sampling_callback(
    context, params: CreateMessageRequestParams
) -> CreateMessageResult:
    """Approve and execute the model request on behalf of the MCP server."""
    del context
    messages = sampling_messages(params)
    preview = messages[-1]["content"][:700] if messages else "(empty prompt)"

    print("\n[MCP Sampling request]", file=sys.stderr)
    print("The server asks this client to send source material to an LLM.", file=sys.stderr)
    print(f"Prompt preview:\n{preview}\n", file=sys.stderr)
    approval = await asyncio.to_thread(input, "Approve model request? [y/N]: ")
    if approval.strip().lower() not in {"y", "yes"}:
        raise PermissionError("Sampling request declined by user.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required by the client.")

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    system_prompt = getattr(params, "system_prompt", None) or (
        "You are a helpful research assistant. Summarize faithfully and cite sources."
    )
    max_tokens = getattr(params, "max_tokens", None) or 1200

    # Anthropic accepts the system prompt separately from conversation messages.
    async with AsyncAnthropic(api_key=api_key) as anthropic:
        response = await anthropic.messages.create(
            model=model,
            max_tokens=min(int(max_tokens), 2000),
            system=system_prompt,
            messages=messages,
        )

    text = "\n".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()
    if not text:
        raise RuntimeError("The model returned no text.")

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=text),
        model=response.model,
    )


async def logging_callback(params: LoggingMessageNotificationParams) -> None:
    """Display server log notifications without polluting stdout."""
    level = getattr(params, "level", "info")
    logger = getattr(params, "logger", None)
    data = getattr(params, "data", "")
    prefix = f"[{str(level).upper()}]"
    if logger:
        prefix += f" [{logger}]"
    print(f"{prefix} {data}", file=sys.stderr)


async def progress_callback(
    progress: float,
    total: float | None,
    message: str | None,
) -> None:
    if total is not None and total > 0:
        percentage = (progress / total) * 100
        print(
            f"[PROGRESS] {percentage:5.1f}% "
            f"({progress}/{total}) — {message or 'Working...'}"
        )
    else:
        print(
            f"[PROGRESS] {progress} — "
            f"{message or 'Working...'}"
        )

async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY in .env before running.")

    server = StdioServerParameters(
        command="uv",
        args=["run", "python", "server.py"],
        env=None,
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(
            read_stream,
            write_stream,
            sampling_callback=sampling_callback,
            logging_callback=logging_callback,
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Connected MCP tools:", file=sys.stderr)
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}", file=sys.stderr)

            topic = input("\nWikipedia topic to research: ").strip()
            result = await session.call_tool(
                "research_and_summarize",
                arguments={"topic": topic},
                progress_callback=progress_callback,
            )
            for content in result.content:
                if isinstance(content, TextContent):
                    print("\n=== RESEARCH SUMMARY ===\n")
                    print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
