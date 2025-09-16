# app/pages/3_FAAB_ROI.py
import os
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from supabase import create_client
from app.lib.streamlit_utils import get_faab_roi_data, get_managers_data, get_players_data

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("💰 FAAB ROI")

# High-level description
st.markdown("""
**What this shows:** This analysis measures the return on investment (ROI) for your free agent acquisitions. 
It shows how many fantasy points you got per dollar spent on each player, helping you evaluate your FAAB spending strategy.
""")

rows = get_faab_roi_data(sb)
if not rows:
    st.info("No FAAB ROI records yet.")
else:
    df = pd.DataFrame(rows)
    names = get_managers_data(sb)
    players = get_players_data(sb)
    name_map = {n["manager_id"]: n["team_name"] for n in names}
    pmap = {p["player_id"]: p["name"] for p in players}

    df["team_name"] = df["manager_id"].map(name_map)
    df["player"] = df["player_id"].map(pmap)

    # Support either-single or dual-metric implementations
    if "points_added_starts" in df.columns:
        df["ppd_starts"] = (df["points_added_starts"] / df["faab_spent"]).replace([float("inf")], None).round(3)
    if "points_added_on_roster" in df.columns:
        df["ppd_on_roster"] = (df["points_added_on_roster"] / df["faab_spent"]).replace([float("inf")], None).round(3)
    if "points_added" in df.columns and "ppd_starts" not in df.columns:
        df["ppd"] = (df["points_added"] / df["faab_spent"]).replace([float("inf")], None).round(3)

    # Prepare display columns based on available data
    display_columns = ["team_name", "player", "faab_spent"]
    column_names = ["Team", "Player", "FAAB Spent ($)"]
    
    # Add available metrics
    if "pts_all" in df.columns:
        display_columns.extend(["pts_all", "pts_per_dollar_all"])
        column_names.extend(["Total Points", "Points per $"])
    if "pts_starting" in df.columns:
        display_columns.extend(["pts_starting", "pts_per_dollar_starting"])
        column_names.extend(["Starting Points", "Starting Points per $"])
    if "start_week" in df.columns and "end_week" in df.columns:
        display_columns.extend(["start_week", "end_week"])
        column_names.extend(["Start Week", "End Week"])
    
    display_df = df[display_columns].copy()
    display_df.columns = column_names
    
    # Sort by FAAB spent (highest first)
    display_df = display_df.sort_values("FAAB Spent ($)", ascending=False)
    
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
        # FAAB Spent range filter
        faab_min, faab_max = int(display_df['FAAB Spent ($)'].min()), int(display_df['FAAB Spent ($)'].max())
        faab_range = st.slider(
            "FAAB Spent ($)", 
            min_value=faab_min, 
            max_value=faab_max, 
            value=(faab_min, faab_max),
            help="Filter by FAAB amount spent"
        )
        
        # Points per $ range filter (if available)
        if "Points per $" in display_df.columns:
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
        # Starting Points per $ range filter (if available)
        if "Starting Points per $" in display_df.columns:
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
        
        # Week range filter (if available)
        if "Start Week" in display_df.columns and "End Week" in display_df.columns:
            week_min, week_max = int(display_df['Start Week'].min()), int(display_df['End Week'].max())
            week_range = st.slider(
                "Week Range", 
                min_value=week_min, 
                max_value=week_max, 
                value=(week_min, week_max),
                help="Filter by acquisition week range"
            )
    
    # Apply filters
    filtered_df = display_df.copy()
    
    # Team filter
    filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]
    
    # Player filter
    if player_search:
        filtered_df = filtered_df[filtered_df['Player'].str.contains(player_search, case=False, na=False)]
    
    # FAAB range filter
    filtered_df = filtered_df[
        (filtered_df['FAAB Spent ($)'] >= faab_range[0]) & 
        (filtered_df['FAAB Spent ($)'] <= faab_range[1])
    ]
    
    # Points per $ range filter
    if "Points per $" in display_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Points per $'].isna()) | 
            ((filtered_df['Points per $'] >= ppd_range[0]) & (filtered_df['Points per $'] <= ppd_range[1]))
        ]
    
    # Starting Points per $ range filter
    if "Starting Points per $" in display_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Starting Points per $'].isna()) | 
            ((filtered_df['Starting Points per $'] >= sppd_range[0]) & (filtered_df['Starting Points per $'] <= sppd_range[1]))
        ]
    
    # Week range filter
    if "Start Week" in display_df.columns and "End Week" in display_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Start Week'] >= week_range[0]) & 
            (filtered_df['Start Week'] <= week_range[1])
        ]
    
    # Show filter results summary
    st.caption(f"Showing {len(filtered_df)} of {len(display_df)} records")
    
    # Use filtered data for display
    display_df = filtered_df
    
    # Configure column display
    column_config = {
        "Team": st.column_config.TextColumn("Team", width="medium"),
        "Player": st.column_config.TextColumn("Player", width="medium"),
        "FAAB Spent ($)": st.column_config.NumberColumn("FAAB Spent ($)", width="small", help="Dollars spent to acquire this player")
    }
    
    # Add dynamic column configs
    if "Total Points" in column_names:
        column_config["Total Points"] = st.column_config.NumberColumn("Total Points", width="small", help="Total fantasy points scored while on roster")
    if "Points per $" in column_names:
        column_config["Points per $"] = st.column_config.NumberColumn("Points per $", width="small", help="Fantasy points per dollar spent")
    if "Starting Points" in column_names:
        column_config["Starting Points"] = st.column_config.NumberColumn("Starting Points", width="small", help="Points scored when player was in starting lineup")
    if "Starting Points per $" in column_names:
        column_config["Starting Points per $"] = st.column_config.NumberColumn("Starting Points per $", width="small", help="Starting points per dollar spent")
    if "Start Week" in column_names:
        column_config["Start Week"] = st.column_config.NumberColumn("Start Week", width="small", help="Week player was acquired")
    if "End Week" in column_names:
        column_config["End Week"] = st.column_config.NumberColumn("End Week", width="small", help="Week player was dropped or season ended")

    # Display table
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config=column_config
    )
    
    # Create scatter plot: Team-level FAAB ROI (aggregated across all players)
    if "Points per $" in display_df.columns:
        # Aggregate by team: total FAAB spent vs total points per dollar
        team_roi = display_df.groupby('Team').agg({
            'FAAB Spent ($)': 'sum',
            'Total Points': 'sum'
        }).reset_index()
        team_roi['Points per $'] = (team_roi['Total Points'] / team_roi['FAAB Spent ($)']).round(3)
        team_roi = team_roi[team_roi['FAAB Spent ($)'] > 0]  # Remove teams with no FAAB spending
        
        if not team_roi.empty:
            scatter = alt.Chart(team_roi).mark_circle(size=120, color='#4682B4').encode(
                x=alt.X('FAAB Spent ($):Q', title='Total FAAB Spent ($)'),
                y=alt.Y('Points per $:Q', title='Points per $'),
                tooltip=['Team:N', 'FAAB Spent ($):Q', 'Points per $:Q', 'Total Points:Q']
            ).properties(
                title='Team FAAB Investment vs ROI (All Players)',
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
                x=alt.X('FAAB Spent ($):Q', title='Total FAAB Spent ($)'),
                y=alt.Y('Points per $:Q', title='Points per $'),
                text='Team:N'
            )
            
            st.altair_chart(scatter + labels, use_container_width=True)
        else:
            st.info("No team-level ROI data available for charting")
    else:
        # Fallback: Show FAAB spending by team
        team_spending = display_df.groupby('Team')['FAAB Spent ($)'].sum().reset_index()
        
        bars = alt.Chart(team_spending).mark_bar().encode(
            x=alt.X('FAAB Spent ($):Q', title='Total FAAB Spent ($)'),
            y=alt.Y('Team:N', title='Team', sort='-x'),
            color=alt.Color('FAAB Spent ($):Q', 
                          scale=alt.Scale(scheme='blues'),
                          legend=None),
            tooltip=['Team:N', 'FAAB Spent ($):Q']
        ).properties(
            title='Total FAAB Spending by Team (All Players)',
            height=400
        )
        
        st.altair_chart(bars, use_container_width=True)
    
    # Create second chart: Team-level starting points per $ (aggregated across all players)
    if "Starting Points per $" in display_df.columns:
        # Aggregate by team: total FAAB spent vs total starting points per dollar
        team_starting_roi = display_df.groupby('Team').agg({
            'FAAB Spent ($)': 'sum',
            'Starting Points': 'sum'
        }).reset_index()
        team_starting_roi['Starting Points per $'] = (team_starting_roi['Starting Points'] / team_starting_roi['FAAB Spent ($)']).round(3)
        team_starting_roi = team_starting_roi[team_starting_roi['FAAB Spent ($)'] > 0]  # Remove teams with no FAAB spending
        
        if not team_starting_roi.empty:
            starting_scatter = alt.Chart(team_starting_roi).mark_circle(size=120).encode(
                x=alt.X('FAAB Spent ($):Q', title='Total FAAB Spent ($)'),
                y=alt.Y('Starting Points per $:Q', title='Starting Points per $'),
                tooltip=['Team:N', 'FAAB Spent ($):Q', 'Starting Points per $:Q', 'Starting Points:Q']
            ).properties(
                title='Team FAAB Investment vs Starting Points ROI (All Players)',
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
                x=alt.X('FAAB Spent ($):Q', title='Total FAAB Spent ($)'),
                y=alt.Y('Starting Points per $:Q', title='Starting Points per $'),
                text='Team:N'
            )
            
            st.altair_chart(starting_scatter + starting_labels, use_container_width=True)
        else:
            st.info("No team-level starting points ROI data available for charting")

# Detailed explanation
with st.expander("📖 How FAAB ROI Works"):
    st.markdown("""
    **Key Metrics:**
    - **FAAB Spent**: Dollars spent to acquire the player
    - **Total Points**: All fantasy points scored while on your roster
    - **Starting Points**: Points scored when player was in your starting lineup
    - **Points per $**: Return on investment (points ÷ dollars spent)
    
    **What to Look For:**
    - **High Points per $**: Great value acquisitions
    - **Low Points per $**: Expensive pickups that didn't pan out
    - **Starting vs Total Points**: Shows if you used the player effectively
    
    **Note**: This analysis only includes players acquired via FAAB bidding, not trades or waiver claims.
    """)
