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

BOARD_FILE="$REPO_ROOT/board_ids.txt"

# Collect board IDs:
# - If args are provided, use them
# - Else read from board_ids.txt
BOARD_IDS=()
if [[ $# -gt 0 ]]; then
  for b in "$@"; do BOARD_IDS+=("$b"); done
else
  if [[ ! -f "$BOARD_FILE" ]]; then
    echo "❌ board_ids.txt not found at: $BOARD_FILE"
    exit 1
  fi
  while IFS= read -r line; do
    line="$(echo "$line" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue
    BOARD_IDS+=("$line")
  done < "$BOARD_FILE"
fi

if [[ ${#BOARD_IDS[@]} -eq 0 ]]; then
  echo "❌ No board IDs found."
  exit 1
fi

echo "Fetching sprint goals for boards: ${BOARD_IDS[*]}"
echo

exec "$SCRIPT_DIR/fetch_sprint_details.sh" "${BOARD_IDS[@]}"