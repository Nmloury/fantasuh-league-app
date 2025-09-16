# app/pages/2_Lineup_Efficiency.py
import os
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from supabase import create_client
from app.lib.streamlit_utils import get_lineup_efficiency_data, get_managers_data

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("⚡ Lineup Efficiency")

# High-level description
st.markdown("""
**What this shows:** This analysis compares your actual lineup performance to the optimal lineup you could have started. 
It shows how many points you left on the bench and how efficiently you're using your roster.
""")

# Get all data for filtering
all_le = get_lineup_efficiency_data(sb)
names = get_managers_data(sb)

df = pd.DataFrame(all_le)
if df.empty:
    st.info("No lineup efficiency data available yet.")
else:
    name_map = {n["manager_id"]: n["team_name"] for n in names}
    df["team_name"] = df["manager_id"].map(name_map)
    df = df[["week","team_name","actual_pts","optimal_pts","regret","efficiency"]]
    df["efficiency"] = df["efficiency"].round(3)
    
    # Prepare data with human-readable column names
    display_df = df.copy()
    display_df.columns = ["Week", "Team", "Actual Points", "Optimal Points", "Points Left on Bench", "Efficiency %"]
    display_df["Efficiency %"] = (display_df["Efficiency %"] * 100).round(1)
    
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
        # Week range filter
        week_min, week_max = int(display_df['Week'].min()), int(display_df['Week'].max())
        # Handle case where there's only one week of data
        if week_min == week_max:
            st.write(f"**Week:** {week_min}")
            week_range = (week_min, week_max)
        else:
            week_range = st.slider(
                "Week Range", 
                min_value=week_min, 
                max_value=week_max, 
                value=(week_min, week_max),  # Default to all weeks
                help="Filter by week range"
            )
    
    with col2:
        # Efficiency % range filter
        eff_min, eff_max = float(display_df['Efficiency %'].min()), float(display_df['Efficiency %'].max())
        # Handle case where min == max
        if eff_min == eff_max:
            eff_max = eff_min + 0.1
        eff_range = st.slider(
            "Efficiency %", 
            min_value=eff_min, 
            max_value=eff_max, 
            value=(eff_min, eff_max),
            format="%.1f",
            help="Filter by lineup efficiency percentage"
        )
        
        # Actual Points range filter
        actual_min, actual_max = float(display_df['Actual Points'].min()), float(display_df['Actual Points'].max())
        # Handle case where min == max
        if actual_min == actual_max:
            actual_max = actual_min + 0.1
        actual_range = st.slider(
            "Actual Points", 
            min_value=actual_min, 
            max_value=actual_max, 
            value=(actual_min, actual_max),
            format="%.1f",
            help="Filter by actual points scored"
        )
    
    with col3:
        # Points Left on Bench range filter
        regret_min, regret_max = float(display_df['Points Left on Bench'].min()), float(display_df['Points Left on Bench'].max())
        # Handle case where min == max
        if regret_min == regret_max:
            regret_max = regret_min + 0.1
        regret_range = st.slider(
            "Points Left on Bench", 
            min_value=regret_min, 
            max_value=regret_max, 
            value=(regret_min, regret_max),
            format="%.1f",
            help="Filter by points left on bench"
        )
        
        # Optimal Points range filter
        optimal_min, optimal_max = float(display_df['Optimal Points'].min()), float(display_df['Optimal Points'].max())
        # Handle case where min == max
        if optimal_min == optimal_max:
            optimal_max = optimal_min + 0.1
        optimal_range = st.slider(
            "Optimal Points", 
            min_value=optimal_min, 
            max_value=optimal_max, 
            value=(optimal_min, optimal_max),
            format="%.1f",
            help="Filter by optimal points possible"
        )
    
    # Apply filters
    filtered_df = display_df.copy()
    
    # Week range filter
    filtered_df = filtered_df[
        (filtered_df['Week'] >= week_range[0]) & 
        (filtered_df['Week'] <= week_range[1])
    ]
    
    # Team filter
    filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]
    
    # Efficiency % range filter
    filtered_df = filtered_df[
        (filtered_df['Efficiency %'] >= eff_range[0]) & 
        (filtered_df['Efficiency %'] <= eff_range[1])
    ]
    
    # Actual Points range filter
    filtered_df = filtered_df[
        (filtered_df['Actual Points'] >= actual_range[0]) & 
        (filtered_df['Actual Points'] <= actual_range[1])
    ]
    
    # Points Left on Bench range filter
    filtered_df = filtered_df[
        (filtered_df['Points Left on Bench'] >= regret_range[0]) & 
        (filtered_df['Points Left on Bench'] <= regret_range[1])
    ]
    
    # Optimal Points range filter
    filtered_df = filtered_df[
        (filtered_df['Optimal Points'] >= optimal_range[0]) & 
        (filtered_df['Optimal Points'] <= optimal_range[1])
    ]
    
    # Show filter results summary
    st.caption(f"Showing {len(filtered_df)} of {len(display_df)} records")
    
    # Use filtered data for display
    display_df = filtered_df
    
    # Sort by points left on bench (regret) - highest first
    display_df = display_df.sort_values("Points Left on Bench", ascending=False)
    
    # Display table
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "Week": st.column_config.NumberColumn("Week", width="small"),
            "Team": st.column_config.TextColumn("Team", width="medium"),
            "Actual Points": st.column_config.NumberColumn("Actual Points", width="small", help="Points scored by your starting lineup"),
            "Optimal Points": st.column_config.NumberColumn("Optimal Points", width="small", help="Maximum points possible with your roster"),
            "Points Left on Bench": st.column_config.NumberColumn("Points Left on Bench", width="small", help="Points you missed by not starting optimal lineup"),
            "Efficiency %": st.column_config.NumberColumn("Efficiency %", width="small", help="Actual Points / Optimal Points × 100")
        }
    )
    
    # Create bar chart: Average Efficiency % by Team (across all weeks)
    team_efficiency = display_df.groupby('Team').agg({
        'Efficiency %': 'mean',
        'Points Left on Bench': 'sum',
        'Actual Points': 'sum',
        'Optimal Points': 'sum'
    }).reset_index()
    team_efficiency['Efficiency %'] = team_efficiency['Efficiency %'].round(1)
    
    bars = alt.Chart(team_efficiency).mark_bar().encode(
        x=alt.X('Efficiency %:Q', title='Average Efficiency %', scale=alt.Scale(domain=[0, 100])),
        y=alt.Y('Team:N', title='Team', sort='-x'),
        color=alt.Color('Efficiency %:Q', 
                      scale=alt.Scale(domain=[0, 100], range=['#DC143C', '#FFD700', '#2E8B57']),
                      legend=None),
        tooltip=['Team:N', 'Efficiency %:Q', 'Points Left on Bench:Q', 'Actual Points:Q', 'Optimal Points:Q']
    ).properties(
        title='Average Lineup Efficiency by Team (All Weeks)',
        height=400
    )
    
    st.altair_chart(bars, use_container_width=True)

# Detailed explanation
with st.expander("📖 How Lineup Efficiency Works"):
    st.markdown("""
    **Key Metrics:**
    - **Actual Points**: Points scored by your starting lineup
    - **Optimal Points**: Maximum points possible with your entire roster
    - **Points Left on Bench**: The difference (regret) - points you missed
    - **Efficiency %**: How well you used your roster (Actual/Optimal × 100)
    
    **What to Look For:**
    - **High Efficiency (90%+)**: Great lineup decisions
    - **Low Efficiency (<80%)**: Consider reviewing your start/sit decisions
    - **High "Points Left on Bench"**: You had better options on your bench
    
    **Note**: This analysis assumes you would have known the optimal lineup beforehand - it's meant to show potential, not criticize decisions made with incomplete information.
    """)
