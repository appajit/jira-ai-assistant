import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
from langchain_core.messages import HumanMessage

from agent.config import Settings
from agent.graph import build_graph

ROOT = Path(__file__).parent

# Load .env explicitly for local dev (avoids Python 3.13 dotenv auto-discovery issues)
load_dotenv(dotenv_path=ROOT / ".env", override=True)

# On Streamlit Cloud, load secrets into environment variables
if hasattr(st, "secrets"):
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ.setdefault(key, value)

st.set_page_config(page_title="JIRA Assistant AI", page_icon="🤖", layout="centered")
st.title("🤖 JIRA Assistant AI")
st.caption('Try: "Fetch sprint details for Aqua", "Fetch sprint details for all teams", "Push to Miro"')

settings = Settings.load(ROOT)
graph = build_graph(
    scripts_dir=settings.scripts_dir,
    board_ids_file=settings.board_ids_file,
    default_miro_board_id=settings.default_miro_board_id,
)

if "history" not in st.session_state:
    st.session_state.history = []  # [{"role": "user"|"assistant", "content": "..."}]

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Type your request…")
if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    result = graph.invoke({"messages": [HumanMessage(content=prompt)]})
    reply = result["messages"][-1].content

    st.session_state.history.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)