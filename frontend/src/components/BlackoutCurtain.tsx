type BlackoutCurtainProps = {
  stage: "closing" | "opening";
};

export function BlackoutCurtain({ stage }: BlackoutCurtainProps) {
  return (
    <div
      className={`blackout-curtain blackout-curtain--${stage}`}
      aria-hidden="true"
    >
      <div className="blackout-curtain__panel blackout-curtain__panel--left" />
      <div className="blackout-curtain__panel blackout-curtain__panel--right" />
    </div>
  );
}
