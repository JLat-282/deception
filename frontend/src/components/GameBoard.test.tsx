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

  it("pairs the entered and decoded letters during Reverse Entry", () => {
    const { container } = render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={[]}
        revealing={false}
        reverseTransition={{
          enteredGuess: "enarc",
          decodedGuess: "crane",
        }}
      />,
    );

    expect(container.querySelectorAll(".tile--reversing")).toHaveLength(5);
    expect(
      container.querySelectorAll(".tile-letter--reverse-from"),
    ).toHaveLength(5);
    expect(container.querySelectorAll(".tile-letter--reverse-to")).toHaveLength(
      5,
    );
    expect(
      screen.getByRole("cell", { name: "C, not submitted" }),
    ).toHaveTextContent("EC");
  });

  it("shows a consumed timer attempt without inventing feedback", () => {
    render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={[
          {
            timedOut: true,
            attempt: 1,
            status: "playing",
            timer: { state: "expired" },
          },
        ]}
        revealing
      />,
    );

    expect(screen.getByText("Time expired")).toBeInTheDocument();
    expect(
      screen.getByRole("cell", { name: "Row 1, time expired" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("cell")).toHaveLength(30);
  });

  it("keeps guessed letters while erasing feedback through a Blackout row", () => {
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
        blackoutCutoffAttempt={1}
      />,
    );

    expect(screen.getByText("S")).toBeInTheDocument();
    expect(
      screen.getByRole("cell", {
        name: "S, previous feedback erased by Blackout",
      }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".tile--blackout")).toHaveLength(5);
    expect(container.querySelector(".tile--g")).not.toBeInTheDocument();
  });
});
