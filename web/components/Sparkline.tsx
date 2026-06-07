export default function Sparkline({ values, w = 84, h = 24 }: { values: number[]; w?: number; h?: number }) {
  if (values.length < 2) return <div style={{ width: w, height: h }} />;
  const lo = Math.min(...values), hi = Math.max(...values), n = values.length - 1;
  const px = (i: number) => 2 + (i / n) * (w - 4);
  const py = (v: number) => (hi === lo ? h / 2 : h - 3 - ((v - lo) / (hi - lo)) * (h - 6));
  const pts = values.map((v, i) => `${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} className="block">
      <polyline points={pts} fill="none" stroke="#6A6354" strokeWidth={1.6} />
      <circle cx={px(n)} cy={py(values[n])} r={2.2} fill="#C8431B" />
    </svg>
  );
}
