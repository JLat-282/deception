import { useEffect, useRef } from "react";
import type { DifficultyPresetSummary } from "../api/types";
import { BrandHeader } from "./BrandHeader";

type PracticeDifficultySelectProps = {
  presets: DifficultyPresetSummary[];
  busy: boolean;
  selectedPresetKey: string | null;
  message?: string;
  onBack: () => void;
  onHelp: () => void;
  onSelect: (presetKey: string) => void;
};

export function PracticeDifficultySelect({
  presets,
  busy,
  selectedPresetKey,
  message,
  onBack,
  onHelp,
  onSelect,
}: PracticeDifficultySelectProps) {
  const orderedPresets = [...presets].sort((a, b) => a.rank - b.rank);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <main className="mode-screen difficulty-screen">
      <BrandHeader onHelp={onHelp} helpDisabled={busy} />
      <section
        className="difficulty-selection"
        aria-labelledby="difficulty-heading"
        aria-busy={busy}
      >
        <button
          className="difficulty-back"
          type="button"
          disabled={busy}
          onClick={onBack}
        >
          <span aria-hidden="true">←</span> Back to modes
        </button>
        <div className="difficulty-intro">
          <p className="difficulty-eyebrow">Infinite</p>
          <h2 id="difficulty-heading" ref={headingRef} tabIndex={-1}>
            Choose your doubt
          </h2>
          <p>
            Each step applies more pressure. Choose how far you want to descend.
          </p>
        </div>

        {message ? (
          <p className="mode-message" role="alert">
            {message}
          </p>
        ) : null}

        <div className="difficulty-grid">
          {orderedPresets.map((preset) => {
            const isStarting = busy && selectedPresetKey === preset.presetKey;
            const descriptionId = `preset-${preset.rank}-description`;
            const pressureId = `preset-${preset.rank}-pressure`;
            return (
              <button
                className={`difficulty-card difficulty-card--rank-${preset.rank}`}
                key={preset.presetKey}
                type="button"
                disabled={busy || !preset.available}
                aria-label={
                  preset.available
                    ? `Play Infinite on ${preset.name}`
                    : `${preset.name} unavailable`
                }
                aria-describedby={`${pressureId} ${descriptionId}`}
                onClick={() => onSelect(preset.presetKey)}
              >
                <div className="difficulty-card__heading">
                  <p className="difficulty-card__rank">
                    {String(preset.rank).padStart(2, "0")}
                  </p>
                  <p className="difficulty-card__pressure" id={pressureId}>
                    {preset.pressure}
                  </p>
                </div>
                <h3>{preset.name}</h3>
                <p className="difficulty-card__description" id={descriptionId}>
                  {preset.description}
                </p>
                <span className="difficulty-card__action">
                  {isStarting
                    ? "Preparing…"
                    : preset.available
                      ? "Choose"
                      : "Unavailable"}
                </span>
              </button>
            );
          })}
        </div>
        <p className="visually-hidden" role="status" aria-live="polite">
          {busy && selectedPresetKey
            ? `Preparing ${orderedPresets.find((preset) => preset.presetKey === selectedPresetKey)?.name ?? "Infinite"}`
            : ""}
        </p>
      </section>
    </main>
  );
}
