START_SLOTS = {"QB","RB","WR","TE","W/R/T","Q/W/R/T","DST","K"}

def compute_faab_roi(sb):
    # candidate adds
    adds = sb.table("transactions").select("tx_id,ts,type,manager_id,player_id,faab_spent") \
             .eq("type","add").not_.is_("faab_spent","null").execute().data

    # last available week
    weeks = sb.table("rosters").select("week").order("week", desc=True).limit(1).execute().data
    last_w = weeks[0]["week"] if weeks else None
    if last_w is None: return

    for tx in adds:
        txid, mid, pid, faab = tx["tx_id"], tx["manager_id"], tx["player_id"], int(tx["faab_spent"])
        # first seen week on roster for this manager (>= transaction date)
        roster_rows = sb.table("rosters").select("week,slot,started").eq("manager_id",mid).eq("player_id",pid).order("week").execute().data
        if not roster_rows: 
            continue
        start_week = roster_rows[0]["week"]

        # collect all weeks on roster and started weeks
        all_weeks = [r["week"] for r in roster_rows if r["week"] >= start_week]
        started_weeks = [r["week"] for r in roster_rows if r["started"] and r["slot"] in START_SLOTS and r["week"] >= start_week]
        
        # calculate points for all weeks on roster
        if not all_weeks:
            pts_all = 0.0
        else:
            ps_all = sb.table("player_stats").select("week,total_points") \
                    .eq("player_id", pid).in_("week", all_weeks).execute().data
            pts_all = sum(float(p["total_points"]) for p in ps_all)
        
        # calculate points for started weeks only
        if not started_weeks:
            pts_starting = 0.0
        else:
            ps_starting = sb.table("player_stats").select("week,total_points") \
                    .eq("player_id", pid).in_("week", started_weeks).execute().data
            pts_starting = sum(float(p["total_points"]) for p in ps_starting)

        # calculate points per dollar (not dollars per point)
        pts_per_dollar_all = (pts_all / faab) if faab > 0 else 0
        pts_per_dollar_starting = (pts_starting / faab) if faab > 0 else 0
        
        sb.table("faab_roi").upsert([{
            "tx_id": txid, "manager_id": mid, "player_id": pid,
            "start_week": start_week, "end_week": last_w,
            "pts_all": pts_all, "pts_starting": pts_starting, "faab_spent": faab, 
            "pts_per_dollar_all": pts_per_dollar_all, "pts_per_dollar_starting": pts_per_dollar_starting
        }], on_conflict="tx_id,player_id").execute()
