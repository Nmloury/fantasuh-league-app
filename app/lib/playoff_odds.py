import numpy as np
from collections import defaultdict

def simulate_playoff_odds(sb, n_sims=20000, playoff_teams=6):
    # team list
    teams = [m["manager_id"] for m in sb.table("managers").select("manager_id").execute().data]
    # historical totals
    mts = sb.table("matchups").select("team_a,team_b,score_a,score_b").execute().data
    totals = defaultdict(list)
    for r in mts:
        if r["score_a"] is not None: totals[r["team_a"]].append(float(r["score_a"]))
        if r["score_b"] is not None: totals[r["team_b"]].append(float(r["score_b"]))
    draws = {t: (np.array(v) if v else np.array([100.0])) for t,v in totals.items()}
    # current standings
    wins = defaultdict(float); pf = defaultdict(float)
    for r in mts:
        a,b,sa,sb_ = r["team_a"], r["team_b"], float(r["score_a"] or 0), float(r["score_b"] or 0)
        pf[a]+=sa; pf[b]+=sb_
        if sa>sb_: wins[a]+=1
        elif sb_>sa: wins[b]+=1
        else: wins[a]+=0.5; wins[b]+=0.5
    # remaining schedule
    sched = sb.table("schedule").select("week,team_a,team_b").order("week").execute().data
    if not sched: 
        return None  # ok for Day 2; we’ll populate once 2025 schedule is known

    playoffs = defaultdict(int); byes = defaultdict(int)
    for _ in range(n_sims):
        W = wins.copy(); PF = pf.copy()
        for s in sched:
            a,b = s["team_a"], s["team_b"]
            sa = np.random.choice(draws.get(a, draws[teams[0]]))
            sb = np.random.choice(draws.get(b, draws[teams[0]]))
            PF[a]+=sa; PF[b]+=sb
            if sa>sb: W[a]+=1
            elif sb>sa: W[b]+=1
            else: W[a]+=0.5; W[b]+=0.5
        final = sorted(teams, key=lambda t: (W[t], PF[t]), reverse=True)
        top = set(final[:playoff_teams])
        for t in top: playoffs[t]+=1
        for t in final[:2]: byes[t]+=1
    # Return odds; you can persist later if you prefer
    return {t: {"playoff": playoffs[t]/n_sims, "bye": byes[t]/n_sims} for t in teams}
