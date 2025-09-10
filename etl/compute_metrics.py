import os
from dotenv import load_dotenv
from supabase import create_client
from app.lib.lineup_efficiency import compute_lineup_efficiency
from app.lib.expected_wins import compute_expected_wins
from app.lib.faab_roi import compute_faab_roi
# from app.lib.playoff_odds import simulate_playoff_odds

def get_most_recent_completed_week(sb):
    """Get the most recently completed week from matchups data."""
    try:
        # Get all weeks with completed matchups (both scores not null and at least one not zero)
        completed_weeks = sb.table("matchups").select("week").not_.is_("score_a", "null").not_.is_("score_b", "null").or_("score_a.gt.0,score_b.gt.0").order("week", desc=True).execute()
        
        if not completed_weeks.data:
            return 1  # Default to week 1 if no completed weeks found
        
        return completed_weeks.data[0]["week"]
    except Exception as e:
        print(f"Error getting most recent completed week: {e}")
        return 1  # Default to week 1 on error

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

most_recent_week = get_most_recent_completed_week(sb)
print("Computing lineup efficiency")
print(f"Computing lineup efficiency up to week {most_recent_week}")
compute_lineup_efficiency(sb, max_week=most_recent_week)
print("Computing expected wins")
print(f"Computing expected wins up to week {most_recent_week}")
compute_expected_wins(sb, max_week=most_recent_week)
print("Computing FAAB ROI")
compute_faab_roi(sb)
# TODO: uncomment this when we have the schedule data
# simulate_playoff_odds(sb, n_sims=20000)
print("Derived metrics computed.")
