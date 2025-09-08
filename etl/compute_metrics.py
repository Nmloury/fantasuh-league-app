import os
from dotenv import load_dotenv
from supabase import create_client
from app.lib.lineup_efficiency import compute_lineup_efficiency
from app.lib.expected_wins import compute_expected_wins
from app.lib.faab_roi import compute_faab_roi
# from app.lib.playoff_odds import simulate_playoff_odds

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

print("Computing lineup efficiency")    
compute_lineup_efficiency(sb)
print("Computing expected wins")
compute_expected_wins(sb)
print("Computing FAAB ROI")
compute_faab_roi(sb)
# TODO: uncomment this when we have the schedule data
# simulate_playoff_odds(sb, n_sims=20000)
print("Derived metrics computed.")
