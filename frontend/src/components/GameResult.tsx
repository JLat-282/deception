import { useEffect, useRef, useState } from "react";
import type { GameMode, GameStatus } from "../api/types";

type GameResultProps = {
  mode: GameMode;
  status: Exclude<GameStatus, "playing">;
  answer: string;
  attempt: number;
  onPractice: () => void;
  onModes: () => void;
};

export function GameResult({
  mode,
  status,
  answer,
  attempt,
  onPractice,
  onModes,
}: GameResultProps) {
  const [open, setOpen] = useState(true);
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = Array.from(
        panelRef.current?.querySelectorAll<HTMLButtonElement>(
          "button:not(:disabled)",
        ) ?? [],
      );
      const first = focusable.at(0);
      const last = focusable.at(-1);
      if (!first || !last) return;

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="result-overlay">
      <section
        ref={panelRef}
        className="result-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="result-heading"
        aria-describedby="result-summary"
      >
        <button
          ref={closeButtonRef}
          className="result-close"
          type="button"
          aria-label="Close result"
          onClick={() => setOpen(false)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 5l14 14M19 5L5 19" />
          </svg>
        </button>
        <h2 id="result-heading">
          {status === "won" ? "Word found." : "The word escaped."}
        </h2>
        <div id="result-summary">
          <p className="answer-reveal">
            The answer was <strong>{answer.toUpperCase()}</strong>.
          </p>
          {status === "won" ? (
            <p>
              Solved in {attempt} {attempt === 1 ? "guess" : "guesses"}.
            </p>
          ) : null}
        </div>
        <div className="result-actions">
          <button
            className="mode-button mode-button--primary"
            type="button"
            onClick={onPractice}
          >
            {mode === "daily" ? "Play Practice" : "Play Again"}
          </button>
          <button className="text-button" type="button" onClick={onModes}>
            Return to modes
          </button>
        </div>
      </section>
    </div>
  );
}
