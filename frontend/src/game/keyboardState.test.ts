import { describe, expect, it } from "vitest";
import type { GuessResponse } from "../api/types";
import { buildKeyboardFeedback } from "./keyboardState";

function result(guess: string, feedback: string): GuessResponse {
  return {
    guess,
    feedback,
    attempt: 1,
    status: "playing",
  };
}

describe("buildKeyboardFeedback", () => {
  it("keeps the strongest known state for each letter", () => {
    const feedback = buildKeyboardFeedback([
      result("eerie", "BBYBG"),
      result("crane", "GGGGG"),
    ]);

    expect(feedback.E).toBe("G");
    expect(feedback.R).toBe("G");
    expect(feedback.I).toBe("B");
  });

  it("does not downgrade a correct letter on a later guess", () => {
    const feedback = buildKeyboardFeedback([
      result("crane", "GGGGG"),
      result("eerie", "BBYBG"),
    ]);

    expect(feedback.E).toBe("G");
  });
});
