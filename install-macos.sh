#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.sprintgoals.streamlit"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/sprint-goals-agent"

mkdir -p "$LOG_DIR"

# 1) Ensure venv exists
if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi

# 2) Install deps
source "$APP_DIR/.venv/bin/activate"
pip install -U pip >/dev/null
pip install -U streamlit >/dev/null
# If you have requirements.txt, use it. Otherwise install your key deps:
pip install -U langchain langgraph langchain-openai python-dotenv typer >/dev/null

# 3) Create a small runner script
RUNNER="$APP_DIR/run_streamlit.sh"
cat > "$RUNNER" <<EOF
#!/bin/bash
set -e
cd "$APP_DIR"
source "$APP_DIR/.venv/bin/activate"
exec streamlit run ui_app.py --server.address 0.0.0.0 --server.port 8501
EOF
chmod +x "$RUNNER"

# 4) Create LaunchAgent plist
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"\>
<plist version="1.0">
 <dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${RUNNER}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${LOG_DIR}/stdout.log</string>
  <key>StandardErrorPath</key><string>${LOG_DIR}/stderr.log</string>
 </dict>
</plist>
EOF

# 5) Load + start service
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
launchctl start "$LABEL"

echo "✅ Installed and started."
echo "Open: http://localhost:8501"
