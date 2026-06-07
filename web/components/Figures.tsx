import { Context } from "@/lib/types";
import CountUp from "./CountUp";

export default function Figures({ ctx }: { ctx: Context }) {
  const kf = ctx.key_figures;
  const cells: { n: React.ReactNode; l: string }[] = [];
  if (kf.multiple)
    cells.push({ n: <CountUp value={kf.multiple} suffix="×" />, l: "frontier vs GPT-4-class cost" });
  cells.push({ n: <CountUp value={ctx.model_count} />, l: "models priced" });
  cells.push({ n: <CountUp value={kf.providers_total} />, l: "providers tracked" });

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-hair border border-hair my-10 rise" style={{ animationDelay: ".18s" }}>
      {cells.slice(0, 3).map((c, i) => (
        <div key={i} className="bg-paper px-5 py-5">
          <div className="font-mono font-semibold text-[clamp(28px,4vw,40px)] tracking-tight tnum text-ink">{c.n}</div>
          <div className="font-mono text-[11px] tracking-[.12em] uppercase text-soft mt-1">{c.l}</div>
        </div>
      ))}
    </div>
  );
}
