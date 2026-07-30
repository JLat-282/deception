export const MINIMUM_REVEAL_START_MS = 100;

export function waitForRevealStart(): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, MINIMUM_REVEAL_START_MS);
  });
}
