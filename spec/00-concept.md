# 00 — Concept and constraints

**Status:** working draft. Seeded from the trader's own chart and stated method, 2026-08-24.
Phase 1 research fills the gaps; Phase 2 turns this into executable rules.

---

## 1. The method, as the trader describes and trades it

Primary timeframe **15m**, instrument **MES** (chart evidence: MES Sep 2026 contract).

| Element | Current usage |
|---|---|
| Trend | Moving-average ribbon (green = up, dark red = down) plus a single white MA |
| Order blocks | Zones drawn at supply/demand, currently overlaid with horizontal levels |
| Volume profile | **Fixed Range VP**, manually anchored: last swing high → current bar, or last swing low → current bar. Also anchored across ranges. |
| Confluence thesis | **POC overlapping an order block = a stronger zone.** Trader's own observation. |
| Confirmation | RSI, Live RVOL (0.6 at time of capture — below-average participation) |
| **Entry** | **At 50% of the order block** — the "mean threshold", marked by a dashed midline |
| Setup type | Trend continuation: retracement back into the OB that originated the move |
| Execution | Bracket orders placed directly on chart: 5 contracts, −$100 stop, +$750 target |

The POC-over-OB confluence idea is the strongest thing in this description and should become
a first-class scored input, not an afterthought. Two independent methods — traded volume
concentration and price-structure imbalance — pointing at the same price is a genuinely
different signal from either alone.

---

## 2. The binding constraint: contracts × stop is fixed

This is the central finding, and it is arithmetic, not opinion.

With MES at **$5/point** and a **$100 per-trade risk** budget (from the $200 daily cap ÷ 2
losers before lockout):

> **contracts × stop-in-points = 20** — always.

And to reach the **$450 daily target**:

> **contracts × net-points-per-day = 90** — always.

Which produces this table. ES 15m ATR is roughly 7–12 points in normal volatility:

| Contracts | Stop for $100 | Stop ÷ 15m ATR (~10 pt) | Verdict | Net pts/day for $450 |
|---|---|---|---|---|
| 1 MES | 20.0 pt | 2.0× | Survivable | 90 |
| 2 MES | 10.0 pt | 1.0× | Marginal | 45 |
| 3 MES | 6.7 pt | 0.67× | Too tight | 30 |
| **5 MES** | **4.0 pt** | **0.4×** | **Noise** | **18** |

**The chart's bracket is 5 MES with a $100 stop — a 4-point stop, 16 ticks.** On 15m MES that
is under half a single bar's typical range. During the selloff visible in the screenshot,
individual 15m bars span 15–25 points. A 4-point stop inside those bars is not a risk
control; it is a coin flip on tick sequencing. The trade is stopped out by noise
irrespective of whether the directional read was correct.

The +$750 target is 30 points — a 7.5:1 reward-to-risk. That number looks excellent and is
precisely the trap: it requires price to travel 7.5 stop-widths in favour without ever
retracing one stop-width against. On 15m, 4-point retracements happen constantly inside
winning moves. The bracket is geometrically near-unfillable.

**This is very likely the primary reason the strategy "isn't working" — and it is not a
signal-quality problem.** No entry logic survives a stop set below the instrument's noise
floor. Before touching the indicator, the sizing has to be fixed.

### The vice

Adding contracts lowers the points needed per day (good) but tightens the stop
proportionally (bad). Win rate collapses faster below ~1.5× ATR than the point requirement
falls. The optimum sits at **1–2 MES**, which is where the real cost shows up: **45–90 net
points per day** on 15m. That is a large number.

### R is invariant

Required daily performance is **$450 ÷ $100 = 4.5R per day**, and contract count does not
change it. Sizing only determines whether the stop is survivable. The only real levers are
trades per day, win rate, and R per winner.

On 15m RTH (08:30–15:00 = 26 bars), a POC+OB confluence system realistically produces 1–3
qualifying setups per day. At 3 trades/day, 50% win rate, 3R winners: `1.5×3 − 1.5×1 = 3R`
≈ $300/day. At 2 trades/day: ≈ 2R = $200/day.

**Honest projection: $200–300/day is the plausible ceiling for this approach on 15m.
$450 is roughly 1.5–2× that.** Phase 5 tests it rather than assuming it, but the plan should
not be built on the expectation that the target is reachable as stated. Options if it is
not: accept a lower daily target, add a second timeframe for more setups, or accept a
higher daily loss cap to permit larger size. Those are trade-offs for the trader to choose —
they are not something to engineer around silently.

---

## 3. Defects visible in the screenshot

Evidence-based, from what the chart shows:

1. **Signals fire against the trend filter.** Blue up-arrows appear during the selloff while
   the MA ribbon is dark red. Whatever generates the arrows is not gated by the ribbon. This
   is the most visible logic defect and the easiest to fix.
2. **No signal cooldown.** Arrows cluster several bars apart in both directions through the
   drop — classic whipsaw. One signal per structural event is needed, not one per bar that
   meets the condition.
3. **Counter-trend entries into an impulsive move.** Multiple long signals fire into a fast
   decline. Needs either a "wait for the impulse to complete" rule or a volatility-expansion
   lockout.
4. **The Fixed Range VP is stale.** The profile is anchored over the left-hand consolidation,
   but price has since broken well below it. Its POC no longer describes where volume is
   trading now. Re-anchoring from the swing high that began the decline would give a POC
   relevant to current price — which is exactly the trader's stated manual process, applied
   more often than by hand.
5. **RVOL 0.6.** Below-average participation. Whether low RVOL should suppress entries is an
   open question for Phase 2, but it should be measured.

*Caveat:* the arrow-generating indicator is not identified from the image alone. Items 1–3
describe observed behaviour; the cause needs the source.

---

## 3b. The working setup (second screenshot) — what it defines

A cleaner chart: no signal arrows, no volume profile, manually drawn OB. The trader reports
this one as working "almost perfectly". It pins down several rules the first chart could not.

**The order block is a multi-candle zone at the *origin* of the impulse.** Drawn across the
cluster of candles that preceded the decline, not a single candle. The zone spans roughly
7742–7760.

**Entry is at the 50% level, not the proximal edge.** The dashed midline is the trigger.
This is the ICT "mean threshold" convention. The trade-off is explicit and must be modelled:
a better fill price and a tighter stop, at the cost of setups where price rejects from the
proximal edge and never fills. **The backtest has to count the misses, not just the fills** —
comparing 50%-entry against proximal-edge entry on identical zones is a specific experiment
worth running in Phase 5.

**Sequence:** downtrend → impulsive leg down out of the zone → extended base → rally back
into the origin zone → expectation of continuation down.

### The multi-timeframe tension this exposes

Price retraced from ~7760 to ~7660 and back to ~7747 — roughly an **87% retracement** of the
impulse. On the right side of the chart the 15m ribbon has turned green and price sits above
the white MA. **So the 15m trend filter says up while the setup is a short.**

That is not a contradiction in the trader's method — it means the ribbon is being used for
*timing*, not for *bias*. The "trend" in trend-continuation refers to a higher-timeframe
structure, while the 15m ribbon flips during any deep retracement by construction.

**Architectural consequence: the trend engine must be multi-timeframe.** HTF (60m or 4H)
establishes directional bias and gates which side of OBs are tradeable; 15m handles entry
timing and confirmation. A single-timeframe ribbon filter would have vetoed this setup. This
also revises the read on the first screenshot — the arrows firing against the ribbon may be
less wrong than they appeared, though the clustering and lack of cooldown still stand.

**Open risk on this specific setup:** an 87% retracement is deep. Much beyond ~79% and many
practitioners stop treating it as a continuation and start treating it as a failed leg. Two
things need resolving in Phase 2: whether a maximum retracement depth invalidates the zone,
and how long an OB stays valid — the base here ran for a very large number of bars before
price returned.

---

## 4. What this implies for the build

**Auto-anchored volume profile.** The trader anchors manually from the last swing point.
`ta.pivothigh` / `ta.pivotlow` detect that automatically, so the profile re-anchors on every
confirmed swing and the POC is never stale. This directly automates the existing manual
process and is a strong candidate for the highest-value feature in the project.

Pine implementation note: TradingView's built-in Fixed Range Volume Profile is **not readable
from Pine**. The profile must be computed in-script by binning volume across price levels,
using `request.security_lower_tf()` for intrabar resolution. This is feasible — many
open-source Pine profiles do it — but it is bounded by intrabar data caps and the 500-object
drawing limit. Bin count will need tuning. Scope this before promising it.

**Confluence scoring, not boolean AND.** Rather than requiring every condition, score a zone:
OB present, POC within N ticks of the OB, trend agreement, RVOL, session window. Enter above
a threshold. This makes the POC+OB overlap the trader identified into a measurable weight and
lets the backtest reveal which components actually carry the edge.

**Sizing is derived, never fixed.** Position size must be computed from stop distance so that
dollar risk stays constant: `contracts = floor(riskDollars / (stopPoints × 5))`, with the
stop set at 1.5–2× ATR(15m). This structurally prevents the 5-contract/4-point configuration
from recurring. Cap contracts so the daily loss limit cannot be breached by a single trade.

---

## 5. Open questions for the trader

1. What generates the arrows — a public indicator, purchased, or self-written? Source
   changes whether Phase 4 fixes or rebuilds it.
2. Which MA ribbon and settings? It becomes the 15m timing layer.
3. **What is the HTF bias drawn from** — 60m, 4H, daily structure, or discretionary read?
   This is now the most important open question: it determines the trend engine's top layer.
4. Zone boundaries: **wick or body**? The 50% is measured between them, so this directly
   moves every entry price.
5. Zone invalidation: first touch, close through, or full sweep? And does an OB expire after
   N bars, or stay valid indefinitely until mitigated?
6. Maximum retracement depth before a continuation setup is abandoned — or is there none?
7. Where does the stop sit relative to the zone — beyond the distal edge, beyond the wick,
   or a fixed ATR multiple?
8. Is the 5-contract/$100-stop bracket a deliberate choice or a platform default?
9. RTH only, or is Globex traded too?
10. On the "almost" in *working almost perfectly* — what fell short on that trade? Fill,
    target, stop placement, or timing?
