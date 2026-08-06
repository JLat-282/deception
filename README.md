# Deception

Deception is a five-letter word game where the feedback can lie. The ordinary
Wordle rules remain intact, but secretly selected rows may show believable
false feedback on one or two tiles.

Planning references:

- [Product decisions](docs/DECEPTION_PRODUCT_DECISIONS.md)
- [Student session handoff](docs/STUDENT_SESSION_HANDOFF.md)

The app supports:

- A four-stage Daily Descent that resets at 03:00 UTC.
- One anonymous-browser Daily attempt, consumed by the first accepted guess.
- Infinite games with a fresh answer and unrestricted replay.
- Four versioned Practice difficulty presets, from Doubt I through Deception.
- Standard repeated-letter Wordle evaluation.
- A hidden preset-owned lie and punishment blueprint persisted with each game.
- Feedback-only lies that preserve submitted letters and tile positions.
- A postgame audit of every activated or avoided opportunity.
- Keyboard, mouse, and touch input with non-color-only feedback.

Local development uses SQLite. Production uses managed Postgres when
`DATABASE_URL` or `POSTGRES_URL` is configured, so game state survives
serverless restarts and deployments. `DATABASE_URL` takes precedence when both
are present. Clearing the browser cookie resets the anonymous player identity;
clearing the selected database resets stored games.

## Quick start

Requirements:

- Python 3.11 or newer.
- Node.js 22 or newer.

From this directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api`
requests to FastAPI on port 8000, so the browser uses one local origin.

Local defaults work without an `.env` file. Copy `.env.example` to `.env` only
when you need to override local settings. Fixed answer, clock, lie-row, and
session-seed values are deterministic test controls, not ordinary play options.

## Deploy to Vercel

Import `JLat-282/deception` into Vercel and keep the project Root Directory at
the repository root. The checked-in `vercel.json` builds `frontend/dist` and
deploys `api/index.py` as the catch-all FastAPI function.

Connect a managed Postgres database through Vercel's Marketplace, Neon,
Supabase, or another provider. The Vercel Supabase integration automatically
adds `POSTGRES_URL`, which the backend accepts directly. If you connect a
database manually, add `DATABASE_URL` instead. Also add these application
variables to Production and Preview in Vercel:

```text
DECEPTION_DAILY_SEED=<a long random secret>
DECEPTION_SECURE_COOKIE=true
```

For Supabase, apply the checked-in SQL files in
[`supabase/migrations`](supabase/migrations) in filename order before deploying.
The exact order and connection-string guidance are documented in
[`supabase/README.md`](supabase/README.md). Production does not run schema DDL
during a function cold start.

After connecting the integration or changing environment variables, redeploy so
the deployment receives them. The API and frontend share one Vercel domain. Do
not create `VITE_API_BASE_URL` for this setup; leaving it unset makes the browser
call the same-origin `/api` routes. This application does not use Supabase's
browser SDK, so it does not need a Supabase URL, publishable key, anon key, or
service-role key.

## Commands

```powershell
npm run dev
npm test
npm run test:e2e
npm run benchmark:deception
npm run benchmark:punishments
npm run balance:simulate
npm run balance:activation
npm run balance:trace -- --preset deception@3 --answer crane --guess slate
npm run build
npm run lint
```

Backend tests create a unique temporary directory under `.tmp/` for each run
and remove it automatically. This avoids shared-temp permission and file-lock
problems in OneDrive workspaces.

The deception benchmark enforces 25ms common-path and 35ms maximum-history p99
budgets with a 50ms p99.9 ceiling. The punishment benchmark enforces a 3ms p99
and 10ms p99.9 ceiling for schema-6 blueprint generation. `balance:simulate`
runs 100,000 seeded blueprints and fails on probability, compatibility,
pressure-stack, or latency drift. `balance:activation` plays representative
high-information histories through every level and gates early lie activation
plus decision latency. `balance:trace` provides a private contributor view of
one seed without expanding the public API.

FastAPI publishes the local API schema at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Architecture

```text
React/Vite TypeScript
        |
        | /api through Vite proxy locally; same-origin on Vercel
        v
FastAPI HTTP/API shell
        |
        +--> game service
        |       +--> pure truth engine
        |       +--> pure deception planner
        +--> SQLite locally / managed Postgres in production
        +--> curated words and answers
```

The backend owns a versioned preset registry and generates a deterministic,
immutable challenge blueprint before play. Games persist their exact preset key
and blueprint so later balance changes cannot rewrite an active game. Public API
responses expose only names, descriptions, rank, and availability; schedules and
probabilities remain server-only.

The database stores `truth_feedback` and `display_feedback` separately. The
truth engine remains the only source of Wordle evaluation. On a selected row,
the deception planner scores credible player-belief worlds: an alternate answer
may explain the board when a difficulty-bounded number of prior displayed tiles
are treated as lies. This gives early guesses broad deceptive freedom without
requiring one exact dictionary decoy. Late unsupported rare-letter probes may
remain truthful. If no belief-backed choice exists, the planner may fabricate a
supported yellow on a previously untouched letter. Active API responses never
expose truthful feedback, scheduled rows, seeds, or candidate worlds.

Daily schedules are stored once per puzzle so every player faces the same
possible lie timing. Practice schedules are stored per game. Schema upgrades
preserve existing data: pre-deception games finish truthfully, while games
already using the one-row rules keep their stored schedule.

## Current preset behavior

New games use the `@3` preset family and schema-6 blueprints. Stored `@1` and
`@2` games retain their exact preset, schedule, and strategy. Daily Descent
puzzles pin their preset set for the full daily run.

| Difficulty | Scheduled lie-row distribution | Two-tile chance per row |
| --- | --- | --- |
| Doubt I | 1: 85%, 2: 15% | 0% |
| Doubt II | 1: 20%, 2: 75%, 3: 5% | 0% |
| Doubt III | 2: 25%, 3: 70%, 4: 5% | 35% |
| Deception | 3: 5%, 4: 40%, 5: 55% | 65% |

The exact rows are selected uniformly without replacement. There are no phase
patterns or guaranteed early/middle/late quotas. Winning guesses and guess six
remain truthful. A scheduled row may also stay truthful when no credible lie
survives the quality and deadline gates. Repeat lie threads are possible at
every difficulty but become more likely as difficulty rises.

Doubt I permits at most one punishment. Doubt II allows light overlap. Doubt
III and Deception coordinate high-pressure scenes while keeping the exact
combination and timing unpredictable. Reverse Entry and Forced Commitment may
combine on the top two levels; a ten-second Timer can never join that two-input
stack. Distinct Reverse Entry events may be scheduled on consecutive guesses.
The current pressure pass targets Timers in 95% of Doubt III games and every
Deception game, Reverse Entry in 55% and 75%, and Blackout in 75% and 95%.
Blackout stays on guesses three through five and favors guesses four and five.
The result dialog explains lies but does not recap punishments.

The complete tuning matrix and delivery boundary live in
`docs/DIFFICULTY_AND_DAILY_DESCENT_DESIGN.md`.

## Punishment behavior

- Reverse Entry may require the next accepted word to be typed backwards.
- Timer count and duration scale by difficulty; Deception always schedules at
  least one and may schedule as many as three.
- Timer deadlines are persisted and enforced by the API. Invalid words do not
  stop or reset the countdown.
- Expiration consumes the current attempt and records a `Time expired` row
  without creating fake feedback.
- If Reverse Entry affected the expired attempt, that event ends with the lost
  guess. Only a separately scheduled Reverse Entry can affect the next guess.
- Blind Entry conceals typed letters until the guess is submitted. No Revision
  locks Backspace after the first letter. Forced Commitment submits the fifth
  letter immediately and consumes an invalid committed attempt.
- Corrupted History temporarily masks one prior row. Memory Tax persistently
  leaves only the two newest rows visible until terminal history restoration.
- Blackout erases accumulated color feedback and resets the keyboard. Future
  guesses reveal normally, and the full board returns after the game ends.
- Intrusion takes over the screen and blocks all guess input until its moving
  Dismiss control is activated. It has no separate per-game cap and does not
  pause an active Timer.
- Every blueprint passes pressure-budget, lifecycle, overlap, and final-attempt
  validation before it is stored. Winning guesses cancel pending post-guess
  punishments.

The planner caches per-guess truth patterns, scans candidate answer worlds once,
and aggregates the false markers those worlds support. It returns the best
candidate found if the deadline arrives after any plausible option; truth is
returned only when no candidate survives or the strategy forbids one. Private
diagnostics distinguish no candidate, deadline expiration, and strategy limits.

## Daily attempt behavior

- Opening Daily does not consume the attempt.
- Invalid or short guesses do not consume it.
- The first accepted five-letter guess consumes it atomically.
- The open tab can finish the game, but an interrupted Daily is not resumable.
- Returning to the mode screen or refreshing after the first accepted guess
  makes Daily unavailable until the next 03:00 UTC reset.
- Practice remains available after Daily is consumed or completed.

## Deterministic tests

Tests inject fixed values through the same planner and seed seams used by the
application. Browser tests can set:

```text
DECEPTION_FIXED_ANSWER
DECEPTION_FIXED_NOW
DECEPTION_FIXED_LIE_ROW
DECEPTION_FIXED_LIE_ROWS
DECEPTION_FIXED_SESSION_SEED
```

`DECEPTION_FIXED_LIE_ROW` preserves the single-row test override.
`DECEPTION_FIXED_LIE_ROWS` accepts one through five distinct comma-separated
rows, such as `1,3,5`. These values are never returned by bootstrap, game-start, or
active-guess responses.

## Source references

- Product decisions: `docs/DECEPTION_PRODUCT_DECISIONS.md`
- Third-party notices: `THIRD_PARTY_NOTICES.md`
- Original teaching prototype: the sibling `wordle-list/` repository, which is
  not modified or used at runtime.
