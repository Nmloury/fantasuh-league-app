"""
facts.py — Build the JSON facts payload for the Weekly Recap page.

Outputs shape:
{
  "week": int,
  "standings_changes": [{"team": str, "delta": "+2" | "-1" | "0"}],
  "top_scorer": {"team": str, "points": float},
  "biggest_blowout": {"winner": str, "loser": str, "margin": float} | null,
  "closest_game": {"winner": str, "loser": str, "margin": float} | null,
  "unluckiest_loss": {"team": str, "actual": float, "would_beat_pct": float} | null,
  "best_waiver": {"team": str, "player": str, "faab": int, "points_window": float} | null,
  "lineup_regret_leader": {"team": str, "regret": float} | null,
  "mvp": {"player": str, "team": str, "points": float, "position": str, "stats": dict} | null,
  "lvp": {"player": str, "team": str, "points": float, "position": str, "stats": dict} | null,
  "surprise_stat": {"player": str, "team": str, "points": float, "position": str, "stats": dict, "description": str} | null,
  "benchwarmer": {"player": str, "team": str, "points": float, "position": str, "stats": dict} | null
}

Notes:
- Uses Supabase Python client.
- Loads .env on import so os.environ works in local dev.
- Minimizes round-trips by batching where practical (Supabase has no server-side joins).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from supabase import Client

# Ensure .env is loaded wherever this module is used
load_dotenv()

# Import the existing Supabase client function
from .supa import supa


# ---------- Small cache helpers ----------
def _team_name_map(sb: Client) -> Dict[str, str]:
    rows = sb.table("managers").select("manager_id,team_name").execute().data
    return {r["manager_id"]: r["team_name"] for r in rows}


def _team_scores_for_week(sb: Client, week: int) -> List[Dict]:
    # v_team_week_scores is created in sql/20_views.sql
    return sb.table("v_team_week_scores").select("*").eq("week", week).execute().data


# ---------- Fact builders ----------
def top_scorer(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    rows = _team_scores_for_week(sb, week)
    if not rows:
        return None
    best = max(rows, key=lambda r: float(r["points_for"] or 0.0))
    return {
        "team": name_map.get(best["manager_id"], best["manager_id"]),
        "points": float(best["points_for"] or 0.0),
    }


def _label_pair(name_map: Dict[str, str], winner_id: str, loser_id: str, margin: float) -> Dict:
    return {
        "winner": name_map.get(winner_id, winner_id),
        "loser": name_map.get(loser_id, loser_id),
        "margin": float(margin),
    }


def blowout_and_closest(sb: Client, week: int, name_map: Dict[str, str]) -> Tuple[Optional[Dict], Optional[Dict]]:
    mts = sb.table("matchups").select("team_a,team_b,score_a,score_b").eq("week", week).execute().data
    if not mts:
        return None, None
    diffs: List[Tuple[Tuple[str, str], float]] = []
    for m in mts:
        sa = float(m["score_a"] or 0.0)
        sb_ = float(m["score_b"] or 0.0)
        if sa == sb_:
            continue
        if sa > sb_:
            diffs.append(((m["team_a"], m["team_b"]), sa - sb_))
        else:
            diffs.append(((m["team_b"], m["team_a"]), sb_ - sa))
    if not diffs:
        return None, None
    big = max(diffs, key=lambda x: x[1])
    close = min(diffs, key=lambda x: x[1])
    blow = _label_pair(name_map, big[0][0], big[0][1], big[1])
    closest = _label_pair(name_map, close[0][0], close[0][1], close[1])
    return blow, closest


def unluckiest_loss(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    rows = _team_scores_for_week(sb, week)
    if not rows:
        return None
    all_scores = [float(r["points_for"] or 0.0) for r in rows]
    losers = [r for r in rows if int(r["win"] or 0) == 0]
    if not losers:
        return None
    n = len(all_scores)
    best_row = None
    best_pct = -1.0
    for r in losers:
        s = float(r["points_for"] or 0.0)
        would_beat = sum(1 for x in all_scores if s > float(x))
        pct = (would_beat / max(1, (n - 1))) if n > 1 else 0.0
        if pct > best_pct:
            best_row, best_pct = r, pct
    return {
        "team": name_map.get(best_row["manager_id"], best_row["manager_id"]),
        "actual": float(best_row["points_for"] or 0.0),
        "would_beat_pct": round(best_pct, 3),
    }


def best_waiver_this_week(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    """
    Find FAAB adds whose player STARTED for that manager in this week.
    Pick the add that yielded the highest points this week.
    """
    # 1) Candidate FAAB adds (tx rows)
    adds = sb.table("transactions") \
             .select("tx_id,manager_id,player_id,faab_spent") \
             .eq("type", "add").not_.is_("faab_spent", "null") \
             .execute().data
    if not adds:
        return None

    # 2) From those adds, which (manager, player) pairs were STARTED this week?
    add_player_ids = list({a["player_id"] for a in adds})
    roster_rows = sb.table("rosters") \
                    .select("manager_id,player_id,started,slot") \
                    .eq("week", week) \
                    .in_("player_id", add_player_ids) \
                    .execute().data
    started_pairs = {(r["manager_id"], r["player_id"]) for r in roster_rows if r.get("started")}

    if not started_pairs:
        return None

    # 3) Pull this week's points for all started add players in one query
    started_player_ids = list({pid for _, pid in started_pairs})
    ps = sb.table("player_stats").select("player_id,total_points") \
           .eq("week", week).in_("player_id", started_player_ids).execute().data
    pts_map = {p["player_id"]: float(p["total_points"] or 0.0) for p in ps}

    # 4) Choose the best (max points) add event
    best = None
    for a in adds:
        key = (a["manager_id"], a["player_id"])
        if key not in started_pairs:
            continue
        pts = pts_map.get(a["player_id"], 0.0)
        if (best is None) or (pts > best["points_window"]):
            # lookup player name once
            player_row = sb.table("players").select("name").eq("player_id", a["player_id"]).single().execute().data
            best = {
                "team": name_map.get(a["manager_id"], a["manager_id"]),
                "player": player_row["name"] if player_row else a["player_id"],
                "faab": int(a["faab_spent"] or 0),
                "points_window": float(pts),
            }
    return best


def lineup_regret_leader(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    row = sb.table("lineup_efficiency").select("manager_id,regret") \
            .eq("week", week).order("regret", desc=True).limit(1).execute().data
    if not row:
        return None
    r = row[0]
    return {
        "team": name_map.get(r["manager_id"], r["manager_id"]),
        "regret": float(r["regret"] or 0.0),
    }


def standings_changes(sb: Client, week: int, name_map: Dict[str, str]) -> List[Dict]:
    if week <= 1:
        return []
    prev = sb.table("v_standings").select("*").eq("week", week - 1).execute().data
    curr = sb.table("v_standings").select("*").eq("week", week).execute().data
    if not prev or not curr:
        return []

    def rank(rows: List[Dict]) -> Dict[str, int]:
        ordered = sorted(rows, key=lambda r: (float(r["cum_wins"] or 0.0), float(r["cum_pf"] or 0.0)), reverse=True)
        return {r["manager_id"]: i + 1 for i, r in enumerate(ordered)}

    r_prev, r_curr = rank(prev), rank(curr)
    out: List[Dict] = []
    for mid, rk in r_curr.items():
        delta = r_prev.get(mid, rk) - rk
        if delta != 0:
            out.append({"team": name_map.get(mid, mid), "delta": f"{'+' if delta > 0 else ''}{delta}"})
    return out


def _get_player_stats_dict(stats_row: Dict) -> Dict:
    """Convert player_stats row to a clean stats dictionary."""
    return {
        "pass_yds": int(stats_row.get("pass_yds", 0)),
        "pass_td": int(stats_row.get("pass_td", 0)),
        "pass_int": int(stats_row.get("pass_int", 0)),
        "rush_yds": int(stats_row.get("rush_yds", 0)),
        "rush_td": int(stats_row.get("rush_td", 0)),
        "rec": int(stats_row.get("rec", 0)),
        "rec_yds": int(stats_row.get("rec_yds", 0)),
        "rec_td": int(stats_row.get("rec_td", 0)),
        "return_td": int(stats_row.get("return_td", 0)),
        "two_pt": int(stats_row.get("two_pt", 0)),
        "fum_lost": int(stats_row.get("fum_lost", 0)),
        "fum_ret_td": int(stats_row.get("fum_ret_td", 0)),
        "fg_0_19": int(stats_row.get("fg_0_19", 0)),
        "fg_20_29": int(stats_row.get("fg_20_29", 0)),
        "fg_30_39": int(stats_row.get("fg_30_39", 0)),
        "fg_40_49": int(stats_row.get("fg_40_49", 0)),
        "fg_50_plus": int(stats_row.get("fg_50_plus", 0)),
        "pat_made": int(stats_row.get("pat_made", 0)),
        "dst_sacks": int(stats_row.get("dst_sacks", 0)),
        "dst_int": int(stats_row.get("dst_int", 0)),
        "dst_fum_rec": int(stats_row.get("dst_fum_rec", 0)),
        "dst_td": int(stats_row.get("dst_td", 0)),
        "safeties": int(stats_row.get("safeties", 0)),
        "blk_kick": int(stats_row.get("blk_kick", 0)),
        "dst_ret_td": int(stats_row.get("dst_ret_td", 0)),
        "pts_allow_0": int(stats_row.get("pts_allow_0", 0)),
        "pts_allow_1_6": int(stats_row.get("pts_allow_1_6", 0)),
        "pts_allow_7_13": int(stats_row.get("pts_allow_7_13", 0)),
        "pts_allow_14_20": int(stats_row.get("pts_allow_14_20", 0)),
        "pts_allow_21_27": int(stats_row.get("pts_allow_21_27", 0)),
        "pts_allow_28_34": int(stats_row.get("pts_allow_28_34", 0)),
        "pts_allow_35_plus": int(stats_row.get("pts_allow_35_plus", 0)),
        "xpr": int(stats_row.get("xpr", 0)),
    }


def mvp(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    """
    Find the highest-scoring starter from a winning team.
    """
    # Get all winning teams for this week
    winning_teams = sb.table("v_team_week_scores").select("manager_id").eq("week", week).eq("win", 1).execute().data
    if not winning_teams:
        return None
    
    winning_manager_ids = [wt["manager_id"] for wt in winning_teams]
    
    # Get all started players for winning teams
    started_players = sb.table("rosters").select("manager_id,player_id").eq("week", week).eq("started", True).in_("manager_id", winning_manager_ids).execute().data
    if not started_players:
        return None
    
    # Get player stats for all started players
    player_ids = [sp["player_id"] for sp in started_players]
    player_stats = sb.table("player_stats").select("*").eq("week", week).in_("player_id", player_ids).execute().data
    if not player_stats:
        return None
    
    # Get player names and positions
    players_info = sb.table("players").select("player_id,name,pos_type").in_("player_id", player_ids).execute().data
    players_map = {p["player_id"]: p for p in players_info}
    
    # Find highest scoring started player from winning team
    best_player = None
    best_points = -1.0
    
    for stats in player_stats:
        points = float(stats["total_points"] or 0.0)
        if points > best_points:
            # Find which manager started this player
            for sp in started_players:
                if sp["player_id"] == stats["player_id"]:
                    player_info = players_map.get(stats["player_id"], {})
                    best_player = {
                        "player": player_info.get("name", stats["player_id"]),
                        "team": name_map.get(sp["manager_id"], sp["manager_id"]),
                        "points": points,
                        "position": player_info.get("pos_type", "UNKNOWN"),
                        "stats": _get_player_stats_dict(stats)
                    }
                    best_points = points
                    break
    
    return best_player


def lvp(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    """
    Find a low-scoring starter that cost their team in a loss.
    Focus on players with high expectations (typically skill position players) who underperformed.
    """
    # Get all losing teams for this week
    losing_teams = sb.table("v_team_week_scores").select("manager_id").eq("week", week).eq("win", 0).execute().data
    if not losing_teams:
        return None
    
    losing_manager_ids = [lt["manager_id"] for lt in losing_teams]
    
    # Get all started players for losing teams, focusing on skill positions
    started_players = sb.table("rosters").select("manager_id,player_id").eq("week", week).eq("started", True).in_("manager_id", losing_manager_ids).execute().data
    if not started_players:
        return None
    
    # Get player stats and info
    player_ids = [sp["player_id"] for sp in started_players]
    player_stats = sb.table("player_stats").select("*").eq("week", week).in_("player_id", player_ids).execute().data
    players_info = sb.table("players").select("player_id,name,pos_type").in_("player_id", player_ids).execute().data
    
    if not player_stats or not players_info:
        return None
    
    players_map = {p["player_id"]: p for p in players_info}
    
    # Find worst performing skill position player (QB, RB, WR, TE) from losing team
    worst_player = None
    worst_score = float('inf')
    
    for stats in player_stats:
        points = float(stats["total_points"] or 0.0)
        player_info = players_map.get(stats["player_id"], {})
        position = player_info.get("pos_type", "")
        
        # Focus on offensive players, avoid K and DEF for LVP
        if position == "O" and points < worst_score and points >= 0:
            # Find which manager started this player
            for sp in started_players:
                if sp["player_id"] == stats["player_id"]:
                    worst_player = {
                        "player": player_info.get("name", stats["player_id"]),
                        "team": name_map.get(sp["manager_id"], sp["manager_id"]),
                        "points": points,
                        "position": position,
                        "stats": _get_player_stats_dict(stats)
                    }
                    worst_score = points
                    break
    
    return worst_player


def surprise_stat(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    """
    Find weird/unique stat lines that stand out.
    Examples: WR with 2 catches but 2 TDs, QB with 300 yards but no TDs, etc.
    """
    # Get all started players with their stats
    started_players = sb.table("rosters").select("manager_id,player_id").eq("week", week).eq("started", True).execute().data
    if not started_players:
        return None
    
    player_ids = [sp["player_id"] for sp in started_players]
    player_stats = sb.table("player_stats").select("*").eq("week", week).in_("player_id", player_ids).execute().data
    players_info = sb.table("players").select("player_id,name,pos_type").in_("player_id", player_ids).execute().data
    
    if not player_stats or not players_info:
        return None
    
    players_map = {p["player_id"]: p for p in players_info}
    
    best_surprise = None
    best_surprise_score = 0.0
    
    for stats in player_stats:
        player_info = players_map.get(stats["player_id"], {})
        position = player_info.get("pos_type", "")
        points = float(stats["total_points"] or 0.0)
        
        # Calculate surprise score based on position-specific weird stats
        surprise_score = 0.0
        description = ""
        
        if position == "QB":
            pass_yds = int(stats.get("pass_yds", 0))
            pass_td = int(stats.get("pass_td", 0))
            pass_int = int(stats.get("pass_int", 0))
            
            # High yards, no TDs
            if pass_yds >= 300 and pass_td == 0:
                surprise_score = pass_yds / 10.0
                description = f"QB threw for {pass_yds} yards but no touchdowns"
            # Many TDs, low yards
            elif pass_td >= 3 and pass_yds < 200:
                surprise_score = pass_td * 10.0
                description = f"QB threw {pass_td} touchdowns on just {pass_yds} yards"
            # High yards, many INTs
            elif pass_yds >= 400 and pass_int >= 3:
                surprise_score = pass_yds / 20.0
                description = f"QB threw for {pass_yds} yards but had {pass_int} interceptions"
        
        elif position == "O":  # Offensive players (RB, WR, TE)
            rec = int(stats.get("rec", 0))
            rec_td = int(stats.get("rec_td", 0))
            rec_yds = int(stats.get("rec_yds", 0))
            rush_yds = int(stats.get("rush_yds", 0))
            rush_td = int(stats.get("rush_td", 0))
            
            # Few catches, many TDs
            if rec <= 3 and rec_td >= 2:
                surprise_score = rec_td * 15.0
                description = f"Offensive player had {rec} catches but {rec_td} receiving touchdowns"
            # Many catches, no TDs, high yards
            elif rec >= 8 and rec_td == 0 and rec_yds >= 100:
                surprise_score = rec * 2.0
                description = f"Offensive player had {rec} catches for {rec_yds} yards but no touchdowns"
            # Player with receiving TDs but no rushing yards
            elif rec_td >= 1 and rush_yds < 20:
                surprise_score = rec_td * 12.0
                description = f"Player had {rec_td} receiving touchdowns but only {rush_yds} rushing yards"
        
        elif position == "K":
            fg_50_plus = int(stats.get("fg_50_plus", 0))
            fg_missed = 3 - (int(stats.get("fg_0_19", 0)) + int(stats.get("fg_20_29", 0)) + int(stats.get("fg_30_39", 0)) + int(stats.get("fg_40_49", 0)) + fg_50_plus)
            
            if fg_50_plus >= 2:
                surprise_score = fg_50_plus * 8.0
                description = f"Kicker made {fg_50_plus} field goals from 50+ yards"
        
        elif position == "DT":  # Defense/Team
            dst_td = int(stats.get("dst_td", 0))
            dst_int = int(stats.get("dst_int", 0))
            dst_fum_rec = int(stats.get("dst_fum_rec", 0))
            
            if dst_td >= 2:
                surprise_score = dst_td * 10.0
                description = f"Defense scored {dst_td} touchdowns"
            elif dst_int >= 4:
                surprise_score = dst_int * 3.0
                description = f"Defense had {dst_int} interceptions"
        
        if surprise_score > best_surprise_score and surprise_score > 0:
            # Find which manager started this player
            for sp in started_players:
                if sp["player_id"] == stats["player_id"]:
                    best_surprise = {
                        "player": player_info.get("name", stats["player_id"]),
                        "team": name_map.get(sp["manager_id"], sp["manager_id"]),
                        "points": points,
                        "position": position,
                        "stats": _get_player_stats_dict(stats),
                        "description": description
                    }
                    best_surprise_score = surprise_score
                    break
    
    return best_surprise


def benchwarmer(sb: Client, week: int, name_map: Dict[str, str]) -> Optional[Dict]:
    """
    Find the highest points left on the bench.
    """
    # Get all benched players with their stats
    benched_players = sb.table("rosters").select("manager_id,player_id").eq("week", week).eq("started", False).execute().data
    if not benched_players:
        return None
    
    player_ids = [bp["player_id"] for bp in benched_players]
    player_stats = sb.table("player_stats").select("*").eq("week", week).in_("player_id", player_ids).execute().data
    players_info = sb.table("players").select("player_id,name,pos_type").in_("player_id", player_ids).execute().data
    
    if not player_stats or not players_info:
        return None
    
    players_map = {p["player_id"]: p for p in players_info}
    
    best_benchwarmer = None
    best_points = -1.0
    
    for stats in player_stats:
        points = float(stats["total_points"] or 0.0)
        if points > best_points:
            # Find which manager benched this player
            for bp in benched_players:
                if bp["player_id"] == stats["player_id"]:
                    player_info = players_map.get(stats["player_id"], {})
                    
                    best_benchwarmer = {
                        "player": player_info.get("name", stats["player_id"]),
                        "team": name_map.get(bp["manager_id"], bp["manager_id"]),
                        "points": points,
                        "position": player_info.get("pos_type", "UNKNOWN"),
                        "stats": _get_player_stats_dict(stats)
                    }
                    best_points = points
                    break
    
    return best_benchwarmer


def build_facts(sb: Optional[Client], week: int) -> Dict:
    """
    Build and return the facts JSON for a given week.

    If sb is None, a client is created via environment variables.
    """
    if sb is None:
        sb = supa()

    name_map = _team_name_map(sb)

    top = top_scorer(sb, week, name_map)
    blow, close = blowout_and_closest(sb, week, name_map)
    unlucky = unluckiest_loss(sb, week, name_map)
    waiver = best_waiver_this_week(sb, week, name_map)
    regret = lineup_regret_leader(sb, week, name_map)
    changes = standings_changes(sb, week, name_map)
    
    # New player-specific categories
    mvp_player = mvp(sb, week, name_map)
    lvp_player = lvp(sb, week, name_map)
    surprise = surprise_stat(sb, week, name_map)
    bench = benchwarmer(sb, week, name_map)

    return {
        "week": int(week),
        "standings_changes": changes or [],
        "top_scorer": top or {"team": "N/A", "points": 0.0},
        "biggest_blowout": blow,
        "closest_game": close,
        "unluckiest_loss": unlucky,
        "best_waiver": waiver,
        "lineup_regret_leader": regret,
        "mvp": mvp_player,
        "lvp": lvp_player,
        "surprise_stat": surprise,
        "benchwarmer": bench,
    }
