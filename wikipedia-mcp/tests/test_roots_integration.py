"""End-to-end tests: a real MCP client session talking to server.mcp in memory."""

import sys

import httpx
import pytest
import respx
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import (
    CreateMessageResult,
    ListRootsResult,
    Root,
    TextContent,
)
from pydantic import FileUrl

from client import make_list_roots_callback
from server import NO_ROOTS_MESSAGE, mcp


class Recorder:
    """Collects the logging and progress notifications a client receives."""

    def __init__(self):
        self.logs: list[str] = []
        self.progress: list[tuple[float, float | None, str | None]] = []

    async def logging_callback(self, params):
        self.logs.append(str(params.data))

    async def progress_callback(self, progress, total, message):
        self.progress.append((progress, total, message))


def text_of(result) -> str:
    return "\n".join(c.text for c in result.content if isinstance(c, TextContent))


@pytest.fixture
def docs(tmp_path):
    root = (tmp_path / "approved" / "docs").resolve()
    root.mkdir(parents=True)
    (root / "roots.md").write_text("MCP Roots share directories with a server.")
    return root


@pytest.mark.asyncio
async def test_core_tools_are_listed():
    async with create_connected_server_and_client_session(mcp) as session:
        names = {tool.name for tool in (await session.list_tools()).tools}

    assert {"research_and_summarize", "search_local_documents"} <= names


@pytest.mark.asyncio
async def test_server_discovers_roots_and_searches_them(docs):
    recorder = Recorder()
    async with create_connected_server_and_client_session(
        mcp,
        list_roots_callback=make_list_roots_callback([docs]),
        logging_callback=recorder.logging_callback,
    ) as session:
        result = await session.call_tool(
            "search_local_documents",
            {"query": "directories"},
            progress_callback=recorder.progress_callback,
        )

    text = text_of(result)
    assert not result.isError
    assert str(docs / "roots.md") in text
    assert "matched in: content" in text
    # logging: the approved root was announced
    assert any("Approved root" in line for line in recorder.logs)
    # progress: monotonically increasing and ends at 100
    values = [p[0] for p in recorder.progress]
    assert values == sorted(values)
    assert values[-1] == 100


@pytest.mark.asyncio
async def test_client_without_roots_support_gets_clear_message():
    recorder = Recorder()
    async with create_connected_server_and_client_session(
        mcp, logging_callback=recorder.logging_callback
    ) as session:
        result = await session.call_tool("search_local_documents", {"query": "x"})

    assert text_of(result) == NO_ROOTS_MESSAGE
    assert any("does not support MCP Roots" in line for line in recorder.logs)


@pytest.mark.asyncio
async def test_empty_roots_list_gets_clear_message():
    async with create_connected_server_and_client_session(
        mcp, list_roots_callback=make_list_roots_callback([])
    ) as session:
        result = await session.call_tool("search_local_documents", {"query": "x"})

    assert text_of(result) == NO_ROOTS_MESSAGE


@pytest.mark.asyncio
async def test_non_file_and_missing_roots_are_ignored(docs, tmp_path):
    async def callback(context):
        return ListRootsResult(
            roots=[
                Root(uri=FileUrl("file:///definitely/not/here"), name="missing"),
                Root(uri=FileUrl((tmp_path / "nope").as_uri()), name="nope"),
            ]
        )

    recorder = Recorder()
    async with create_connected_server_and_client_session(
        mcp,
        list_roots_callback=callback,
        logging_callback=recorder.logging_callback,
    ) as session:
        result = await session.call_tool("search_local_documents", {"query": "x"})

    assert text_of(result) == NO_ROOTS_MESSAGE
    assert sum("Ignoring root" in line for line in recorder.logs) == 2


@pytest.mark.asyncio
async def test_traversal_style_root_uri_only_exposes_its_resolved_directory(docs):
    (docs.parent / "top.md").write_text("directories (outside the docs folder)")

    async def callback(context):
        # .../approved/docs/../docs  -> resolves to .../approved/docs
        return ListRootsResult(
            roots=[Root(uri=FileUrl((docs / ".." / "docs").as_uri()), name="docs")]
        )

    async with create_connected_server_and_client_session(
        mcp, list_roots_callback=callback
    ) as session:
        result = await session.call_tool(
            "search_local_documents", {"query": "directories"}
        )

    text = text_of(result)
    assert str(docs / "roots.md") in text
    assert "top.md" not in text


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges")
async def test_symlink_escape_is_blocked_over_the_protocol(docs, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("directories: TOP SECRET")
    (docs / "innocent.txt").symlink_to(secret)

    async with create_connected_server_and_client_session(
        mcp, list_roots_callback=make_list_roots_callback([docs])
    ) as session:
        result = await session.call_tool(
            "search_local_documents", {"query": "directories"}
        )

    text = text_of(result)
    assert "TOP SECRET" not in text
    assert "innocent.txt" not in text
    assert str(docs / "roots.md") in text


@pytest.mark.asyncio
async def test_no_match_message_and_blank_query(docs):
    async with create_connected_server_and_client_session(
        mcp, list_roots_callback=make_list_roots_callback([docs])
    ) as session:
        none = await session.call_tool(
            "search_local_documents", {"query": "zzz-no-such-text"}
        )
        blank = await session.call_tool("search_local_documents", {"query": "  "})

    assert "No documents matched" in text_of(none)
    assert blank.isError


@pytest.mark.asyncio
async def test_max_results_is_respected(docs):
    for i in range(6):
        (docs / f"extra{i}.md").write_text("directories")

    async with create_connected_server_and_client_session(
        mcp, list_roots_callback=make_list_roots_callback([docs])
    ) as session:
        result = await session.call_tool(
            "search_local_documents", {"query": "directories", "max_results": 2}
        )

    assert "Found 2 document(s)" in text_of(result)


# ---------- regression: existing features still work over the real protocol ----------


@pytest.mark.asyncio
@respx.mock
async def test_wikipedia_research_still_samples_logs_and_reports_progress():
    respx.get("https://en.wikipedia.org/w/rest.php/v1/search/page").mock(
        return_value=httpx.Response(
            200, json={"pages": [{"title": "Ada Lovelace", "excerpt": "Mathematician"}]}
        )
    )
    respx.get("https://en.wikipedia.org/api/rest_v1/page/summary/Ada_Lovelace").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Ada Lovelace",
                "extract": "Ada Lovelace was an English mathematician.",
                "content_urls": {
                    "desktop": {"page": "https://en.wikipedia.org/wiki/Ada_Lovelace"}
                },
            },
        )
    )
    sampled_prompts: list[str] = []

    async def sampling_callback(context, params):
        sampled_prompts.append(params.messages[-1].content.text)
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text="SUMMARY FROM STUB LLM"),
            model="stub-model",
        )

    recorder = Recorder()
    async with create_connected_server_and_client_session(
        mcp,
        sampling_callback=sampling_callback,
        logging_callback=recorder.logging_callback,
    ) as session:
        result = await session.call_tool(
            "research_and_summarize",
            {"topic": "Ada Lovelace", "max_articles": 1},
            progress_callback=recorder.progress_callback,
        )

    assert text_of(result) == "SUMMARY FROM STUB LLM"
    assert "Ada Lovelace was an English mathematician." in sampled_prompts[0]
    assert any("Retrieved 1 Wikipedia article" in line for line in recorder.logs)
    assert recorder.progress[-1][0] == 100
