# app/pages/1_Luck_and_Expected_Wins.py
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

st.title("Luck Index & Expected Wins")

xw = sb.table("expected_wins").select("manager_id,cum_xw,week").execute().data
wins = sb.table("v_actual_wins").select("manager_id,wins").execute().data
names = sb.table("managers").select("manager_id,team_name").execute().data

dx = pd.DataFrame(xw).sort_values("week").groupby("manager_id", as_index=False)["cum_xw"].last()
dw = pd.DataFrame(wins)
nm = pd.DataFrame(names)

df = dw.merge(dx, on="manager_id", how="left").merge(nm, on="manager_id", how="left")
df["cum_xw"] = df["cum_xw"].fillna(0.0).round(2)
df["luck_delta"] = (df["wins"] - df["cum_xw"]).round(2)

st.dataframe(
    df[["team_name","wins","cum_xw","luck_delta"]].sort_values(["wins","cum_xw"], ascending=False),
    use_container_width=True,
)
st.caption("LuckΔ = Actual Wins − Expected Wins (sum of weekly P(win)).")
