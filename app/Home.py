import os
import re
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from lib.streamlit_utils import (
    get_current_week, 
    get_latest_recap, 
    get_closest_matchup, 
    get_standings, 
    get_team_names
)

# Load .env so env vars work in local dev
load_dotenv()

st.set_page_config(page_title="League Hub", layout="wide")

# --- Supabase client ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not (SUPABASE_URL and SUPABASE_KEY):
    st.error("Supabase env vars missing. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env.")
    st.stop()

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Cached data functions are now imported from streamlit_utils ---

# --- Main Layout ---
st.title("🏈 Fantasuhhhhh 2025 League Hub")

# Section 1: Weekly Recap Hero
st.header("📰 Weekly Recap")
latest_recap = get_latest_recap(sb)

if latest_recap:
    st.subheader(latest_recap.get("title", "Weekly Recap"))
    
    # Extract title and bullet points from content
    content = latest_recap.get("content_md", "")
    lines = content.split('\n')
    
    # Find bullet points (lines starting with "- ")
    bullet_points = []
    for line in lines:
        line = line.strip()
        if line.startswith('- '):
            # Remove the bullet point marker and clean up
            bullet_text = line[2:].strip()
            if bullet_text:
                bullet_points.append(bullet_text)
    
    # Display bullet points if found
    if bullet_points:
        for bullet in bullet_points:
            st.write(f"• {bullet}")
    else:
        # Fallback: show first few lines if no bullet points found
        first_lines = [line.strip() for line in lines[:3] if line.strip() and not line.startswith('#')]
        if first_lines:
            st.write('\n'.join(first_lines))
    if st.button("Read full recap →", key="recap_link"):
        st.switch_page("pages/1_Weekly_Recap.py")
else:
    st.info("No recaps available yet. Check back after the first week!")

st.divider()

# Section 2: Two columns - Game of the Week and Standings
col1, col2 = st.columns(2)

with col1:
    st.header("🎯 Game of the Week")
    closest_data = get_closest_matchup(sb)
    
    if closest_data:
        matchup, week = closest_data
        team_names = get_team_names(sb)
        
        team_a_name = team_names.get(matchup["team_a"], matchup["team_a"])
        team_b_name = team_names.get(matchup["team_b"], matchup["team_b"])
        
        st.subheader(f"{team_a_name} vs {team_b_name}")
        st.metric("Final Score", f"{matchup['score_a']:.1f} - {matchup['score_b']:.1f}")
        st.caption(f"Closest matchup of Week {week}")
    else:
        st.info("No completed games yet.")

with col2:
    st.header("📊 Standings Snapshot")
    standings = get_standings(sb)
    
    if standings:
        # Create compact standings table using Streamlit dataframe
        standings_data = []
        for i, team in enumerate(standings, 1):  # Show all teams
            standings_data.append({
                "Rank": i,
                "Team": team['team_name'],
                "Record": f"{team['wins']}-{team['losses']}",
                "Streak": team['streak']
            })
        
        if standings_data:
            st.dataframe(
                standings_data,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rank": st.column_config.NumberColumn("Rank", width="small"),
                    "Team": st.column_config.TextColumn("Team", width="medium"),
                    "Record": st.column_config.TextColumn("Record", width="small"),
                    "Streak": st.column_config.TextColumn("Streak", width="small")
                }
            )
    else:
        st.info("No completed games yet.")

st.divider()

# Section 3: What Else You Can Explore
st.header("🔍 What Else You Can Explore")

explore_col1, explore_col2 = st.columns(2)

with explore_col1:
    st.markdown("**📈 Analytics & Insights**")
    
    if st.button("🎯 Luck Index & Expected Wins", key="luck_link"):
        st.switch_page("pages/4_Luck_and Expected_Wins.py")
    st.caption("See who's getting lucky")
    
    if st.button("⚡ Lineup Efficiency", key="lineup_link"):
        st.switch_page("pages/2_Lineup_Efficiency.py")
    st.caption("Optimal lineup analysis")
    
    if st.button("💰 FAAB ROI", key="faab_link"):
        st.switch_page("pages/3_FAAB_ROI.py")
    st.caption("Free agent acquisition value")
    
    if st.button("🏈 Draft ROI", key="draft_link"):
        st.switch_page("pages/4_Draft_ROI.py")
    st.caption("Draft pick value analysis")

with explore_col2:
    st.markdown("**📰 Content & Recaps**")
    
    if st.button("📰 Weekly Recaps", key="recaps_link"):
        st.switch_page("pages/1_Weekly_Recap.py")
    st.caption("AI-generated league stories")

st.divider()

# Navigation reminder
st.markdown("💡 **Quick Navigation**: Use the sidebar to jump to any page, or click the links above for detailed analysis.")
