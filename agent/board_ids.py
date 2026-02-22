from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class TeamBoard:
    team: str
    board_id: int

def parse_board_ids(path: Path) -> list[TeamBoard]:
    """Parse board_ids.txt:

    # Team Name
    350
    # Another Team
    492
    """
    teams: list[TeamBoard] = []
    current_team: str | None = None

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_team = line.lstrip("#").strip()
            continue
        if re.fullmatch(r"\d+", line):
            if current_team is None:
                current_team = f"Board {line}"
            teams.append(TeamBoard(team=current_team, board_id=int(line)))
            current_team = None

    return teams

def resolve_board_ids(path: Path, team_query: str | None = None) -> list[int]:
    boards = parse_board_ids(path)
    if not team_query:
        return [b.board_id for b in boards]

    tq = team_query.strip().lower()
    matched = [b.board_id for b in boards if tq in b.team.lower()]
    if matched:
        return matched

    if re.fullmatch(r"\d+", tq):
        return [int(tq)]

    return []
