import type { ReactNode } from "react";
import type { GameMode } from "../api/types";

type BrandHeaderProps = {
  mode?: GameMode;
  presetName?: string;
  onReturn?: () => void;
  onHelp: () => void;
  helpDisabled?: boolean;
  timer?: ReactNode;
};

function HelpButton({
  onHelp,
  disabled = false,
}: {
  onHelp: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      className="help-button"
      type="button"
      aria-label="Open Deception Guide"
      disabled={disabled}
      title={disabled ? "Unavailable while the timer is running" : undefined}
      onClick={onHelp}
    >
      <span aria-hidden="true">?</span>
    </button>
  );
}

export function BrandHeader({
  mode,
  presetName,
  onReturn,
  onHelp,
  helpDisabled = false,
  timer,
}: BrandHeaderProps) {
  if (!mode) {
    return (
      <header className="brand-header brand-header--select">
        <div className="select-utility">
          <HelpButton onHelp={onHelp} disabled={helpDisabled} />
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
      <div className={`game-brand ${timer ? "game-brand--timer" : ""}`}>
        {timer ?? <h1 className="brand-title">DECEPTION</h1>}
      </div>
      <div className="game-header-actions">
        <p className={`mode-name mode-name--${mode}`}>
          {mode === "daily"
            ? "Daily"
            : presetName
              ? `Practice · ${presetName}`
              : "Practice"}
        </p>
        <HelpButton onHelp={onHelp} disabled={helpDisabled} />
      </div>
    </header>
  );
}
