import os, math
from datetime import datetime
from typing import Dict, Any, List
from collections import ChainMap
from dotenv import load_dotenv
import yahoo_fantasy_api as yfa
from app.lib.supa import supa
from app.lib.yahoo_client import get_session, get_league

load_dotenv()

YEAR = int(os.environ.get("YAHOO_LEAGUE_YEAR"))
LEAGUE_ID_SHORT = os.environ.get("YAHOO_LEAGUE_ID_SHORT")

# ---------- small utils ----------
def chunked(seq, n=500):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

# ---------- upsert helpers ----------
def upsert_managers(sb, lg):
    teams = lg.teams()  # { team_key: {...} }
    rows = []
    for team_key, t in teams.items():
        manager_name = t["managers"][0]["manager"]["nickname"]
        rows.append({
            "manager_id": team_key, 
            "team_name": t["name"], 
            "manager_name": manager_name
        })
    sb.table("managers").upsert(rows, on_conflict="manager_id").execute()

def upsert_players(sb, lg, sc):
    # This gets taken players (T), free agents (FA), waivers (W), and keepers (K)
    yh = yfa.yhandler.YHandler(sc)
    
    # Get league key from the league object
    league_key = lg.league_id
    start = 0
    page = 25
    rows = []
    
    # Fetch players for all statuses: Taken, Free Agents, Waivers, Keepers
    for player_status in ["T", "FA", "W", "K"]:
        print(f"Pulling {player_status} players")
        start = 0  # Reset start for each status
        while True:
            # Get players for this status
            data = yh.get_players_raw(league_key, start=start, status=player_status)['fantasy_content']['league'][1]['players']
            if not data:
                break
            for player_key, player_data in data.items():
                if player_key == 'count':
                    continue
                player_dict = ChainMap(*[obj for obj in player_data['player'][0] if isinstance(obj, dict)])
                rows.append({
                    "player_id": str(player_dict["player_id"]),
                    "name": player_dict["name"]["full"],
                    "pos_type": player_dict["position_type"],
                    "eligible_positions": [pos_dict['position'] for pos_dict in player_dict["eligible_positions"]]
                })
            start += page
    
    print(f"Added {len(rows)} total players")
    
    # Upsert in chunks
    for part in chunked(rows, 500):
        sb.table("players").upsert(part, on_conflict="player_id").execute()

def write_matchups(sb, lg, week: int):
    # Get matchups from the nested JSON structure
    matchups = lg.matchups(week=week)['fantasy_content']['league'][1]['scoreboard']['0']['matchups']
    rows = []
    
    for matchup_key, matchup_data in matchups.items():
        if matchup_key == 'count':
            continue
            
        matchup = matchup_data['matchup']
        teams = matchup['0']['teams']
        
        # Get team A (index 0)
        team_a_data = teams['0']['team']
        team_a_key = None
        team_a_score = None
        team_a_key = next(
            (obj['team_key'] for obj in team_a_data[0]
            if isinstance(obj, dict) and 'team_key' in obj),
            None,  # default if not found
        )
        team_a_score = float(team_a_data[1]['team_points']['total'])
        
        # Get team B (index 1)
        team_b_data = teams['1']['team']
        team_b_key = None
        team_b_score = None
        team_b_key = next(
            (obj['team_key'] for obj in team_b_data[0]
            if isinstance(obj, dict) and 'team_key' in obj),
            None,  # default if not found
        )
        team_b_score = float(team_b_data[1]['team_points']['total'])
        
        if team_a_key and team_b_key:
            matchup_id = f"{YEAR}-{week}-{team_a_key}-vs-{team_b_key}"
            rows.append({
                "week": week,
                "matchup_id": matchup_id,
                "team_a": team_a_key,
                "team_b": team_b_key,
                "score_a": team_a_score,
                "score_b": team_b_score
            })
    
    for part in chunked(rows, 500):
        sb.table("matchups").upsert(part, on_conflict="week,matchup_id").execute()

def write_rosters(sb, lg, week: int):
    teams = lg.teams().keys()
    roster_rows = []
    for team_key in teams:
        tm = lg.to_team(team_key)
        r = tm.roster(week=week)  # list of players w/ selected_position etc.
        for ply in r:
            roster_rows.append({
                "week": week, 
                "manager_id": team_key, 
                "player_id": str(ply["player_id"]),
                "slot": ply["selected_position"],
                "started": ply["selected_position"] not in ("BN", "IR")
            })
    for part in chunked(roster_rows, 500):
        sb.table("rosters").upsert(part, on_conflict="week,manager_id,player_id").execute()

def write_player_stats(sb, lg, player_ids: List[str], week: int):
    """Write player stats to database using new Yahoo API JSON format."""
    rows = []
    
    try:
        # Get all player stats in one request (no chunking needed)
        stats_resp = lg.player_stats(player_ids, "week", week=week)
    except Exception:
        stats_resp = []

    # Process each player's stats
    for p in (stats_resp or []):
        pid = str(p.get("player_id") or "")
        if not pid:
            continue

        position_type = p.get("position_type", "").upper()

        # Initialize all columns with safe defaults (DB has NOT NULL + defaults)
        out = {
            "week": week,
            "player_id": pid,
            "total_points": 0.0,
            "pass_yds": 0,
            "pass_td": 0,
            "pass_int": 0,
            "rush_yds": 0,
            "rush_td": 0,
            "rec": 0,
            "rec_yds": 0,
            "rec_td": 0,
            "return_td": 0,
            "two_pt": 0,
            "fum_lost": 0,
            "fum_ret_td": 0,
            "fg_0_19": 0,
            "fg_20_29": 0,
            "fg_30_39": 0,
            "fg_40_49": 0,
            "fg_50_plus": 0,
            "pat_made": 0,
            "dst_sacks": 0,
            "dst_int": 0,
            "dst_fum_rec": 0,
            "dst_td": 0,
            "safeties": 0,
            "blk_kick": 0,
            "dst_ret_td": 0,
            "pts_allow_0": 0,
            "pts_allow_1_6": 0,
            "pts_allow_7_13": 0,
            "pts_allow_14_20": 0,
            "pts_allow_21_27": 0,
            "pts_allow_28_34": 0,
            "pts_allow_35_plus": 0,
            "xpr": 0,
        }

        # Map stats based on position type and field names
        if position_type == "O":  # Offensive players
            out["pass_yds"] = int(p.get("Pass Yds", 0) or 0)
            out["pass_td"] = int(p.get("Pass TD", 0) or 0)
            out["pass_int"] = int(p.get("Int", 0) or 0)
            out["rush_yds"] = int(p.get("Rush Yds", 0) or 0)
            out["rush_td"] = int(p.get("Rush TD", 0) or 0)
            out["rec"] = int(p.get("Rec", 0) or 0)
            out["rec_yds"] = int(p.get("Rec Yds", 0) or 0)
            out["rec_td"] = int(p.get("Rec TD", 0) or 0)
            out["return_td"] = int(p.get("Ret TD", 0) or 0)
            out["two_pt"] = int(p.get("2-PT", 0) or 0)
            out["fum_lost"] = int(p.get("Fum Lost", 0) or 0)
            out["fum_ret_td"] = int(p.get("Fum Ret TD", 0) or 0)

        elif position_type == "K":  # Kickers
            out["fg_0_19"] = int(p.get("FG 0-19", 0) or 0)
            out["fg_20_29"] = int(p.get("FG 20-29", 0) or 0)
            out["fg_30_39"] = int(p.get("FG 30-39", 0) or 0)
            out["fg_40_49"] = int(p.get("FG 40-49", 0) or 0)
            out["fg_50_plus"] = int(p.get("FG 50+", 0) or 0)
            out["pat_made"] = int(p.get("PAT Made", 0) or 0)

        elif position_type == "DT":  # Defense/Team
            out["dst_sacks"] = int(p.get("Sack", 0) or 0)
            out["dst_int"] = int(p.get("Int", 0) or 0)
            out["dst_fum_rec"] = int(p.get("Fum Rec", 0) or 0)
            out["dst_td"] = int(p.get("TD", 0) or 0)
            out["safeties"] = int(p.get("Safe", 0) or 0)
            out["blk_kick"] = int(p.get("Blk Kick", 0) or 0)
            out["dst_ret_td"] = int(p.get("Ret TD", 0) or 0)
            out["pts_allow_0"] = int(p.get("Pts Allow 0", 0) or 0)
            out["pts_allow_1_6"] = int(p.get("Pts Allow 1-6", 0) or 0)
            out["pts_allow_7_13"] = int(p.get("Pts Allow 7-13", 0) or 0)
            out["pts_allow_14_20"] = int(p.get("Pts Allow 14-20", 0) or 0)
            out["pts_allow_21_27"] = int(p.get("Pts Allow 21-27", 0) or 0)
            out["pts_allow_28_34"] = int(p.get("Pts Allow 28-34", 0) or 0)
            out["pts_allow_35_plus"] = int(p.get("Pts Allow 35+", 0) or 0)
            out["xpr"] = int(p.get("XPR", 0) or 0)

        # Extract total_points for all position types
        try:
            total_points_val = p.get("total_points")
            if total_points_val is not None:
                out["total_points"] = float(total_points_val)
        except (ValueError, TypeError):
            # Keep default value of 0.0 if conversion fails
            pass

        rows.append(out)

    # Insert all rows in batches
    for part in chunked(rows, 500):
        sb.table("player_stats").upsert(part, on_conflict="week,player_id").execute()

def write_transactions(sb, lg):
    # returns all league transactions; we only need adds (+ possible FAAB)
    # NOTE: doc: league.transactions returns ALL transactions and can be large. :contentReference[oaicite:8]{index=8}
    txs = lg.transactions(tran_types="add,drop", count=None)  # wrapper: all types
    rows = []
    for tx in txs:
        tx_id = tx.get("transaction_id")
        status = tx.get("status")
        ts = tx.get("timestamp")
        ts = datetime.fromtimestamp(int(tx.get("timestamp","0")))
        faab = tx.get("faab_bid")
        players = [v['player'] for k,v in tx.get("players").items() if k != 'count']
        for p in players:
            player_dict = dict(ChainMap(*reversed(p[0])))

            # normalize transaction_data from list -> dict
            td = p[1].get("transaction_data")
            td = td[0] if isinstance(td, list) and td and isinstance(td[0], dict) else td

            # build the single flat dict (keeping 'name' as a nested dict)
            flat = {**player_dict, **{**p[1], "transaction_data": td}}
            
            pid = str(flat.get("player_id"))
            ttype = flat.get("transaction_data",{}).get("type")
            dest = flat.get("transaction_data",{}).get("destination_team_key")
            source = flat.get("transaction_data",{}).get("source_team_key")
            rows.append({
                "ts": ts.isoformat(),
                "type": ttype,
                "tx_id": tx_id,
                "status": status,
                "manager_id": dest if dest else source,
                "player_id": pid,
                "faab_spent": faab,
            })
    for part in chunked(rows, 500):
        sb.table("transactions").upsert(
            part,
            on_conflict="tx_id,player_id"  # matches PK
        ).execute()

def main():
    sb = supa()
    sc = get_session()
    lg = get_league(sc, YEAR, LEAGUE_ID_SHORT)

    # managers first (FK target)
    upsert_managers(sb, lg)
    
    # players next (FK target for rosters and stats)
    upsert_players(sb, lg, sc)

    # played weeks
    settings = lg.settings()
    start_w = int(settings.get("start_week","1"))
    end_w = int(settings.get("end_week", lg.end_week()))
    for w in range(start_w, end_w + 1):
        print(f"Writing matchups, rosters, and player stats for week {w}")
        write_matchups(sb, lg, w)
        write_rosters(sb, lg, w)
        try:
            res = sb.table("players").select("player_id").execute()
            player_ids = [str(r["player_id"]) for r in (getattr(res, "data", None) or [])]
        except Exception:
            player_ids = []
        if player_ids:
            write_player_stats(sb, lg, player_ids, w)

    print("Writing transactions")
    write_transactions(sb, lg)
    print("Backfill complete.")

if __name__ == "__main__":
    main()
