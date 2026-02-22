from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    repo_root: Path
    scripts_dir: Path
    board_ids_file: Path
    default_miro_board_id: str | None

    @staticmethod
    def load(repo_root: Path) -> "Settings":
        return Settings(
            repo_root=repo_root,
            scripts_dir=repo_root / "scripts",
            board_ids_file=repo_root / "board_ids.txt",
            default_miro_board_id=os.getenv("MIRO_BOARD_ID") or None,
        )
