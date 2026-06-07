// Shape of site/index.json produced by `python3 -m beacon.site`.
export interface Tier {
  name: string;
  threshold: number;
  value_usd_per_mtok: number;
  spread: number | null;
  n_qualifying: number;
  provider_count: number;
  cheapest_model: string | null;
  prices: number[];
  change_pct?: number | null;
}

export interface Charts {
  scatter: { model: string; capability: number; price: number }[];
  frontier: [number, number | null][];
  trend: Record<string, [string, number][]>;
}

export interface Context {
  as_of: string;
  model_count: number;
  methodology_version: string;
  benchmark: string;
  tiers: Tier[];
  key_figures: { providers_total: number; multiple: number | null };
  onchain: { address: string; explorer_url: string } | null;
  charts: Charts;
}

export const TIER_LABEL: Record<string, string> = {
  frontier: "Frontier",
  strong: "Strong",
  "gpt-4-class": "GPT-4 class",
};
export const TIER_COLOR: Record<string, string> = {
  frontier: "#C8431B",
  strong: "#2F5D74",
  "gpt-4-class": "#A07C2C",
};

export const money = (v: number) =>
  v >= 1 ? String(Math.round(v)) : String(+v.toFixed(2)).replace(/^0/, "0");
export const shortModel = (m: string | null) => (m && m.includes("/") ? m.split("/").slice(1).join("/") : m || "—");
