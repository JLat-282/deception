# Deception

Deception Layer 1 is a truthful five-letter word-game baseline for a closed
playtest. It validates the six-guess game contract before lies, punishments, and
other antagonistic mechanics are introduced.

The app supports:

- A shared Daily puzzle that resets at 03:00 UTC.
- One anonymous-browser Daily attempt, consumed by the first accepted guess.
- Practice games with a fresh answer and unrestricted replay.
- Standard repeated-letter Wordle evaluation.
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
when you need to override the database path or Daily seed.

## Commands

```powershell
npm run dev
npm test
npm run test:e2e
npm run build
npm run lint
```

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
        +--> game service --> pure truth engine
        +--> SQLite repository
        +--> curated words and answers
```

The database stores `truth_feedback` and `display_feedback` separately. They
are identical in Layer 1. Layer 2 can alter displayed feedback without changing
the truthful evaluation engine or exposing truthful feedback to the browser.

## Daily attempt behavior

- Opening Daily does not consume the attempt.
- Invalid or short guesses do not consume it.
- The first accepted five-letter guess consumes it atomically.
- The open tab can finish the game, but an interrupted Daily is not resumable.
- Returning to the mode screen or refreshing after the first accepted guess
  makes Daily unavailable until the next 03:00 UTC reset.
- Practice remains available after Daily is consumed or completed.

## Source references

- Product decisions: `docs/DECEPTION_PRODUCT_DECISIONS.md`
- Third-party notices: `THIRD_PARTY_NOTICES.md`
- Original teaching prototype: the sibling `wordle-list/` repository, which is
  not modified or used at runtime.
