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
  });

  it("closes with Escape", () => {
    render(
      <GameResult
        mode="practice"
        status="won"
        answer="crane"
        attempt={2}
        onPractice={vi.fn()}
        onModes={vi.fn()}
      />,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
