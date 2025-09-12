START_SLOTS = {"QB","RB","WR","TE","W/R/T","Q/W/R/T","DST","K"}

def compute_draft_roi(sb):
    # Get all draft picks with their costs
    draft_picks = sb.table("draft_picks").select("manager_id,player_id,cost").execute().data
    
    if not draft_picks:
        print("No draft picks found")
        return
    
    # Get last available week
    weeks = sb.table("rosters").select("week").order("week", desc=True).limit(1).execute().data
    last_w = weeks[0]["week"] if weeks else None
    if last_w is None:
        print("No roster data found")
        return
    
    print(f"Computing draft ROI for {len(draft_picks)} draft picks up to week {last_w}")
    
    for pick in draft_picks:
        mid, pid, draft_cost = pick["manager_id"], pick["player_id"], int(pick["cost"])
        
        # Get all roster data for this player and manager
        roster_rows = sb.table("rosters").select("week,slot,started").eq("manager_id", mid).eq("player_id", pid).order("week").execute().data
        
        if not roster_rows:
            print(f"No roster data found for manager {mid}, player {pid}")
            continue
        
        # Collect all weeks on roster and started weeks
        all_weeks = [r["week"] for r in roster_rows]
        started_weeks = [r["week"] for r in roster_rows if r["started"] and r["slot"] in START_SLOTS]
        
        # Calculate points for all weeks on roster
        if not all_weeks:
            pts_all = 0.0
        else:
            ps_all = sb.table("player_stats").select("week,total_points") \
                    .eq("player_id", pid).in_("week", all_weeks).execute().data
            pts_all = sum(float(p["total_points"]) for p in ps_all)
        
        # Calculate points for started weeks only
        if not started_weeks:
            pts_starting = 0.0
        else:
            ps_starting = sb.table("player_stats").select("week,total_points") \
                    .eq("player_id", pid).in_("week", started_weeks).execute().data
            pts_starting = sum(float(p["total_points"]) for p in ps_starting)
        
        # Calculate points per dollar (not dollars per point)
        pts_per_dollar_all = (pts_all / draft_cost) if draft_cost > 0 else 0
        pts_per_dollar_starting = (pts_starting / draft_cost) if draft_cost > 0 else 0
        
        # Upsert to draft_roi table
        sb.table("draft_roi").upsert([{
            "manager_id": mid, 
            "player_id": pid,
            "draft_cost": draft_cost,
            "pts_all": pts_all, 
            "pts_starting": pts_starting, 
            "pts_per_dollar_all": pts_per_dollar_all, 
            "pts_per_dollar_starting": pts_per_dollar_starting
        }], on_conflict="manager_id,player_id").execute()
    
    print(f"Draft ROI computation completed for {len(draft_picks)} players")
