#!/bin/zsh
set -e

APP_DIR="$HOME/GitHub/JIRA-AI-Assistant"
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

source "$VENV/bin/activate"

exec streamlit run ui_app_ai.py \
  --server.headless=true \
  --server.address=127.0.0.1 \
  --server.port=8503
