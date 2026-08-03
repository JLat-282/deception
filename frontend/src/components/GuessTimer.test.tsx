import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GuessTimer } from "./GuessTimer";

afterEach(() => {
  vi.useRealTimers();
});

describe("GuessTimer", () => {
  it("counts down and expires exactly once", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-28T12:00:00Z"));
    const onExpire = vi.fn();

    render(
      <GuessTimer
        timer={{
          state: "activated",
          durationSeconds: 10,
          startsAt: "2026-07-28T12:00:00Z",
          deadlineAt: "2026-07-28T12:00:10Z",
        }}
        enabled
        onExpire={onExpire}
      />,
    );

    expect(screen.getByText("0:10")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(10_100));
    expect(screen.getByText("0:00")).toBeInTheDocument();
    expect(onExpire).toHaveBeenCalledOnce();
    act(() => vi.advanceTimersByTime(1_000));
    expect(onExpire).toHaveBeenCalledOnce();
  });

  it("waits for game input to become available before expiring", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-28T12:00:00Z"));
    const onExpire = vi.fn();
    const timer = {
      state: "activated" as const,
      durationSeconds: 10 as const,
      startsAt: "2026-07-28T12:00:00Z",
      deadlineAt: "2026-07-28T12:00:10Z",
    };

    const { rerender } = render(
      <GuessTimer timer={timer} enabled={false} onExpire={onExpire} />,
    );
    act(() => vi.advanceTimersByTime(10_100));
    expect(onExpire).not.toHaveBeenCalled();

    rerender(<GuessTimer timer={timer} enabled onExpire={onExpire} />);
    expect(onExpire).toHaveBeenCalledOnce();
  });
});
