import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModeSelect } from "./ModeSelect";

describe("ModeSelect", () => {
  it("makes Daily Descent primary and Infinite available", () => {
    const onStart = vi.fn();
    const onInfinite = vi.fn();
    render(
      <ModeSelect
        daily={{
          puzzleKey: "2026-07-28",
          availability: "available",
          resetAt: "2026-07-29T03:00:00Z",
          status: "unstarted",
          currentStage: 1,
          clearedStages: 0,
        }}
        busy={false}
        onStart={onStart}
        onInfinite={onInfinite}
        onHelp={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Begin Descent" }));
    fireEvent.click(screen.getByRole("button", { name: "Play Infinite" }));

    expect(onStart).toHaveBeenCalledOnce();
    expect(onStart).toHaveBeenCalledWith("daily");
    expect(onInfinite).toHaveBeenCalledOnce();
    expect(
      screen.queryByText(/Truth Baseline|Lies are not active|under test/i),
    ).not.toBeInTheDocument();
  });

  it("blocks an ended Daily Descent while leaving Infinite available", () => {
    render(
      <ModeSelect
        daily={{
          puzzleKey: "2026-07-28",
          availability: "used",
          resetAt: "2026-07-29T03:00:00Z",
          status: "failed",
          currentStage: 1,
          clearedStages: 0,
        }}
        busy={false}
        onStart={() => undefined}
        onInfinite={() => undefined}
        onHelp={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Descent Ended" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Play Infinite" })).toBeEnabled();
  });

  it("resumes from a cleared stage checkpoint", () => {
    const onStart = vi.fn();
    render(
      <ModeSelect
        daily={{
          puzzleKey: "2026-07-28",
          availability: "available",
          resetAt: "2026-07-29T03:00:00Z",
          status: "checkpoint",
          currentStage: 4,
          clearedStages: 3,
        }}
        busy={false}
        onStart={onStart}
        onInfinite={vi.fn()}
        onHelp={vi.fn()}
      />,
    );

    expect(screen.getByText("3 of 4 stages cleared.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enter Deception" }));
    expect(onStart).toHaveBeenCalledWith("daily");
  });
});
