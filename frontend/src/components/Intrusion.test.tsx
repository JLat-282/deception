import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { INTRUSION_RELOCATION_MS, Intrusion } from "./Intrusion";

describe("Intrusion", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("covers the viewport and keeps moving its focused dismissal", () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random")
      .mockReturnValueOnce(0.25)
      .mockReturnValueOnce(0.75);
    const onDismiss = vi.fn();
    render(
      <Intrusion
        intrusion={{ state: "activated", placement: "lowerRight" }}
        onDismiss={onDismiss}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: "Intrusion" });
    const dismiss = screen.getByRole("button", { name: "Dismiss" });
    expect(dialog.parentElement).toHaveClass("intrusion-shield");
    expect(dialog.parentElement).toHaveAttribute(
      "data-placement",
      "lowerRight",
    );
    expect(dismiss).toHaveFocus();
    expect(dismiss.style.left).toBe("");

    act(() => vi.advanceTimersByTime(INTRUSION_RELOCATION_MS));

    expect(dismiss.style.left).not.toBe("");
    expect(dismiss.style.top).not.toBe("");
    fireEvent.keyDown(dismiss, { key: "Enter" });
    fireEvent.keyDown(dismiss, { key: " " });
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.click(dismiss);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it.each(["Enter", "Escape"])(
    "does not dismiss from the global %s key",
    (key) => {
      const onDismiss = vi.fn();
      render(
        <Intrusion
          intrusion={{ state: "activated", placement: "upperLeft" }}
          onDismiss={onDismiss}
        />,
      );

      fireEvent.keyDown(window, { key });
      expect(onDismiss).not.toHaveBeenCalled();
    },
  );
});
