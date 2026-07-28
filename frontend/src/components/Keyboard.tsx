import type { FeedbackMarker } from "../api/types";
import type { KeyboardFeedback } from "../game/keyboardState";

const KEYBOARD_ROWS = [
  ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
  ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
  ["Z", "X", "C", "V", "B", "N", "M"],
];

const STATE_LABEL: Record<FeedbackMarker, string> = {
  G: "correct position",
  Y: "present elsewhere",
  B: "absent",
};

type KeyboardProps = {
  feedback: KeyboardFeedback;
  disabled: boolean;
  onLetter: (letter: string) => void;
  onEnter: () => void;
  onBackspace: () => void;
};

function LetterKey({
  letter,
  marker,
  disabled,
  onLetter,
}: {
  letter: string;
  marker?: FeedbackMarker;
  disabled: boolean;
  onLetter: (letter: string) => void;
}) {
  const stateClass = marker ? `key--${marker.toLowerCase()}` : "";
  const stateLabel = marker ? `, ${STATE_LABEL[marker]}` : "";
  return (
    <button
      className={`key ${stateClass}`}
      type="button"
      aria-label={`${letter}${stateLabel}`}
      disabled={disabled}
      onClick={() => onLetter(letter)}
    >
      {letter}
    </button>
  );
}

export function Keyboard({
  feedback,
  disabled,
  onLetter,
  onEnter,
  onBackspace,
}: KeyboardProps) {
  return (
    <fieldset className="keyboard" aria-label="On-screen keyboard">
      <div className="keyboard-row">
        {KEYBOARD_ROWS[0].map((letter) => (
          <LetterKey
            key={letter}
            letter={letter}
            marker={feedback[letter]}
            disabled={disabled}
            onLetter={onLetter}
          />
        ))}
      </div>
      <div className="keyboard-row keyboard-row--middle">
        {KEYBOARD_ROWS[1].map((letter) => (
          <LetterKey
            key={letter}
            letter={letter}
            marker={feedback[letter]}
            disabled={disabled}
            onLetter={onLetter}
          />
        ))}
      </div>
      <div className="keyboard-row">
        <button
          className="key key--wide"
          type="button"
          disabled={disabled}
          onClick={onEnter}
        >
          Enter
        </button>
        {KEYBOARD_ROWS[2].map((letter) => (
          <LetterKey
            key={letter}
            letter={letter}
            marker={feedback[letter]}
            disabled={disabled}
            onLetter={onLetter}
          />
        ))}
        <button
          className="key key--wide"
          type="button"
          aria-label="Backspace"
          disabled={disabled}
          onClick={onBackspace}
        >
          <svg aria-hidden="true" viewBox="0 0 32 24" width="28" height="22">
            <path d="M12 3h16v18H12L3 12l9-9Z" />
            <path d="m17 8 6 8m0-8-6 8" />
          </svg>
        </button>
      </div>
    </fieldset>
  );
}
