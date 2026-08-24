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

These are two distinct setups with different logic. What distinguishes an A day from a B day
*at 08:35*, forward-looking rather than in hindsight, is the hardest rule in the project.

**It is deliberately not being answered yet.** See §2.1.

### 2.1 The bias rule is deferred — measure first, filter second

Writing a directional rule now would mean guessing one and then discovering whether the guess
was any good. Instead, the **baseline system is direction-agnostic**: inside the session
window, take *every* qualifying OB setup, long and short, with no bias filter at all.

Every trade is then tagged with a set of **pre-registered attributes**, and Phase 5 slices
results by those attributes to see which ones actually separate winners from losers. The data
proposes the bias rule; it is not assumed.

This is better than guessing for three reasons:

1. **It establishes a baseline.** Does the OB + 50%-entry concept have an edge at all,
   before any directional overlay? If it does not, no bias filter is going to rescue it, and
   that is worth knowing in week one rather than month three.
2. **It measures the filter's contribution.** The value of a bias rule is
   `filtered result − baseline result`. Without a baseline that number cannot be computed.
3. **It tests whether the edge is mechanisable at all.** If direction-agnostic trading is
   break-even and only the discretionary subset works, the edge lives in the trader's
   judgement rather than in the rules — which means an automated version will not reproduce
   it. Better to learn that from a backtest than after the whole system is built.

**Nothing else is deferred.** The baseline still needs complete, exact rules for: OB
qualification, session windows, stop placement, target placement, and sizing. Only the
directional filter waits.

### 2.2 Pre-registered attributes

**These are fixed before any results are seen.** Attributes are chosen now, in advance,
precisely so that Phase 5 cannot go fishing through arbitrary slices until something looks
good. That is how curve-fitting gets laundered into a "discovery", and `CLAUDE.md` forbids it.

| Group | Attributes |
|---|---|
| **Time** | Session at entry (Asia / London / NY first hour / midday / afternoon); minutes since NY open |
| **Pre-open** | Push direction (sign of net change 06:00–08:30 CT); push magnitude in ATR; whether the pre-open high/low was swept after 08:30 and by how many ticks; whether that sweep was reclaimed within N bars |
| **London** | Net session direction; session range in ATR |
| **Alignment** | Trade agrees with London direction (bool); trade opposes the pre-open push (bool) |
| **Zone** | Width in ATR; bars since formation; retracement depth into the impulse at entry (%); impulse leg size in ATR |
| **Volume profile** | Distance from POC in ticks; HVN between entry and target (bool); LVN between entry and target (bool) |
| **Context** | RVOL at entry; ATR regime bucket; day of week |

Discipline for Phase 5, non-negotiable:

- Only these attributes are tested. Adding one later requires saying so in the report.
- Any filter that looks promising in-sample must **hold out-of-sample** before it is adopted.
- A filter needs a *mechanism*, not just a number. "Tuesdays are good" is noise until there
  is a reason.
- The report states how many attributes were examined, so the reader can discount for
  multiple comparisons.

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

### Live worked example — the actual defect

Reconstructed exactly from the fifth screenshot, where the price axis is legible.

Short 5 MES, +$87.50 unrealised = **3.5 points onside** at 7677.25. So:

| | Price | Distance from entry |
|---|---|---|
| OB zone high | 7684.00 | +3.25 |
| **Entry (50% of OB)** | **7680.75** | — |
| OB zone low | 7677.50 | −3.25 |
| **Stop** | **7684.00** | **+3.25 pt = $81 on 5 MES** |
| Target (buy limit) | 7651.00 | −29.75 pt = $744 on 5 MES |

The zone is **7677.50 – 7684.00**, 6.5 points wide, and 7680.75 is its exact midpoint —
confirming the 50% entry rule. And that exposes the real defect:

> **The stop is placed exactly at the order block's distal edge.**

The top of the zone is the single most likely price in the entire chart to be traded through.
A wick into the zone extreme is not an anomaly — it is the *normal* behaviour of price
testing a level, and it happens on most zones that ultimately hold. Placing the stop there
converts the most probable event into a loss. This is a structural error, not a sizing
preference, and it explains the trader's own forecast that the trade will be stopped despite
being onside.

**It is also not really a "5 contracts is too many" problem.** The causation runs the other
way: the stop was placed at an arbitrary dollar amount, the zone width was never consulted,
and the size followed from that. Fix the stop placement and the size falls out correctly.

### The corrected geometry

Stop beyond the zone's distal edge plus a buffer — say 7687.00, three points clear of the
zone high — then derive size from that distance at the same $100 risk:

| | Value |
|---|---|
| Stop distance | 7687.00 − 7680.75 = **6.25 pt** |
| Size | `floor(100 / (6.25 × 5))` = **3 MES** |
| Risk | 6.25 × 3 × $5 = **$93.75** |
| Reward at 7651.00 | 29.75 × 3 × $5 = **$446.25** |
| R:R | **4.76 : 1** |

**One correctly structured trade is worth $446 — essentially the entire daily target.** The
trade idea, the zone, and the target were all fine. Only the stop placement was wrong, and it
was wrong in the way that guarantees the maximum possible stop-out rate.

### What this revises

Break-even win rate at 4.76:1 is `1 / (1 + 4.76) ≈ 17.4%`. Anything above that is profitable,
which is a far more forgiving bar than the earlier analysis implied. **Per-trade expectancy is
not the problem.**

The remaining constraint is **frequency**. At a realistic 30–35% hit rate on a 30-point
target, expectancy is roughly 0.7–1.0R per trade. Reaching 4.5R/day then needs 4–5 trades,
and the NY first hour yields 1–2. So:

- **Per-trade geometry: solved.** Stop beyond the zone, size derived from it.
- **Daily target: still short.** ~1–2R/day ≈ $150–250 from one window.

The gap closes through frequency or through exit management, not through tighter stops. Two
candidates for Phase 2: adding the 13:00–15:00 window, and **scaling out** — partial at
1.5–2R where hit rates are high, runner to the full target. Scaling raises the effective win
rate and smooths the daily distribution, which matters a great deal when a −$200 cap can end
the day.

**Consequence for the build:** the risk engine (`spec/04-risk-engine.md`) is the **first**
module to spec and implement, ahead of the OB engine. Any backtest of entry logic with the
stop inside the zone will show it failing regardless of merit, because the stop rather than
the rule determines the outcome. Stop placement must be a *derived* property of the zone
geometry, and position size a derived property of the stop — never inputs set by hand.

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

Deliberately deferred to Phase 5 (see §2.1) — **not blocking**:

- What distinguishes an open-reversal day from a London-continuation day at 08:35. Recorded
  as attributes now, resolved from data later.
- How much of a pre-open push counts, and against which level.

Blocking for Phase 2 — the baseline cannot be specced without these:

1. **OB qualification.** Not every candle cluster before a move is a tradeable zone. What
   makes the impulse leaving it "impulsive" — a minimum size in ATR, a displacement candle,
   an unfilled imbalance? This is the rule that decides how many setups per day exist, so it
   drives everything downstream.
2. OB invalidation: first touch, close through, or full sweep? Do zones expire after N bars?
4. Stop placement: beyond the distal edge of the zone, beyond the wick, or a fixed ATR
   multiple?
5. **Target placement relative to structure.** In the live example the buy limit sits at
   7651.00 while the recent swing low is 7657.75 — the target is **6.75 points beyond the
   low**, so the trade requires that low to break rather than merely to be retested. That is
   defensible as a liquidity-sweep target (resting stops sit below an obvious low, and price
   often spikes through), but it is a materially different bet from taking profit just above
   the low. Both need testing: target *before* the level vs. *beyond* it. Candidates for the
   rule: fixed R multiple, the next LVN, the opposing OB, a session level, or a fixed offset
   past the prior swing.
6. Is the afternoon window (13:00–15:00) worth including, or strictly the first hour?
7. Maximum retracement depth before a continuation setup is abandoned — or is there none?
8. Which MA ribbon and settings are on the chart? Still useful as a 15m timing filter even
   though bias comes from the session engine.
