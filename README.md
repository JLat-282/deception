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
- Standard repeated-letter Wordle evaluation.
- A hidden one-or-two-row schedule in both Daily and Practice.
- Feedback-only lies that preserve submitted letters and tile positions.
- A postgame audit of every activated or avoided opportunity.
- Keyboard, mouse, and touch input with non-color-only feedback.

This build runs on the developer machine only. Clearing the browser cookie or
the local SQLite database resets the anonymous playtest identity.

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
        | /api through Vite proxy
        v
FastAPI HTTP/API shell
        |
        +--> game service
        |       +--> pure truth engine
        |       +--> pure deception planner
        +--> SQLite repository
        +--> curated words and answers
```

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

## Deception behavior

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
