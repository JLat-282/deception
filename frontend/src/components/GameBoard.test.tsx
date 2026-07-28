import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GameBoard } from "./GameBoard";

describe("GameBoard", () => {
  it("renders the full empty six by five grid", () => {
    render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={[]}
        revealing={false}
      />,
    );

    const board = screen.getByRole("table");
    expect(within(board).getAllByRole("row")).toHaveLength(6);
    expect(within(board).getAllByRole("cell")).toHaveLength(30);
  });

  it("keeps semantic labels without overlaying symbols on revealed tiles", () => {
    const { container } = render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={[
          {
            guess: "slate",
            feedback: "BBGBG",
            attempt: 1,
            status: "playing",
          },
        ]}
        revealing={false}
      />,
    );

    expect(
      screen.getByRole("cell", { name: "A, correct position" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "S, absent" })).toBeInTheDocument();
    expect(container.querySelector(".tile-marker")).not.toBeInTheDocument();
  });
});
