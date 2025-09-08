-- helpful indexes
create index if not exists rosters_manager_week on rosters(manager_id, week);
create index if not exists rosters_player_week on rosters(player_id, week);
create index if not exists matchups_team_a_week on matchups(team_a, week);
create index if not exists matchups_team_b_week on matchups(team_b, week);
create index if not exists transactions_mgr_ts on transactions(manager_id, ts);
create index if not exists transactions_faab_add on transactions(type, faab_spent) where type='add' and faab_spent is not null;