# app/pages/4_Draft_ROI.py
import os
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("🏈 Draft ROI")

# High-level description
st.markdown("""
**What this shows:** This analysis measures the return on investment (ROI) for your draft picks. 
It shows how many fantasy points you got per draft pick spent on each player, helping you evaluate your draft strategy and player value.
""")

rows = sb.table("draft_roi").select("*").execute().data
if not rows:
    st.info("No Draft ROI records yet.")
else:
    df = pd.DataFrame(rows)
    names = sb.table("managers").select("manager_id,team_name").execute().data
    players = sb.table("players").select("player_id,name").execute().data
    name_map = {n["manager_id"]: n["team_name"] for n in names}
    pmap = {p["player_id"]: p["name"] for p in players}

    df["team_name"] = df["manager_id"].map(name_map)
    df["player"] = df["player_id"].map(pmap)

    # Prepare display columns
    display_columns = ["team_name", "player", "draft_cost", "pts_all", "pts_per_dollar_all", "pts_starting", "pts_per_dollar_starting"]
    column_names = ["Team", "Player", "Draft Cost (Pick)", "Total Points", "Points per $", "Starting Points", "Starting Points per $"]
    
    display_df = df[display_columns].copy()
    display_df.columns = column_names
    
    # Sort by draft cost (highest first)
    display_df = display_df.sort_values("Draft Cost (Pick)", ascending=False)
    
    # === FILTERS SECTION ===
    st.subheader("🔍 Filters")
    
    # Team filter - full width at top
    available_teams = sorted(display_df['Team'].unique())
    selected_teams = st.multiselect(
        "Teams", 
        options=available_teams, 
        default=available_teams,
        help="Select teams to include in analysis"
    )
    
    # Create three columns for remaining filter layout
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Player filter - always use search for players
        player_search = st.text_input(
            "🔍 Search Players", 
            placeholder="Type player name...",
            help="Search for specific players"
        )
        if player_search:
            available_players = [p for p in display_df['Player'].unique() if player_search.lower() in p.lower()]
        else:
            available_players = display_df['Player'].unique()
    
    with col2:
        # Draft Cost range filter
        cost_min, cost_max = int(display_df['Draft Cost (Pick)'].min()), int(display_df['Draft Cost (Pick)'].max())
        cost_range = st.slider(
            "Draft Cost (Pick)", 
            min_value=cost_min, 
            max_value=cost_max, 
            value=(cost_min, cost_max),
            help="Filter by draft pick number"
        )
        
        # Points per $ range filter
        ppd_data = display_df['Points per $'].dropna()
        if not ppd_data.empty:
            ppd_min, ppd_max = float(ppd_data.min()), float(ppd_data.max())
            # Handle case where min == max
            if ppd_min == ppd_max:
                ppd_max = ppd_min + 0.01
            ppd_range = st.slider(
                "Points per $", 
                min_value=ppd_min, 
                max_value=ppd_max, 
                value=(ppd_min, ppd_max),
                format="%.2f",
                help="Filter by points per dollar ratio"
            )
    
    with col3:
        # Starting Points per $ range filter
        sppd_data = display_df['Starting Points per $'].dropna()
        if not sppd_data.empty:
            sppd_min, sppd_max = float(sppd_data.min()), float(sppd_data.max())
            # Handle case where min == max
            if sppd_min == sppd_max:
                sppd_max = sppd_min + 0.01
            sppd_range = st.slider(
                "Starting Points per $", 
                min_value=sppd_min, 
                max_value=sppd_max, 
                value=(sppd_min, sppd_max),
                format="%.2f",
                help="Filter by starting points per dollar ratio"
            )
    
    # Apply filters
    filtered_df = display_df.copy()
    
    # Team filter
    filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]
    
    # Player filter
    if player_search:
        filtered_df = filtered_df[filtered_df['Player'].str.contains(player_search, case=False, na=False)]
    
    # Draft cost range filter
    filtered_df = filtered_df[
        (filtered_df['Draft Cost (Pick)'] >= cost_range[0]) & 
        (filtered_df['Draft Cost (Pick)'] <= cost_range[1])
    ]
    
    # Points per $ range filter
    filtered_df = filtered_df[
        (filtered_df['Points per $'].isna()) | 
        ((filtered_df['Points per $'] >= ppd_range[0]) & (filtered_df['Points per $'] <= ppd_range[1]))
    ]
    
    # Starting Points per $ range filter
    filtered_df = filtered_df[
        (filtered_df['Starting Points per $'].isna()) | 
        ((filtered_df['Starting Points per $'] >= sppd_range[0]) & (filtered_df['Starting Points per $'] <= sppd_range[1]))
    ]
    
    # Show filter results summary
    st.caption(f"Showing {len(filtered_df)} of {len(display_df)} records")
    
    # Use filtered data for display
    display_df = filtered_df
    
    # Configure column display
    column_config = {
        "Team": st.column_config.TextColumn("Team", width="medium"),
        "Player": st.column_config.TextColumn("Player", width="medium"),
        "Draft Cost (Pick)": st.column_config.NumberColumn("Draft Cost (Pick)", width="small", help="Draft pick number used to acquire this player"),
        "Total Points": st.column_config.NumberColumn("Total Points", width="small", help="Total fantasy points scored while on roster"),
        "Points per $": st.column_config.NumberColumn("Points per $", width="small", help="Fantasy points per draft pick spent"),
        "Starting Points": st.column_config.NumberColumn("Starting Points", width="small", help="Points scored when player was in starting lineup"),
        "Starting Points per $": st.column_config.NumberColumn("Starting Points per $", width="small", help="Starting points per draft pick spent")
    }

    # Display table
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config=column_config
    )
    
    # Create scatter plot: Team-level Draft ROI (aggregated across all players)
    # Aggregate by team: total draft investment vs total points per dollar
    team_roi = display_df.groupby('Team').agg({
        'Draft Cost (Pick)': 'sum',
        'Total Points': 'sum'
    }).reset_index()
    team_roi['Points per $'] = (team_roi['Total Points'] / team_roi['Draft Cost (Pick)']).round(3)
    team_roi = team_roi[team_roi['Draft Cost (Pick)'] > 0]  # Remove teams with no draft investment
    
    if not team_roi.empty:
        scatter = alt.Chart(team_roi).mark_circle(size=120, color='#4682B4').encode(
            x=alt.X('Draft Cost (Pick):Q', title='Total Draft Investment (Sum of Pick Numbers)'),
            y=alt.Y('Points per $:Q', title='Points per $'),
            tooltip=['Team:N', 'Draft Cost (Pick):Q', 'Points per $:Q', 'Total Points:Q']
        ).properties(
            title='Team Draft Investment vs ROI (Total Points)',
            height=400
        )
        
        # Add team name labels
        labels = alt.Chart(team_roi).mark_text(
            align='left',
            baseline='middle',
            dx=8,
            fontSize=12,
            fontWeight='bold',
            color='white'  # Match dark theme text color
        ).encode(
            x=alt.X('Draft Cost (Pick):Q', title='Total Draft Investment (Sum of Pick Numbers)'),
            y=alt.Y('Points per $:Q', title='Points per $'),
            text='Team:N'
        )
        
        st.altair_chart(scatter + labels, use_container_width=True)
    else:
        st.info("No team-level ROI data available for charting")
    
    # Create second chart: Team-level starting points per $ (aggregated across all players)
    # Aggregate by team: total draft investment vs total starting points per dollar
    team_starting_roi = display_df.groupby('Team').agg({
        'Draft Cost (Pick)': 'sum',
        'Starting Points': 'sum'
    }).reset_index()
    team_starting_roi['Starting Points per $'] = (team_starting_roi['Starting Points'] / team_starting_roi['Draft Cost (Pick)']).round(3)
    team_starting_roi = team_starting_roi[team_starting_roi['Draft Cost (Pick)'] > 0]  # Remove teams with no draft investment
    
    if not team_starting_roi.empty:
        starting_scatter = alt.Chart(team_starting_roi).mark_circle(size=120).encode(
            x=alt.X('Draft Cost (Pick):Q', title='Total Draft Investment (Sum of Pick Numbers)'),
            y=alt.Y('Starting Points per $:Q', title='Starting Points per $'),
            tooltip=['Team:N', 'Draft Cost (Pick):Q', 'Starting Points per $:Q', 'Starting Points:Q']
        ).properties(
            title='Team Draft Investment vs Starting Points ROI',
            height=400
        )
        
        # Add team name labels
        starting_labels = alt.Chart(team_starting_roi).mark_text(
            align='left',
            baseline='middle',
            dx=8,
            fontSize=12,
            fontWeight='bold',
            color='white'  # Match dark theme text color
        ).encode(
            x=alt.X('Draft Cost (Pick):Q', title='Total Draft Investment (Sum of Pick Numbers)'),
            y=alt.Y('Starting Points per $:Q', title='Starting Points per $'),
            text='Team:N'
        )
        
        st.altair_chart(starting_scatter + starting_labels, use_container_width=True)
    else:
        st.info("No team-level starting points ROI data available for charting")

# Detailed explanation
with st.expander("📖 How Draft ROI Works"):
    st.markdown("""
    **Key Metrics:**
    - **Draft Cost (Pick)**: Draft pick number used to acquire the player
    - **Total Points**: All fantasy points scored while on your roster
    - **Starting Points**: Points scored when player was in your starting lineup
    - **Points per $**: Return on investment (points ÷ draft pick number)
    
    **What to Look For:**
    - **High Points per $**: Great value draft picks (late round steals)
    - **Low Points per $**: Early round picks that didn't pan out
    - **Starting vs Total Points**: Shows if you used the player effectively in your lineup
    
    **Note**: This analysis only includes players acquired through the draft, not free agent pickups or trades.
    Lower draft pick numbers (earlier picks) represent higher "cost" in this analysis.
    """)
