import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ActivatedIntrusion } from "../api/types";

type IntrusionProps = {
  intrusion: ActivatedIntrusion;
  onDismiss: () => void;
};

type ButtonPosition = {
  left: number;
  top: number;
};

export const INTRUSION_RELOCATION_MS = 1_000;

function randomButtonPosition(button: HTMLButtonElement): ButtonPosition {
  const bounds = button.getBoundingClientRect();
  const width = bounds.width || 128;
  const height = bounds.height || 48;
  const padding = 16;
  const minLeft = padding + width / 2;
  const maxLeft = Math.max(minLeft, window.innerWidth - padding - width / 2);
  const minTop = padding + height / 2;
  const maxTop = Math.max(minTop, window.innerHeight - padding - height / 2);

  return {
    left: minLeft + Math.random() * (maxLeft - minLeft),
    top: minTop + Math.random() * (maxTop - minTop),
  };
}

export function Intrusion({ intrusion, onDismiss }: IntrusionProps) {
  const titleId = useId();
  const dismissRef = useRef<HTMLButtonElement>(null);
  const [buttonPosition, setButtonPosition] = useState<ButtonPosition | null>(
    null,
  );

  useEffect(() => {
    const button = dismissRef.current;
    if (!button) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    button.focus();

    const relocate = () => setButtonPosition(randomButtonPosition(button));
    const interval = window.setInterval(relocate, INTRUSION_RELOCATION_MS);
    window.addEventListener("resize", relocate);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("resize", relocate);
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return createPortal(
    <div className="intrusion-shield" data-placement={intrusion.placement}>
      <section
        className="intrusion-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <span className="intrusion-signal" aria-hidden="true">
          SIGNAL INTERRUPTED
        </span>
        <h2 id={titleId}>Intrusion</h2>
        <p>Your view has been compromised.</p>
      </section>
      <button
        ref={dismissRef}
        className="intrusion-dismiss"
        style={
          buttonPosition
            ? { left: buttonPosition.left, top: buttonPosition.top }
            : undefined
        }
        type="button"
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
          }
        }}
        onClick={onDismiss}
      >
        Dismiss
      </button>
    </div>,
    document.body,
  );
}
