from __future__ import annotations
from pathlib import Path
import typer
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from .config import Settings
from .graph import build_graph
from .board_ids import parse_board_ids, resolve_board_ids
from .tools import fetch_sprint_details, push_goals_to_miro

app = typer.Typer(help="Sprint Goals AI Agent (Jira -> optional Miro publish)")

def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

@app.command()
def chat(prompt: str = typer.Argument(..., help="Natural language request")):
    
    from pathlib import Path
    load_dotenv(dotenv_path=Path(repo_root()) / ".env", override=True)
    settings = Settings.load(repo_root())
    graph = build_graph(
        scripts_dir=settings.scripts_dir,
        board_ids_file=settings.board_ids_file,
        default_miro_board_id=settings.default_miro_board_id,
    )
    state = {"messages": [HumanMessage(content=prompt)]}
    result = graph.invoke(state)
    typer.echo(result["messages"][-1].content)

@app.command("list-teams")
def list_teams():
    settings = Settings.load(repo_root())
    for b in parse_board_ids(settings.board_ids_file):
        typer.echo(f"{b.team}: {b.board_id}")

@app.command()
def fetch(team: str = typer.Option("", help="Team name contains (e.g. Aqua) or board id")):
    from pathlib import Path
    load_dotenv(dotenv_path=Path(repo_root()) / ".env", override=True)
    settings = Settings.load(repo_root())
    ids = resolve_board_ids(settings.board_ids_file, team_query=team or None)
    if not ids:
        typer.echo("No matching boards. Try: sprint-goals-agent list-teams")
        raise typer.Exit(code=2)
    r = fetch_sprint_details(settings.scripts_dir, ids)
    typer.echo(r.stdout)
    if r.stderr:
        typer.echo(r.stderr)

@app.command()
def push(miro_board_id: str = typer.Argument(..., help="Miro board id from URL")):
    from pathlib import Path
    load_dotenv(dotenv_path=Path(repo_root()) / ".env", override=True)
    settings = Settings.load(repo_root())
    r = push_goals_to_miro(settings.scripts_dir, miro_board_id)
    typer.echo(r.stdout)
    if r.stderr:
        typer.echo(r.stderr)

if __name__ == "__main__":
    app()
