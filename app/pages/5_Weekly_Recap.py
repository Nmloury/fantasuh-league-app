# app/pages/5_Weekly_Recap.py
import io
import json
import os

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

from lib.facts import build_facts
from lib.recap_llm import generate_recap

load_dotenv()

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("Weekly League Recap (Trash-Talk)")
week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

col1, col2, col3 = st.columns([1,1,1])
with col1:
    gen = st.button("Generate Recap")
with col2:
    show_facts = st.button("Show Facts JSON")
with col3:
    export_btn = st.button("Export Markdown")

# Build facts once
facts = build_facts(sb, int(week))

if show_facts:
    st.code(json.dumps(facts, indent=2), language="json")

recap_md = None
if gen:
    recap = generate_recap(facts)
    st.markdown(f"### {recap['title']}")
    if recap.get("headlines"):
        for h in recap["headlines"]:
            st.markdown(f"- {h.get('text','')}")
    if recap.get("sections"):
        for s in recap["sections"]:
            st.markdown(f"#### {s.get('title','')}")
            st.markdown(s.get("body",""))
    # assemble MD for export
    lines = [f"# {recap['title']}", ""]
    if recap.get("headlines"):
        for h in recap["headlines"]:
            lines.append(f"- {h.get('text','')}")
        lines.append("")
    if recap.get("sections"):
        for s in recap["sections"]:
            lines.append(f"## {s.get('title','')}")
            lines.append(s.get("body",""))
            lines.append("")
    recap_md = "\n".join(lines)

if export_btn:
    if recap_md is None:
        st.warning("Generate a recap first.")
    else:
        bio = io.BytesIO(recap_md.encode("utf-8"))
        st.download_button("Download recap.md", bio, file_name=f"week_{int(week)}_recap.md", mime="text/markdown")
