# app/pages/2_Lineup_Efficiency.py
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("Lineup Efficiency")

week = st.number_input("Week", 1, 18, 1)
le = sb.table("lineup_efficiency").select("*").eq("week", int(week)).execute().data
names = sb.table("managers").select("manager_id,team_name").execute().data

df = pd.DataFrame(le)
if df.empty:
    st.info("No data for this week yet.")
else:
    name_map = {n["manager_id"]: n["team_name"] for n in names}
    df["team_name"] = df["manager_id"].map(name_map)
    df = df[["week","team_name","actual_pts","optimal_pts","regret","efficiency"]]
    df["efficiency"] = df["efficiency"].round(3)
    st.dataframe(df.sort_values("regret", ascending=False), use_container_width=True)
