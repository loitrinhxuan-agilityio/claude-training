# Wikipedia Research & Summarization MCP Server

An educational MCP project based on the Claude Academy **Model Context Protocol: Advanced Topics** course. It combines:

- **Sampling:** the server asks the connected client to run an LLM completion.
- **Logging notifications:** the server sends stage updates through MCP logging.
- **Progress notifications:** the server reports progress while the tool runs.

The included reference client uses the **Anthropic Messages API** for Sampling and asks for user approval before sending Wikipedia source material to the model.

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
MCP Client -- user approval --> Anthropic API
  |
  +---- sampling result back to MCP Server
```

## Protocol-version note

This is a course exercise using the MCP Python SDK v1.x API surface. Check the exact lesson material and installed SDK version when reproducing the examples. Treat legacy protocol features as learning/compatibility exercises; verify current MCP specification guidance before adopting them in production.

## Requirements

- Python 3.11+
- `uv`
- Anthropic API key with available API credits

## Setup

```bash
uv sync --extra dev
cp .env.example .env
```

Set your key in `.env`:

```dotenv
ANTHROPIC_API_KEY=your-key
ANTHROPIC_MODEL=claude-sonnet-4-5
```

You can change `ANTHROPIC_MODEL` to another model available to your Anthropic API account. Do not commit `.env` or share your API key. The server does not receive or store the Anthropic key; the client loads it locally.

## Run

```bash
uv run python client.py
```

Enter a topic such as `Model Context Protocol`, `event sourcing`, or `distributed systems`. The client displays server log/progress notifications and asks for approval before making the Sampling request to Anthropic.

## What to observe

1. Server logs appear with `[INFO]` prefixes.
2. Progress updates appear with `[PROGRESS]` and percentages.
3. The Sampling prompt preview is shown before the approval prompt.
4. Declining approval stops the model request.
5. The final summary includes article titles and URLs.

## Tests

```bash
uv run pytest
```

## Claude Code registration (optional)

After testing with the included reference client:

```bash
claude mcp add wikipedia-research -- uv run --directory /absolute/path/to/wikipedia-mcp-sampling python server.py
```

The included client is the reference implementation for this Sampling lesson because it explicitly implements the sampling callback. A different MCP client may not support the same legacy Sampling flow.

## Guardrails

- The server has no Anthropic credentials.
- The client asks for approval before each model request.
- Wikipedia text is treated as untrusted input.
- HTTP requests have timeouts and a descriptive User-Agent.
- Keep `.env` out of version control and respect Wikimedia API usage policies.
