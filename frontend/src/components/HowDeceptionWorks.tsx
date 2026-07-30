import { Dialog } from "./Dialog";

type HowDeceptionWorksProps = {
  onClose: () => void;
};

export function HowDeceptionWorks({ onClose }: HowDeceptionWorksProps) {
  return (
    <Dialog
      title="How Deception Works"
      closeLabel="Close How Deception Works"
      className="help-dialog"
      onClose={onClose}
    >
      <div className="help-sections">
        <section>
          <h3>The rule</h3>
          <p>
            Rows are selected in secret. If a row lies, only one tile in that
            row can show the wrong color. Feedback may lie more than once.
          </p>
        </section>
        <section>
          <h3>What can lie</h3>
          <p>
            Only feedback can lie. Letters never change or move. A lie can hide
            a real clue or create a convincing false one. A winning guess is
            always truthful.
          </p>
        </section>
        <section>
          <h3>Modes</h3>
          <p>
            Daily: one shared word, one attempt. Practice: a fresh word every
            game, replay anytime. Deception works the same in both.
          </p>
        </section>
        <section>
          <h3>Reverse Entry</h3>
          <p>
            A guess showing four or five absent letters triggers Reverse Entry.
            Other accepted guesses have a small chance to trigger it. Enter the
            next word backwards; once accepted, the row turns itself around
            before its feedback appears.
          </p>
        </section>
        <section>
          <h3>After the game</h3>
          <p>
            Every selected row is revealed after the game, including rows that
            stayed truthful or were never reached.
          </p>
        </section>
      </div>
    </Dialog>
  );
}
