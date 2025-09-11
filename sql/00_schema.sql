create table if not exists managers (
  manager_id text primary key,
  manager_name text not null,
  team_name  text not null
);

create table if not exists players (
  player_id text primary key,
  name      text not null,
  pos_type  text not null,
  eligible_positions text[] not null
);

create table if not exists draft_picks (
  manager_id text not null references managers(manager_id),
  player_id text not null references players(player_id),
  cost int not null,
  primary key (manager_id, player_id)
);

create table if not exists matchups (
  week int not null,
  matchup_id text not null,
  team_a text not null references managers(manager_id),
  team_b text not null references managers(manager_id),
  score_a numeric,
  score_b numeric,
  primary key (week, matchup_id)
);



create table if not exists rosters (
  week int not null,
  manager_id text not null references managers(manager_id),
  player_id text not null references players(player_id),
  slot text not null,                  -- QB,RB,WR,TE,W/R/T,Q/W/R/T,DEF,K,BN,IR
  started boolean not null default false,
  primary key (week, manager_id, player_id)
);

create table if not exists transactions (
  tx_id text not null,
  ts timestamptz not null,
  type text not null,                  -- add, drop, trade, commish
  status text not null,
  manager_id text references managers(manager_id),
  player_id text references players(player_id),
  faab_spent int,
  primary key (tx_id, player_id)
);

create table if not exists player_stats (
  week int not null,
  player_id text not null references players(player_id),
  total_points numeric not null default 0,
  pass_yds int not null default 0,
  pass_td int not null default 0,
  pass_int int not null default 0,
  rush_yds int not null default 0,
  rush_td int not null default 0,
  rec int not null default 0,
  rec_yds int not null default 0,
  rec_td int not null default 0,
  return_td int not null default 0,
  two_pt int not null default 0,
  fum_lost int not null default 0,
  fum_ret_td int not null default 0,
  fg_0_19 int not null default 0,
  fg_20_29 int not null default 0,
  fg_30_39 int not null default 0,
  fg_40_49 int not null default 0,
  fg_50_plus int not null default 0,
  pat_made int not null default 0,
  dst_sacks int not null default 0,
  dst_int int not null default 0,
  dst_fum_rec int not null default 0,
  dst_td int not null default 0,
  safeties int not null default 0,
  blk_kick int not null default 0,
  dst_ret_td int not null default 0,
  pts_allow_0 int not null default 0,
  pts_allow_1_6 int not null default 0,
  pts_allow_7_13 int not null default 0,
  pts_allow_14_20 int not null default 0,
  pts_allow_21_27 int not null default 0,
  pts_allow_28_34 int not null default 0,
  pts_allow_35_plus int not null default 0,
  xpr int not null default 0,
  primary key (week, player_id)
);

-- Lineup efficiency per (week, team)
create table if not exists lineup_efficiency (
  week int not null,
  manager_id text not null references managers(manager_id),
  actual_pts numeric not null,
  optimal_pts numeric not null,
  regret numeric not null,
  efficiency numeric not null,
  primary key (week, manager_id)
);

-- Expected wins (weekly p_win and season-to-date cum_xw)
create table if not exists expected_wins (
  week int not null,
  manager_id text not null references managers(manager_id),
  p_win numeric not null,
  cum_xw numeric not null,
  primary key (week, manager_id)
);

-- FAAB ROI (rest-of-season realized points from STARTS and ALL weeks)
create table if not exists faab_roi (
  tx_id text not null,
  manager_id text not null references managers(manager_id),
  player_id text not null references players(player_id),
  start_week int not null,
  end_week int not null,
  pts_all numeric not null,
  pts_starting numeric not null,
  faab_spent int not null,
  pts_per_dollar_all numeric,
  pts_per_dollar_starting numeric,
  primary key (tx_id, player_id)
);

-- Schedule (needed for playoff odds during active season)
create table if not exists schedule (
  week int not null,
  team_a text not null references managers(manager_id),
  team_b text not null references managers(manager_id),
  primary key (week, team_a, team_b)
);

-- Recaps (used for the recap generation)
create table if not exists recaps (
  id            uuid primary key default gen_random_uuid(),
  league_id     text not null,
  week          int  not null,
  title         text,
  content_md    text not null,         -- markdown you render in Streamlit
  model         text not null,         -- e.g., 'gpt-5-mini-2025-08-07'
  prompt_hash   text,                  -- to detect prompt changes
  inputs_json   jsonb,                 -- light context (standings, big moves, etc.)
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
