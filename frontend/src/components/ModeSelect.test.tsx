import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModeSelect } from "./ModeSelect";

describe("ModeSelect", () => {
  it("makes Daily primary and Practice available", () => {
    const onStart = vi.fn();
    const onPractice = vi.fn();
    render(
      <ModeSelect
        daily={{
          puzzleKey: "2026-07-28",
          availability: "available",
          resetAt: "2026-07-29T03:00:00Z",
        }}
        busy={false}
        onStart={onStart}
        onPractice={onPractice}
        onHelp={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Play Daily" }));
    fireEvent.click(screen.getByRole("button", { name: "Play Practice" }));

    expect(onStart).toHaveBeenCalledOnce();
    expect(onStart).toHaveBeenCalledWith("daily");
    expect(onPractice).toHaveBeenCalledOnce();
    expect(
      screen.queryByText(/Truth Baseline|Lies are not active|under test/i),
    ).not.toBeInTheDocument();
  });

  it("blocks a used Daily while leaving Practice available", () => {
    render(
      <ModeSelect
        daily={{
          puzzleKey: "2026-07-28",
          availability: "used",
          resetAt: "2026-07-29T03:00:00Z",
        }}
        busy={false}
        onStart={() => undefined}
        onPractice={() => undefined}
        onHelp={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Daily Used" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Play Practice" })).toBeEnabled();
  });
});
