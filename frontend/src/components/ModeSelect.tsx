import type { Ref } from "react";
import type { DailyInfo, GameMode } from "../api/types";
import { BrandHeader } from "./BrandHeader";

type ModeSelectProps = {
  daily: DailyInfo;
  busy: boolean;
  message?: string;
  onStart: (mode: GameMode) => void;
  onInfinite: () => void;
  onHelp: () => void;
  infiniteButtonRef?: Ref<HTMLButtonElement>;
};

export function ModeSelect({
  daily,
  busy,
  message,
  onStart,
  onInfinite,
  onHelp,
  infiniteButtonRef,
}: ModeSelectProps) {
  const dailyEnded = ["failed", "forfeited", "completed", "expired"].includes(
    daily.status,
  );
  const stageNames = ["Doubt I", "Doubt II", "Doubt III", "Deception"];
  const nextAction =
    daily.currentStage === 4
      ? "Enter Deception"
      : `Descend to ${stageNames[daily.currentStage - 1]}`;
  const dailyAction =
    daily.status === "checkpoint" ? nextAction : "Begin Descent";

  return (
    <main className="mode-screen">
      <BrandHeader onHelp={onHelp} />

      {message ? (
        <p className="mode-message" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}

      <section className="mode-options" aria-label="Choose a game mode">
        <article className="mode-option mode-option--daily">
          <h2>Daily Descent</h2>
          <div className="mode-divider" aria-hidden="true" />
          {daily.status === "completed" ? (
            <>
              <p className="mode-lead">You survived the full descent.</p>
              <p>A new run begins after the daily reset.</p>
            </>
          ) : dailyEnded ? (
            <>
              <p className="mode-lead">Today’s descent has ended.</p>
              <p>Infinite remains open while you wait for another run.</p>
            </>
          ) : daily.status === "checkpoint" ? (
            <>
              <p className="mode-lead">
                {daily.clearedStages} of 4 stages cleared.
              </p>
              <p>
                Your next stage is waiting. It starts with your first valid
                guess.
              </p>
            </>
          ) : (
            <>
              <p className="mode-lead">Four stages. One uninterrupted run.</p>
              <p>
                Begin at Doubt I. Clear every word; one loss ends the descent.
              </p>
            </>
          )}
          <ol className="descent-path" aria-label="Daily Descent stages">
            {stageNames.map((name, index) => {
              const stage = index + 1;
              const state =
                stage <= daily.clearedStages
                  ? "cleared"
                  : stage === daily.currentStage && !dailyEnded
                    ? "current"
                    : "locked";
              return (
                <li
                  className={`descent-path__stage descent-path__stage--${state}`}
                  key={name}
                >
                  <span aria-hidden="true">{stage}</span>
                  <small>{name}</small>
                </li>
              );
            })}
          </ol>
          <button
            className="mode-button mode-button--primary"
            type="button"
            disabled={busy || dailyEnded}
            onClick={() => onStart("daily")}
          >
            {dailyEnded
              ? daily.status === "completed"
                ? "Descent Complete"
                : "Descent Ended"
              : dailyAction}
          </button>
          <p className="mode-note" title={daily.resetAt}>
            Next puzzle at 03:00 UTC
          </p>
        </article>

        <article className="mode-option mode-option--practice">
          <h2>Infinite</h2>
          <div className="mode-divider" aria-hidden="true" />
          <p className="mode-lead">Fresh words. Unlimited runs.</p>
          <p>Choose any difficulty and replay without waiting.</p>
          <button
            className="mode-button mode-button--practice"
            ref={infiniteButtonRef}
            type="button"
            disabled={busy}
            onClick={onInfinite}
          >
            Play Infinite
          </button>
          <p className="mode-note">Replay anytime</p>
        </article>
      </section>
    </main>
  );
}
