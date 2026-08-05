const ITEMS = [
  { marker: "✓", label: "Correct position", state: "g" },
  { marker: null, label: "Present elsewhere", state: "y" },
  { marker: "×", label: "Absent", state: "b" },
];

function ElsewhereIcon() {
  return (
    <svg className="legend-marker__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m8 7-5 5 5 5M3 12h18M16 7l5 5-5 5" />
    </svg>
  );
}

export function FeedbackLegend() {
  return (
    <ul className="feedback-legend" aria-label="Feedback legend">
      {ITEMS.map((item) => (
        <li key={item.state}>
          <span
            className={`legend-marker legend-marker--${item.state}`}
            aria-hidden="true"
          >
            {item.state === "y" ? <ElsewhereIcon /> : item.marker}
          </span>
          {item.label}
        </li>
      ))}
    </ul>
  );
}
