# World Cup Intelligence Platform — Frontend (Next.js 15)

The web client for the platform. Consumes the FastAPI backend's REST API to
predict matches, run Monte Carlo tournament simulations, and browse teams.

> Verified: `tsc --noEmit` passes and `next build` compiles all 10 routes
> cleanly (Google Fonts require network at build time).

## Stack

Next.js 15 (App Router) · React 19 · TypeScript · TailwindCSS · TanStack Query ·
Recharts · Framer Motion · React Hook Form + Zod · Zustand. Auth consumes the
backend's JWT endpoints directly via a typed client with transparent refresh.

## Design

A **scoreboard / stadium-night** aesthetic: midnight base, an acid-lime "pitch"
accent with a coral counter-accent, condensed editorial display type (Bricolage
Grotesque) over a clean body (Hanken Grotesk), and tabular IBM Plex Mono for
every statistic so probabilities read like live data. Subtle grain + radial glow
for depth.

## Structure

```
app/
├── layout.tsx              fonts, providers, nav, footer
├── globals.css             design tokens, grain, base styles
├── providers.tsx           React Query + Auth
├── page.tsx                landing (→ dashboard when authed)
├── login / register        auth forms
├── dashboard               overview + top contenders
├── simulate                single-match predictor
├── tournament              Monte Carlo runner + chart + funnel bracket
└── teams                   sortable nations table
lib/
├── types.ts                API types (mirror backend schemas)
├── api.ts                  typed fetch client (tokens, refresh, errors)
├── auth-context.tsx        JWT auth provider
├── queries.ts              React Query hooks per endpoint
└── utils.ts                cn(), formatters
components/
├── ui/                     button, card, input, select, slider, skeleton, badge
├── nav.tsx                 auth-aware navigation
├── probability-bar.tsx     animated W/D/L split
├── champion-chart.tsx      Recharts champion probability + CI whiskers
├── match-predictor.tsx     fixture pickers + scenario sliders + result
└── bracket.tsx             probability-driven advancement funnel
middleware.ts               security headers
Dockerfile · vercel.json · .env.local.example
```

## Local setup

```bash
npm install
cp .env.local.example .env.local
npm run dev            # http://localhost:3000
```

`next.config.mjs` proxies `/backend/*` → `http://localhost:8000` so the browser
avoids CORS in dev. Run the backend (`uvicorn app.main:app`) alongside.

## Deployment (Vercel)

Set `NEXT_PUBLIC_API_BASE=/backend/api/v1` and edit the rewrite in `vercel.json`
to point `/backend/*` at your Render API URL. Also add the Vercel domain to the
backend's `BACKEND_CORS_ORIGINS`.

## Auth note

Authentication uses the backend's own JWT login/refresh endpoints (faithful to
"consume the existing APIs"). NextAuth with Google/GitHub OAuth is the drop-in
production upgrade — the backend already carries the OAuth client-config fields.

## Remaining pages

`team/[id]`, `scenarios`, `saved`, `history`, `profile`, `admin` follow the
patterns already established (a React Query hook from `lib/queries.ts` + a page
composing the existing UI primitives). See `REPO_CHECKLIST.md`.
