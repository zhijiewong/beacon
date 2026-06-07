import data from "@/data/index.json";
import { Context } from "@/lib/types";
import Figures from "@/components/Figures";
import RateSheet from "@/components/RateSheet";
import FrontierChart from "@/components/FrontierChart";
import DispersionChart from "@/components/DispersionChart";
import TrendChart from "@/components/TrendChart";

const ctx = data as unknown as Context;

function Figure({ children, caption, delay }: { children: React.ReactNode; caption: string; delay?: string }) {
  return (
    <figure className="my-10 p-[18px] pb-2 bg-paper2 border border-hair rise" style={{ animationDelay: delay }}>
      {children}
      <figcaption className="font-mono text-xs tracking-[.1em] uppercase text-soft pt-2.5 px-1">{caption}</figcaption>
    </figure>
  );
}

export default function Page() {
  return (
    <main className="max-w-[1040px] mx-auto px-5 sm:px-10 pt-12 sm:pt-16 pb-24">
      <header className="flex justify-between items-baseline gap-6 border-b-[1.5px] border-ink pb-4 flex-wrap rise">
        <div className="font-serif text-[clamp(40px,7vw,76px)] leading-[.9]">Beacon</div>
        <div className="font-mono text-xs tracking-[.16em] uppercase text-soft text-right">The Reference Rate<br />for AI Inference</div>
      </header>

      <div className="flex gap-5 flex-wrap font-mono text-xs tracking-[.12em] uppercase text-soft pt-3 rise" style={{ animationDelay: ".06s" }}>
        <span><span className="inline-block w-[7px] h-[7px] rounded-full bg-sig mr-1.5 live-dot" />As of {ctx.as_of}</span>
        <span>{ctx.model_count} models</span>
        <span>{ctx.key_figures.providers_total} providers</span>
        <span>Methodology v{ctx.methodology_version}</span>
      </div>

      <h1 className="font-serif text-[clamp(34px,5.6vw,60px)] leading-[1.04] max-w-[18ch] mt-10 sm:mt-16 mb-3.5 rise" style={{ animationDelay: ".1s" }}>
        What a unit of intelligence costs.
      </h1>
      <p className="max-w-[58ch] text-[#3a352b] text-[clamp(16px,2vw,18px)] mb-7 rise" style={{ animationDelay: ".14s" }}>
        The cheapest price to reach a fixed AI capability — not a raw average that only falls — measured across every major provider and published as a neutral reference rate.
      </p>

      <Figures ctx={ctx} />

      <div className="font-mono text-xs tracking-[.18em] uppercase text-soft mt-2 mb-1.5 rise">Today&apos;s rates · $/million tokens</div>
      <RateSheet ctx={ctx} />

      <Figure caption="Price × capability frontier — cheapest $/Mtok to reach each level today" delay=".1s">
        <FrontierChart ctx={ctx} />
      </Figure>
      <Figure caption="Price dispersion — what every provider charges, by capability tier" delay=".1s">
        <DispersionChart ctx={ctx} />
      </Figure>
      <Figure caption="LLMflation — cheapest price to hold each tier, over time" delay=".1s">
        <TrendChart ctx={ctx} />
      </Figure>

      <h2 className="font-serif text-[clamp(26px,3.4vw,34px)] mt-16 mb-3 rise">How it&apos;s measured</h2>
      <p className="max-w-[62ch] text-[#33302a] rise">
        Beacon is a <em>capability-normalized</em> index. Rather than averaging sticker prices — which only fall and hide what you actually get — it tracks the lowest $/million-tokens to reach a fixed capability tier (scored on {ctx.benchmark}) across every major model. The construction is rules-based, reproducible, and transparent, the way credible commodity and rate benchmarks are built.
      </p>

      {ctx.onchain && (
        <div className="mt-11 px-6 py-5 border-[1.5px] border-ink flex gap-[18px] items-center flex-wrap justify-between bg-paper2 rise">
          <span className="font-mono text-xs tracking-[.14em] uppercase text-soft">Published on-chain · Base Sepolia · readable by any contract</span>
          <a href={ctx.onchain.explorer_url} className="font-mono text-sm text-ink no-underline border-b-2 border-sig break-all hover:bg-sig hover:text-paper">{ctx.onchain.address}</a>
        </div>
      )}

      <footer className="mt-16 border-t border-hair pt-4 font-mono text-xs tracking-[.08em] uppercase text-soft flex justify-between gap-4 flex-wrap">
        <span>Beacon · Neutral reference rate for AI inference</span>
        <span>Capability-normalized · Rules-based · Reproducible</span>
      </footer>
    </main>
  );
}
