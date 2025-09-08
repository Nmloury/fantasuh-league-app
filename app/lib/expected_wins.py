import numpy as np
from math import sqrt, erf

def _phi(z): return 0.5*(1+erf(z/np.sqrt(2)))

def compute_expected_wins(sb):
    mts = sb.table("matchups").select("week,team_a,team_b,score_a,score_b").order("week").execute().data
    if not mts: return
    # history of totals per team
    totals = {}
    for row in mts:
        a,b = row["team_a"], row["team_b"]
        sa,sb_ = float(row["score_a"] or 0), float(row["score_b"] or 0)
        totals.setdefault(a, []).append(sa)
        totals.setdefault(b, []).append(sb_)

    cum_xw = {}
    for row in mts:
        w,a,b,sa,sb_ = row["week"], row["team_a"], row["team_b"], float(row["score_a"] or 0), float(row["score_b"] or 0)
        hist_a = totals[a][:-1] if len(totals[a])>1 else totals[a]
        hist_b = totals[b][:-1] if len(totals[b])>1 else totals[b]
        mu_a, sd_a = (np.mean(hist_a), np.std(hist_a, ddof=0)) if hist_a else (sa, 0)
        mu_b, sd_b = (np.mean(hist_b), np.std(hist_b, ddof=0)) if hist_b else (sb_, 0)
        denom = sqrt(sd_a**2 + sd_b**2)
        pa = _phi(((mu_a - mu_b)/denom) if denom>0 else (0.0 if mu_a==mu_b else (10 if mu_a>mu_b else -10)))
        for mid,p in [(a,pa),(b,1-pa)]:
            cum_xw[mid] = cum_xw.get(mid,0.0) + float(p)
            sb.table("expected_wins").upsert([{
                "week": w, "manager_id": mid, "p_win": float(p), "cum_xw": float(cum_xw[mid])
            }], on_conflict="week,manager_id").execute()
