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
      title="Deception Guide"
      closeLabel="Close Deception Guide"
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
              <h3>The rule</h3>
              <p>
                Rows are selected in secret. If a row lies, only one tile in
                that row can show the wrong color. Feedback may lie more than
                once.
              </p>
            </section>
            <section>
              <h3>What can lie</h3>
              <p>
                Only feedback can lie. Letters never change or move. A lie can
                hide a real clue or create a convincing false one. A winning
                guess is always truthful.
              </p>
            </section>
            <section>
              <h3>Modes</h3>
              <p>
                Daily: one shared word, one attempt. Practice: a fresh word
                every game, replay anytime. Deception works the same in both.
              </p>
            </section>
            <section>
              <h3>After the game</h3>
              <p>
                Every selected row is revealed after the game, including rows
                that stayed truthful or were never reached.
              </p>
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
              <span>Type your next guess backwards.</span>
            </li>
            <li>
              <strong>Guess Timer</strong>
              <span>Submit your next guess before time runs out.</span>
            </li>
            <li>
              <strong>Blackout</strong>
              <span>
                Earlier feedback disappears, and the keyboard starts over.
              </span>
            </li>
          </ul>
        </details>
      </div>
    </Dialog>
  );
}
