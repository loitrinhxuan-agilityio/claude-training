# Wikipedia Research & Summarization MCP Server

An educational MCP project based on the Claude Academy **Model Context Protocol: Advanced Topics** course. It combines:

- **Sampling:** the server asks the connected client to run an LLM completion.
- **Logging notifications:** the server sends stage updates through MCP logging.
- **Progress notifications:** the server reports progress while the tool runs.
- **Roots:** the client shares chosen local directories and the server searches `.md`/`.txt` documents inside them.

The included reference client uses either the **Anthropic Messages API** or the **OpenAI Chat Completions API** for Sampling (your choice, via environment variables) and asks for user approval before sending Wikipedia source material to the model.

## Architecture

```text
User
  |
MCP Client (client.py)
  | tools/call + progress callback
MCP Server (server.py) ----> Wikipedia REST API
  |  logging/progress notifications
  |
  | sampling request
  v
MCP Client -- user approval --> Anthropic / OpenAI API
  |
  +---- sampling result back to MCP Server
```

## Protocol-version note

This is a course exercise using the MCP Python SDK v1.x API surface. Check the exact lesson material and installed SDK version when reproducing the examples. Treat legacy protocol features as learning/compatibility exercises; verify current MCP specification guidance before adopting them in production.

## Requirements

- Python 3.11+
- `uv`
- An Anthropic **or** OpenAI API key with available API credits

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

Set the key for the provider you want in `.env`:

```dotenv
# Anthropic
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

```dotenv
# OpenAI
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4.1-mini
```

### Choosing a provider

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_PROVIDER` | Optional. `anthropic` or `openai` (case-insensitive). | auto-detect |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Anthropic credentials and model. | model: `claude-sonnet-4-5` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI credentials and model. | model: `gpt-4.1-mini` |

The provider is resolved in this order:

1. `LLM_PROVIDER`, if set. Its API key must also be set.
2. Otherwise `ANTHROPIC_API_KEY`, if set.
3. Otherwise `OPENAI_API_KEY`, if set.

So to use OpenAI, set only `OPENAI_API_KEY`. If both keys are present, set `LLM_PROVIDER=openai` to use OpenAI. Empty values are treated as unset. The client prints the active provider and model to stderr on startup.

Do not commit `.env` or share your API keys. The server does not receive or store any LLM key; the client loads it locally.

## Run

```bash
uv run python client.py                      # share nothing
uv run python client.py --root ./sample-docs # share a directory (repeat --root for more)
MCP_ROOTS=./sample-docs uv run python client.py
```

After connecting, the client offers a menu:

1. **Wikipedia research** (default, press Enter): enter a topic such as `Model Context Protocol`, `event sourcing`, or `distributed systems`. The client displays server log/progress notifications and asks for approval before making the Sampling request to the selected provider.
2. **Search local documents:** enter a query. The server searches the shared directories only; no LLM is involved.

## MCP Roots

Roots let a client tell a server which directories it is willing to share. In this project:

- `--root DIR` (repeatable) or `MCP_ROOTS` selects the directories. `--root` wins if both are set. The client prints every shared directory with its `file://` URI.
- The client registers a `list_roots_callback`, which also makes it advertise the `roots` capability.
- The `search_local_documents(query, max_results=5)` tool asks the client for its roots on every call (so changes are picked up), then searches file names and contents of `.md` and `.txt` files.
- If the client has no Roots support, or shares nothing, the tool returns a message saying so instead of failing.

**Roots are not a sandbox.** They only say what the client *intends* to share, so the server enforces its own limits in `local_files.py`:

- every path is resolved (`..` and symlinks collapsed) and must stay inside an approved root
- symlinked directories are never followed; a symlinked file that points outside the roots, to a hidden location or to an unsupported file type is skipped
- hidden files and directories are skipped
- only `.md` and `.txt` files are read, up to 1 MB each (binary content is skipped)
- at most 5,000 files are scanned per root, and I/O errors on one file skip that file only

Known limitation: a file could be swapped for a symlink between the check and the read (a time-of-check/time-of-use race). The path is re-validated right before reading, but this is a learning project, not a hardened sandbox.

Try it: `uv run python client.py --root ./sample-docs`, choose `2`, and search for `sampling` or `roots`.

## What to observe

1. Server logs appear with `[INFO]` prefixes.
2. Progress updates appear with `[PROGRESS]` and percentages.
3. The Sampling prompt preview is shown before the approval prompt.
4. Declining approval stops the model request.
5. The final summary includes article titles and URLs.
6. A local search logs `Approved root: …` for each shared directory, and finds nothing outside them.

## Tests

```bash
uv run --extra dev python -m pytest
```

The Roots tests include an in-memory client/server session (`tests/test_roots_integration.py`), so they exercise the real protocol without starting a subprocess.

## Claude Code registration (optional)

After testing with the included reference client:

```bash
claude mcp add wikipedia-research -- uv run --directory /absolute/path/to/wikipedia-mcp-sampling python server.py
```

The included client is the reference implementation for this Sampling lesson because it explicitly implements the sampling callback. A different MCP client may not support the same legacy Sampling flow.

## Guardrails

- The server has no LLM credentials.
- The client asks for approval before each model request.
- Wikipedia text and local document snippets are treated as untrusted input.
- The server only reads files inside directories the client shares, and validates every path itself.
- HTTP requests have timeouts and a descriptive User-Agent.
- Keep `.env` out of version control and respect Wikimedia API usage policies.
