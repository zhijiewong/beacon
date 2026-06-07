import type { Config } from "tailwindcss";

// Almanac palette — Tremor's semantic tokens are remapped onto it so Tremor
// components (charts, cards) inherit the paper/ink aesthetic, not the default.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#F3F0E7",
        paper2: "#EBE7DA",
        ink: "#18140D",
        soft: "#6A6354",
        hair: "#D7D0BF",
        sig: "#C8431B",
        slate: "#2F5D74",
        ochre: "#A07C2C",
        // Tremor tokens -> almanac
        tremor: {
          brand: { DEFAULT: "#C8431B", emphasis: "#A6360F", muted: "#EBE7DA", subtle: "#E2C7B8", inverted: "#F3F0E7" },
          background: { DEFAULT: "#F3F0E7", muted: "#EBE7DA", subtle: "#E4DFD1", emphasis: "#6A6354" },
          border: { DEFAULT: "#D7D0BF" },
          ring: { DEFAULT: "#D7D0BF" },
          content: { DEFAULT: "#6A6354", subtle: "#8A8475", emphasis: "#18140D", strong: "#18140D", inverted: "#F3F0E7" },
        },
      },
      fontFamily: {
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        "tremor-card": "0 1px 2px 0 rgb(0 0 0 / 0.03)",
        "tremor-dropdown": "0 4px 12px 0 rgb(0 0 0 / 0.08)",
      },
      borderRadius: {
        "tremor-small": "0.25rem",
        "tremor-default": "0.375rem",
        "tremor-full": "9999px",
      },
      fontSize: {
        "tremor-label": ["0.75rem", { lineHeight: "1rem" }],
        "tremor-default": ["0.875rem", { lineHeight: "1.25rem" }],
        "tremor-title": ["1.125rem", { lineHeight: "1.75rem" }],
        "tremor-metric": ["1.875rem", { lineHeight: "2.25rem" }],
      },
    },
  },
  safelist: [
    // Tremor applies color classes dynamically — keep them from being purged.
    {
      pattern: /^(bg|text|border|ring|fill|stroke)-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-(50|100|200|300|400|500|600|700|800|900|950)$/,
      variants: ["hover", "ui-selected"],
    },
    { pattern: /^(bg|text|border|ring|stroke|fill)-(sig|ink|ochre|soft|hair|paper|paper2)/ },
  ],
  plugins: [],
};
export default config;
