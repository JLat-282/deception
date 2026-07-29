import type { GameMode } from "../api/types";

type BrandHeaderProps = {
  mode?: GameMode;
  onReturn?: () => void;
  onHelp: () => void;
};

function HelpButton({ onHelp }: { onHelp: () => void }) {
  return (
    <button
      className="help-button"
      type="button"
      aria-label="How Deception Works"
      onClick={onHelp}
    >
      <span aria-hidden="true">?</span>
    </button>
  );
}

export function BrandHeader({ mode, onReturn, onHelp }: BrandHeaderProps) {
  if (!mode) {
    return (
      <header className="brand-header brand-header--select">
        <div className="select-utility">
          <HelpButton onHelp={onHelp} />
        </div>
        <h1 className="brand-title">DECEPTION</h1>
        <div className="brand-rule" aria-hidden="true" />
        <p className="brand-tagline">Choose your words carefully.</p>
      </header>
    );
  }

  return (
    <header className="brand-header brand-header--game">
      <button className="return-button" type="button" onClick={onReturn}>
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
          <path d="M15 5 8 12l7 7" />
        </svg>
        Return to modes
      </button>
      <div className="game-brand">
        <h1 className="brand-title">DECEPTION</h1>
      </div>
      <div className="game-header-actions">
        <p className={`mode-name mode-name--${mode}`}>
          {mode === "daily" ? "Daily" : "Practice"}
        </p>
        <HelpButton onHelp={onHelp} />
      </div>
    </header>
  );
}
