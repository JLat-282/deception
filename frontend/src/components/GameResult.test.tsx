import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GameResult } from "./GameResult";

describe("GameResult", () => {
  it("offers Infinite rather than replaying a failed Daily Descent", () => {
    render(
      <GameResult
        mode="daily"
        status="lost"
        answer="butch"
        attempt={6}
        deception={{
          events: [
            {
              outcome: "notActivated",
              scheduledAttempt: 6,
              reason: "finalAttempt",
            },
          ],
        }}
        onClose={vi.fn()}
        onInfinite={vi.fn()}
        onDescend={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Play Infinite" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Play Again" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Six guesses used.")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Row 6 was selected, but the final guess always stays truthful.",
      ),
    ).toBeInTheDocument();
  });

  it("continues a won Daily stage into the next descent checkpoint", () => {
    const onDescend = vi.fn();
    render(
      <GameResult
        mode="daily"
        status="won"
        answer="crane"
        attempt={3}
        dailyStage={2}
        onClose={vi.fn()}
        onInfinite={vi.fn()}
        onDescend={onDescend}
        onModes={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Descend to Doubt III" }),
    );
    expect(onDescend).toHaveBeenCalledOnce();
  });

  it("closes with Escape", () => {
    const onClose = vi.fn();
    render(
      <GameResult
        mode="practice"
        status="won"
        answer="crane"
        attempt={2}
        onClose={onClose}
        onInfinite={vi.fn()}
        onDescend={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("reveals the exact activated tile in plain language", () => {
    render(
      <GameResult
        mode="practice"
        status="won"
        answer="crane"
        attempt={2}
        deception={{
          events: [
            {
              outcome: "activated",
              kind: "feedbackLie",
              scheduledAttempt: 1,
              changes: [
                {
                  tileIndex: 3,
                  letter: "t",
                  truthfulFeedback: "B",
                  displayedFeedback: "Y",
                },
              ],
            },
            {
              outcome: "notActivated",
              scheduledAttempt: 4,
              reason: "notReached",
            },
          ],
        }}
        onClose={vi.fn()}
        onInfinite={vi.fn()}
        onDescend={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        /Row 1 lied on one tile\. T was shown as in the word in another position/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Row 4 was selected, but you finished before reaching it.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Punishments" }),
    ).not.toBeInTheDocument();
  });

  it("reveals when Deception rejected an earlier correct answer", () => {
    render(
      <GameResult
        mode="practice"
        status="won"
        answer="crane"
        attempt={3}
        deception={{
          events: [
            {
              outcome: "activated",
              kind: "falseVictory",
              scheduledAttempt: 2,
              changes: [
                {
                  tileIndex: 1,
                  letter: "r",
                  truthfulFeedback: "G",
                  displayedFeedback: "B",
                },
              ],
            },
          ],
        }}
        onClose={vi.fn()}
        onInfinite={vi.fn()}
        onDescend={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    expect(
      screen.getByText("Row 2 was the answer, but Deception rejected it."),
    ).toBeInTheDocument();
  });
});
