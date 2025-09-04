create table if not exists managers (
  manager_id text primary key,
  manager_name text not null,
  team_name  text not null,
);

create table if not exists players (
  player_id text primary key,
  name      text not null,
  pos_type  text not null,
  eligible_positions text[] not null
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
  slot text not null,                  -- QB,RB,WR,TE,FLEX,SFLEX,DST,K,BN,IR
  started boolean not null default false,
  primary key (week, manager_id, player_id)
);

create table if not exists transactions (
  ts timestamptz not null,
  type text not null,                  -- add, drop, trade, commish
  manager_id text references managers(manager_id),
  player_id text references players(player_id),
  faab_spent int,
  details jsonb,
  primary key (ts, type, manager_id, player_id)
);

create table if not exists player_stats (
  week int not null,
  player_id text not null references players(player_id),
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
