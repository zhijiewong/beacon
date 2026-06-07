import { Context, TIER_LABEL, TIER_COLOR, money } from "@/lib/types";

const INK = "#18140D", SOFT = "#6A6354", HAIR = "#D7D0BF";

export default function DispersionChart({ ctx }: { ctx: Context }) {
  const rows = ctx.tiers.filter((t) => t.prices.length);
  const all = rows.flatMap((t) => t.prices);
  if (!all.length) return null;
  const w = 900, h = 300, padL = 130, padR = 40, padT = 30, padB = 46;
  const lo = Math.floor(Math.log10(Math.min(...all))), hi = Math.ceil(Math.log10(Math.max(...all)));
  const px = (p: number) => padL + ((Math.log10(p) - lo) / Math.max(1e-9, hi - lo)) * (w - padL - padR);
  const laneH = (h - padT - padB) / Math.max(1, rows.length);
  const ticks = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="block w-full h-auto" fontFamily="var(--font-mono), monospace">
      <text x={padL} y={18} fill={SOFT} fontSize={12} letterSpacing="0.1em">
        PRICE $/MTOK (LOG) — EACH DOT IS A PROVIDER; RINGED = CHEAPEST
      </text>
      {ticks.map((d) => (
        <g key={d}>
          <line x1={px(10 ** d)} y1={padT} x2={px(10 ** d)} y2={h - padB} stroke={HAIR} />
          <text x={px(10 ** d)} y={h - padB + 22} fill={SOFT} fontSize={12} textAnchor="middle">${money(10 ** d)}</text>
        </g>
      ))}
      {rows.map((t, i) => {
        const cy = padT + laneH * (i + 0.5);
        const c = TIER_COLOR[t.name] || INK;
        const cheapest = Math.min(...t.prices);
        return (
          <g key={t.name}>
            <text x={padL - 16} y={cy + 4} fill={INK} fontSize={13} textAnchor="end" fontFamily="var(--font-sans), sans-serif">
              {TIER_LABEL[t.name] || t.name}
            </text>
            {t.prices.map((p, j) => {
              const big = p === cheapest;
              return (
                <g key={j}>
                  <circle cx={px(p)} cy={cy} r={big ? 5.5 : 4} fill={c} opacity={big ? 1 : 0.42} />
                  {big && <circle cx={px(p)} cy={cy} r={8.5} fill="none" stroke={c} strokeWidth={1.3} />}
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
