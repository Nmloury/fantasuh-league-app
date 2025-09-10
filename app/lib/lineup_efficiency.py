from supabase import create_client
import os, itertools
import pulp

# TODO: change this to the superflex slots when updating for the 2025 season
STARTING_SLOTS = ["QB","RB","RB","WR","WR","TE","W/R/T", "Q/W/R/T", "DEF","K"]

def compute_lineup_efficiency(sb, max_week=14):
    # weeks present
    weeks = sorted({r["week"] for r in sb.table("rosters").select("week").execute().data})
    # Filter to only include weeks up to max_week
    weeks = [w for w in weeks if w <= max_week]
    # managers
    managers = [m["manager_id"] for m in sb.table("managers").select("manager_id").execute().data]

    for w in weeks:
        # cache player points for week
        ps = sb.table("player_stats").select("player_id,total_points").eq("week", w).execute().data
        pts = {p["player_id"]: float(p["total_points"]) for p in ps}

        for mid in managers:
            roster = sb.table("rosters").select("player_id,slot,started").eq("week",w).eq("manager_id",mid).execute().data
            if not roster: 
                continue

            # actual points from starts
            actual = sum(pts.get(r["player_id"], 0.0) for r in roster if r["started"])

            # candidates with eligibility
            pids = [r["player_id"] for r in roster]
            players = sb.table("players").select("player_id,eligible_positions").in_("player_id", pids).execute().data
            elig = {p["player_id"]: set(p["eligible_positions"]) for p in players}

            # ILP: choose at most one player per slot, each player ≤ 1 slot
            prob = pulp.LpProblem("opt_lineup", pulp.LpMaximize)
            X = {(pid, i): pulp.LpVariable(f"x_{pid}_{i}", 0, 1, cat="Binary")
                 for pid in pids for i,_ in enumerate(STARTING_SLOTS)
                 if STARTING_SLOTS[i] in elig.get(pid, set())}

            prob += pulp.lpSum(X.get((pid,i), 0) * pts.get(pid, 0.0) for pid in pids for i in range(len(STARTING_SLOTS)))
            # slot coverage - at most one player per slot (can be empty)
            for i,_ in enumerate(STARTING_SLOTS):
                prob += pulp.lpSum(X.get((pid,i), 0) for pid in pids) <= 1
            # player at most once
            for pid in pids:
                prob += pulp.lpSum(X.get((pid,i), 0) for i in range(len(STARTING_SLOTS))) <= 1

            prob.solve(pulp.PULP_CBC_CMD(msg=False))
            optimal = sum(pts.get(pid,0.0) for (pid,i),var in X.items() if var.value()==1)
            regret = max(0.0, optimal - actual)
            eff = (actual / optimal) if optimal > 0 else 1.0

            sb.table("lineup_efficiency").upsert([{
                "week": w, "manager_id": mid,
                "actual_pts": actual, "optimal_pts": optimal,
                "regret": regret, "efficiency": eff
            }], on_conflict="week,manager_id").execute()
