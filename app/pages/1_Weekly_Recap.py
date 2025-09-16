# app/pages/4_Weekly_Recap.py
import io
import os

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from app.lib.streamlit_utils import get_current_week, get_available_weeks, get_recap_for_week, get_available_recap_weeks

load_dotenv()

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("📰 Weekly League Recaps")

# --- Cached data functions are now imported from streamlit_utils ---

# Get available weeks
available_weeks = get_available_recap_weeks(sb)

if not available_weeks:
    st.info("No recaps available yet. Recaps will appear here once they're generated.")
    st.stop()

# Week selector
default_week = available_weeks[0]  # Most recent week
week = st.selectbox(
    "Select Week", 
    options=available_weeks, 
    index=0,
    format_func=lambda x: f"Week {x}"
)

# Get recap for selected week
recap = get_recap_for_week(sb, week)

if recap:
    # Display recap content
    content_md = recap.get('content_md', '')
    if content_md:
        st.markdown(content_md)
    else:
        st.warning("No content available for this recap.")
    
    # Export button
    st.divider()
    if st.button("📥 Export as Markdown"):
        bio = io.BytesIO(content_md.encode("utf-8"))
        st.download_button(
            "Download recap.md", 
            bio, 
            file_name=f"week_{week}_recap.md", 
            mime="text/markdown"
        )

else:
    st.warning(f"No recap found for Week {week}.")
