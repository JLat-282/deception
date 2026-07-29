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
            One row is chosen in secret. If you reach it, one tile may show the
            wrong color.
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
          <h3>After the game</h3>
          <p>
            We reveal the row and tile that lied. If you finished before the
            selected row, we tell you where it was waiting.
          </p>
        </section>
      </div>
    </Dialog>
  );
}
