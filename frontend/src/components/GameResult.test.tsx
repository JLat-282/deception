import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GameResult } from "./GameResult";

describe("GameResult", () => {
  it("offers Practice rather than replaying a finished Daily", () => {
    render(
      <GameResult
        mode="daily"
        status="lost"
        answer="butch"
        attempt={6}
        deception={{
          outcome: "notActivated",
          scheduledAttempt: 6,
          reason: "finalAttempt",
        }}
        onClose={vi.fn()}
        onPractice={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Play Practice" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Play Again" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Six guesses used.")).not.toBeInTheDocument();
    expect(
      screen.getByText("The lie was waiting on row 6. It never activated."),
    ).toBeInTheDocument();
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
        onPractice={vi.fn()}
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
          outcome: "activated",
          scheduledAttempt: 1,
          change: {
            tileIndex: 3,
            letter: "t",
            truthfulFeedback: "B",
            displayedFeedback: "Y",
          },
        }}
        onClose={vi.fn()}
        onPractice={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    expect(
      screen.getByText(
        /Row 1 lied\. T was shown as in the word in another position\./,
      ),
    ).toBeInTheDocument();
  });
});
