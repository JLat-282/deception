import { afterEach, describe, expect, it, vi } from "vitest";
import { MINIMUM_REVEAL_START_MS, waitForRevealStart } from "./revealTiming";

afterEach(() => {
  vi.useRealTimers();
});

describe("reveal timing", () => {
  it("holds accepted feedback until the 100ms reveal window", async () => {
    vi.useFakeTimers();
    let finished = false;
    const wait = waitForRevealStart().then(() => {
      finished = true;
    });

    await vi.advanceTimersByTimeAsync(MINIMUM_REVEAL_START_MS - 1);
    expect(finished).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    await wait;
    expect(finished).toBe(true);
  });
});
