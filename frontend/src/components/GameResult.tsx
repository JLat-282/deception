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
  return (
    <section
      className="result-panel"
      aria-labelledby="result-heading"
      aria-live="polite"
    >
      <h2 id="result-heading">
        {status === "won" ? "Word found." : "The word escaped."}
      </h2>
      <p className="answer-reveal">
        The answer was <strong>{answer.toUpperCase()}</strong>.
      </p>
      <p>
        {status === "won"
          ? `Solved in ${attempt} ${attempt === 1 ? "guess" : "guesses"}.`
          : "Six guesses used."}
      </p>
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
  );
}
