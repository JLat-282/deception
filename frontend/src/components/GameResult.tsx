import type {
  DeceptionReveal,
  FeedbackMarker,
  GameMode,
  GameStatus,
} from "../api/types";
import { Dialog } from "./Dialog";

type GameResultProps = {
  mode: GameMode;
  status: Exclude<GameStatus, "playing">;
  answer: string;
  attempt: number;
  deception?: DeceptionReveal;
  onClose: () => void;
  onPractice: () => void;
  onModes: () => void;
};

export function GameResult({
  mode,
  status,
  answer,
  attempt,
  deception,
  onClose,
  onPractice,
  onModes,
}: GameResultProps) {
  const feedbackText: Record<FeedbackMarker, string> = {
    G: "in the correct position",
    Y: "in the word in another position",
    B: "absent",
  };

  let deceptionSummary: string | null = null;
  if (deception?.outcome === "activated") {
    const { change } = deception;
    deceptionSummary = `Row ${deception.scheduledAttempt} lied. ${change.letter.toUpperCase()} was shown as ${feedbackText[change.displayedFeedback]}. It was actually ${feedbackText[change.truthfulFeedback]}.`;
  } else if (deception?.reason === "notReached") {
    deceptionSummary = `The lie was waiting on row ${deception.scheduledAttempt}. You finished before it.`;
  } else if (deception?.reason === "winningGuess") {
    deceptionSummary = `The lie was waiting on row ${deception.scheduledAttempt}. Solving the word kept that row truthful.`;
  } else if (deception?.reason === "finalAttempt") {
    deceptionSummary = "The lie was waiting on row 6. It never activated.";
  } else if (deception?.reason === "noEligibleLie") {
    deceptionSummary = "No lie was activated.";
  }

  return (
    <Dialog
      title={status === "won" ? "Word found." : "The word escaped."}
      closeLabel="Close result"
      className="result-panel"
      onClose={onClose}
    >
      <div className="result-summary">
        <p className="answer-reveal">
          The answer was <strong>{answer.toUpperCase()}</strong>.
        </p>
        {status === "won" ? (
          <p>
            Solved in {attempt} {attempt === 1 ? "guess" : "guesses"}.
          </p>
        ) : null}
        {deceptionSummary ? (
          <section className="deception-result">
            <h3>What happened</h3>
            <p>{deceptionSummary}</p>
          </section>
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
    </Dialog>
  );
}
