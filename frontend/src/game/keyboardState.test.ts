import { describe, expect, it } from "vitest";
import type { GuessResponse } from "../api/types";
import { buildKeyboardFeedback } from "./keyboardState";

function result(guess: string, feedback: string, attempt = 1): GuessResponse {
  return {
    guess,
    feedback,
    attempt,
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

  it("rebuilds keyboard knowledge only from guesses after Blackout", () => {
    const feedback = buildKeyboardFeedback(
      [
        result("crane", "GGGGG", 1),
        result("fight", "BBBBB", 2),
        result("eerie", "BBYBG", 3),
      ],
      2,
    );

    expect(feedback.C).toBeUndefined();
    expect(feedback.F).toBeUndefined();
    expect(feedback.E).toBe("G");
  });
});
