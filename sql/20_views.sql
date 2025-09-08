-- per-team weekly total and win flag
create or replace view v_team_week_scores as
select week, team_a as manager_id, score_a as points_for,
       case when score_a > score_b then 1 else 0 end as win
from matchups
union all
select week, team_b, score_b,
       case when score_b > score_a then 1 else 0 end
from matchups;

-- standings through a given week (wins & PF)
-- (UI will filter by week)
create or replace view v_standings as
select week, manager_id,
       sum(win) over (partition by manager_id order by week) as cum_wins,
       sum(points_for) over (partition by manager_id order by week) as cum_pf
from v_team_week_scores;

-- convenience for luck/xW page: actual wins per team
create or replace view v_actual_wins as
select manager_id, sum(win)::int as wins
from v_team_week_scores
group by manager_id;