import type { DailyInfo, GameMode } from "../api/types";
import { BrandHeader } from "./BrandHeader";

type ModeSelectProps = {
  daily: DailyInfo;
  busy: boolean;
  message?: string;
  onStart: (mode: GameMode) => void;
};

export function ModeSelect({ daily, busy, message, onStart }: ModeSelectProps) {
  const dailyUsed = daily.availability === "used";

  return (
    <main className="mode-screen">
      <BrandHeader />

      {message ? (
        <p className="mode-message" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}

      <section className="mode-options" aria-label="Choose a game mode">
        <article className="mode-option mode-option--daily">
          <h2>Daily</h2>
          <div className="mode-divider" aria-hidden="true" />
          {dailyUsed ? (
            <>
              <p className="mode-lead">Today’s attempt has been used.</p>
              <p>
                Practice remains available while you wait for the next puzzle.
              </p>
            </>
          ) : (
            <>
              <p className="mode-lead">One answer. One attempt.</p>
              <p>Your first valid guess starts it. Leaving forfeits it.</p>
            </>
          )}
          <button
            className="mode-button mode-button--primary"
            type="button"
            disabled={busy || dailyUsed}
            onClick={() => onStart("daily")}
          >
            {dailyUsed ? "Daily Used" : "Play Daily"}
          </button>
          <p className="mode-note" title={daily.resetAt}>
            Next puzzle at 03:00 UTC
          </p>
        </article>

        <article className="mode-option mode-option--practice">
          <h2>Practice</h2>
          <div className="mode-divider" aria-hidden="true" />
          <p className="mode-lead">Unlimited games. No lives.</p>
          <p>Each round starts with a fresh word.</p>
          <button
            className="mode-button mode-button--practice"
            type="button"
            disabled={busy}
            onClick={() => onStart("practice")}
          >
            Play Practice
          </button>
          <p className="mode-note">Replay anytime</p>
        </article>
      </section>
    </main>
  );
}
