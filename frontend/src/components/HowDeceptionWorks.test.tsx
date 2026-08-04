import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HowDeceptionWorks } from "./HowDeceptionWorks";

describe("HowDeceptionWorks", () => {
  it("explains feedback lies and lists punishments without trigger rules", () => {
    render(<HowDeceptionWorks expandAll onClose={vi.fn()} />);

    expect(
      screen.getByRole("heading", { name: "Deception Guide" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Only feedback can lie/)).toBeInTheDocument();
    expect(
      screen.getByText(/Letters never change or move/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Feedback may lie more than once/),
    ).toBeInTheDocument();
    expect(screen.getByText(/one or two tiles/)).toBeInTheDocument();
    expect(
      screen.getByText(/correct answer can also be rejected/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Difficulties" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Possible punishments")).toBeInTheDocument();
    expect(screen.getByText("Reverse Entry")).toBeInTheDocument();
    expect(screen.getByText("Guess Timer")).toBeInTheDocument();
    expect(screen.getByText("Blackout")).toBeInTheDocument();
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
