---
name: es-market-context
description: ES and MES contract specs, CME session structure, tick and dollar math, and position sizing against this project's daily P&L guardrails. Load before writing any risk, sizing, or session-handling logic, and before quoting any dollar figure.
---

# ES / MES market context

Everything here is contract specification or exchange schedule — check it before writing
sizing logic. Getting point value wrong is the single easiest way to produce a backtest
that is off by 10x.

---

## 1. Contract specifications

| | **ES** (E-mini S&P 500) | **MES** (Micro E-mini) |
|---|---|---|
| Multiplier | $50 × index | $5 × index |
| Minimum tick | 0.25 index points | 0.25 index points |
| Tick value | **$12.50** | **$1.25** |
| Ticks per point | 4 | 4 |
| Point value | **$50** | **$5** |
| Typical RT commission | ~$4.00 | ~$1.20 |
| TradingView symbol | `ES1!` (continuous) | `MES1!` |

`ES1!` is the continuous front-month contract — it rolls, which introduces price gaps at
roll dates. For backtests spanning multiple quarters, be aware roll gaps can register as
large phantom moves. Note this in any report covering a roll.

---

## 2. Session structure (all times America/Chicago)

| Session | Time | Character |
|---|---|---|
| Globex open | 17:00 previous day | Thin, wide spreads |
| Asia | 19:00 – 02:00 | Low volume, ranges hold |
| London | 02:00 – 08:30 | Volume picks up, often sets overnight extremes |
| **RTH open** | **08:30** | Highest volume of the day |
| Initial Balance (IB) | 08:30 – 09:30 | First hour range — a key reference level |
| Lunch | 11:00 – 13:00 | Volume drop, chop, high false-breakout rate |
| Afternoon trend | 13:00 – 15:00 | Second trend window |
| RTH close | 15:00 | Settlement |
| Daily maintenance halt | 16:00 – 17:00 | No trading |

Weekly: opens Sunday 17:00, closes Friday 16:00.

**Implications for the strategy:**
- The lunch window is where most intraday trend systems bleed. Consider a time filter.
- Overnight high/low (ONH/ONL) and IB high/low are the reference levels most likely to have
  resting stops clustered against them — they matter to the liquidity map.
- The 16:00–17:00 halt creates a bar gap; daily P&L reset logic must key on the session, not
  the calendar bar.

---

## 3. Reference levels that matter on ES

These are the levels the liquidity-proxy map should track:

- **Prior day high / low / close** (PDH / PDL / PDC)
- **Overnight high / low** (ONH / ONL) — Globex open to RTH open
- **Initial Balance high / low** — first 60 min of RTH
- **VWAP** and its standard-deviation bands (session-anchored)
- **Volume Point of Control (POC)** and value area high/low
- **Unfilled gaps** between prior close and current open
- **Equal highs / equal lows** — repeated touches within a tick or two, where stops pool

---

## 4. Volatility reference

Rough ES daily ranges (verify against current data before relying on these):

| Regime | Daily range | 5m ATR |
|---|---|---|
| Low vol | 20–35 pts | 2–4 pts |
| Normal | 35–60 pts | 4–7 pts |
| High vol | 60–120+ pts | 8–20 pts |

A stop tighter than roughly 1.5× the 5m ATR will be taken out by noise regardless of whether
the directional idea was right.

---

## 5. Position sizing against this project's guardrails

Constraints: **max daily loss $200**, **daily target $400–500**.

With a 2-losers-before-lockout rule, per-trade risk is ~$100.

**On ES ($50/pt):**
$100 ÷ $50 = **2-point stop**. That is 8 ticks — well inside 5m noise in any regime above
"low vol". This size is not viable for an intraday trend system. Stated plainly: you cannot
trade full-size ES with a $200 daily cap and a realistic stop.

**On MES ($5/pt):**

| Contracts | $100 risk buys | Viable? |
|---|---|---|
| 1 MES | 20-pt stop | Yes, comfortable in all regimes |
| 2 MES | 10-pt stop | Yes in normal vol |
| 4 MES | 5-pt stop | Only in low vol; marginal |

**MES is the correct instrument for these guardrails.** Recommended baseline: 2 MES with a
stop of 1.5–2× the 5m ATR, sizing down when ATR expands so dollar risk stays flat.

**What the daily target demands.** $450 on $100 risk units is **4.5R per day**. Reaching that
consistently requires either several winners per day at 2R+, or a high win rate with runners.
For reference, an intraday system taking 3 trades/day at 50% win rate and 2R average winners
nets about +1R/day = $100. **Getting to $450/day is roughly 4x that.** This is the central
open question of the project, and the backtest — not an assumption — has to answer it. Do
not size up to force the number: 4x the size is also 4x the drawdown, and it breaches the
$200 cap on the first bad day.

---

## 6. Costs — always applied

| | ES | MES |
|---|---|---|
| Commission RT | ~$4.00 | ~$1.20 |
| Slippage, 1 tick/side | $25.00 RT | $2.50 RT |
| **Total per RT** | **~$29** | **~$3.70** |

On MES with 2 contracts, round-trip cost is ~$7.40 — about 7% of a $100 risk unit. A system
taking 5 trades/day burns ~$37/day in costs, which is ~8% of the $450 target. Material,
and a reason to prefer fewer, larger trades over scalping.

---

## 7. Data availability on TradingView

Historical bar count is capped by subscription tier (roughly 5k–20k bars). On 5m ES,
10k bars ≈ 26 RTH days. Backtest windows must be checked against what was actually loaded —
`data_get_ohlcv` returning fewer bars than requested means the window was truncated, and
any report must say so.
