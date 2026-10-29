# Calculations, ratings and statistical insights

This file documents GameSense-created algorithms and their assumptions.
The ratings are **experimental GameSense metrics, not official league
statistics**. They are fixed-reference indicators, not predictions or an
objective ranking across sports, positions or eras.

## Missing data and observation grain

`None`, `NaN`, infinite values and unavailable fields do not count as measured
zero. Additive totals use present observations and state their coverage.
An entirely missing metric has no total. One player-season row may represent
82 games; it must not be treated as one game.

For known totals `x_i` and matching games `g_i`:

`per_game = sum(x_i) / sum(g_i)`.

Both numerator and denominator use rows where the metric is observed.
Unknown or invalid required game denominators leave per-game output missing.
A legacy season per-game average `a_i` becomes a total only where `g_i` is
known: `total = sum(a_i * g_i)`. Positions, percentages, ranks and lap times
are non-additive. Their totals are deliberately unavailable.

For example, 100 points in 10 games and 300 in 20 games give 400 points and
`400/30 = 13.333...` points/game, not 200 points/game. A shooting sample of
1 made from 1 attempt plus 0 from 9 gives `1/10 = 10%`, not the unweighted
mean of 100% and 0%. These examples are controlled in `tests/test_statistics.py`.

## Football and AFL club calculations

`club_matches` accepts observed team matches with both finite scores and
removes duplicated record IDs. An athlete row does not supply a club result.
With `F_i` scored and `A_i` conceded, the result is W if `F_i>A_i`, D if equal
and L if lower. `win_rate = wins / known_matches * 100`; a draw is not a win.

| Quantity | Formula/definition |
| --- | --- |
| Scored, conceded | `sum(F_i)`, `sum(A_i)` over eligible matches |
| Difference | `sum(F_i) - sum(A_i)` |
| Average scored/conceded | Corresponding sum divided by eligible matches |
| Home/away | Same summary restricted to the source's recorded venue flag |
| Last five/ten | Latest eligible dated matches in the selected scope, capped at the stated window; report actual sample size |
| Recent result form | Ordered W/D/L sequence from those observations |
| Current streak | Consecutive identical results at the end of the chronological sequence |
| Longest winning/losing streak | Longest consecutive W/L run in the eligible chronological sequence |
| Club season progression | Cumulative observed scores/results within each competition-season; competitions remain separate |
| AFL scoring percentage | `100 * total_points_for / total_points_against`, only with a nonzero known denominator |
| Goals and behinds | Sum actual supplied goal/behind fields; do not infer player statistics from a club total |

Football match points use supplied `table_points` when available rather than
assuming that 3/1/0 applies to every historic rule set. Their sum is observed
match points, not a reconstructed official table with deductions. AFL
scoring percentage is not scoring-shot accuracy; the latter would instead
use `goals/(goals+behinds)` when both are recorded.

## NBA and F1 summaries

NBA season/career totals and points, rebounds and assists per game use the
grain rules above. Shooting fractions are recomputed from eligible makes and
attempts, then displayed consistently as fractions or labelled percentages.
Available advanced provider measurements retain their names; the app does
not invent historic values where they were not recorded.

F1 wins count recorded first places and podiums count recorded places 1–3.
Average finishing position uses observed valid finishing positions. DNF
does not acquire an invented position. Grid versus race improvement is
`grid_position - finish_position` for paired observations. Points progression
sums recorded event points; it must not add cumulative championship snapshots.
Driver contributions can be aggregated for a constructor, but a constructor
comparison is labelled separately from a driver comparison. Rule changes and
historical dropped-score systems limit cross-era interpretation.

## Experimental 0–100 ratings

Define `clip(z)=min(1,max(0,z))`. For each positive reference `R`, normalize
a measured rate as `clip(x/R)`. Fixed references make scores explainable and
stable when a user changes a filter; they do not assert a population maximum.
Weights are explicit design choices that sum to one. Every required
component must be present: missing inputs never trigger silent reweighting.

| Entity | Formula | Reason for weights and limitations |
| --- | --- | --- |
| NBA player | `100 * (.50*clip(points_pg/40) + .25*clip(rebounds_pg/15) + .25*clip(assists_pg/12))` | Scoring contributes half, rebounding and creation each a quarter. Rates avoid rewarding extra games; defense, minutes, role and era are omitted. |
| AFL player | `100 * (.45*clip(disposals_pg/35) + .20*clip(marks_pg/10) + .20*clip(tackles_pg/10) + .15*clip(goals_pg/5))` | Ball involvement leads; marking and tackling balance possession; goals add attacking output. Position/minutes/opponent strength are not adjusted. |
| Soccer player | `100 * (.45*clip(goals_pg/1) + .30*clip(assists_pg/.7) + .15*clip(shots_pg/5) + .10*clip(tackles_pg/5))` | A transparent attacking-volume indicator. It strongly favours forwards and is not a fair goalkeeper/defender ranking. |
| Soccer club | `100 * (.70*result + .30*clip(.5 + goal_margin/8))` | Result is 1/0.5/0 for W/D/L. Result leads; margin adds bounded context using a 4-goal reference. Opposition and venue are not adjusted. |
| AFL club | `100 * (.70*result + .30*clip(.5 + points_margin/120))` | Same result logic, with a 60-point margin reference. Scoring environment and era are not adjusted. |
| F1 driver | `100 * (.80*clip((21-finish)/20) + .20*clip((grid-finish+10)/20))` | Finishing dominates and grid-to-finish movement adds context. Fixed 20-position baseline, car performance, grid size and era limit comparisons. |

Club ratings require actual match-level scores. A season aggregate such as
100 goals scored and 80 conceded over 38 matches cannot establish wins or
losses and receives no club rating; GameSense never interprets it as one
100–80 win. This rule is verified for both football and AFL in
`test_club_season_totals_never_imply_a_single_match_win`.

At reference NBA rates of 40 points, 15 rebounds and 12 assists/game, the
score is 100. At half each reference it is 50. A football club winning by
two goals scores `100*(.70 + .30*.75)=92.5`; a draw scores 50. A driver
starting fifth and finishing first scores
`100*(.80*1 + .20*.70)=94`. These hand-checkable examples are tested.

Event records use that event's measured counts. Season totals first divide
by recorded games; source per-game rows are already rates. A recent rating
takes the last five observed games/season rows first, then averages the
available scores within that window. An unknown newest score cannot bring
an older observation back into the window. Eligible and missing counts
are stated. Five season rows do not mean the player's last five games.
Rating timelines preserve source dates/season labels and do not generate
intermediate observations. Clipping intentionally makes very high values
saturate, so this score cannot distinguish every elite performance.

The compatibility `rating` column now uses the same normalized algorithm as
`experimental_rating`; the old unbounded weighted sum has been replaced.
Old stored provider rows are calculated through the current analytical view
when needed rather than treating an earlier raw sum as the new scale.

## Deterministic insights and comparison rules

The insights engine selects applicable, finite observations, calculates the
statistic and attaches its observed period and provider. It uses fixed text
templates; no language model invents explanations or results. A statement
such as winning four of five matches requires exactly that recorded result
count. A finishing-position trend needs comparable earlier/later observed
values; a lower position is better. A single observation cannot establish a
multi-season trend.

Comparisons require the same sport and compatible entity/record types.
Per-game averages use each competitor's matching games; totals disclose
different sample sizes. Radar axes use meaningful shared statistics and a
stated normalization. Missing measurements stay unavailable rather than
becoming a flattering zero. Sources, periods and incomplete coverage accompany
the comparison because arithmetic correctness alone does not make two
different samples equivalent.

Implementation: `gamesense/analytics.py`, `team_analytics.py`, `ratings.py`
and `insights.py`. Verification: `tests/test_statistics.py`,
`tests/test_club_profiles.py` and `tests/test_final_analytics.py`.
See [TEST_REPORT.md](TEST_REPORT.md) for actual execution outcomes.
