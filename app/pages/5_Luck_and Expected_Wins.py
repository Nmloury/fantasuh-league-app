# app/pages/1_Luck_and_Expected_Wins.py
import os
import pandas as pd
import streamlit as st
import altair as alt
from dotenv import load_dotenv
from supabase import create_client
from lib.streamlit_utils import get_expected_wins_data, get_actual_wins_data, get_managers_data

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("🎯 Luck Index & Expected Wins")

# High-level description
st.markdown("""
**What this shows:** This analysis compares each team's actual wins to their expected wins based on their weekly performance. 
Teams with positive luck have won more games than their performance suggests they should have, while teams with negative luck 
have been unlucky despite strong performances.
""")

# Data processing
xw = get_expected_wins_data(sb)
wins = get_actual_wins_data(sb)
names = get_managers_data(sb)

dx = pd.DataFrame(xw).sort_values("week").groupby("manager_id", as_index=False)["cum_xw"].last()
dw = pd.DataFrame(wins)
nm = pd.DataFrame(names)

df = dw.merge(dx, on="manager_id", how="left").merge(nm, on="manager_id", how="left")
df["cum_xw"] = df["cum_xw"].fillna(0.0).round(2)
df["luck_delta"] = (df["wins"] - df["cum_xw"]).round(2)

# Prepare data with human-readable column names
display_df = df[["team_name","wins","cum_xw","luck_delta"]].copy()
display_df.columns = ["Team", "Actual Wins", "Expected Wins", "Luck Index"]

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
    # Actual Wins range filter
    wins_min, wins_max = int(display_df['Actual Wins'].min()), int(display_df['Actual Wins'].max())
    wins_range = st.slider(
        "Actual Wins", 
        min_value=wins_min, 
        max_value=wins_max, 
        value=(wins_min, wins_max),
        help="Filter by actual wins"
    )

with col2:
    # Expected Wins range filter
    xw_min, xw_max = float(display_df['Expected Wins'].min()), float(display_df['Expected Wins'].max())
    # Handle case where min == max
    if xw_min == xw_max:
        xw_max = xw_min + 0.01
    xw_range = st.slider(
        "Expected Wins", 
        min_value=xw_min, 
        max_value=xw_max, 
        value=(xw_min, xw_max),
        format="%.2f",
        help="Filter by expected wins"
    )

with col3:
    # Luck Index range filter
    luck_min, luck_max = float(display_df['Luck Index'].min()), float(display_df['Luck Index'].max())
    # Handle case where min == max
    if luck_min == luck_max:
        luck_max = luck_min + 0.01
    luck_range = st.slider(
        "Luck Index", 
        min_value=luck_min, 
        max_value=luck_max, 
        value=(luck_min, luck_max),
        format="%.2f",
        help="Filter by luck index (positive = lucky, negative = unlucky)"
    )

# Apply filters
filtered_df = display_df.copy()

# Team filter
filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]

# Actual Wins range filter
filtered_df = filtered_df[
    (filtered_df['Actual Wins'] >= wins_range[0]) & 
    (filtered_df['Actual Wins'] <= wins_range[1])
]

# Expected Wins range filter
filtered_df = filtered_df[
    (filtered_df['Expected Wins'] >= xw_range[0]) & 
    (filtered_df['Expected Wins'] <= xw_range[1])
]

# Luck Index range filter
filtered_df = filtered_df[
    (filtered_df['Luck Index'] >= luck_range[0]) & 
    (filtered_df['Luck Index'] <= luck_range[1])
]

# Show filter results summary
st.caption(f"Showing {len(filtered_df)} of {len(display_df)} records")

# Use filtered data for display and sort
display_df = filtered_df.sort_values(["Actual Wins", "Expected Wins"], ascending=False)

# Display table
st.dataframe(
    display_df,
    use_container_width=True,
    column_config={
        "Team": st.column_config.TextColumn("Team", width="medium"),
        "Actual Wins": st.column_config.NumberColumn("Actual Wins", width="small", help="Total wins this season"),
        "Expected Wins": st.column_config.NumberColumn("Expected Wins", width="small", help="Expected wins based on weekly performance probabilities"),
        "Luck Index": st.column_config.NumberColumn("Luck Index", width="small", help="Actual Wins - Expected Wins. Positive = lucky, Negative = unlucky")
    }
)

# Create scatter plot: Actual vs Expected Wins
chart_data = display_df.copy()
chart_data['Luck_Color'] = chart_data['Luck Index'].apply(lambda x: 'Lucky' if x > 0 else 'Unlucky' if x < 0 else 'Neutral')

scatter = alt.Chart(chart_data).mark_circle(size=120).add_selection(
    alt.selection_interval()
).encode(
    x=alt.X('Expected Wins:Q', title='Expected Wins', scale=alt.Scale(zero=False)),
    y=alt.Y('Actual Wins:Q', title='Actual Wins', scale=alt.Scale(zero=False)),
    color=alt.Color('Luck_Color:N', title='Luck Status',
                  scale=alt.Scale(domain=['Lucky', 'Neutral', 'Unlucky'], 
                                range=['#2E8B57', '#4682B4', '#DC143C'])),
    tooltip=['Team:N', 'Actual Wins:Q', 'Expected Wins:Q', 'Luck Index:Q']
).properties(
    title='Actual vs Expected Wins',
    height=400
)

# Add team name labels
labels = alt.Chart(chart_data).mark_text(
    align='left',
    baseline='middle',
    dx=8,
    fontSize=12,
    fontWeight='bold',
    color='white'  # Match dark theme text color
).encode(
    x=alt.X('Expected Wins:Q', title='Expected Wins', scale=alt.Scale(zero=False)),
    y=alt.Y('Actual Wins:Q', title='Actual Wins', scale=alt.Scale(zero=False)),
    text='Team:N'
)

# Add diagonal line (perfect luck line)
diagonal = alt.Chart(pd.DataFrame({'x': [0, max(chart_data['Expected Wins'].max(), chart_data['Actual Wins'].max())]})).mark_line(
    color='gray', strokeDash=[5, 5]
).encode(
    x='x:Q',
    y='x:Q'
)

st.altair_chart(scatter + labels + diagonal, use_container_width=True)

# Detailed explanation
with st.expander("📖 How Expected Wins Work"):
    st.markdown("""
    **Expected Wins Calculation:**
    - Each week, we calculate the probability of winning based on your score vs. all other teams
    - Expected wins = sum of all weekly win probabilities
    - Example: If you had 80% chance to win Week 1, 60% chance Week 2, your expected wins = 1.4
    
    **Luck Index Interpretation:**
    - **Positive Luck Index**: You've won more games than your performance suggests (lucky!)
    - **Negative Luck Index**: You've won fewer games than your performance suggests (unlucky)
    - **Near Zero**: Your record matches your performance level
    """)
