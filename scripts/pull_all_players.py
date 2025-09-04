from collections import ChainMap
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import yahoo_fantasy_api as yfa
from app.lib.yahoo_client import get_session, get_league

sc = get_session()
yh = yfa.yhandler.YHandler(sc)

league_key = '449.l.311671'   # your league key
start = 0
page = 25
rows = []

while True:
    # All players in league context (omit status); or use status="T,FA,W,K"
    data = yh.get_players_raw(league_key, start=start, status="T")['fantasy_content']['league'][1]['players']
    for player_key, player_data in data.items():
        if player_key == 'count':
            continue
        player_dict = ChainMap(*[obj for obj in player_data['player'][0] if isinstance(obj, dict)])
        rows.append({
            "player_id": player_dict["player_id"],
            "name": player_dict["name"]["full"],
            "pos_type": player_dict["position_type"],
            "eligible_positions": player_dict["eligible_positions"]
        })
    print(f"Added {len(rows)} players")
    start += page

