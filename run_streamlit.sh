#!/bin/bash
set -e
cd "/Users/appaji.tholeti/GitHub/JIRA-AI-Assistant"
source "/Users/appaji.tholeti/GitHub/JIRA-AI-Assistant/.venv/bin/activate"
exec streamlit run ui_app.py --server.address 0.0.0.0 --server.port 8501
