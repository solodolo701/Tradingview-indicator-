# 00 — Concept and constraints

**Status:** working draft. Seeded from the trader's own charts and answers, 2026-08-24.
Phase 1 research fills the gaps; Phase 2 turns this into executable rules.

Instrument **MES**, primary timeframe **15m**.

---

## 1. The method, as actually traded

| Layer | Rule |
|---|---|
| **Directional bias** | Session-derived from price action — see §2. Not indicator-derived. |
| **Primary window** | **First hour of the New York open**, 08:30–09:30 CT |
| **Secondary** | Trend continuation in the direction of the **London session** move |
| **Not traded** | **Asia session.** A setup outside the window is not a setup. |
| **Order blocks** | Multi-candle zone at the *origin* of an impulse. **Bounds: candle high to candle low** (wick to wick). |
| **Entry** | **50% of the OB** — the mean threshold, midpoint of the wick-to-wick range |
| **Volume profile** | Fixed Range VP, anchored **from the last swing high (or low) to the current bar**. Also used across ranges. |
| **Confluence** | POC overlapping an OB = stronger zone. **HVN against the trade = blocker.** |
| **Confirmation** | RSI, Live RVOL |
| **Execution** | Chart brackets via Tradovate |

---

## 2. The session bias engine — the top layer

The trader's bias is **session-structural, not indicator-based**. This is a better foundation
than an HTF moving average and it is cleanly mechanisable in Pine via `time()` windows. It
replaces the "HTF ribbon" idea entirely.

All times America/Chicago (CME time).

| Window | Time | Role |
|---|---|---|
| Asia | 19:00 – 02:00 | **Excluded.** No entries. |
| London | 02:00 – 08:30 | Establishes the continuation direction |
| Pre-open push | ~06:00 – 08:30 | The directional push before the NY open |
| **NY first hour** | **08:30 – 09:30** | **Primary trading window** (also the Initial Balance) |
| Afternoon | 13:00 – 15:00 | Candidate secondary window — to be tested |

### The two setups

**A — Open reversal.** Price pushes one direction ahead of the NY open, then reverses hard
into/after the open. Bias is *against* the pre-open push. This is the pattern commonly called
a judas swing or opening liquidity sweep: the pre-open move runs stops, then the real
direction asserts itself. Mechanically it needs: measure the pre-open push direction and
magnitude, detect a sweep of the pre-open extreme after 08:30, then take OBs on the
opposite side.

**B — London continuation.** Where no reversal occurs, bias follows the London session's
net direction, and OBs are taken on that side only.

These are two distinct setups with different logic and they should be **specced, coded, and
backtested separately** before any attempt to run them together. Setup A is conditional on a
sweep; Setup B is conditional on the absence of one. Conflating them hides which one carries
the edge.

**Open question:** what distinguishes an A day from a B day *at 08:35*, in advance rather
than in hindsight? This is the single hardest rule in the project and Phase 2 has to answer
it with something testable — a sweep of the pre-open high/low by more than X ticks followed
by a reclaim within N bars, or similar. Without a forward-looking trigger, Setup A is
unbacktestable.

---

## 3. Order block rules (settled)

- **Zone:** the candle cluster at the origin of the impulsive leg
- **Bounds:** candle **high to low**, wicks included
- **Entry:** **50% level** = `(zoneHigh + zoneLow) / 2`
- **Setup shape:** price leaves the zone impulsively, later retraces back into it, continuation expected

Wick-to-wick bounds make the zone wider than a body-based definition, so the 50% sits deeper
and fills more often — at the cost of a worse average price and a wider stop. That trade-off
is now fixed by the trader's choice and should not be silently re-litigated in code.

**The backtest must count missed fills.** A 50% entry rule generates setups where price
reacts off the proximal edge and never reaches the midpoint. Counting only filled trades
inflates the apparent win rate of the rule. Phase 5 runs 50%-entry against proximal-edge
entry on identical zones as a controlled comparison.

**Still open:** invalidation (first touch / close through / full sweep), whether zones expire
after N bars, and where the stop sits relative to the zone.

---

## 4. The volume profile layer

Anchored from the **last swing high or low to the current bar** — which `ta.pivothigh` /
`ta.pivotlow` can detect automatically, so the profile re-anchors on every confirmed swing
and never goes stale. This directly automates the trader's manual process and is a strong
candidate for the highest-value feature in the build.

The profile contributes **three distinct signals**, not one:

| Node | Meaning | Use |
|---|---|---|
| **POC** | Highest-volume price | Overlapping an OB → confluence, strongest zone |
| **HVN** | High-volume shelf | **Barrier.** Price stalls here. Against the trade → veto or downgrade. |
| **LVN** | Low-volume gap | Price travels fast through. Natural target, poor place to sit. |

The third screenshot is the case that establishes the HVN rule: price cleared the OB's 50%
— which read as bullish continuation — but **an HVN built during the prior downtrend capped
the rally**. So the profile is not merely a confluence bonus on top of the OB; it can
**override the OB read**. That makes it an independent input in the scoring model, with veto
power, rather than a tiebreaker.

Pine note: TradingView's built-in Fixed Range Volume Profile is **not readable from Pine**.
The profile must be computed in-script by binning volume across price levels, using
`request.security_lower_tf()` for intrabar resolution. Feasible — many open-source Pine
profiles do it — but bounded by intrabar data caps and the 500-drawing-object limit. HVN and
LVN classification needs a defined threshold (e.g. bins above/below X% of POC volume). Scope
this properly before committing to it.

---

## 5. The binding constraint: contracts × stop is fixed

This is the central finding, and it is arithmetic, not opinion.

MES is **$5/point**. With **$100 per-trade risk** (the $200 daily cap ÷ 2 losers):

> **contracts × stop-in-points = 20** — always.
> **contracts × net-points-per-day = 90** — to reach the $450 target.

ES 15m ATR is roughly 7–12 points in normal volatility:

| Contracts | Stop for $100 | Stop ÷ 15m ATR (~10 pt) | Verdict | Net pts/day for $450 |
|---|---|---|---|---|
| 1 MES | 20.0 pt | 2.0× | Survivable | 90 |
| 2 MES | 10.0 pt | 1.0× | Marginal | 45 |
| 3 MES | 6.7 pt | 0.67× | Too tight | 30 |
| **5 MES** | **4.0 pt** | **0.4×** | **Noise** | **18** |

The observed bracket — 5 MES, $100 stop — is a **4-point stop, 16 ticks**. Under half the
range of a single 15m bar during an impulsive move. It is not a risk control at that width;
it is a coin flip on tick sequencing, and a correct directional read does not help.

The paired +$750 target is 30 points, a 7.5:1 reward-to-risk. That ratio is exactly the trap:
it needs price to travel 7.5 stop-widths in favour without one stop-width against. On 15m,
4-point retracements occur constantly inside winning moves. The geometry is near-unfillable.

**The vice.** More contracts lowers the points needed per day but tightens the stop
proportionally, and win rate collapses faster below ~1.5× ATR than the requirement falls.
The optimum is **1–2 MES**, which is where the real cost appears: **45–90 net points/day**.

**R is invariant.** Required daily performance is `$450 ÷ $100 = 4.5R/day` regardless of
contract count. Sizing only decides whether the stop survives. The only levers are trades
per day, win rate, and R per winner.

Trading one window (NY first hour) yields perhaps 1–2 qualifying setups per day. At 2
trades/day, 50% win rate, 3R winners: `1×3 − 1×1 = 2R` ≈ $200/day.

**Honest projection: $200–300/day is the plausible ceiling on this approach. $450 is
1.5–2× that**, and the single-window constraint tightens it further. Phase 5 measures it
rather than assuming it. If the target proves unreachable, the levers are: accept a lower
daily target, add the afternoon window for more setups, or raise the daily loss cap to permit
size. Those are the trader's trade-offs to choose — not something to engineer around silently
by sizing up.

---

## 6. Chart observations — corrected

**Correction to an earlier reading.** The arrows in the first screenshot were initially read
as indicator signals firing against the trend filter. They are **Tradovate trade open/close
markers** — the trader's own fills. The "signals fire against the ribbon" and "no signal
cooldown" observations were therefore wrong and are withdrawn.

The corrected reading **strengthens the sizing finding rather than weakening it**: a tight
cluster of entry and exit markers through a fast decline is a record of repeated entries
being stopped out in quick succession. That is precisely the signature a 4-point stop
produces on 15m. The first chart is direct evidence for §5.

Standing observations:

- **The Fixed Range VP was stale** in the first screenshot — anchored over the left-hand
  consolidation while price had broken well below it, leaving its POC describing a regime
  price had left. Auto-anchoring on the last confirmed swing fixes this.
- **RVOL 0.6** — below-average participation on that move. Whether low RVOL should suppress
  entries is a Phase 2 question, but it should be measured.
- **The "almost" on the working setup** was that it occurred during the **Asia session**,
  outside the traded window. Not a logic failure — a session-filter confirmation. It argues
  for the indicator marking valid setups outside the window differently (visible, but not
  alertable) so out-of-window setups never present as tradeable.

---

## 7. Architecture implications

1. **Session engine is the top layer**, not an HTF indicator. Bias, window gating, and the
   Asia exclusion all derive from `time()` windows in America/Chicago.
2. **Setups A and B are separate modules**, separately backtested. Do not merge before both
   have standalone results.
3. **Confluence scoring, not boolean AND.** Score each zone: OB present, POC within N ticks,
   session bias agreement, RVOL, HVN opposition (negative weight, possibly a veto). Enter
   above a threshold. This makes the trader's own observations measurable and lets the
   backtest reveal which components carry the edge.
4. **Sizing is derived, never fixed.** `contracts = floor(riskDollars / (stopPoints × 5))`
   with the stop at 1.5–2× ATR(15m), capped so one trade cannot breach the daily limit.
   This structurally prevents the 5-contract/4-point configuration from recurring.
5. **Auto-anchored volume profile** on the last confirmed pivot, classifying POC/HVN/LVN.

---

## 8. Open questions

1. **What distinguishes an open-reversal day from a London-continuation day at 08:35?**
   The hardest and most important rule. Needs a forward-looking, testable trigger.
2. How much of a pre-open push counts — a minimum range, or a sweep of a specific level
   (pre-open high/low, ONH/ONL, prior day high/low)?
3. OB invalidation: first touch, close through, or full sweep? Do zones expire after N bars?
4. Stop placement: beyond the distal edge of the zone, beyond the wick, or a fixed ATR
   multiple?
5. Target: fixed R multiple, the next LVN, the opposing OB, or a session level?
6. Is the afternoon window (13:00–15:00) worth including, or strictly the first hour?
7. Maximum retracement depth before a continuation setup is abandoned — or is there none?
8. Which MA ribbon and settings are on the chart? Still useful as a 15m timing filter even
   though bias comes from the session engine.
