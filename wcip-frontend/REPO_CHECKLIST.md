# Frontend Repository Checklist

Tracks the Next.js frontend build. ✅ done · 🔲 follows established pattern.

## Foundation
- ✅ `package.json` — deps (Next 15, React 19, TS, Tailwind, React Query, Recharts, Zod, RHF, Framer Motion)
- ✅ `tsconfig.json`, `next.config.mjs`, `postcss.config.mjs`
- ✅ `vercel.json` — Vercel config for Root Directory `wcip-frontend`, build command `npm run vercel-build`, output `.next`
- ✅ `tailwind.config.ts` — design tokens (scoreboard theme)
- ✅ `app/globals.css` — CSS variables, fonts, grain, base styles
- ✅ `.env.local.example`
- ✅ `middleware.ts` — protect authed routes

## Lib (data layer)
- ✅ `lib/types.ts` — API response types (mirror backend schemas)
- ✅ `lib/api.ts` — typed fetch client, token handling, error normalisation
- ✅ `lib/auth-context.tsx` — JWT auth provider (login/register/refresh/logout)
- ✅ `lib/queries.ts` — React Query hooks for every endpoint
- ✅ `lib/utils.ts` — cn(), formatters

## UI primitives
- ✅ `components/ui/button.tsx`
- ✅ `components/ui/card.tsx`
- ✅ `components/ui/input.tsx`
- ✅ `components/ui/select.tsx`
- ✅ `components/ui/slider.tsx`
- ✅ `components/ui/skeleton.tsx`
- ✅ `components/ui/badge.tsx`

## Shared components
- ✅ `app/providers.tsx` — React Query + Auth + theme
- ✅ `components/nav.tsx` — top navigation + auth state
- ✅ `components/probability-bar.tsx` — W/D/L split bar
- ✅ `components/match-predictor.tsx` — team pickers + modifiers + result
- ✅ `components/champion-chart.tsx` — Recharts champion-probability bar chart
- ✅ `components/bracket.tsx` — animated knockout bracket

## Pages
- ✅ `app/layout.tsx` — root layout, fonts, providers
- ✅ `app/page.tsx` — landing → dashboard
- ✅ `app/login/page.tsx`
- ✅ `app/register/page.tsx`
- ✅ `app/dashboard/page.tsx` — overview, top contenders, recent sims
- ✅ `app/simulate/page.tsx` — single-match predictor + explanation
- ✅ `app/tournament/page.tsx` — Monte Carlo runner + champion chart + bracket
- ✅ `app/teams/page.tsx` — team table sortable by Elo
- ✅ `app/team/[id]/page.tsx` — team detail, stats, Elo trend (Recharts area)
- ✅ `app/scenarios/page.tsx` — 2–3 scenario compare with per-team modifiers + delta table
- ✅ `app/saved/page.tsx` — rename, share toggle, copy link, duplicate, delete, inline chart
- ✅ `app/history/page.tsx` — activity timeline of simulation runs
- ✅ `app/profile/page.tsx` — account details + sim count + sign out
- ✅ `app/admin/page.tsx` — analytics (users, sims, status breakdown), admin-gated
- ✅ `components/require-auth.tsx` — auth/admin route guard

## Notes
- Auth consumes the backend's own JWT endpoints directly. NextAuth + Google/GitHub
  OAuth is the production extension (backend already has the OAuth config fields).
- Vercel must use Root Directory `wcip-frontend`; the repository root does not
  contain the Next.js `app/` directory.
- Required production env vars: `NEXT_PUBLIC_API_BASE_URL`,
  `NEXT_PUBLIC_APP_NAME`, `NEXT_PUBLIC_ENABLE_ML`,
  `NEXT_PUBLIC_ENABLE_SCENARIOS`, and `NEXT_PUBLIC_ENABLE_EXPLAINABILITY`.
- `NEXT_PUBLIC_API_BASE_URL` must be the deployed FastAPI origin only. The API
  client appends `/api/v1` and reports a configuration error if the env var is
  missing or already includes `/api/v1`.
- Verified command set: `npm install`, `npm run typecheck`, `npm run build`.
