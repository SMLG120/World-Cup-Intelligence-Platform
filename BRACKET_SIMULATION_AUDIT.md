# Bracket Simulation Audit

Date: 2026-06-13

## What Already Works

- `wcip-backend/wcip/engine/tournament.py` simulates the 2026 format with 12
  groups of four teams.
- Group-stage ranking uses points, goal difference, and goals for.
- The top two teams in each group advance.
- The eight best third-place teams advance into a 32-team knockout field.
- The knockout engine resolves Round of 32, Round of 16, quarter-finals,
  semi-finals, final, and third-place match.
- `POST /api/v1/world_cup/2026/simulate` exists as an alias for the 2026
  simulator.
- The current simulation response includes aggregate team probabilities,
  group tables, best third-place teams, knockout rounds, flat match results,
  champion, runner-up, and third place.
- `/world-cup` already renders overview charts, team ratings, group tables, and
  a basic bracket tab.
- `/wc2026/simulate` loads the canonical World Cup dashboard.

## What Is Missing

- Match objects do not include statistical, ML, and ensemble probabilities.
- Match objects do not include a single displayed win probability for the
  predicted advancing team.
- Match objects do not explain why a team advanced.
- Match objects do not include team codes/flags for compact bracket cards.
- `SimulateRequest` does not accept a prediction mode (`statistical`, `ml`, or
  `ensemble`), so the frontend cannot ask for a mode-specific bracket.
- Group-stage match results are reflected only through standings; individual
  group fixtures are not serialized.
- The bracket UI is a basic horizontal list and does not yet show model mode,
  expected scoreline, win probability, or advancement reason.
- There is no dedicated `/wc2026/bracket` route.
- Existing tests verify high-level response shape, but not all elimination
  invariants or per-round reappearance rules.

## What Must Change

- Extend the simulation request with `prediction_mode`.
- Enrich backend match serialization with:
  - team codes
  - expected scoreline
  - statistical prediction
  - ML prediction
  - ensemble prediction
  - selected mode
  - winner win probability
  - advancement reason
- Serialize group-stage fixtures in addition to group tables.
- Keep Monte Carlo champion probabilities as the tournament-level probability
  source and attach each team winner's champion probability to relevant matches.
- Add backend safeguards/tests for:
  - 32 qualified teams after group stage
  - eight best third-place teams
  - no eliminated knockout loser reappears in later rounds, except semi-final
    losers in the third-place match
  - match probabilities are finite and normalized
- Update frontend types and API calls for `prediction_mode`.
- Add a dedicated `/wc2026/bracket` route.
- Upgrade bracket UI cards to show score, winner, probability, model mode, and
  reason while remaining responsive.
- Update README, docs/MEMORY.md, and docs/REPO_CHECKLIST.md with the final flow.

## What Should Not Change

- Do not hardcode winners or force a country-specific champion.
- Do not replace the existing tournament engine.
- Do not remove saved simulation behavior.
- Do not change the v2 ML feature order.
- Do not destructively overwrite historical Elo/FIFA/player snapshots.
