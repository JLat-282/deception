import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PracticeDifficultySelect } from "./PracticeDifficultySelect";

const presets = [
  {
    presetKey: "doubt-1@1",
    name: "Doubt I",
    rank: 1,
    pressure: "Uneasy",
    description: "A measured first step into uncertainty.",
    available: true,
  },
  {
    presetKey: "doubt-2@1",
    name: "Doubt II",
    rank: 2,
    pressure: "Unsettling",
    description: "The familiar rules begin to push back.",
    available: true,
  },
  {
    presetKey: "doubt-3@1",
    name: "Doubt III",
    rank: 3,
    pressure: "Severe",
    description: "Relentless pressure rewards careful play.",
    available: true,
  },
  {
    presetKey: "deception@1",
    name: "Deception",
    rank: 4,
    pressure: "Merciless",
    description: "Nothing is offered without a cost.",
    available: true,
  },
];

describe("PracticeDifficultySelect", () => {
  it("offers all four Practice difficulties", () => {
    const onSelect = vi.fn();
    render(
      <PracticeDifficultySelect
        presets={presets}
        busy={false}
        selectedPresetKey={null}
        onBack={vi.fn()}
        onHelp={vi.fn()}
        onSelect={onSelect}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Choose your doubt" }),
    ).toHaveFocus();
    fireEvent.click(
      screen.getByRole("button", { name: "Play Practice on Doubt II" }),
    );
    expect(onSelect).toHaveBeenCalledWith("doubt-2@1");
    expect(
      screen.getByRole("button", { name: "Play Practice on Doubt III" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Play Practice on Deception" }),
    ).toBeEnabled();
  });

  it("disables navigation and announces the selected card while starting", () => {
    render(
      <PracticeDifficultySelect
        presets={presets}
        busy
        selectedPresetKey="doubt-1@1"
        onBack={vi.fn()}
        onHelp={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Preparing…")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Back to modes" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("region", { name: "Choose your doubt" }),
    ).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Preparing Doubt I");
  });
});
