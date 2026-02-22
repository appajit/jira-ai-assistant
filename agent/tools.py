from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess
import os
import json
import subprocess
from pathlib import Path
from typing import List

@dataclass(frozen=True)
class ToolResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int

def _run(cmd: list[str], cwd: Path) -> ToolResult:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )
    return ToolResult(ok=p.returncode == 0, stdout=p.stdout, stderr=p.stderr, returncode=p.returncode)

def fetch_sprint_details(scripts_dir: Path, board_ids: list[int]) -> ToolResult:
    script = scripts_dir / "fetch_sprint_details.sh"
    cmd = ["bash", str(script)] + [str(b) for b in board_ids]
    return _run(cmd, cwd=scripts_dir)

def push_goals_to_miro(scripts_dir: Path, miro_board_id: str, team_filter: str = "") -> ToolResult:
    script = scripts_dir / "push_to_miro_cards.sh"
    cmd = ["bash", str(script), miro_board_id, team_filter]
    return _run(cmd, cwd=scripts_dir)

def fetch_customer_outcomes(sprint_id: str) -> List[str]:
    """
    Returns a de-duplicated list of Customer Outcomes (plain text) for the given sprint_id.
    Uses scripts/fetch_customer_outcomes.sh which outputs JSON lines:
      {"epic":"ILX-58923","outcome":"..."}
    """
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "fetch_customer_outcomes.sh"

    if not script.exists():
        return []

    try:
        r = subprocess.run(
            [str(script), str(sprint_id)],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return []

    outcomes: List[str] = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            out = (obj.get("outcome") or "").strip()
            if out:
                outcomes.append(out)
        except Exception:
            # ignore any non-json lines
            continue

    # de-dupe (case-insensitive) while preserving order
    seen = set()
    uniq: List[str] = []
    for o in outcomes:
        k = o.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(o)

    return uniq