# app/pages/3_FAAB_ROI.py
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("FAAB ROI")

rows = sb.table("faab_roi").select("*").execute().data
if not rows:
    st.info("No FAAB ROI records yet.")
else:
    df = pd.DataFrame(rows)
    names = sb.table("managers").select("manager_id,team_name").execute().data
    players = sb.table("players").select("player_id,name").execute().data
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

    st.dataframe(
        df.sort_values("faab_spent", ascending=False),
        use_container_width=True
    )
