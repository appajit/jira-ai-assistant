#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

: "${MIRO_TOKEN:?MIRO_TOKEN not set}"
MIRO_BOARD_ID="${1:-${MIRO_BOARD_ID:-}}"
: "${MIRO_BOARD_ID:?MIRO_BOARD_ID not set (in .env or pass as arg)}"
MIRO_BOARD_ID="${MIRO_BOARD_ID#-}"

# Optional team filter (second argument) - case insensitive partial match
TEAM_FILTER="${2:-}"

REPORTS_DIR="$REPO_ROOT/reports"
LATEST_CSV="$(ls -t "$REPORTS_DIR"/Sprint_Goals_*.csv 2>/dev/null | head -n 1 || true)"
if [[ -z "${LATEST_CSV}" || ! -f "${LATEST_CSV}" ]]; then
  echo "❌ No Sprint Goals CSV found in: $REPORTS_DIR"
  exit 1
fi

echo "🚀 Pushing Sprint Goals to Miro (Cards)"
echo "================================"
echo "Miro Board ID: $MIRO_BOARD_ID"
echo "Using report : $LATEST_CSV"
echo

MIRO_API_BASE="https://api.miro.com/v2"

# Generate card payloads to a temp file first
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

export LATEST_CSV
export TEAM_FILTER
python3 -c '
import csv, json, os, sys

csv_path = os.environ["LATEST_CSV"]
team_filter = os.environ.get("TEAM_FILTER", "").strip().lower()

def norm_row(row):
    return { (k or "").lstrip("\ufeff").strip(): (v or "") for k,v in row.items() }

def bullets_text(text):
    text = (text or "").strip()
    if not text:
        return "  • Not specified"
    parts = [p.strip() for p in text.replace(" ; ", ";").split(";") if p.strip()]
    if not parts:
        parts = [text]
    return "\n".join([f"  • {p}" for p in parts])

# Card positioning - arrange in a grid
card_width = 500
card_height = 450
cols = 4
card_index = 0

with open(csv_path, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for raw in r:
        row = norm_row(raw)

        board_id = row.get("Board ID","").strip()
        board_name = row.get("Board Name","").strip()
        sprint_id = row.get("Sprint ID","").strip()
        sprint_name = row.get("Sprint Name","").strip()
        sprint_state = row.get("Sprint State","").strip()
        start_date = row.get("Start Date","").strip()
        end_date = row.get("End Date","").strip()
        goal = row.get("Sprint Goal","").strip()
        outcome = row.get("Customer Outcome","").strip()

        if not board_name:
            continue

        # Apply team filter if specified
        if team_filter:
            # Match against board name (case insensitive, partial match)
            if team_filter not in board_name.lower():
                continue

        # Put ALL content in title field - this displays on card face
        title = (
            f"<b>{board_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧩 Sprint: {sprint_name}\n"
            f"📅 State: {sprint_state}\n"
            f"📆 Dates: {start_date} → {end_date}\n\n"
            f"📌 Sprint Goal\n"
            f"{bullets_text(goal)}\n\n"
            f"🎯 Customer Outcome\n"
            f"{bullets_text(outcome)}"
        )

        # Position cards in a grid
        col = card_index % cols
        row_num = card_index // cols
        x_pos = col * (card_width + 50)
        y_pos = row_num * (card_height + 50)

        payload = {
            "data": {"title": title},
            "position": {"x": x_pos, "y": y_pos},
            "geometry": {"width": card_width}
        }
        print(json.dumps({"title": board_name, "payload": payload}))
        card_index += 1
' > "$TEMP_FILE"

# Count how many cards to create
CARD_COUNT=$(wc -l < "$TEMP_FILE" | tr -d ' ')
echo "Found $CARD_COUNT team(s) to push"
echo

# Read and create cards
SUCCESS=0
FAILED=0

while IFS= read -r line; do
  title=$(echo "$line" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])")
  payload=$(echo "$line" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['payload']))")

  echo "Creating card: $title"

  HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/miro_resp.json \
    -X POST "${MIRO_API_BASE}/boards/${MIRO_BOARD_ID}/cards" \
    -H "Authorization: Bearer ${MIRO_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "${payload}"
  )

  if [[ "$HTTP_CODE" != "201" ]]; then
    echo "  Failed (HTTP $HTTP_CODE)"
    cat /tmp/miro_resp.json
    echo
    FAILED=$((FAILED + 1))
  else
    echo "  Created successfully"
    SUCCESS=$((SUCCESS + 1))
  fi

  echo
done < "$TEMP_FILE"

echo "================================"
echo "Done! Created $SUCCESS card(s), $FAILED failed"
echo "Open: https://miro.com/app/board/${MIRO_BOARD_ID}/"
