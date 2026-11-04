import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    ListRootsResult,
    LoggingMessageNotificationParams,
    ProgressNotificationParams,
    Root,
    TextContent,
)
from pydantic import FileUrl

from llm_providers import complete, resolve_provider

load_dotenv()


def parse_roots(
    argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None
) -> list[Path]:
    """Choose which directories to share: --root (repeatable), else MCP_ROOTS."""
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description="Wikipedia research MCP client.")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        metavar="DIR",
        help="Directory to share with the server via MCP Roots (repeatable).",
    )
    args = parser.parse_args(argv)

    raw = args.root or [
        item for item in (env.get("MCP_ROOTS") or "").split(os.pathsep) if item.strip()
    ]

    roots: list[Path] = []
    for item in raw:
        try:
            path = Path(item.strip()).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            raise SystemExit(f"Root path does not exist: {item}") from None
        if not path.is_dir():
            raise SystemExit(f"Root path is not a directory: {item}")
        if path not in roots:
            roots.append(path)
    return roots


def make_list_roots_callback(paths: Sequence[Path]):
    """Build the MCP Roots callback that returns the user-selected directories."""
    roots = [
        Root(uri=FileUrl(path.as_uri()), name=path.name or str(path)) for path in paths
    ]

    async def list_roots_callback(context) -> ListRootsResult:
        del context
        return ListRootsResult(roots=list(roots))

    return list_roots_callback


def sampling_messages(params: CreateMessageRequestParams) -> list[dict[str, str]]:
    """Convert MCP sampling messages into role/content dicts.

    The same shape is accepted by both the Anthropic Messages API and the
    OpenAI Chat Completions API.
    """
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

    try:
        config = resolve_provider()
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    system_prompt = getattr(params, "system_prompt", None) or (
        "You are a helpful research assistant. Summarize faithfully and cite sources."
    )
    max_tokens = getattr(params, "max_tokens", None) or 1200

    text, model = await complete(
        config,
        system_prompt=system_prompt,
        messages=messages,
        max_tokens=min(int(max_tokens), 2000),
    )
    if not text:
        raise RuntimeError("The model returned no text.")

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=text),
        model=model,
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

async def run_wikipedia_research(session: ClientSession) -> None:
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


async def run_local_search(session: ClientSession) -> None:
    query = input("\nSearch query: ").strip()
    result = await session.call_tool(
        "search_local_documents",
        arguments={"query": query},
        progress_callback=progress_callback,
    )
    for content in result.content:
        if isinstance(content, TextContent):
            print("\n=== LOCAL DOCUMENT RESULTS ===\n")
            print(content.text)


async def main(argv: Sequence[str] | None = None) -> None:
    root_paths = parse_roots(argv)
    try:
        config = resolve_provider()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        f"Using LLM provider: {config.name} (model {config.model})",
        file=sys.stderr,
    )

    if root_paths:
        print(f"Sharing {len(root_paths)} director(y/ies) via MCP Roots:", file=sys.stderr)
        for path in root_paths:
            print(f"- {path.name or path} -> {path.as_uri()}", file=sys.stderr)
    else:
        print(
            "No directories shared via MCP Roots (local search will find nothing). "
            "Use --root DIR or MCP_ROOTS to share one.",
            file=sys.stderr,
        )

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
            list_roots_callback=make_list_roots_callback(root_paths),
        ) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Connected MCP tools:", file=sys.stderr)
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}", file=sys.stderr)

            print("\nWhat would you like to do?")
            print("  [1] Wikipedia research (default)")
            print("  [2] Search local documents")
            choice = input("Choice [1]: ").strip() or "1"
            if choice == "1":
                await run_wikipedia_research(session)
            elif choice == "2":
                await run_local_search(session)
            else:
                raise SystemExit(f"Unknown choice: {choice}")


if __name__ == "__main__":
    asyncio.run(main())
