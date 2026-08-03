import { useEffect, useMemo, useRef, useState } from "react";
import type { ActivatedGuessTimer } from "../api/types";

type GuessTimerProps = {
  timer: ActivatedGuessTimer;
  enabled: boolean;
  onExpire: () => void;
};

function remainingMilliseconds(timer: ActivatedGuessTimer): number {
  const startsAt = Date.parse(timer.startsAt);
  const deadlineAt = Date.parse(timer.deadlineAt);
  const now = Date.now();
  if (now < startsAt) return timer.durationSeconds * 1_000;
  return Math.max(0, deadlineAt - now);
}

export function GuessTimer({ timer, enabled, onExpire }: GuessTimerProps) {
  const [remainingMs, setRemainingMs] = useState(() =>
    remainingMilliseconds(timer),
  );
  const [announcement, setAnnouncement] = useState(
    `Timer activated. You have ${timer.durationSeconds} seconds.`,
  );
  const expired = useRef(false);
  const announcedSecond = useRef<number | null>(null);

  useEffect(() => {
    expired.current = false;
    announcedSecond.current = null;
    setRemainingMs(remainingMilliseconds(timer));
    setAnnouncement(
      `Timer activated. You have ${timer.durationSeconds} seconds.`,
    );

    const update = () => {
      const nextRemaining = remainingMilliseconds(timer);
      const nextSeconds = Math.ceil(nextRemaining / 1_000);
      setRemainingMs(nextRemaining);

      if (
        [10, 5, 3, 2, 1].includes(nextSeconds) &&
        announcedSecond.current !== nextSeconds
      ) {
        announcedSecond.current = nextSeconds;
        setAnnouncement(
          `${nextSeconds} second${nextSeconds === 1 ? "" : "s"} remaining.`,
        );
      }
      if (nextRemaining === 0 && enabled && !expired.current) {
        expired.current = true;
        setAnnouncement("Time expired.");
        onExpire();
      }
    };

    update();
    const interval = window.setInterval(update, 100);
    return () => window.clearInterval(interval);
  }, [enabled, onExpire, timer]);

  const seconds = Math.ceil(remainingMs / 1_000);
  const urgent = seconds <= 10;
  const progress = useMemo(
    () =>
      Math.max(
        0,
        Math.min(100, (remainingMs / (timer.durationSeconds * 1_000)) * 100),
      ),
    [remainingMs, timer.durationSeconds],
  );

  return (
    <aside
      className={`guess-timer ${urgent ? "guess-timer--urgent" : ""}`}
      aria-label={`Guess timer, ${seconds} seconds remaining`}
    >
      <span className="guess-timer-label">Time limit</span>
      <strong className="guess-timer-value" aria-hidden="true">
        0:{String(seconds).padStart(2, "0")}
      </strong>
      <div
        className="guess-timer-track"
        role="progressbar"
        aria-label="Time remaining"
        aria-valuemin={0}
        aria-valuemax={timer.durationSeconds}
        aria-valuenow={seconds}
      >
        <span style={{ width: `${progress}%` }} />
      </div>
      <p className="visually-hidden" role="status" aria-live="assertive">
        {announcement}
      </p>
    </aside>
  );
}
