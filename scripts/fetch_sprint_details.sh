#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env from repo root
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

: "${JIRA_URL:?Missing JIRA_URL}"
: "${JIRA_USERNAME:?Missing JIRA_USERNAME}"
: "${JIRA_API_TOKEN:?Missing JIRA_API_TOKEN}"

# Optional (only needed for Customer Outcome)
# If not set, we still fetch goals fine.
CUSTOM_OUTCOME_FIELD="${CUSTOM_OUTCOME_FIELD:-}"
EPIC_LINK_FIELD="${EPIC_LINK_FIELD:-}"

command -v jq >/dev/null 2>&1 || { echo "❌ jq is required (brew install jq)"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 is required"; exit 1; }

AUTH="$JIRA_USERNAME:$JIRA_API_TOKEN"

jira_api() {
  local endpoint="$1"
  curl -sS -u "$AUTH" -H "Accept: application/json" "${JIRA_URL}${endpoint}"
}

OUTPUT_DIR="$REPO_ROOT/reports"
mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_FILE="$OUTPUT_DIR/Sprint_Goals_${TIMESTAMP}.csv"

# If no args passed, read from board_ids.txt
BOARD_IDS=()
if [[ $# -gt 0 ]]; then
  for b in "$@"; do BOARD_IDS+=("$b"); done
else
  BOARD_FILE="$REPO_ROOT/board_ids.txt"
  if [[ ! -f "$BOARD_FILE" ]]; then
    echo "❌ No board IDs provided and board_ids.txt not found at: $BOARD_FILE"
    exit 1
  fi
  while IFS= read -r line; do
    line="$(echo "$line" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue
    BOARD_IDS+=("$line")
  done < "$BOARD_FILE"
fi

echo "🚀 JIRA Sprint Goals Fetcher"
echo "================================"
echo "Found ${#BOARD_IDS[@]} boards to process"
echo

# Write CSV header (with Customer Outcome column)
python3 - <<PY
import csv
with open("$OUTPUT_FILE","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["Board ID","Board Name","Sprint ID","Sprint Name","Sprint State","Start Date","End Date","Sprint Goal","Customer Outcome"])
PY

# Helper: aggregate outcome JSON lines -> single string
aggregate_outcomes() {
  python3 -c '
import sys, json
outs=[]
seen=set()
for line in sys.stdin:
    line=line.strip()
    if not line:
        continue
    try:
        obj=json.loads(line)
    except Exception:
        continue
    txt=(obj.get("outcome") or "").strip()
    if not txt:
        continue
    txt=" ".join(txt.split())
    if txt not in seen:
        seen.add(txt)
        outs.append(txt)
print(" ; ".join(outs))
'
}

for board_id in "${BOARD_IDS[@]}"; do
  echo "Processing Board ${board_id}..."

  board_info="$(jira_api "/rest/agile/1.0/board/${board_id}")"
  board_name="$(printf '%s' "$board_info" | jq -r '.name // "Unknown"')"

  sprint_data="$(jira_api "/rest/agile/1.0/board/${board_id}/sprint?state=active")"
  sprint_count="$(printf '%s' "$sprint_data" | jq -r '.values | length // 0')"

  if [[ -z "$sprint_count" || "$sprint_count" == "null" || "$sprint_count" -eq 0 ]] 2>/dev/null; then
    echo "  ⚠ No active sprint found"
    python3 - <<PY
import csv
row = ["$board_id", "$board_name", "", "", "", "", "", "No Active Sprint", ""]
with open("$OUTPUT_FILE","a",newline="",encoding="utf-8") as f:
    csv.writer(f).writerow(row)
PY
    continue
  fi

  sprint_id="$(printf '%s' "$sprint_data" | jq -r '.values[0].id // ""')"
  sprint_name="$(printf '%s' "$sprint_data" | jq -r '.values[0].name // ""')"
  sprint_state="$(printf '%s' "$sprint_data" | jq -r '.values[0].state // ""')"
  start_date="$(printf '%s' "$sprint_data" | jq -r '(.values[0].startDate // "") | split("T")[0]')"
  end_date="$(printf '%s' "$sprint_data" | jq -r '(.values[0].endDate // "") | split("T")[0]')"
  sprint_goal="$(printf '%s' "$sprint_data" | jq -r '.values[0].goal // ""')"

  # Customer Outcome (optional)
  customer_outcome=""
  if [[ -n "$CUSTOM_OUTCOME_FIELD" && -n "$EPIC_LINK_FIELD" && -x "$SCRIPT_DIR/fetch_customer_outcomes.sh" && -n "$sprint_id" ]]; then
    customer_outcome="$(
      "$SCRIPT_DIR/fetch_customer_outcomes.sh" "$sprint_id" 2>/dev/null | aggregate_outcomes
    )"
  fi

  # Export variables for Python and write CSV row
  BOARD_ID="$board_id" \
  BOARD_NAME="$board_name" \
  SPRINT_ID="$sprint_id" \
  SPRINT_NAME="$sprint_name" \
  SPRINT_STATE="$sprint_state" \
  START_DATE="$start_date" \
  END_DATE="$end_date" \
  SPRINT_GOAL="$sprint_goal" \
  CUSTOMER_OUTCOME="$customer_outcome" \
  OUTPUT_FILE="$OUTPUT_FILE" \
  python3 -c '
import csv
import os
import re

# Normalize text: replace newlines with " | " for Excel compatibility
def normalize(text):
    if not text:
        return ""
    text = re.sub(r"\s*\n+\s*", " | ", text.strip())
    return text

row = [
  os.environ.get("BOARD_ID", ""),
  os.environ.get("BOARD_NAME", ""),
  os.environ.get("SPRINT_ID", ""),
  os.environ.get("SPRINT_NAME", ""),
  os.environ.get("SPRINT_STATE", ""),
  os.environ.get("START_DATE", ""),
  os.environ.get("END_DATE", ""),
  normalize(os.environ.get("SPRINT_GOAL", "")),
  os.environ.get("CUSTOMER_OUTCOME", "")
]
with open(os.environ["OUTPUT_FILE"], "a", newline="", encoding="utf-8") as f:
    csv.writer(f).writerow(row)
' 

  echo "  ✓ Found: $sprint_name"
done

echo
echo "================================"
echo "✅ Done! Output saved to:"
echo "$OUTPUT_FILE"
echo
echo "Preview:"
head -n 5 "$OUTPUT_FILE"