import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HowDeceptionWorks } from "./HowDeceptionWorks";

describe("HowDeceptionWorks", () => {
  it("explains current feedback lies without roadmap language", () => {
    render(<HowDeceptionWorks onClose={vi.fn()} />);

    expect(
      screen.getByRole("heading", { name: "How Deception Works" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Only feedback can lie/)).toBeInTheDocument();
    expect(
      screen.getByText(/Letters never change or move/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Feedback may lie more than once/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/80%|20%/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/future|layer|playtest|baseline/i),
    ).not.toBeInTheDocument();
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
