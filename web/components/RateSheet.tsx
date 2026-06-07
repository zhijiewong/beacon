import { Context, TIER_LABEL, shortModel } from "@/lib/types";
import CountUp from "./CountUp";
import Sparkline from "./Sparkline";

function Change({ pct }: { pct?: number | null }) {
  if (pct == null) return null;
  if (Math.abs(pct) < 0.05) return <div className="font-mono text-xs mt-0.5 text-soft">flat dod</div>;
  const down = pct < 0;
  return (
    <div className="font-mono text-xs mt-0.5" style={{ color: down ? "#3F7A4F" : "#C8431B" }}>
      {down ? "▼" : "▲"} {Math.abs(pct).toFixed(1)}% dod
    </div>
  );
}

export default function RateSheet({ ctx }: { ctx: Context }) {
  return (
    <section className="border-t-[1.5px] border-ink">
      {ctx.tiers.map((t, i) => {
        const series = (ctx.charts.trend[t.name] || []).map(([, v]) => v);
        const spread = t.spread != null ? `${t.spread.toFixed(1)}×` : "—";
        return (
          <div
            key={t.name}
            className="group relative grid grid-cols-[1fr_auto] md:grid-cols-[1.2fr_1.3fr_.8fr_1.7fr] gap-x-[18px] gap-y-2 items-center px-2.5 py-5 border-b border-hair transition-colors hover:bg-paper2 rise"
            style={{ animationDelay: `${0.14 + i * 0.07}s` }}
          >
            <span className="absolute left-0 inset-y-0 w-[3px] bg-transparent group-hover:bg-sig transition-colors" />
            <div>
              <div className="font-serif text-[clamp(22px,3vw,30px)] leading-none">{TIER_LABEL[t.name] || t.name}</div>
              <div className="font-mono text-[11px] tracking-[.06em] uppercase text-soft mt-0.5">
                {ctx.benchmark} ≥ {t.threshold}
              </div>
            </div>
            <div>
              <div className="font-mono font-medium text-[clamp(26px,4vw,40px)] tracking-tight tnum">
                <CountUp value={t.value_usd_per_mtok} decimals={3} prefix="$" />
                <span className="text-[.4em] text-soft">/Mtok</span>
              </div>
              <Change pct={t.change_pct} />
            </div>
            <div className="hidden md:block">
              <Sparkline values={series} />
            </div>
            <div className="font-mono text-[12.5px] text-soft text-left md:text-right leading-relaxed col-span-2 md:col-span-1">
              cheapest <span className="text-ink">{shortModel(t.cheapest_model)}</span>
              <br />
              <b className="text-ink font-medium">{t.n_qualifying}</b> models · <b className="text-ink font-medium">{t.provider_count}</b> providers · spread <b className="text-ink font-medium">{spread}</b>
            </div>
          </div>
        );
      })}
    </section>
  );
}
