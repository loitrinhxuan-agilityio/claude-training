# Claude Training

Hands-on practice projects for learning to work with Claude and AI coding tools such as Claude Code. Each project is self-contained, with its own README, dependencies, and setup.

## Projects

| Project | Stack | What it covers |
| --- | --- | --- |
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

- Node.js 24.15+ (see `.nvmrc` in the project)
- Docker (for PostgreSQL)

## Repository layout

```text
claude-training/
└── ai-tools-training/      # NestJS Event Sourcing practice (submodule)
```

## Security notes

- Credentials live in each project's `.env`, which is git-ignored. Only `.env.example` files are committed.
- Never commit real credentials. If a key is exposed, rotate it.
- These are learning projects, not production systems.
