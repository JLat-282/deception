const ITEMS = [
  { marker: "✓", label: "Correct position", state: "g" },
  { marker: "↔", label: "Present elsewhere", state: "y" },
  { marker: "×", label: "Absent", state: "b" },
];

export function FeedbackLegend() {
  return (
    <ul className="feedback-legend" aria-label="Feedback legend">
      {ITEMS.map((item) => (
        <li key={item.state}>
          <span
            className={`legend-marker legend-marker--${item.state}`}
            aria-hidden="true"
          >
            {item.marker}
          </span>
          {item.label}
        </li>
      ))}
    </ul>
  );
}
