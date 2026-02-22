#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env automatically
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

SPRINT_ID="${1:?Usage: fetch_customer_outcomes.sh <SPRINT_ID>}"

: "${JIRA_URL:?Missing JIRA_URL}"
: "${JIRA_USERNAME:?Missing JIRA_USERNAME}"
: "${JIRA_API_TOKEN:?Missing JIRA_API_TOKEN}"
: "${CUSTOM_OUTCOME_FIELD:?Missing CUSTOM_OUTCOME_FIELD}"
: "${EPIC_LINK_FIELD:?Missing EPIC_LINK_FIELD}"

AUTH="$JIRA_USERNAME:$JIRA_API_TOKEN"

curl_json() {
  curl -sS -f -u "$AUTH" -H "Accept: application/json" "$1"
}

is_json_object() {
  local s="$1"
  local first
  first="$(printf '%s' "$s" | tr -d ' \n\r\t' | head -c 1 || true)"
  [[ "$first" == "{" ]]
}

issues_url="$JIRA_URL/rest/agile/1.0/sprint/$SPRINT_ID/issue?maxResults=200&fields=parent,$EPIC_LINK_FIELD"
issues_json="$(curl_json "$issues_url" 2>/dev/null || true)"

if [[ -z "$issues_json" ]] || ! is_json_object "$issues_json"; then
  exit 0
fi

epics="$(printf '%s' "$issues_json" | python3 -c '
import sys, json, os
data=json.load(sys.stdin)
epic_field=os.environ["EPIC_LINK_FIELD"]
keys=set()
for it in data.get("issues", []):
    f=it.get("fields") or {}
    parent=f.get("parent") or {}
    if parent.get("key"):
        keys.add(parent["key"])
    el=f.get(epic_field)
    if isinstance(el, str) and el.strip():
        keys.add(el.strip())
    epic_obj=it.get("epic") or {}
    if isinstance(epic_obj, dict) and epic_obj.get("key"):
        keys.add(epic_obj["key"])
for k in sorted(keys):
    print(k)
')"

[[ -z "$epics" ]] && exit 0

while IFS= read -r epic; do
  [[ -z "$epic" ]] && continue

  epic_url="$JIRA_URL/rest/api/3/issue/$epic?fields=$CUSTOM_OUTCOME_FIELD"
  epic_json="$(curl_json "$epic_url" 2>/dev/null || true)"
  [[ -z "$epic_json" ]] && continue
  is_json_object "$epic_json" || continue

  printf '%s' "$epic_json" | python3 -c '
import sys, json, os

def adf_to_text(node):
    if node is None: return ""
    if isinstance(node, str): return node
    if isinstance(node, list):
        return "\n".join([adf_to_text(x) for x in node if x]).strip()
    if isinstance(node, dict):
        t=node.get("type")
        if t=="text":
            return node.get("text","")
        parts=[adf_to_text(c) for c in (node.get("content") or [])]
        parts=[p for p in parts if p]
        if t in ("paragraph","heading"):
            return "\n".join(parts).strip()
        return "".join(parts).strip()
    return ""

j=json.load(sys.stdin)
field=os.environ["CUSTOM_OUTCOME_FIELD"]
raw=(j.get("fields") or {}).get(field)

text=""
if isinstance(raw, dict) and raw.get("type")=="doc":
    text=adf_to_text(raw).strip()
else:
    text=str(raw or "").strip()

if text:
    print(json.dumps({"epic": j.get("key",""), "outcome": text}))
'
done <<< "$epics"