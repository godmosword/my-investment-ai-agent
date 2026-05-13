function scale(values, width, height, pad) {
  const nums = values.map(Number).filter((n) => Number.isFinite(n));
  if (nums.length < 2) return "";
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const step = (width - pad * 2) / (nums.length - 1);
  return nums
    .map((value, i) => {
      const x = pad + i * step;
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export default function Sparkline({ values = [], tone = "neutral", label = "sparkline" }) {
  const width = 150;
  const height = 42;
  const points = scale(values, width, height, 4);
  const stroke = tone === "up" ? "var(--green)" : tone === "down" ? "var(--red)" : "var(--accent)";

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      className="h-[42px] w-full"
      preserveAspectRatio="none"
    >
      <rect x="0" y="0" width={width} height={height} rx="6" fill="rgba(10,124,104,0.04)" />
      {points ? (
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ) : (
        <line x1="8" x2={width - 8} y1={height / 2} y2={height / 2} stroke="var(--border)" strokeWidth="2" />
      )}
    </svg>
  );
}
