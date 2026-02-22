import os
import subprocess
import csv
import io
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
BOARD_FILE = REPO_ROOT / "board_ids.txt"
SCRIPTS_DIR = REPO_ROOT / "scripts"
PUSH_SCRIPT = SCRIPTS_DIR / "push_to_miro_cards.sh"
REPORTS_DIR = REPO_ROOT / "reports"

# Load .env from repo root
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=True)

st.set_page_config(page_title="Sprint Assistant", page_icon="🎯", layout="wide")
st.title("🎯 Sprint Assistant")


# ---------- Helpers ----------
def normalize_team_name(raw: str) -> str:
    # "# Amber Team" -> "Amber"
    s = raw.strip()
    if s.startswith("#"):
        s = s.lstrip("#").strip()
    # remove trailing "Team" if present
    if s.lower().endswith("team"):
        s = s[:-4].strip()
    return s


def load_teams(board_file: Path) -> dict[str, str]:
    """
    Supports BOTH formats:

    1) Name:ID
       Amber:350

    2) Comment + ID on next line
       # Amber Team
       350
    """
    teams: dict[str, str] = {}
    if not board_file.exists():
        return teams

    pending_name: str | None = None

    for line in board_file.read_text().splitlines():
        line = line.strip()
        if not line:
            continue

        # Format 1: Name:ID
        if ":" in line and not line.startswith("#"):
            name, bid = line.split(":", 1)
            name = normalize_team_name(name)
            bid = bid.strip()
            if name and bid.isdigit():
                teams[name] = bid
            pending_name = None
            continue

        # Format 2: "# Team Name" line
        if line.startswith("#"):
            pending_name = normalize_team_name(line)
            continue

        # Format 2: ID line after "# Team Name"
        if line.isdigit() and pending_name:
            teams[pending_name] = line
            pending_name = None
            continue

        # If it's a naked number without a name, you can optionally keep it:
        # (we’ll ignore it to keep PM UI clean)
        pending_name = None

    return teams


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def pretty_block(title: str, text: str):
    st.subheader(title)
    st.code(text or "(no output)", language="text")


def get_latest_csv() -> Path | None:
    """Get the most recent CSV report file."""
    if not REPORTS_DIR.exists():
        return None
    csvs = sorted(REPORTS_DIR.glob("Sprint_Goals_*.csv"), reverse=True)
    return csvs[0] if csvs else None


def format_bullets(text: str, separator: str = " ; ") -> str:
    """Convert separated text into bullet points."""
    if not text or not text.strip():
        return "• Not specified"
    parts = [p.strip() for p in text.split(separator) if p.strip()]
    if not parts:
        # Try pipe separator
        parts = [p.strip() for p in text.replace(" | ", "|").split("|") if p.strip()]
    if not parts:
        return f"• {text.strip()}"
    return "\n".join([f"• {p}" for p in parts])


def format_sprint_summary(csv_path: Path) -> str:
    """Format CSV data into a nice readable summary."""
    if not csv_path or not csv_path.exists():
        return "No report found."
    
    blocks = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys (handle BOM)
            row = {(k or "").lstrip("\ufeff").strip(): (v or "").strip() for k, v in row.items()}
            
            board_name = row.get("Board Name", "").strip()
            sprint_name = row.get("Sprint Name", "").strip()
            sprint_state = row.get("Sprint State", "").strip()
            start_date = row.get("Start Date", "").strip()
            end_date = row.get("End Date", "").strip()
            goal = row.get("Sprint Goal", "").strip()
            outcome = row.get("Customer Outcome", "").strip()
            
            if not board_name:
                continue
            
            title = f"**{board_name} — {sprint_name}**"
            dates = f"📅 {start_date} → {end_date} ({sprint_state})"
            
            goal_bullets = format_bullets(goal, " | ")
            outcome_bullets = format_bullets(outcome, " ; ")
            
            block = f"""{title}
{dates}

🎯 **Customer Outcome**
{outcome_bullets}

📌 **Sprint Goal**
{goal_bullets}
"""
            blocks.append(block)
    
    return "\n---\n\n".join(blocks) if blocks else "No sprint data found."


# ---------- Sidebar (minimal config) ----------
with st.sidebar:
    st.header("Configuration")

    st.text_input("JIRA URL", value=os.getenv("JIRA_URL", ""), disabled=True)

    miro_board_id = st.text_input(
        "Miro Board ID",
        value=os.getenv("MIRO_BOARD_ID", ""),
        help="Example: uXjVGBjhV7E=",
    )


# ---------- Load teams ----------
teams = load_teams(BOARD_FILE)

if not teams:
    st.error(
        "No teams found.\n\n"
        "Your `board_ids.txt` must be either:\n"
        "• Amber:350\n"
        "• or:\n"
        "# Amber Team\n350"
    )
    st.stop()

team_names = ["All teams"] + sorted(teams.keys())

# ---------- Main UI ----------
team_choice = st.selectbox("Team", team_names, index=0)

col1, col2 = st.columns(2)

with col1:
    fetch_clicked = st.button("Fetch Sprint Details", use_container_width=True)

with col2:
    push_clicked = st.button("Push to Miro", use_container_width=True)


# ---------- Fetch ----------
if fetch_clicked:
    st.divider()

    with st.spinner("Fetching sprint details from JIRA..."):
        if team_choice == "All teams":
            # Fetch all teams directly using the script
            script = str(SCRIPTS_DIR / "fetch_all_team_sprint_details.sh")
            code, out, err = run_cmd(["bash", script])
        else:
            # Fetch single team by board ID
            board_id = teams[team_choice]
            script = str(SCRIPTS_DIR / "fetch_sprint_details.sh")
            code, out, err = run_cmd(["bash", script, board_id])

    if code != 0:
        st.error("Failed to fetch sprint details.")
        pretty_block("Error", err)
    else:
        # Show formatted summary from the CSV
        st.subheader(f"Sprint Details – {team_choice}")
        csv_path = get_latest_csv()
        if csv_path:
            formatted = format_sprint_summary(csv_path)
            st.markdown(formatted)
        else:
            pretty_block(f"Sprint Details – {team_choice}", out.strip())


# ---------- Push to Miro ----------
if push_clicked:
    st.divider()

    if not miro_board_id:
        st.error("Please enter the Miro Board ID.")
        st.stop()

    if not PUSH_SCRIPT.exists():
        st.error("Push to Miro script not found.")
        st.stop()

    with st.spinner("Pushing sprint goals to Miro..."):
        code, out, err = run_cmd(["bash", str(PUSH_SCRIPT), miro_board_id])

    if code != 0:
        st.error("Failed to push sprint goals to Miro.")
        pretty_block("Error", err)
    else:
        st.success("Sprint goals pushed to Miro successfully ✅")
        st.markdown(f"[Open Miro board](https://miro.com/app/board/{miro_board_id}/)")