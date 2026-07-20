"""Streamlit interface for the simple personal digital twin."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from digital_twin import answer_question, build_chunks, load_profile


PROFILE_PATH = Path(__file__).parent / "data" / "profile.json"

st.set_page_config(page_title="My Digital Twin", page_icon="🤖", layout="centered")

profile = load_profile(PROFILE_PATH)
chunks = build_chunks(profile)

with st.sidebar:
    st.header("Settings")
    engine = st.selectbox(
        "Answer engine",
        ["Built-in retrieval", "Ollama (local AI)"],
        help="Built-in mode works immediately. Ollama writes more natural answers.",
    )
    model = st.text_input("Ollama model", value="llama3.2:3b")
    base_url = st.text_input(
        "Ollama URL", value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    st.divider()
    st.caption("Personal data comes only from `data/profile.json`.")
    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("🤖 My Digital Twin")
st.write(
    f"Ask questions about **{profile.get('name', 'this person')}**. "
    "Answers are grounded in the editable profile file."
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! Ask me about my skills, experience, education, or projects.",
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("engine"):
            st.caption(f"Engine: {message['engine']}")
        if message.get("context"):
            with st.expander("Profile context used"):
                for item in message["context"]:
                    st.write(f"**{item['section']}** — {item['text']}")

if question := st.chat_input("Example: What projects have you built?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching my profile..."):
            answer, context, used_engine = answer_question(
                question=question,
                chunks=chunks,
                use_ollama=engine.startswith("Ollama"),
                model=model,
                base_url=base_url,
            )
        st.markdown(answer)
        st.caption(f"Engine: {used_engine}")
        if context:
            with st.expander("Profile context used"):
                for item in context:
                    st.write(f"**{item['section']}** — {item['text']}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "engine": used_engine,
            "context": context,
        }
    )
