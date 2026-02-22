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

REPORTS_DIR="$REPO_ROOT/reports"
LATEST_CSV="$(ls -t "$REPORTS_DIR"/Sprint_Goals_*.csv 2>/dev/null | head -n 1 || true)"
if [[ -z "${LATEST_CSV}" || ! -f "${LATEST_CSV}" ]]; then
  echo "❌ No Sprint Goals CSV found in: $REPORTS_DIR"
  exit 1
fi

echo "🚀 Pushing Sprint Goals to Miro (Stickies)"
echo "================================"
echo "Miro Board ID: $MIRO_BOARD_ID"
echo "Using report : $LATEST_CSV"
echo

MIRO_API_BASE="https://api.miro.com/v2"
COLORS=("yellow" "light_green" "light_blue" "light_pink" "violet" "cyan")
COLOR_INDEX=0
X_POS=0
Y_POS=100

create_text() {
  local content="$1" x="$2" y="$3" size="${4:-48}"
  curl -sS -X POST "${MIRO_API_BASE}/boards/${MIRO_BOARD_ID}/texts" \
    -H "Authorization: Bearer ${MIRO_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "$(python3 - <<PY
import json
print(json.dumps({
  "data":{"content": "$content"},
  "style":{"fontSize": "$size"},
  "position":{"x": $x, "y": $y}
}))
PY
)"
}

create_sticky() {
  local content="$1" color="$2" x="$3" y="$4"
  curl -sS -X POST "${MIRO_API_BASE}/boards/${MIRO_BOARD_ID}/sticky_notes" \
    -H "Authorization: Bearer ${MIRO_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "$(python3 - <<PY
import json
print(json.dumps({
  "data":{"content": "$content", "shape":"rectangle"},
  "style":{"fillColor":"$color","textAlign":"left","textAlignVertical":"top"},
  "position":{"x": $x, "y": $y},
  "geometry":{"width": 450}
}))
PY
)"
}

create_text "🎯 Sprint Goals - $(date '+%Y-%m-%d %H:%M')" 0 -200 48 >/dev/null || true

python3 - <<'PY' "$LATEST_CSV" | while IFS=$'\t' read -r title html; do
import csv, sys

path=sys.argv[1]
def norm_row(row):
    return { (k or "").lstrip("\ufeff").strip(): (v or "") for k,v in row.items() }

with open(path, newline="", encoding="utf-8") as f:
    r=csv.DictReader(f)
    for raw in r:
        row=norm_row(raw)
        bn=row.get("Board Name","").strip()
        sn=row.get("Sprint Name","").strip()
        sd=row.get("Start Date","").strip()
        ed=row.get("End Date","").strip()
        goal=row.get("Sprint Goal","").strip()
        if not goal: 
            continue

        # Convert goal to basic bullet format inside HTML content
        lines=[x.strip() for x in goal.split("\n") if x.strip()]
        if len(lines)==1 and ";" in lines[0]:
            lines=[x.strip() for x in lines[0].split(";") if x.strip()]
        bullets="\\n".join([f"  → {x}" for x in lines]) if lines else "  → (none)"

        content=f"<b>{bn}</b>\\n━━━━━━━━━━━━━━━━━━━━━━\\n\\n<b>Sprint:</b> {sn}\\n<b>Dates:</b> {sd} → {ed}\\n\\n<b>Goals:</b>\\n{bullets}"
        print(f"{bn} – {sn}\t{content}")
PY
  color="${COLORS[$((COLOR_INDEX % ${#COLORS[@]}))]}"

  echo "Creating sticky: $title"
  create_sticky "$html" "$color" "$X_POS" "$Y_POS" >/dev/null || true

  X_POS=$((X_POS + 450))
  if [[ $X_POS -ge 1800 ]]; then
    X_POS=0
    Y_POS=$((Y_POS + 400))
  fi
  COLOR_INDEX=$((COLOR_INDEX + 1))
done

echo "✅ Done! Open:"
echo "https://miro.com/app/board/-${MIRO_BOARD_ID}/"