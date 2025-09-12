import os
from dotenv import load_dotenv
from supabase import create_client
from app.lib.lineup_efficiency import compute_lineup_efficiency
from app.lib.expected_wins import compute_expected_wins
from app.lib.faab_roi import compute_faab_roi
from app.lib.draft_roi import compute_draft_roi
from app.lib.yahoo_client import get_session, get_league
# from app.lib.playoff_odds import simulate_playoff_odds

def get_most_recent_completed_week(sb):
    """Get the most recently completed week from Yahoo Fantasy API."""
    try:
        # Get league ID and year from environment
        league_id = os.getenv("YAHOO_LEAGUE_ID_SHORT")
        year = int(os.getenv("YAHOO_LEAGUE_YEAR", "2025"))
        
        if not league_id:
            print("Warning: YAHOO_LEAGUE_ID_SHORT environment variable not set, falling back to week 1")
            return 1
        
        # Get Yahoo session and league
        sc = get_session()
        lg = get_league(sc, year, league_id)
        
        # Get current week from Yahoo API and subtract 1 (unless it's week 1)
        current_week = lg.current_week()
        completed_week = current_week - 1 if current_week > 1 else 1
        
        print(f"Current week from Yahoo API: {current_week}")
        print(f"Using completed week: {completed_week}")
        
        return completed_week
    except Exception as e:
        print(f"Error getting current week from Yahoo API: {e}")
        print("Falling back to week 1")
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
print("Computing Draft ROI")
compute_draft_roi(sb)
# TODO: uncomment this when we have the schedule data
# simulate_playoff_odds(sb, n_sims=20000)
print("Derived metrics computed.")
