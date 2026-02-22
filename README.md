# Sprint Goals AI Agent (Jira → Miro)

Wraps your existing bash scripts as **tools**, and adds:
- deterministic CLI commands (`fetch`, `push`, `list-teams`)
- an **LLM-powered** `chat` command (LangGraph) that turns natural language into safe actions.

## Setup

1) Ensure `jq` is installed.

2) Create `.env` (copy from `.env.example`) and set:

- `JIRA_USERNAME`, `JIRA_API_TOKEN` (and optionally `JIRA_URL`)
- `MIRO_TOKEN` (and optionally `MIRO_BOARD_ID`)
- Optional for AI mode: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Deterministic usage (no LLM)

```bash
sprint-goals-agent list-teams
sprint-goals-agent fetch
sprint-goals-agent fetch --team Aqua
sprint-goals-agent push uXjVGBjhV7E=
```

## AI usage (LangGraph)

```bash
sprint-goals-agent chat "Fetch sprint goals for Aqua"
sprint-goals-agent chat "Push sprint goals to Miro board uXjVGBjhV7E="
sprint-goals-agent chat "List teams"
```

## Notes

- The scripts in `scripts/` were patched to **remove hardcoded credentials**. Use env vars or `.env`.
- Jira CSV reports are written to `reports/`.
