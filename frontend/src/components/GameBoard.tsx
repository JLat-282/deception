import type { AttemptResponse, FeedbackMarker } from "../api/types";
import { isInvalidCommitment, isTimedOut } from "../api/types";

const STATE_LABEL: Record<FeedbackMarker, string> = {
  G: "correct position",
  Y: "present elsewhere",
  B: "absent",
};

type GameBoardProps = {
  wordLength: number;
  maxGuesses: number;
  currentGuess: string;
  guesses: AttemptResponse[];
  revealing: boolean;
  blackoutCutoffAttempt?: number | null;
  corruptedRowAttempt?: number | null;
  memoryTaxRetainRows?: number | null;
  blindCurrentEntry?: boolean;
  forcedCommitmentActive?: boolean;
  reverseTransition?: {
    enteredGuess: string;
    decodedGuess: string;
  } | null;
};

export function GameBoard({
  wordLength,
  maxGuesses,
  currentGuess,
  guesses,
  revealing,
  blackoutCutoffAttempt = null,
  corruptedRowAttempt = null,
  memoryTaxRetainRows = null,
  blindCurrentEntry = false,
  forcedCommitmentActive = false,
  reverseTransition = null,
}: GameBoardProps) {
  const rows = Array.from({ length: maxGuesses }, (_, index) => ({
    index,
    key: `row-${index + 1}`,
  }));
  const columns = Array.from({ length: wordLength }, (_, index) => ({
    index,
    key: `column-${index + 1}`,
  }));

  return (
    <table
      className="game-board"
      aria-label={`${maxGuesses} guesses of ${wordLength} letters`}
      style={{ "--word-length": wordLength } as React.CSSProperties}
    >
      <tbody>
        {rows.map((row) => {
          const result = guesses[row.index];
          const timedOutResult = result && isTimedOut(result) ? result : null;
          const invalidResult =
            result && isInvalidCommitment(result) ? result : null;
          const guessResult =
            result && !isTimedOut(result) && !isInvalidCommitment(result)
              ? result
              : null;
          const timedOut = timedOutResult !== null;
          const invalidCommitment = invalidResult !== null;
          const attemptNumber = result?.attempt ?? row.index + 1;
          const isMemoryHidden =
            result !== undefined &&
            memoryTaxRetainRows !== null &&
            attemptNumber <= guesses.length - memoryTaxRetainRows;
          const isCorrupted =
            result !== undefined && attemptNumber === corruptedRowAttempt;
          const isBlackedOut =
            guessResult !== null &&
            blackoutCutoffAttempt !== null &&
            guessResult.attempt <= blackoutCutoffAttempt;
          const isCurrentRow = row.index === guesses.length;
          const isReversingRow = isCurrentRow && reverseTransition !== null;
          const letters =
            guessResult?.guess ??
            (invalidResult
              ? invalidResult.attemptedGuess
              : isReversingRow
                ? reverseTransition.decodedGuess
                : isCurrentRow
                  ? currentGuess
                  : "");
          const isRevealingRow =
            revealing && row.index === guesses.length - 1 && !timedOut;

          return (
            <tr
              className={`board-row ${timedOut ? "board-row--timed-out" : ""}`}
              key={row.key}
            >
              {columns.map((column) => {
                const actualLetter = letters[column.index]?.toUpperCase() ?? "";
                const concealCurrent = isCurrentRow && blindCurrentEntry;
                const concealHistory = isMemoryHidden || isCorrupted;
                const letter =
                  concealCurrent || concealHistory ? "" : actualLetter;
                const enteredLetter = isReversingRow
                  ? (reverseTransition.enteredGuess[
                      column.index
                    ]?.toUpperCase() ?? "")
                  : "";
                const marker =
                  guessResult && !isBlackedOut && !concealHistory
                    ? (guessResult.feedback[column.index] as
                        | FeedbackMarker
                        | undefined)
                    : undefined;
                const stateClass = marker
                  ? `tile--${marker.toLowerCase()}`
                  : "";
                const label = timedOut
                  ? column.index === 0
                    ? `Row ${row.index + 1}, time expired`
                    : `Row ${row.index + 1}, position ${column.index + 1}, consumed by timer`
                  : invalidCommitment
                    ? column.index === 0
                      ? `Row ${row.index + 1}, guess rejected and consumed`
                      : `Row ${row.index + 1}, no feedback`
                    : isMemoryHidden
                      ? `Row ${row.index + 1}, hidden by Memory Tax`
                      : isCorrupted
                        ? `Row ${row.index + 1}, history corrupted`
                        : isBlackedOut
                          ? `${letter}, previous feedback erased by Blackout`
                          : marker
                            ? `${letter}, ${STATE_LABEL[marker]}`
                            : actualLetter
                              ? concealCurrent
                                ? `Position ${column.index + 1}, letter hidden during Blind Entry`
                                : `${actualLetter}, not submitted`
                              : `Row ${row.index + 1}, position ${column.index + 1}, empty`;

                return (
                  <td
                    className={`tile ${actualLetter ? "tile--filled" : ""} ${stateClass} ${
                      isRevealingRow ? "tile--revealing" : ""
                    } ${isReversingRow ? "tile--reversing" : ""} ${
                      isReversingRow && column.index === 2
                        ? "tile--reverse-center"
                        : ""
                    } ${timedOut ? "tile--timed-out" : ""} ${
                      isBlackedOut ? "tile--blackout" : ""
                    } ${isCorrupted ? "tile--corrupted" : ""} ${
                      isMemoryHidden ? "tile--memory-tax" : ""
                    } ${concealCurrent && actualLetter ? "tile--blind-entry" : ""} ${
                      isCurrentRow && forcedCommitmentActive
                        ? "tile--forced-commitment"
                        : ""
                    } ${invalidCommitment ? "tile--invalid-commitment" : ""}`}
                    aria-label={label}
                    key={column.key}
                    style={
                      {
                        "--reveal-index": column.index,
                        "--reverse-delay":
                          column.index === 0 || column.index === 4
                            ? "0ms"
                            : column.index === 1 || column.index === 3
                              ? "40ms"
                              : "80ms",
                      } as React.CSSProperties
                    }
                  >
                    {timedOut && column.index === 0 ? (
                      <span className="timeout-row-label">Time expired</span>
                    ) : invalidCommitment && column.index === 0 ? (
                      <span className="timeout-row-label">Guess rejected</span>
                    ) : isReversingRow ? (
                      <>
                        <span className="tile-letter tile-letter--reverse-from">
                          {enteredLetter}
                        </span>
                        <span className="tile-letter tile-letter--reverse-to">
                          {letter}
                        </span>
                      </>
                    ) : (
                      <span className="tile-letter">{letter}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
