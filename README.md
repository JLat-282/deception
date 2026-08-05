# Deception

Deception is a five-letter word game where the feedback can lie. The ordinary
Wordle rules remain intact, but secretly selected rows may each show one
believable false tile.

Planning references:

- [Product decisions](docs/DECEPTION_PRODUCT_DECISIONS.md)
- [Student session handoff](docs/STUDENT_SESSION_HANDOFF.md)

The app supports:

- A shared Daily puzzle that resets at 03:00 UTC.
- One anonymous-browser Daily attempt, consumed by the first accepted guess.
- Practice games with a fresh answer and unrestricted replay.
- Four versioned Practice difficulty presets, from Doubt I through Deception.
- Standard repeated-letter Wordle evaluation.
- A hidden preset-owned lie and punishment blueprint persisted with each game.
- Feedback-only lies that preserve submitted letters and tile positions.
- A postgame audit of every activated or avoided opportunity.
- Keyboard, mouse, and touch input with non-color-only feedback.

Local development uses SQLite. Production uses managed Postgres when
`DATABASE_URL` is configured, so game state survives serverless restarts and
deployments. Clearing the browser cookie resets the anonymous player identity;
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

Create a managed Postgres database through Vercel's Marketplace, Neon,
Supabase, or another provider. Add these Production and Preview environment
variables in Vercel:

```text
DATABASE_URL=<transaction-pooler Postgres URL with SSL enabled>
DECEPTION_DAILY_SEED=<a long random secret>
DECEPTION_SECURE_COOKIE=true
```

The API and frontend share one Vercel domain. Do not create
`VITE_API_BASE_URL` for this setup; leaving it unset makes the browser call the
same-origin `/api` routes. The API creates its Postgres schema idempotently on
startup.

## Commands

```powershell
npm run dev
npm test
npm run test:e2e
npm run benchmark:deception
npm run build
npm run lint
```

Backend tests create a unique temporary directory under `.tmp/` for each run
and remove it automatically. This avoids shared-temp permission and file-lock
problems in OneDrive workspaces.

The deception benchmark reports planner latency at several history depths.
Pass `-- --enforce-target` to verify the current implementation remains at
least 40% faster than the recorded pre-optimization local baseline and keeps
the constraint-backed fallback below its 100ms p99 budget.

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
the deception planner first seeks feedback supported by a plausible alternative
answer. If none exists, it may fabricate a yellow for a previously untouched
letter without contradicting fixed visible information. Active API responses
never expose truthful feedback, scheduled rows, seeds, or decoy candidates.

Daily schedules are stored once per puzzle so every player faces the same
possible lie timing. Practice schedules are stored per game. Schema upgrades
preserve existing data: pre-deception games finish truthfully, while games
already using the one-row rules keep their stored schedule.

## Current preset behavior

- Doubt I provides one possible lie row, lighter Timer and Reverse Entry odds,
  no Blackout, and at most one punishment.
- Doubt II preserves the complete existing rules described below.
- Doubt III adds two or three possible lie rows, occasional coordinated
  two-tile lies, repeated Timers and Reverse Entry, and controlled punishment
  overlap.
- Deception adds three to five possible lie rows, broader punishment overlap,
  up to three Timers and Reverse Entry events, and a rare False Victory threat.
- Intrusion can repeatedly obstruct part of the board after guesses two through
  five. Its per-row chance is 0% / 10% / 30% / 60% from Doubt I through
  Deception.
- Daily remains pinned to `doubt-2@1` during this milestone.

The complete tuning matrix and delivery boundary live in
`docs/DIFFICULTY_AND_DAILY_DESCENT_DESIGN.md`.

### Doubt II

- One row is scheduled 20% of the time and two distinct rows are scheduled 80%
  of the time.
- Invalid guesses do not advance the schedule.
- An eligible selected row from one through five may change exactly one
  feedback marker.
- The lie may hide a true clue or create false certainty.
- Winning guesses and the sixth guess remain truthful.
- If no curated answer supports a lie, the planner may fabricate one safe
  yellow on a previously untouched letter.
- If neither an answer-backed nor constraint-backed lie is safe, the row
  remains truthful.
- Two activated lies never reuse the same tile position.
- The terminal response reveals every selected row and whether it lied.

### Doubt III

- Two lie rows are scheduled 40% of the time and three are scheduled 60% of
  the time.
- Each scheduled row has a 25% chance to seek a jointly plausible two-tile
  lie. The planner falls back to one tile, then truthful feedback, when needed.
- Timer and Reverse Entry may each occur up to twice, including on consecutive
  turns.
- Punishments may overlap. A 30-second Timer may begin after Blackout's curtain;
  a 10-second Timer is moved to another eligible turn instead.
- Blackout remains limited to once per game, and winning guesses cancel newly
  scheduled punishments.

### Deception

- Three, four, or five lie rows are scheduled, with a 50% chance per row to
  seek a coordinated two-tile lie.
- Every game receives at least one Timer and may receive as many as three, but
  never on three consecutive guesses.
- Timer, Reverse Entry, and Blackout may overlap. Timers begin only after the
  Blackout curtain has reopened.
- In 5% of games, one correct answer on guesses two through four may receive
  plausible false feedback when it lands on a scheduled lie row. Any later
  submission of that answer is guaranteed to win.
- Guesses five and six always recognize the correct answer.

## Punishment behavior

- Reverse Entry may require the next accepted word to be typed backwards.
- Each game has a 45% chance to receive one secretly scheduled Guess Timer on
  attempts two through six.
- Scheduled timers are 30 seconds 70% of the time and 10 seconds 30% of the
  time.
- Timer deadlines are persisted and enforced by the API. Invalid words do not
  stop or reset the countdown.
- Expiration consumes the current attempt and records a `Time expired` row
  without creating fake feedback.
- Doubt II has a 20% chance to schedule Blackout after attempt three, four, or
  five, with each attempt equally likely.
- Blackout erases accumulated color feedback and resets the keyboard. Future
  guesses reveal normally, and the full board returns after the game ends.
- Multiple punishments may occur in one base game, but never on the same
  attempt. Blackout also reserves the immediately following attempt so players
  do not emerge directly into Guess Timer or Reverse Entry.
- Guess Timer keeps priority over Reverse Entry if those two would otherwise
  overlap.
- Intrusion takes over the screen and blocks all guess input until its moving
  Dismiss control is activated. It
  has no per-game cap, may repeat on consecutive eligible guesses, and does not
  pause an active Timer. If it overlaps Blackout, it appears after the curtain
  has reopened.

The planner filters the curated answer corpus once against the visible history,
groups possible current feedback patterns, and selects from the smallest
supported decoy group. Its fallback ranks safe false-yellow candidates using a
support index built once from accepted words. This avoids rescanning either
corpus for every mutation.

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
`DECEPTION_FIXED_LIE_ROWS` accepts one or two distinct comma-separated rows,
such as `1,3`. These values are never returned by bootstrap, game-start, or
active-guess responses.

## Source references

- Product decisions: `docs/DECEPTION_PRODUCT_DECISIONS.md`
- Third-party notices: `THIRD_PARTY_NOTICES.md`
- Original teaching prototype: the sibling `wordle-list/` repository, which is
  not modified or used at runtime.
