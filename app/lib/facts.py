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
  "lineup_regret_leader": {"team": str, "regret": float} | null
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

    return {
        "week": int(week),
        "standings_changes": changes or [],
        "top_scorer": top or {"team": "N/A", "points": 0.0},
        "biggest_blowout": blow,
        "closest_game": close,
        "unluckiest_loss": unlucky,
        "best_waiver": waiver,
        "lineup_regret_leader": regret,
    }
