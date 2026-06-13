# Bracket Visualization and Squad-Loading Audit

**Date:** 2026-06-13

---

## Current State

### Backend (wcip-backend)

| Component | Status | Notes |
|-----------|--------|-------|
| `wcip/engine/tournament.py` | ✅ Working | Full 48-team simulation with R32→R16→QF→SF→3P→Final |
| `POST /api/v1/world_cup/2026/simulate` | ✅ Working | Returns `knockout_bracket` array grouped by round |
| `GET /world-cup/teams/{name}` | ✅ Working | Returns team detail + coach stats |
| `GET /world-cup/players/{name}` | ⚠️ Partial | Returns squad but **missing FIFA PDF fields**: `height_cm`, `date_of_birth`, `shirt_number`, `name_on_shirt`, `first_names`, `last_names` |
| `GET /teams/{id}/players` | ✅ Working | Returns PlayerOut with all FIFA fields |
| `GET /teams/{id}/squad-strength` | ✅ Working | Returns 16 strength metrics |
| Alembic migration `b5c7a9e1d3f2` | ✅ Applied | Added all 6 Player + 5 Coach PDF fields to DB |

### Knockout Bracket Data Structure

The backend returns:
```json
{
  "knockout_bracket": [
    { "round": "Round of 32", "matches": [ ...16 matches, sorted by order 49-64... ] },
    { "round": "Round of 16", "matches": [ ...8 matches, order 65-72... ] },
    { "round": "Quarter-finals", "matches": [ ...4 matches, order 73-76... ] },
    { "round": "Semi-finals", "matches": [ ...2 matches, order 200-201... ] },
    { "round": "Third-place match", "matches": [ ...1 match... ] },
    { "round": "Final", "matches": [ ...1 match... ] }
  ],
  "champion": "...",
  "runner_up": "...",
  "third_place": "..."
}
```

Match pairing (standard sequential):
- M49+M50 → M65 → M73 → M200 → FINAL
- M51+M52 → M66 → M73 → M200 → FINAL
- M53+M54 → M67 → M74 → M200 → FINAL
- M55+M56 → M68 → M74 → M200 → FINAL
- M57+M58 → M69 → M75 → M201 → FINAL
- M59+M60 → M70 → M75 → M201 → FINAL
- M61+M62 → M71 → M76 → M201 → FINAL
- M63+M64 → M72 → M76 → M201 → FINAL

---

### Frontend (wcip-frontend)

#### Current `/wc2026/bracket/page.tsx`
- Shows match cards in horizontal columns by round (R32, R16, QF, SF, 3P, Final)
- **No visual connectors** showing which teams advance from round to round
- Flat list layout — no branching tree structure
- No squad panel or player details

#### Current `/app/world-cup/page.tsx` Bracket tab
- Same `KnockoutBracket` column layout as above
- Shows Champion/Runner-up/Third-place summary cards
- **No visual connectors**
- No squad panel

#### Current `components/bracket.tsx`
- Monte Carlo probability "funnel" view (not a match-by-match bracket)
- Shows which teams are most likely to reach each round
- Not a proper tournament tree

#### Missing UX
- No visual branch lines showing advancement path
- No click-to-expand squad panel per team
- No per-match detail drawer
- Player type lacks FIFA PDF fields (`height_cm`, `date_of_birth`, etc.)

---

## What Must Change

### Files to Create
| File | Purpose |
|------|---------|
| `wcip-frontend/components/bracket-tree.tsx` | Visual tournament tree with SVG connector lines |
| `wcip-frontend/components/squad-panel.tsx` | Sliding panel showing team roster by position |

### Files to Modify
| File | Change |
|------|--------|
| `wcip-frontend/lib/types.ts` | Add `height_cm`, `date_of_birth`, `shirt_number`, `name_on_shirt`, `first_names`, `last_names` to `Player` type |
| `wcip-frontend/app/wc2026/bracket/page.tsx` | Replace `BracketColumns` with `TournamentBracket` + `SquadPanel` |
| `wcip-frontend/app/world-cup/page.tsx` | Replace `KnockoutBracket` in Bracket tab with `TournamentBracket` + `SquadPanel` |
| `wcip-backend/app/api/v1/world_cup.py` | Add FIFA PDF fields to `get_team_players` response |

---

## Bracket Visualization Design

### Layout
- Rounds shown left-to-right: R32 → R16 → QF → SF → Final → Champion
- Third-place match shown separately below main bracket
- Horizontal scrolling on all screen widths
- Total height: ~1400px (computed from 16 R32 matches at 80px each)
- Each column uses `position: absolute` with calculated Y offsets

### Position Calculation (math)
With `CARD_H=80`, `R32_UNIT=88` (card + 8px gap):

| Round | Match count | Y positions (tops) |
|-------|-------------|---------------------|
| R32 | 16 | 0, 88, 176, ..., 1320 |
| R16 | 8 | 44, 220, 396, 572, 748, 924, 1100, 1276 |
| QF | 4 | 132, 484, 836, 1188 |
| SF | 2 | 308, 1012 |
| Final | 1 | 660 |

Each match in round N is centered between its two feeding matches from round N-1.

### SVG Connector Lines
Between each pair of rounds, an SVG draws connector lines:
- Horizontal line from each child match's right edge to midpoint (x = CONN_W/2)
- Vertical line connecting top-child to bottom-child at midpoint
- Horizontal line from midpoint to parent match left edge

### Squad Panel
- Slides in from right when team name is clicked in any bracket card
- Uses `GET /world-cup/players/{team_name}` to fetch squad
- Groups players by position: GK → DEF → MID → FWD
- Shows: name, club, height_cm, caps, goals per player
- Shows coach name + win rate at top
- Shows "Squad data incomplete" warning if < 20 players returned

---

## Invariants That Must Not Change

- Backend tournament engine not modified
- No hardcoded bracket results or predetermined winners
- Existing saved-simulation behavior unchanged
- ML feature vector v2 unchanged
- Historical Elo/FIFA/player snapshots not destroyed
- Admin auth on all admin routes

---

## Test Checklist (Step 10)

### Backend
- [ ] `pytest wcip-backend/` — all tests pass
- [ ] `python -m scripts.validate_squad_ingestion` — checks squad DB state
- [ ] `GET /world-cup/players/Brazil` includes `height_cm` and `date_of_birth` fields
- [ ] `GET /world-cup/players/France` returns ≥ 20 players (if PDF has been ingested)

### Frontend
- [ ] `npm run typecheck` — no type errors
- [ ] `npm run build` — clean build
- [ ] Bracket renders all 6 rounds (R32, R16, QF, SF, 3P, Final)
- [ ] SVG connector lines appear between rounds
- [ ] Champion card renders at end of bracket
- [ ] Third-place match card renders below main bracket
- [ ] Clicking a team name opens squad panel
- [ ] Squad panel shows players grouped by position
- [ ] Squad panel closes on backdrop click or X button
- [ ] No crash when squad data is empty or missing
