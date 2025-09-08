import os
import json
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# Load .env so env vars work in local dev
load_dotenv()

st.set_page_config(page_title="League Hub", layout="wide")
st.title("League Hub — Smoke Test")

# --- Env checks ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL_RECAP", "gpt-4.1-mini")
OPENAI_KEY_SET = bool(os.getenv("OPENAI_API_KEY"))

colA, colB, colC = st.columns(3)
with colA:
    st.metric("SUPABASE_URL set?", "yes" if SUPABASE_URL else "no")
with colB:
    st.metric("Service Role Key set?", "yes" if SUPABASE_KEY else "no")
with colC:
    st.metric("OpenAI key set?", "yes" if OPENAI_KEY_SET else "no")

if not (SUPABASE_URL and SUPABASE_KEY):
    st.error("Supabase env vars missing. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env.")
    st.stop()

# --- Supabase client ---
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helpers ---
@st.cache_data(show_spinner=False)
def table_count(name: str) -> int:
    # Uses PostgREST exact count; request minimal rows
    res = sb.table(name).select("*", count="exact").limit(1).execute()
    return int(res.count or 0)

def try_view(name: str) -> bool:
    try:
        _ = sb.table(name).select("*").limit(1).execute()
        return True
    except Exception:
        return False

# --- DB snapshot ---
st.subheader("Database snapshot")

cols = st.columns(6)
tables = ["managers", "players", "matchups", "rosters", "transactions", "player_stats"]
for c, t in zip(cols + st.columns(max(0, len(tables) - len(cols))), tables):
    with c:
        st.metric(t, f"{table_count(t):,}")

derived_cols = st.columns(4)
derived = ["lineup_efficiency", "expected_wins", "faab_roi"]
for c, t in zip(derived_cols, derived):
    with c:
        # Safe even if not created yet
        try:
            st.metric(t, f"{table_count(t):,}")
        except Exception:
            st.metric(t, "—")

# Views check (useful for the facts builder)
views_ok = try_view("v_team_week_scores") and try_view("v_standings")
st.caption(f"Views available: {'yes' if views_ok else 'no'} (v_team_week_scores, v_standings)")

# --- Facts preview (uses your facts.py) ---
st.subheader("Weekly Facts Preview")
week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

facts = None
try:
    from app.lib.facts import build_facts
    facts = build_facts(sb, int(week))
    st.code(json.dumps(facts, indent=2), language="json")
except Exception as e:
    st.warning(f"Could not build facts: {e}")

# --- Recap quick check (optional; only if recap_llm.py exists) ---
st.subheader("Recap Generation (optional quick check)")
gen = st.button("Generate Recap (if recap_llm.py present)")
if gen:
    try:
        from app.lib.recap_llm import generate_recap
        if not OPENAI_KEY_SET:
            st.error("OPENAI_API_KEY missing; set it in .env to generate a recap.")
        elif facts is None:
            st.error("No facts available for this week.")
        else:
            recap = generate_recap(facts)
            st.markdown(f"### {recap.get('title','Weekly Recap')}")
            for h in (recap.get("headlines") or []):
                st.markdown(f"- {h.get('text','')}")
            for s in (recap.get("sections") or []):
                st.markdown(f"#### {s.get('title','')}")
                st.markdown(s.get("body",""))
    except ModuleNotFoundError:
        st.info("recap_llm.py not found yet — create app/lib/recap_llm.py to enable this.")
    except Exception as e:
        st.error(f"Recap generation failed: {e}")

st.divider()
st.write(
    "Use the sidebar to open pages:\n\n"
    "- 1) Luck & Expected Wins\n"
    "- 2) Lineup Efficiency\n"
    "- 3) FAAB ROI\n"
    "- 5) Weekly Recap\n"
)
