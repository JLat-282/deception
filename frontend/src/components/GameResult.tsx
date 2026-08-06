import type {
  DeceptionEvent,
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
  dailyStage?: number;
  onClose: () => void;
  onInfinite: () => void;
  onDescend: () => void;
  onModes: () => void;
};

export function GameResult({
  mode,
  status,
  answer,
  attempt,
  deception,
  dailyStage,
  onClose,
  onInfinite,
  onDescend,
  onModes,
}: GameResultProps) {
  const feedbackText: Record<FeedbackMarker, string> = {
    G: "in the correct position",
    Y: "in the word in another position",
    B: "absent",
  };

  const deceptionSummary = (event: DeceptionEvent): string => {
    if (event.outcome === "activated") {
      if (event.kind === "falseVictory") {
        return `Row ${event.scheduledAttempt} was the answer, but Deception rejected it.`;
      }
      const details = event.changes
        .map(
          (change) =>
            `${change.letter.toUpperCase()} was shown as ${feedbackText[change.displayedFeedback]} but was actually ${feedbackText[change.truthfulFeedback]}`,
        )
        .join("; ");
      return `Row ${event.scheduledAttempt} lied on ${event.changes.length === 1 ? "one tile" : "two tiles"}. ${details}.`;
    }
    if (event.reason === "notReached") {
      return `Row ${event.scheduledAttempt} was selected, but you finished before reaching it.`;
    }
    if (event.reason === "winningGuess") {
      return `Row ${event.scheduledAttempt} was selected, but a winning guess always stays truthful.`;
    }
    if (event.reason === "finalAttempt") {
      return `Row ${event.scheduledAttempt} was selected, but the final guess always stays truthful.`;
    }
    return `Row ${event.scheduledAttempt} was selected, but its feedback stayed truthful.`;
  };

  const canDescend =
    mode === "daily" && status === "won" && !!dailyStage && dailyStage < 4;
  const nextStageLabel =
    dailyStage === 1
      ? "Descend to Doubt II"
      : dailyStage === 2
        ? "Descend to Doubt III"
        : "Enter Deception";

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
        {deception ? (
          <section className="deception-result">
            <h3>What happened</h3>
            <ol>
              {deception.events.map((event) => (
                <li key={event.scheduledAttempt}>{deceptionSummary(event)}</li>
              ))}
            </ol>
          </section>
        ) : null}
      </div>
      <div className="result-actions">
        <button
          className="mode-button mode-button--primary"
          type="button"
          onClick={canDescend ? onDescend : onInfinite}
        >
          {canDescend
            ? nextStageLabel
            : mode === "daily"
              ? "Play Infinite"
              : "Play Again"}
        </button>
        <button className="text-button" type="button" onClick={onModes}>
          Return to modes
        </button>
      </div>
    </Dialog>
  );
}
