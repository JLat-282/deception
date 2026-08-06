import { Dialog } from "./Dialog";

type HowDeceptionWorksProps = {
  onClose: () => void;
  expandAll?: boolean;
};

function DisclosureChevron() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7 9.5 5 5 5-5" />
    </svg>
  );
}

export function HowDeceptionWorks({
  onClose,
  expandAll = false,
}: HowDeceptionWorksProps) {
  return (
    <Dialog
      title="How Deception Works"
      closeLabel="Close How Deception Works"
      className="help-dialog"
      onClose={onClose}
    >
      <div className="guide-disclosures">
        <details className="guide-disclosure" open={expandAll}>
          <summary>
            <span>How it works</span>
            <DisclosureChevron />
          </summary>
          <div className="help-sections">
            <section>
              <h3>What the colors mean</h3>
              <ul className="guide-points">
                <li>
                  <strong>Red:</strong> The letter is in the correct spot.
                </li>
                <li>
                  <strong>Purple:</strong> The letter is in the word but belongs
                  somewhere else.
                </li>
                <li>
                  <strong>Grey:</strong> The letter is not in the word.
                </li>
              </ul>
            </section>
            <section>
              <h3>The lie</h3>
              <ul className="guide-points">
                <li>
                  Some guesses may show the wrong color on one or two tiles.
                  This can happen more than once.
                </li>
                <li>The letters you enter never change or move.</li>
                <li>
                  Example: A tile that should be red might appear purple or
                  grey.
                </li>
                <li>
                  On Deception difficulty, an early correct answer may be marked
                  wrong once. Entering the answer again will win.
                </li>
              </ul>
            </section>
            <section>
              <h3>Game modes</h3>
              <ul className="guide-points">
                <li>
                  <strong>Daily Descent:</strong> Solve four words as the
                  difficulty increases. One loss ends the run.
                </li>
                <li>
                  <strong>Infinite:</strong> Start a new game whenever you want
                  and choose the difficulty.
                </li>
              </ul>
            </section>
            <section>
              <h3>Difficulty levels</h3>
              <ul className="guide-points">
                <li>
                  <strong>Doubt I:</strong> One guess may lie, changing one tile
                  color. Punishments are lighter.
                </li>
                <li>
                  <strong>Doubt II:</strong> One or two guesses may lie,
                  changing one tile color each. More punishments are possible.
                </li>
                <li>
                  <strong>Doubt III:</strong> Two or three guesses may lie. A
                  lie can change two tile colors, and punishments can repeat or
                  happen together.
                </li>
                <li>
                  <strong>Deception:</strong> Three to five guesses may lie. It
                  has the most punishments, and an early correct answer may be
                  marked wrong once.
                </li>
              </ul>
            </section>
            <section>
              <h3>After the game</h3>
              <ul className="guide-points">
                <li>
                  The results reveal every guess chosen for a possible lie. They
                  show which colors changed, which guesses stayed truthful, and
                  which guesses you never reached.
                </li>
              </ul>
            </section>
          </div>
        </details>

        <details className="guide-disclosure" open={expandAll}>
          <summary>
            <span>Possible punishments</span>
            <DisclosureChevron />
          </summary>
          <ul className="punishment-list">
            <li>
              <strong>Reverse Entry</strong>
              <span>
                Type your next word backward. Example: CRANE becomes ENARC.
              </span>
            </li>
            <li>
              <strong>Guess Timer</strong>
              <span>
                You have either 30 or 10 seconds to submit your next guess. If
                time runs out, the game skips that guess.
              </span>
            </li>
            <li>
              <strong>Blackout</strong>
              <span>
                The colors on your previous guesses are erased, and the keyboard
                colors reset.
              </span>
            </li>
            <li>
              <strong>Intrusion</strong>
              <span>
                The game is blocked until you click the moving Dismiss button.
                Timers and other punishments may continue in the background.
              </span>
            </li>
            <li>
              <strong>Blind Entry</strong>
              <span>Your letters stay hidden until you submit the guess.</span>
            </li>
            <li>
              <strong>Corrupted History</strong>
              <span>
                One previous guess is hidden until you submit your next guess.
              </span>
            </li>
            <li>
              <strong>Forced Commitment</strong>
              <span>
                Typing the fifth letter submits the word immediately. An invalid
                word still uses a guess.
              </span>
            </li>
            <li>
              <strong>No Revision</strong>
              <span>
                After typing your first letter, you cannot use Backspace.
              </span>
            </li>
            <li>
              <strong>Memory Tax</strong>
              <span>Only your two most recent guesses stay visible.</span>
            </li>
          </ul>
        </details>
      </div>
    </Dialog>
  );
}
