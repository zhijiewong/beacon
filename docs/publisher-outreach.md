# Publisher-recruitment outreach (drafts)

> **Honesty constraints baked into every version below — do not strip them:**
> Base Sepolia **testnet**, **unaudited**, BEACON is a **valueless test token**, rewards
> **not funded yet**. The ask is to help turn a self-demo into a real multi-publisher feed,
> **not** to earn. Never imply a live token, yield, or audited security. Link the runbook:
> [`docs/publisher-onboarding.md`](./publisher-onboarding.md).

These are drafts to send *yourself* — nothing here has been posted anywhere. Pick the format
per channel and fill the per-recipient `<…>` slots (`<name>`, `<specific reason>`). The shared
links are already filled in:

- **Dashboard:** https://zhijiewong.github.io/beacon-index/
- **Code:** https://github.com/zhijiewong/beacon
- **Publisher runbook:** https://github.com/zhijiewong/beacon/blob/main/docs/publisher-onboarding.md

---

## Who to approach (warmest → coldest)

1. **People already tracking LLM prices** — Epoch AI / Artificial Analysis / inference-index
   folks, FinOps-for-AI engineers, anyone publishing $/token data. They have the data habit
   already; posting it on-chain is a small marginal step and they get a neutral public credit.
2. **Oracle node operators** — existing Pyth/Chainlink/RedStone publishers. They already run
   staking-publisher infra and understand slashing; the Pyth-OIS framing lands instantly.
3. **Crypto-native AI / DeAI builders** — x402 / agent-payments people who'd eventually *read*
   the rate; getting them to also publish bootstraps both sides.
4. **Researchers / indie quants** — anyone who'd find a capability-normalized "SOFR of AI"
   intellectually interesting enough to run a daily script for.

The bar for v1 is low and worth stating plainly: **2 genuinely independent publishers** turns
the median from a self-demo into a real one. That's the whole ask.

---

## A. One-liner (DM / Twitter reply / Telegram)

> Building **Beacon** — a capability-normalized reference rate for LLM inference ("$/unit of
> intelligence"), published **on-chain** so contracts can settle against it. The oracle is
> Pyth-style: publishers stake on the accuracy of their submissions, slashed for bad data.
> It's live on Base Sepolia and I'm looking for **2–3 independent publishers** to make the
> median real. Testnet + unaudited, no token, ~10 min to try. Interested?

---

## B. Twitter/X thread (recruiting post)

**1/** Web2 dashboards tell a human what AI costs. None give a *contract* a trustless price to
settle on. I've been building **Beacon**: a capability-normalized inference reference rate —
the "SOFR/Brent of AI" — published on-chain.

**2/** "Capability-normalized" = not raw $/token (which only falls and isn't quality-fungible).
It's the cheapest credible price to hit a fixed capability tier (e.g. GPQA-Diamond:frontier),
hedonic-indexed the way BLS does CPI for computers. Frontier / strong / GPT-4-class sub-rates +
the cross-provider spread.

**3/** The crypto-native part: the rate is an **economically-secured oracle** (Pyth Oracle
Integrity Staking blueprint). Publishers self-stake, submit per round, and a **stake-weighted
median** is published. Deviate past tolerance → your stake is **slashed**. Skin in the game,
not trust.

**4/** It's live on **Base Sepolia** today: token, staking, the median oracle, and a reference
**consumer contract** that reads the rate and settles a sample quote against it. All verified
on-chain, open source.

**5/** What I need: **2–3 independent publishers** to turn the median from a one-publisher demo
into a real multi-source feed. There's a runbook + scripts — funded, self-stake, post the
index — ~10 minutes.

**6/** Straight up: this is **testnet, unaudited**, the staked token is **valueless test
BEACON**, and **rewards aren't funded** yet. No token launch, no yield pitch. It's a
picks-and-shovels bet on the agentic-settlement future, and I want a couple of credible
co-publishers on the record. DM me. 🔦

**7/** Live rate → https://zhijiewong.github.io/beacon-index/ · code + publisher runbook →
https://github.com/zhijiewong/beacon

---

## C. Cold email / longer DM

**Subject:** 2 publishers needed for an on-chain AI-inference reference rate (testnet)

Hi <name>,

I'm building **Beacon** — a capability-normalized **reference rate for LLM inference**,
published **on-chain** as an economically-secured oracle. The thesis: as agents settle payments
and inference derivatives form, they'll need a neutral price a *contract* can settle against —
the way SOFR or Brent anchor their markets. Web2 price trackers can't be that; an on-chain,
stake-secured rate can.

I reached out to you because <specific reason — "you publish the inference price index" /
"you run a Pyth publisher" / "you're building x402 agent payments">, which makes you exactly the
kind of independent publisher the feed needs.

How it works (Pyth Oracle Integrity Staking blueprint):

- An open Python pipeline computes the capability-normalized index (cheapest price to reach a
  fixed benchmark tier; frontier / strong / GPT-4-class + cross-provider spread).
- Eligible publishers self-stake and submit a value per round; the contract publishes the
  **stake-weighted median** and **slashes** anyone who deviates past tolerance. Honest
  submissions are never touched.
- A reference consumer contract already reads the published rate and settles a sample quote
  against it.

It's **live on Base Sepolia**, open source, with a step-by-step runbook. Becoming a publisher
takes ~10 minutes: get funded with test tokens, self-stake the minimum, run one post script.

Full honesty up front: this is **testnet and unaudited**, the staked BEACON is a **valueless
test token**, and **rewards aren't funded** yet — there's no token launch and nothing to earn
today. The ask is to put a couple of credible, independent publishers on the record so the
median is real rather than a self-demo. A professional audit gates anything with real value.

If a neutral, economically-secured rate for AI compute is interesting to you, I'd love to walk
you through it — or you can just follow the runbook:
https://github.com/zhijiewong/beacon/blob/main/docs/publisher-onboarding.md

Dashboard: https://zhijiewong.github.io/beacon-index/ · Code: https://github.com/zhijiewong/beacon

Thanks,
<your name>

---

## D. Discord / forum post (oracle or DeAI community)

**[Recruiting] 2–3 publishers for an on-chain LLM-inference reference rate (Base Sepolia, testnet)**

**TL;DR:** Beacon is a capability-normalized reference rate for AI inference, published on-chain
as a Pyth-OIS-style staked oracle (stake on accuracy, slashed for bad data). Live on Base
Sepolia. Looking for a couple of independent publishers to make the median real. Testnet,
unaudited, no token, ~10 min to join.

**Why it exists:** raw $/token only falls and isn't quality-comparable, so Beacon indexes the
cheapest credible price to hit a fixed capability tier (GPQA-Diamond frontier / strong /
GPT-4-class), plus the cross-provider spread. Web2 trackers already do dashboards; the open
wedge is a *settlement-grade, on-chain* rate that contracts and x402 agents can reference.

**What's live:** ERC-20 (BEACON, testnet) · staking with capped slashing + delegation + unbonding
· `BeaconOracleV2` (stake-weighted median, auto-slash on deviation, staleness window) ·
a reference `BeaconConsumer` that reads the rate and settles a quote. All open source + verified
on-chain.

**The publisher role:** self-stake the minimum, submit the open-source index each round; the
contract publishes the stake-weighted median and slashes deviation past tolerance.
Runbook + scripts: https://github.com/zhijiewong/beacon/blob/main/docs/publisher-onboarding.md
Code: https://github.com/zhijiewong/beacon · Dashboard: https://zhijiewong.github.io/beacon-index/

**Honest caveats:** Base Sepolia testnet, **unaudited**, staked token is **valueless**, rewards
**not funded**, no token launch. This is bootstrapping a credible multi-publisher feed, not a
yield/airdrop play. Audit gates real value.

Reply or DM if you'll run a publisher — happy to fund your testnet wallet and pair through setup.

---

## E. Objection handling (keep answers honest)

| They say | Honest answer |
|----------|---------------|
| "What do I earn?" | Nothing today — testnet, rewards unfunded. On-chain reward plumbing (stablecoin, pro-rata to stake) exists; funding is gated on real traction. You're an early publisher of record, not a yield farmer. |
| "Is my stake at risk?" | Only valueless **test** BEACON, and only slashed if your submission deviates >10% from the median. Use a throwaway testnet key with no real funds — that's the documented setup. |
| "Why not just a dashboard?" | Dashboards can't give a *contract* a trustless number. The whole point is settlement-grade + economic security, which a Web2 feed structurally can't offer. |
| "Is it audited?" | No — explicitly unaudited, testnet only. A professional audit is the non-negotiable gate before any mainnet/real value. Stated everywhere. |
| "How much work?" | ~10 min to start (funded → self-stake → one post script). Daily posting is a cron-able script; the index computation is open source. |
| "Why should I trust the index method?" | It's fully open (`beacon/` + methodology doc), reproduces published LLMflation curves on an acceptance test, and uses the same hedonic approach as BLS/Epoch. Inspect or fork it. |
| "Isn't on-chain inference demand basically zero today?" | Yes — said plainly. It's a timing bet on agentic settlement + inference derivatives forming. Phase 1 (the public index) stands alone meanwhile; being an early publisher costs ~nothing and books the position. |

---

## F. Sequencing tips

- **Warm intros first.** One credible independent publisher makes the next ask far easier
  ("X is already publishing"). Land #1 before broadcasting.
- **Offer to fund their testnet wallet** (`fund-publisher.js`) and pair through setup live —
  removes all friction.
- **Lead with the consumer demo, not the token.** "A contract already settles against this"
  is the differentiator; the token is just the security layer.
- **Never overstate.** The credibility of a *reference rate* is the entire asset. One
  oversold claim (live token, real yield, "audited") costs more than it gains.
