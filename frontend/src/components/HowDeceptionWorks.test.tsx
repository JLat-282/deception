import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HowDeceptionWorks } from "./HowDeceptionWorks";

describe("HowDeceptionWorks", () => {
  it("explains feedback lies and lists punishments without trigger rules", () => {
    render(<HowDeceptionWorks expandAll onClose={vi.fn()} />);

    expect(
      screen.getByRole("heading", { name: "How Deception Works" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The letter is in the correct spot/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The letter is in the word but belongs somewhere else/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/The letter is not in the word/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/letters you enter never change or move/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/This can happen more than once/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/wrong color on one or two tiles/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/early correct answer may be marked wrong once/),
    ).toHaveLength(2);
    expect(
      screen.getByRole("heading", { name: "Difficulty levels" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Possible punishments")).toBeInTheDocument();
    expect(screen.getByText("Reverse Entry")).toBeInTheDocument();
    expect(screen.getByText("Guess Timer")).toBeInTheDocument();
    expect(screen.getByText("Blackout")).toBeInTheDocument();
    expect(screen.getByText("Intrusion")).toBeInTheDocument();
    expect(screen.getByText("Blind Entry")).toBeInTheDocument();
    expect(screen.getByText("Corrupted History")).toBeInTheDocument();
    expect(screen.getByText("Forced Commitment")).toBeInTheDocument();
    expect(screen.getByText("No Revision")).toBeInTheDocument();
    expect(screen.getByText("Memory Tax")).toBeInTheDocument();
    expect(screen.getByText(/either 30 or 10 seconds/)).toBeInTheDocument();
    expect(screen.getByText(/moving Dismiss button/)).toBeInTheDocument();
    expect(screen.queryByText(/80%|20%/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /four or five absent|small chance|future|layer|playtest|baseline/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("keeps how it works and punishments as separate disclosures", () => {
    render(<HowDeceptionWorks onClose={vi.fn()} />);

    const howItWorks = screen.getByText("How it works").closest("details");
    const punishments = screen
      .getByText("Possible punishments")
      .closest("details");
    expect(howItWorks).not.toHaveAttribute("open");
    expect(punishments).not.toHaveAttribute("open");

    fireEvent.click(screen.getByText("How it works"));
    expect(howItWorks).toHaveAttribute("open");
    expect(punishments).not.toHaveAttribute("open");
  });

  it("closes with Escape and restores focus to its trigger", () => {
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const { unmount } = render(<HowDeceptionWorks onClose={onClose} />);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });
});
