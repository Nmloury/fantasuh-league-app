import os
import re
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

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

# --- Cached data functions ---
@st.cache_data(show_spinner=False)
def get_latest_recap():
    """Get the most recent recap from the database."""
    try:
        result = sb.table("recaps").select("*").order("week", desc=True).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def get_closest_matchup():
    """Get the closest finished matchup from the last completed week."""
    try:
        # Get all weeks with completed matchups (both scores not null and at least one not zero)
        completed_weeks = sb.table("matchups").select("week").not_.is_("score_a", "null").not_.is_("score_b", "null").or_("score_a.gt.0,score_b.gt.0").order("week", desc=True).execute()
        
        if not completed_weeks.data:
            return None
        
        # Get the most recent completed week
        week = completed_weeks.data[0]["week"]
        
        # Get all matchups for that week with actual scores
        matchups = sb.table("matchups").select("*").eq("week", week).not_.is_("score_a", "null").not_.is_("score_b", "null").or_("score_a.gt.0,score_b.gt.0").execute()
        
        if not matchups.data:
            return None
        
        # Find closest matchup
        closest = None
        min_diff = float('inf')
        
        for matchup in matchups.data:
            diff = abs(matchup["score_a"] - matchup["score_b"])
            if diff < min_diff:
                min_diff = diff
                closest = matchup
        
        return closest, week
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def get_standings():
    """Get current standings with team names for the last completed week."""
    try:
        # Get the most recent completed week (where games have been played with actual scores)
        completed_weeks = sb.table("matchups").select("week").not_.is_("score_a", "null").not_.is_("score_b", "null").or_("score_a.gt.0,score_b.gt.0").order("week", desc=True).execute()
        
        if not completed_weeks.data:
            return []
        
        week = completed_weeks.data[0]["week"]
        
        # Get standings for that week
        standings = sb.table("v_standings").select("manager_id, cum_wins, cum_pf").eq("week", week).order("cum_wins", desc=True).order("cum_pf", desc=True).execute()
        
        # Get team names
        managers = sb.table("managers").select("manager_id, team_name").execute()
        team_names = {m["manager_id"]: m["team_name"] for m in managers.data}
        
        # Calculate records and streaks
        results = []
        for standing in standings.data:
            manager_id = standing["manager_id"]
            wins = standing["cum_wins"]
            losses = week - wins
            
            # Get recent results for streak calculation (only up to the most recent completed week)
            recent_scores = sb.table("v_team_week_scores").select("win").eq("manager_id", manager_id).gte("week", max(1, week-4)).lte("week", week).order("week", desc=True).execute()
            
            streak = "—"
            if recent_scores.data:
                streak_wins = 0
                streak_losses = 0
                for score in recent_scores.data:
                    if score["win"]:
                        if streak_losses > 0:
                            break
                        streak_wins += 1
                    else:
                        if streak_wins > 0:
                            break
                        streak_losses += 1
                
                if streak_wins > 0:
                    streak = f"W{streak_wins}"
                elif streak_losses > 0:
                    streak = f"L{streak_losses}"
            
            results.append({
                "team_name": team_names.get(manager_id, manager_id),
                "wins": wins,
                "losses": losses,
                "streak": streak
            })
        
        return results
    except Exception:
        return []

@st.cache_data(show_spinner=False)
def get_team_names():
    """Get mapping of manager_id to team_name."""
    try:
        result = sb.table("managers").select("manager_id, team_name").execute()
        return {m["manager_id"]: m["team_name"] for m in result.data}
    except Exception:
        return {}

# --- Main Layout ---
st.title("🏈 Fantasuhhhhh 2025 League Hub")

# Section 1: Weekly Recap Hero
st.header("📰 Weekly Recap")
latest_recap = get_latest_recap()

if latest_recap:
    st.subheader(latest_recap.get("title", "Weekly Recap"))
    
    # Extract first few sentences from content for blurb
    content = latest_recap.get("content_md", "")
    # Remove markdown formatting for cleaner blurb
    clean_content = re.sub(r'[#*`\[\]()]', '', content)
    sentences = clean_content.split('. ')
    blurb = '. '.join(sentences[:2]) + '.' if len(sentences) >= 2 else clean_content[:200] + "..."
    
    st.write(blurb)
    if st.button("Read full recap →", key="recap_link"):
        st.switch_page("pages/1_Weekly_Recap.py")
else:
    st.info("No recaps available yet. Check back after the first week!")

st.divider()

# Section 2: Two columns - Game of the Week and Standings
col1, col2 = st.columns(2)

with col1:
    st.header("🎯 Game of the Week")
    closest_data = get_closest_matchup()
    
    if closest_data:
        matchup, week = closest_data
        team_names = get_team_names()
        
        team_a_name = team_names.get(matchup["team_a"], matchup["team_a"])
        team_b_name = team_names.get(matchup["team_b"], matchup["team_b"])
        
        st.subheader(f"{team_a_name} vs {team_b_name}")
        st.metric("Final Score", f"{matchup['score_a']:.1f} - {matchup['score_b']:.1f}")
        st.caption(f"Closest matchup of Week {week}")
    else:
        st.info("No completed games yet.")

with col2:
    st.header("📊 Standings Snapshot")
    standings = get_standings()
    
    if standings:
        # Create compact standings table using Streamlit dataframe
        standings_data = []
        for i, team in enumerate(standings[:8], 1):  # Show top 8
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

with explore_col2:
    st.markdown("**📰 Content & Recaps**")
    
    if st.button("📰 Weekly Recaps", key="recaps_link"):
        st.switch_page("pages/1_Weekly_Recap.py")
    st.caption("AI-generated league stories")

st.divider()

# Navigation reminder
st.markdown("💡 **Quick Navigation**: Use the sidebar to jump to any page, or click the links above for detailed analysis.")
