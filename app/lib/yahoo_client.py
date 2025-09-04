import os
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_session():
    oauth_path = os.environ.get("YAHOO_OAUTH_JSON_PATH")
    if not oauth_path:
        raise RuntimeError("Set YAHOO_OAUTH_JSON_PATH environment variable")
    
    return OAuth2(None, None, from_file=oauth_path)

def get_league(sc, year: int, league_id_short: str):
    gm = yfa.Game(sc, 'nfl')
    # e.g., ['430.l.576892', '428.l.311671', ...]; pick one ending with ".l.{short}"
    league_keys = gm.league_ids(year=year)
    league_key = next(k for k in league_keys if k.endswith(f".l.{league_id_short}"))
    return yfa.League(sc, league_key)