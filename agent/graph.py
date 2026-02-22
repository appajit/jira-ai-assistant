from __future__ import annotations

from typing import TypedDict, Literal, Optional, List, Any
from pathlib import Path
import json
import re

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from .board_ids import resolve_board_ids, parse_board_ids
from .tools import fetch_sprint_details, push_goals_to_miro, fetch_customer_outcomes
from .llm import get_llm


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s or "")


def extract_preview_rows(stdout: str) -> list[str]:
    """
    Extract CSV-like rows from the script output.
    We find the header 'Board ID,Board Name,...' and then reconstruct rows.
    """
    text = strip_ansi(stdout)
    # Support both old (8 col) and new (9 col with Customer Outcome) headers
    header_new = "Board ID,Board Name,Sprint ID,Sprint Name,Sprint State,Start Date,End Date,Sprint Goal,Customer Outcome"
    header_old = "Board ID,Board Name,Sprint ID,Sprint Name,Sprint State,Start Date,End Date,Sprint Goal"
    
    header = header_new if header_new in text else header_old
    idx = text.find(header)
    if idx == -1:
        return []

    preview = text[idx:]
    # Ensure header starts on its own line
    preview = preview.replace(header, header + "\n", 1)

    # Rows often appear on one line separated by spaces; insert newline before each "<digits>,"
    # Example: "...Sprint Goal 350,ILX..." => "\n350,ILX..."
    preview = re.sub(r"\s(\d+),", r"\n\1,", preview)

    # Split into lines and keep only data rows (start with digits)
    lines = [ln.strip() for ln in preview.splitlines() if ln.strip()]
    rows = [ln for ln in lines if re.match(r"^\d+,", ln)]
    return rows


def parse_row(line: str) -> dict:
    """
    Split into 9 fields (including Customer Outcome), allowing commas inside fields by using CSV parsing.
    """
    import csv
    from io import StringIO
    
    # Use CSV reader to properly handle quoted fields with commas
    try:
        reader = csv.reader(StringIO(line))
        parts = next(reader)
    except Exception:
        parts = line.split(",", 8)
    
    # Pad to 9 fields if necessary
    while len(parts) < 9:
        parts.append("")
    
    return {
        "board_id": parts[0].strip(),
        "board_name": parts[1].strip(),
        "sprint_id": parts[2].strip(),
        "sprint_name": parts[3].strip(),
        "sprint_state": parts[4].strip(),
        "start": parts[5].strip(),
        "end": parts[6].strip(),
        "goal": parts[7].strip(),
        "customer_outcome": parts[8].strip() if len(parts) > 8 else "",
    }


def goal_to_bullets(goal: str, max_items: int = 8) -> list[str]:
    """
    Heuristic bulleting: split on periods, semicolons, and ' - '.
    """
    g = (goal or "").strip()
    if not g:
        return []

    # Normalize separators
    g = g.replace("\n", " ").replace("  ", " ")
    chunks = re.split(r";\s*|\.\s+|\s-\s+", g)
    chunks = [c.strip(" -•\t") for c in chunks if c.strip(" -•\t")]

    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for c in chunks:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(c)

    return deduped[:max_items]


def _fetch_outcomes_safe(scripts_dir: Path, sprint_id: str) -> list[str]:
    """
    fetch_customer_outcomes() signature can vary depending on local tools.py.
    This wrapper supports both:
      - fetch_customer_outcomes(scripts_dir, sprint_id)
      - fetch_customer_outcomes(sprint_id)
    """
    try:
        return fetch_customer_outcomes(scripts_dir, sprint_id)  # type: ignore[arg-type]
    except TypeError:
        try:
            return fetch_customer_outcomes(sprint_id)  # type: ignore[call-arg]
        except Exception:
            return []
    except Exception:
        return []


def format_summary(stdout: str, scripts_dir: Path | None = None, display_filter: str = "all") -> str:
    rows = extract_preview_rows(stdout)
    if not rows:
        return strip_ansi(stdout).strip() or "No output."

    items = [parse_row(r) for r in rows]

    blocks: list[str] = []
    for it in items:
        title = f"**{it['board_name']} — {it['sprint_name']}**"
        dates = f"📅 {it['start']} → {it['end']}"

        # Sprint Goal
        bullets = goal_to_bullets(it["goal"])
        if bullets:
            goal_body = "\n".join([f"  • {b}" for b in bullets])
        else:
            goal_body = "  • (No sprint goal found)"

        # Customer Outcomes - use from CSV first, fallback to fetching
        outcomes_body = ""
        csv_outcome = it.get("customer_outcome", "").strip()
        
        if csv_outcome:
            # Parse outcomes separated by " ; "
            outcomes = [o.strip() for o in csv_outcome.split(" ; ") if o.strip()]
            if outcomes:
                outcomes_body = "\n".join([f"  • {o}" for o in outcomes[:8]])
        elif scripts_dir is not None and it.get("sprint_id"):
            # Fallback: fetch outcomes if not in CSV
            outcomes = _fetch_outcomes_safe(scripts_dir, it["sprint_id"])
            if outcomes:
                outcomes_body = "\n".join([f"  • {o}" for o in outcomes[:8]])
            else:
                outcomes_body = "  • Not set on epics for this sprint"

        # Build block based on display_filter
        if display_filter == "goals_only":
            block = f"""{title}
{dates}

📌 **Sprint Goal**
{goal_body}
"""
        elif display_filter == "outcomes_only":
            block = f"""{title}
{dates}

🎯 **Customer Outcome**
{outcomes_body if outcomes_body else "  • Not specified"}
"""
        else:  # "all"
            block = f"""{title}
{dates}

🎯 **Customer Outcome**
{outcomes_body if outcomes_body else "  • Not specified"}

📌 **Sprint Goal**
{goal_body}
"""
        blocks.append(block)

    return "\n---\n\n".join(blocks).strip()


class AgentState(TypedDict, total=False):
    messages: List[Any]

    intent: Literal["fetch", "push", "list", "help"]
    team_query: Optional[str]
    miro_board_id: Optional[str]
    display_filter: Optional[Literal["all", "goals_only", "outcomes_only"]]

    board_ids: List[int]
    fetch_stdout: str
    fetch_stderr: str
    push_stdout: str
    push_stderr: str


def node_parse_intent(state: AgentState):
    llm = get_llm()
    user = state["messages"][-1].content

    instruction = (
        "Return ONLY JSON. Keys: intent (fetch|push|list|help), team_query (string|null), miro_board_id (string|null), display_filter (all|goals_only|outcomes_only). "
        "Rules: if user asks to push/post/update to miro -> push. "
        "If user asks to fetch/show/report sprint goals/details/outcomes -> fetch. "
        "If user asks to list teams/boards -> list. Otherwise help. "
        "For display_filter: if user asks for 'only goals' or 'just goals' or 'sprint goals only' -> goals_only. "
        "If user asks for 'only outcomes' or 'just outcomes' or 'customer outcomes only' -> outcomes_only. "
        "Otherwise -> all."
    )
    resp = llm.invoke([HumanMessage(content=f"{instruction}\nUser: {user}")])
    text = resp.content.strip()

    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"intent": "help", "team_query": None, "miro_board_id": None, "display_filter": "all"}

    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"intent": "help", "team_query": None, "miro_board_id": None, "display_filter": "all"}

    intent = data.get("intent")
    if intent not in {"fetch", "push", "list", "help"}:
        intent = "help"
    
    display_filter = data.get("display_filter", "all")
    if display_filter not in {"all", "goals_only", "outcomes_only"}:
        display_filter = "all"
    
    return {
        "intent": intent,
        "team_query": data.get("team_query"),
        "miro_board_id": data.get("miro_board_id"),
        "display_filter": display_filter,
    }


def node_resolve_boards(state: AgentState, board_ids_file: Path):
    team_query = state.get("team_query")

    # Normalize "all teams" requests
    if team_query:
        tq = team_query.strip().lower()
        if tq in {"all", "all teams", "everyone", "all boards", "all team"}:
            team_query = None

    ids = resolve_board_ids(board_ids_file, team_query)
    return {"board_ids": ids}


def node_fetch(state: AgentState, scripts_dir: Path):
    ids = state.get("board_ids", [])
    if not ids:
        return {"fetch_stdout": "", "fetch_stderr": "No matching boards found. Try 'list teams'."}

    r = fetch_sprint_details(scripts_dir, ids)

    # PM-friendly output with optional filtering
    display_filter = state.get("display_filter", "all")
    pretty = format_summary(r.stdout, scripts_dir=scripts_dir, display_filter=display_filter)

    return {"fetch_stdout": pretty, "fetch_stderr": strip_ansi(r.stderr)}


def node_push(state: AgentState, scripts_dir: Path, default_miro_board_id: str | None):
    miro_board_id = state.get("miro_board_id") or default_miro_board_id
    if not miro_board_id:
        return {"push_stdout": "", "push_stderr": "Missing Miro board id. Provide it or set MIRO_BOARD_ID."}
    
    # Get team filter if specified
    team_query = state.get("team_query", "") or ""
    # Normalize - if "all teams" variants, clear the filter
    if team_query.strip().lower() in {"all", "all teams", "everyone", "all boards", "all team", ""}:
        team_filter = ""
    else:
        team_filter = team_query.strip()
    
    r = push_goals_to_miro(scripts_dir, miro_board_id, team_filter)
    return {"push_stdout": r.stdout, "push_stderr": r.stderr}


def node_list(state: AgentState, board_ids_file: Path):
    boards = parse_board_ids(board_ids_file)
    lines = ["Teams/Boards:"] + [f"- {b.team}: {b.board_id}" for b in boards]
    return {"fetch_stdout": "\n".join(lines), "fetch_stderr": ""}


def node_render(state: AgentState):
    intent = state.get("intent", "help")
    if intent in {"fetch", "list"}:
        msg = (state.get("fetch_stdout", "") + "\n" + state.get("fetch_stderr", "")).strip()
        return {"messages": state["messages"] + [AIMessage(content=msg or "No output.")]}

    if intent == "push":
        msg = (state.get("push_stdout", "") + "\n" + state.get("push_stderr", "")).strip()
        return {"messages": state["messages"] + [AIMessage(content=msg or "No output.")]}

    help_text = (
        "Try:\n"
        "• Fetch sprint goals for all teams\n"
        "• Fetch sprint goals for Aqua\n"
        "• Push sprint goals to Miro board uXj...\n"
        "• List teams\n\n"
        "Required env vars: JIRA_USERNAME, JIRA_API_TOKEN, MIRO_TOKEN.\n"
        "Optional for chat: OPENAI_API_KEY or ANTHROPIC_API_KEY."
    )
    return {"messages": state["messages"] + [AIMessage(content=help_text)]}


def build_graph(*, scripts_dir: Path, board_ids_file: Path, default_miro_board_id: str | None):
    g = StateGraph(AgentState)
    g.add_node("parse_intent", node_parse_intent)
    g.add_node("resolve_boards", lambda s: node_resolve_boards(s, board_ids_file))
    g.add_node("fetch", lambda s: node_fetch(s, scripts_dir))
    g.add_node("push", lambda s: node_push(s, scripts_dir, default_miro_board_id))
    g.add_node("list", lambda s: node_list(s, board_ids_file))
    g.add_node("render", node_render)

    g.set_entry_point("parse_intent")

    def route(state: AgentState):
        return state.get("intent", "help")

    g.add_conditional_edges(
        "parse_intent",
        route,
        {
            "fetch": "resolve_boards",
            "push": "push",
            "list": "list",
            "help": "render",
        },
    )

    g.add_edge("resolve_boards", "fetch")
    g.add_edge("fetch", "render")
    g.add_edge("push", "render")
    g.add_edge("list", "render")
    g.add_edge("render", END)

    return g.compile()