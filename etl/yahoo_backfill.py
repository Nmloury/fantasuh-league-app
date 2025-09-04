import os, math
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
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

def upsert_players(sb, lg):
    # Get all players in the league using lg.taken_players()
    # TODO: Get all free agents using lg.free_agents() and add them to the players table    
    taken_players = lg.taken_players()
    rows = []
    
    for player in taken_players:
        rows.append({
            "player_id": str(player["player_id"]),
            "name": player["name"],
            "pos_type": player["position_type"],
            "eligible_positions": player["eligible_positions"]
        })    
    
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
    # Build stat id -> name map to interpret categories more robustly
    id_to_name = {}
    try:
        # Some versions expose stat_categories() directly
        cats = lg.stat_categories()  # type: ignore[attr-defined]
    except Exception:
        cats = (lg.settings() or {}).get("stat_categories") or []
    try:
        for c in cats:
            sid = str(c.get("stat_id"))
            nm = (c.get("name") or c.get("display_name") or c.get("display_name_full") or "").lower()
            if sid:
                id_to_name[sid] = nm
    except Exception:
        pass

    # For some ambiguous categories (e.g., interceptions), use player position to disambiguate DST vs offensive
    pos_by_pid = {}
    try:
        # Limit to the players we are about to fetch to keep payload smaller
        res = sb.table("players").select("player_id,pos_type").in_("player_id", player_ids).execute()
        for r in (getattr(res, "data", None) or []):
            pos_by_pid[str(r.get("player_id"))] = r.get("pos_type")
    except Exception:
        pass

    rows = []
    # Yahoo often limits batch sizes; keep request sizes modest
    for part_ids in chunked(player_ids, 25):
        try:
            # API expects period type and week argument for weekly stats
            stats_resp = lg.player_stats(part_ids, "week", week=week)
        except Exception:
            stats_resp = []

        # Normalize over the response structure differences
        for p in (stats_resp or []):
            pid = str(p.get("player_id") or "")
            if not pid:
                continue

            position = (pos_by_pid.get(pid) or "").upper()

            # Initialize all columns with safe defaults (DB has NOT NULL + defaults)
            out = {
                "week": week,
                "player_id": pid,
                "passing_yards": 0,
                "passing_tds": 0,
                "interceptions": 0,
                "rushing_yards": 0,
                "rushing_tds": 0,
                "receptions": 0,
                "receiving_yards": 0,
                "receiving_tds": 0,
                "fumbles_lost": 0,
                "fg_made": 0,
                "fg_missed": 0,
                "xp_made": 0,
                "dst_sacks": 0,
                "dst_interceptions": 0,
                "dst_fumbles_recovered": 0,
                "dst_tds": 0,
                "dst_safeties": 0,
                "dst_points_allowed": 0,
                "fantasy_points": None,
            }

            # Try to read fantasy points if present on the record
            try:
                val = p.get("total_points")
                out["fantasy_points"] = float(val)
            except Exception:
                pass

            # Offense
            if nmin("pass yds") or nmin("passing yards"):
                out["passing_yards"] += ival
            elif nmin("pass tds") or nmin("passing touchdowns"):
                out["passing_tds"] += ival
            elif (nmin("interceptions") or nm == "int") and position != "DST":
                out["interceptions"] += ival
            elif nmin("rush yds") or nmin("rushing yards"):
                out["rushing_yards"] += ival
            elif nmin("rush tds") or nmin("rushing touchdowns"):
                out["rushing_tds"] += ival
            elif nmin("receptions"):
                out["receptions"] += ival
            elif nmin("rec yds") or nmin("receiving yards"):
                out["receiving_yards"] += ival
            elif nmin("rec tds") or nmin("receiving touchdowns"):
                out["receiving_tds"] += ival
            elif nmin("fumbles lost"):
                out["fumbles_lost"] += ival

            # Kicking
            elif nmin("field goals made") or (nmin("fg made") and not nmin("miss")):
                out["fg_made"] += ival
            elif nmin("field goals missed") or nmin("fg missed"):
                out["fg_missed"] += ival
            elif nmin("pat made") or nmin("extra points made") or nmin("xp made"):
                out["xp_made"] += ival

            # Defense (DST)
            elif position == "DST" and (nmin("sacks")):
                out["dst_sacks"] += ival
            elif position == "DST" and (nmin("interceptions")):
                out["dst_interceptions"] += ival
            elif position == "DST" and (nmin("fumbles recovered")):
                out["dst_fumbles_recovered"] += ival
            elif position == "DST" and (nmin("safeties")):
                out["dst_safeties"] += ival
            elif position == "DST" and (nmin("touchdowns")):
                out["dst_tds"] += ival
            elif position == "DST" and (nmin("points allowed") or nmin("pts allowed")):
                out["dst_points_allowed"] = ival
            else:
                # Fallbacks by known IDs if names are missing
                try:
                    sid_int = int(sid)
                except Exception:
                    sid_int = -1

                    if sid_int in (4,):
                        out["passing_yards"] += ival
                    elif sid_int in (5,):
                        out["passing_tds"] += ival
                    elif sid_int in (6,):
                        if position == "DST":
                            out["dst_interceptions"] += ival
                        else:
                            out["interceptions"] += ival
                    elif sid_int in (10,):
                        out["rushing_yards"] += ival
                    elif sid_int in (11,):
                        out["rushing_tds"] += ival
                    elif sid_int in (12,):
                        out["receptions"] += ival
                    elif sid_int in (13,):
                        out["receiving_yards"] += ival
                    elif sid_int in (14,):
                        out["receiving_tds"] += ival
                    elif sid_int in (49, 50, 19):
                        out["fumbles_lost"] += ival
                    elif sid_int in (22, 23, 24, 25, 26):
                        out["fg_made"] += ival
                    elif sid_int in (27, 28):
                        out["fg_missed"] += ival
                    elif sid_int in (29,):
                        out["xp_made"] += ival
                    elif position == "DST" and sid_int in (32,):
                        out["dst_sacks"] += ival
                    elif position == "DST" and sid_int in (33,):
                        out["dst_interceptions"] += ival
                    elif position == "DST" and sid_int in (34,):
                        out["dst_fumbles_recovered"] += ival
                    elif position == "DST" and sid_int in (35,):
                        out["dst_safeties"] += ival
                    elif position == "DST" and sid_int in (36,):
                        out["dst_tds"] += ival
                    elif position == "DST" and sid_int in (54,):
                        out["dst_points_allowed"] = ival

            rows.append(out)

    for part in chunked(rows, 500):
        sb.table("player_stats").upsert(part, on_conflict="week,player_id").execute()

def write_transactions(sb, lg):
    # returns all league transactions; we only need adds (+ possible FAAB)
    # NOTE: doc: league.transactions returns ALL transactions and can be large. :contentReference[oaicite:8]{index=8}
    txs = lg.transactions(tran_types="add,drop,commish,trade", count=None)  # wrapper: all types
    rows = []
    for tx in txs:
        ttype = tx.get("type")
        ts = datetime.fromtimestamp(int(tx.get("timestamp","0")))
        faab = None
        if "faab" in tx and tx["faab"] not in ("", None):
            try: faab = int(tx["faab"])
            except Exception: pass

        players = (tx.get("players") or {}).get("player", [])
        if isinstance(players, dict): players = [players]
        for p in players:
            pid = str(p.get("player_id") or p.get("player",{}).get("player_id"))
            dest = (p.get("transaction_data",{}) or {}).get("destination_team_key") \
                   or tx.get("trader_team_key") or tx.get("tradee_team_key")
            if not pid or not dest: 
                continue
            rows.append({
                "ts": ts.isoformat(),
                "type": ttype,
                "manager_id": dest,
                "player_id": pid,
                "faab_spent": faab,
                "details": tx
            })
    for part in chunked(rows, 500):
        sb.table("transactions").upsert(
            part,
            on_conflict="ts,type,manager_id,player_id"  # matches PK
        ).execute()

def main():
    sb = supa()
    sc = get_session()
    lg = get_league(sc, YEAR, LEAGUE_ID_SHORT)

    # managers first (FK target)
    upsert_managers(sb, lg)
    
    # players next (FK target for rosters and stats)
    upsert_players(sb, lg)

    # played weeks
    settings = lg.settings()
    start_w = int(1)
    end_w   = int(1)
    for w in range(start_w, end_w + 1):
        write_matchups(sb, lg, w)
        write_rosters(sb, lg, w)
        try:
            res = sb.table("players").select("player_id").execute()
            player_ids = [str(r["player_id"]) for r in (getattr(res, "data", None) or [])]
        except Exception:
            player_ids = []
        if player_ids:
            write_player_stats(sb, lg, player_ids, w)

    write_transactions(sb, lg)
    print("Backfill complete.")

if __name__ == "__main__":
    main()
