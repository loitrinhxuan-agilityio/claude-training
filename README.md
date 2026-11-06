# Claude Training

Hands-on practice projects for learning to work with Claude and AI coding tools such as Claude Code. Each project is self-contained, with its own README, dependencies, and setup.

## Projects

| Project | Stack | What it covers |
| --- | --- | --- |
| [`wikipedia-mcp/`](wikipedia-mcp) | Python, MCP SDK, Anthropic API | An MCP server that researches and summarizes Wikipedia articles. Demonstrates **Sampling**, **logging notifications**, and **progress notifications**. The reference client uses the Anthropic Messages API. |
| [`claude-api/`](claude-api) | Python, Anthropic SDK | Exercises from the Claude Academy course *Building with the Claude API*, one folder per lesson topic: [`prompt_evaluation/`](claude-api/prompt_evaluation) (test datasets, code-based and model-based grading), [`rag_pipeline/`](claude-api/rag_pipeline) (BM25 + vector search merged with reciprocal rank fusion), and [`image_support/`](claude-api/image_support) (image blocks and prompting for vision). |
| [`ai-tools-training/`](ai-tools-training) | TypeScript, NestJS, PostgreSQL | A small banking domain built with **Event Sourcing** and **CQRS**. Used to practice Claude Code workflows: `CLAUDE.md`, skills, subagents, and documentation generation. |

> **`ai-tools-training/` is a git submodule** that points to its own repository,
> [`loitrinhxuan-agilityio/ai-tools-training`](https://github.com/loitrinhxuan-agilityio/ai-tools-training).
> Clone with `--recurse-submodules`, or run `git submodule update --init` after cloning.

## Getting started

```bash
git clone --recurse-submodules git@github.com:loitrinhxuan-agilityio/claude-training.git
cd claude-training/ai-tools-training
```

Then follow the README inside the project.

### Prerequisites

| Project | Needs |
| --- | --- |
| `wikipedia-mcp` | Python 3.11+, [`uv`](https://docs.astral.sh/uv/), and an Anthropic API key |
| `claude-api` | Python 3.13+, [`uv`](https://docs.astral.sh/uv/), and an Anthropic API key (the `rag_pipeline` tests and retrieval eval run offline) |
| `ai-tools-training` | Node.js 24.15+ (see `.nvmrc`) and Docker |

### Quick start: Claude API practices

```bash
cd claude-api
uv sync
echo "ANTHROPIC_API_KEY=your-key" > .env     # git-ignored; never commit it

uv run python prompt_evaluation/run_eval.py                       # classification eval (v1, v2, v3 prompts)
uv run python prompt_evaluation/run_reply_eval.py                 # model-based grading of drafted replies
PYTHONPATH=rag_pipeline uv run python -m unittest discover -s rag_pipeline   # RRF tests, offline
uv run python rag_pipeline/eval_retrieval.py                      # vector vs BM25 vs hybrid, offline
uv run python image_support/practice.py                           # image blocks + marble counting
```

Run these from inside `claude-api/`. The eval, `ask.py` and image scripts call the API
and cost a small amount (they default to `claude-haiku-4-5`). Each practice folder has
its own README with the results observed, caveats, and exercises.

### Quick start: Wikipedia MCP

```bash
cd wikipedia-mcp
uv sync --extra dev
cp .env.example .env        # then add your API key
uv run python client.py
```

## Repository layout

```text
claude-training/
├── wikipedia-mcp/          # MCP Sampling demo (Anthropic)
├── claude-api/             # Building with the Claude API exercises
│   ├── prompt_evaluation/  #   evals, code-based + model-based grading
│   ├── rag_pipeline/       #   multi-index RAG with reciprocal rank fusion
│   └── image_support/      #   vision: image blocks and prompting
└── ai-tools-training/      # NestJS Event Sourcing practice (submodule)
```

## Security notes

- Credentials live in each project's `.env`, which is git-ignored. Only `.env.example` files are committed.
- Never commit real credentials. If a key is exposed, rotate it.
- These are learning projects, not production systems.
