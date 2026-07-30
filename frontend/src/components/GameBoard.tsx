import type { FeedbackMarker, GuessResponse } from "../api/types";

const STATE_LABEL: Record<FeedbackMarker, string> = {
  G: "correct position",
  Y: "present elsewhere",
  B: "absent",
};

type GameBoardProps = {
  wordLength: number;
  maxGuesses: number;
  currentGuess: string;
  guesses: GuessResponse[];
  revealing: boolean;
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
          const isCurrentRow = row.index === guesses.length;
          const isReversingRow = isCurrentRow && reverseTransition !== null;
          const letters =
            result?.guess ??
            (isReversingRow
              ? reverseTransition.decodedGuess
              : isCurrentRow
                ? currentGuess
                : "");
          const isRevealingRow = revealing && row.index === guesses.length - 1;

          return (
            <tr className="board-row" key={row.key}>
              {columns.map((column) => {
                const letter = letters[column.index]?.toUpperCase() ?? "";
                const enteredLetter = isReversingRow
                  ? (reverseTransition.enteredGuess[column.index]?.toUpperCase() ??
                    "")
                  : "";
                const marker = result?.feedback[column.index] as
                  | FeedbackMarker
                  | undefined;
                const stateClass = marker
                  ? `tile--${marker.toLowerCase()}`
                  : "";
                const label = marker
                  ? `${letter}, ${STATE_LABEL[marker]}`
                  : letter
                    ? `${letter}, not submitted`
                    : `Row ${row.index + 1}, position ${column.index + 1}, empty`;

                return (
                  <td
                    className={`tile ${letter ? "tile--filled" : ""} ${stateClass} ${
                      isRevealingRow ? "tile--revealing" : ""
                    } ${isReversingRow ? "tile--reversing" : ""} ${
                      isReversingRow && column.index === 2
                        ? "tile--reverse-center"
                        : ""
                    }`}
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
                    {isReversingRow ? (
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
