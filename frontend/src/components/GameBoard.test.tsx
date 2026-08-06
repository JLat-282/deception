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

  it("renders every attempted letter uniformly after Forced Commitment rejects a guess", () => {
    render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={[
          {
            consumed: true,
            reason: "invalidCommitment",
            attemptedGuess: "cranz",
            attempt: 1,
            status: "playing",
          },
        ]}
        revealing={false}
      />,
    );

    const rejectedRow = screen.getAllByRole("row")[0];
    expect(rejectedRow.querySelectorAll(".tile-letter")).toHaveLength(5);
    expect(
      screen.getByRole("cell", {
        name: "Row 1, guess rejected and consumed",
      }),
    ).toHaveTextContent("C");
    expect(screen.queryByText("Guess rejected")).not.toBeInTheDocument();
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

  it("conceals a complete Blind Entry until it is submitted", () => {
    const { container } = render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess="crane"
        guesses={[]}
        revealing={false}
        blindCurrentEntry
      />,
    );
    expect(container.querySelectorAll(".tile--blind-entry")).toHaveLength(5);
    expect(screen.queryByText("C")).not.toBeInTheDocument();
    expect(screen.queryByText("E")).not.toBeInTheDocument();
    expect(
      screen.getByRole("cell", {
        name: "Position 1, letter hidden during Blind Entry",
      }),
    ).toBeInTheDocument();
  });

  it("shows Blind Entry progress without exposing its letters", () => {
    const { container, rerender } = render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess="c"
        guesses={[]}
        revealing={false}
        blindCurrentEntry
      />,
    );

    expect(container.querySelectorAll(".tile--blind-entry")).toHaveLength(1);
    expect(container.querySelectorAll(".tile--filled")).toHaveLength(1);
    expect(screen.queryByText("C")).not.toBeInTheDocument();

    rerender(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess="cran"
        guesses={[]}
        revealing={false}
        blindCurrentEntry
      />,
    );

    expect(container.querySelectorAll(".tile--blind-entry")).toHaveLength(4);
    expect(container.querySelectorAll(".tile--filled")).toHaveLength(4);
    expect(screen.queryByText("R")).not.toBeInTheDocument();
  });

  it("masks corrupted and Memory Tax rows without shifting the grid", () => {
    const guesses = [
      {
        guess: "slate",
        feedback: "BBBBB",
        attempt: 1,
        status: "playing" as const,
      },
      {
        guess: "fight",
        feedback: "BBBBB",
        attempt: 2,
        status: "playing" as const,
      },
      {
        guess: "mould",
        feedback: "BBBBB",
        attempt: 3,
        status: "playing" as const,
      },
    ];
    const { container } = render(
      <GameBoard
        wordLength={5}
        maxGuesses={6}
        currentGuess=""
        guesses={guesses}
        revealing={false}
        memoryTaxRetainRows={2}
        corruptedRowAttempt={2}
      />,
    );
    expect(container.querySelectorAll(".tile--memory-tax")).toHaveLength(5);
    expect(container.querySelectorAll(".tile--corrupted")).toHaveLength(5);
    expect(screen.getAllByRole("cell")).toHaveLength(30);
  });
});
