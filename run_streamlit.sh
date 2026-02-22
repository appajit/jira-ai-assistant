#!/bin/bash
set -e
cd "/Users/appaji.tholeti/Projects/sprint-goals-agent"
source "/Users/appaji.tholeti/Projects/sprint-goals-agent/.venv/bin/activate"
exec streamlit run ui_app.py --server.address 0.0.0.0 --server.port 8501
