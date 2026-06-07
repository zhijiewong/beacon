import { Context, TIER_LABEL, TIER_COLOR, money } from "@/lib/types";

const INK = "#18140D", SOFT = "#6A6354", HAIR = "#D7D0BF", SIG = "#C8431B";

export default function FrontierChart({ ctx }: { ctx: Context }) {
  const pts = ctx.charts.scatter;
  if (!pts.length) return null;
  const w = 900, h = 460, pad = 70;
  const xs = pts.map((p) => p.capability);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ly = pts.map((p) => Math.log10(p.price));
  const ymin = Math.floor(Math.min(...ly)), ymax = Math.ceil(Math.max(...ly));
  const px = (c: number) => pad + ((c - xmin) / (xmax - xmin)) * (w - 2 * pad);
  const py = (p: number) => h - pad - ((Math.log10(p) - ymin) / (ymax - ymin)) * (h - 2 * pad);

  const yTicks = Array.from({ length: ymax - ymin + 1 }, (_, i) => ymin + i);
  const xTicks: number[] = [];
  for (let c = Math.floor(xmin / 10) * 10; c <= xmax; c += 10) if (c >= xmin) xTicks.push(c);
  const fr = ctx.charts.frontier.filter(([, v]) => v != null) as [number, number][];
  const frPath = "M" + fr.map(([t, v]) => `${px(t).toFixed(1)} ${py(v).toFixed(1)}`).join(" L");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="block w-full h-auto" fontFamily="var(--font-mono), monospace">
      {yTicks.map((d) => (
        <g key={`y${d}`}>
          <line x1={pad} y1={py(10 ** d)} x2={w - pad} y2={py(10 ** d)} stroke={HAIR} />
          <text x={pad - 12} y={py(10 ** d) + 4} fill={SOFT} fontSize={12} textAnchor="end">${money(10 ** d)}</text>
        </g>
      ))}
      {xTicks.map((c) => (
        <text key={`x${c}`} x={px(c)} y={h - pad + 24} fill={SOFT} fontSize={12} textAnchor="middle">{c}</text>
      ))}
      {ctx.tiers.map((t) =>
        t.threshold >= xmin && t.threshold <= xmax ? (
          <g key={`g${t.name}`}>
            <line x1={px(t.threshold)} y1={pad} x2={px(t.threshold)} y2={h - pad} stroke={TIER_COLOR[t.name]} strokeDasharray="3 4" opacity={0.7} />
            <text x={px(t.threshold)} y={pad - 8} fill={TIER_COLOR[t.name]} fontSize={11} textAnchor="middle" letterSpacing="0.06em">
              {(TIER_LABEL[t.name] || t.name).toUpperCase()}
            </text>
          </g>
        ) : null
      )}
      {fr.length > 0 && <path d={frPath} fill="none" stroke={SIG} strokeWidth={2.5} />}
      {pts.map((p, i) => <circle key={i} cx={px(p.capability)} cy={py(p.price)} r={3.6} fill={INK} opacity={0.28} />)}
      <text x={w / 2} y={h - 18} fill={SOFT} fontSize={12} textAnchor="middle" letterSpacing="0.12em">
        {ctx.benchmark.toUpperCase()} CAPABILITY →
      </text>
    </svg>
  );
}
