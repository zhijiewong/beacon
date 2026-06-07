"use client";
import { AreaChart } from "@tremor/react";
import { Context, TIER_LABEL, TIER_COLOR } from "@/lib/types";

export default function TrendChart({ ctx }: { ctx: Context }) {
  const trend = ctx.charts.trend;
  const names = Object.keys(trend).filter((n) => (trend[n] || []).length >= 2);
  if (!names.length) {
    return (
      <p className="font-mono text-[13px] text-soft p-7 border border-dashed border-hair my-10 text-center">
        The LLMflation trend fills in as daily snapshots accrue.
      </p>
    );
  }
  const dates = (trend[names[0]] || []).map(([d]) => d);
  const data = dates.map((d, i) => {
    const row: Record<string, string | number> = { date: d };
    for (const n of names) row[TIER_LABEL[n] || n] = trend[n][i]?.[1] ?? 0;
    return row;
  });
  const categories = names.map((n) => TIER_LABEL[n] || n);
  const colors = names.map((n) => TIER_COLOR[n] || "#18140D");

  return (
    <AreaChart
      data={data}
      index="date"
      categories={categories}
      colors={colors}
      valueFormatter={(v) => `$${v.toFixed(3)}`}
      showLegend
      showGridLines
      yAxisWidth={56}
      curveType="monotone"
      className="h-72 mt-2"
    />
  );
}
