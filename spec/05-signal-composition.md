# 05 — Signal composition

**Status:** draft for sign-off.
**Depends on:** `01-session-engine`, `02-orderblock-engine`, `03-liquidity-map`,
`04-risk-engine`.
**Consumed by:** both entry scripts.

This module owns the state machine, the attribute tagging, and the interfaces the other four
must satisfy. It contains no trading rules of its own — it sequences the others.

---

## 1. The baseline is direction-agnostic

Per `00-concept.md` §2.1: inside the entry window, take **every** qualifying setup, long and
short, with **no directional bias filter**. Tag each trade with pre-registered attributes and
let Phase 5 determine which conditions separate winners from losers.

This establishes a baseline, makes any future filter's contribution computable as
`filtered − baseline`, and reveals whether the edge is mechanisable at all. If
direction-agnostic trading is break-even and only the discretionary subset works, the edge
lives in the trader's judgement — which is worth discovering from a backtest rather than
after the system is built.

**No bias rule is to be added to this module without a Phase 5 result justifying it.**

---

## 2. The state machine

From the trader's own description of the working setup (`00-concept.md` §3.1):

> liquidity sweep → internal structure break → retest of the resulting OB → confirmation

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
  ┌──────────┐  sweep    ┌─────────┐  BOS     ┌───────────┐
  │  0 IDLE  │──────────▶│1 SWEPT  │─────────▶│ 2 ARMED   │
  └──────────┘           └─────────┘          └───────────┘
        ▲                     │                     │
        │                     │ timeout             │ price hits 50%
        │                     ▼                     ▼
        │                 (reset)            ┌───────────┐
        │                                    │ 3 TRIGGER │
        └────────────────────────────────────└───────────┘
                    fill, invalidate, or timeout
```

| State | Advance condition | Records |
|---|---|---|
| **0 · Idle** | `03` reports a sweep of a tracked level | direction, level, bar |
| **1 · Swept** | `02` reports a BOS *against* the sweep direction within `BOS_MAX_BARS` | the OB created by that break |
| **2 · Armed** | Price reaches the zone's 50%, refined per `02` §5 | zone, entry, timeframe |
| **3 · Trigger** | `04` returns a valid size and target | order |

**Reset from any state:** timeout, zone invalidated (close beyond distal edge), an opposing
sweep, session window closes, or the daily cap is hit.

**Only one machine runs at a time.** Concurrent setups are not tracked — this matches the
one-position-at-a-time rule in `04-risk-engine` §1 and keeps risk accounting exact. If a
second sweep occurs while armed, the existing setup is kept and the new one dropped; the
count of dropped setups is reported, because a high count would mean the single-machine
simplification is costing real opportunities.

### 2.1 The sweep precondition is itself a hypothesis

Requiring a sweep is the trader's observation, not an established fact. `REQUIRE_SWEEP`
(default `true`) makes it switchable, and **the baseline is run both ways**. If results are
equivalent without it, the sweep stage is complexity carrying no weight and should go.

---

## 3. Confirmation filters — tagged, not enforced

RVOL and RSI are recorded as attributes and **do not gate entries in the baseline**.

The reason is concrete: RVOL was **0.6** — below average — on the setup the trader identified
as working (`00-concept.md` §3.1). A plausible-looking `RVOL > 1.0` filter would have
rejected it. Intuition about which confirmations help is exactly what the attribute
framework exists to test rather than assume.

---

## 4. Attribute tagging

Every trade *and every rejected setup* records the pre-registered attribute set from
`00-concept.md` §2.2. Written to `reports/attributes-<run>.csv`, one row per setup.

**Rejected setups are recorded too, with the rejection reason.** A system's skips are as
informative as its fills — a rule rejecting 90% of setups for one reason is a rule worth
examining, and it cannot be seen from filled trades alone.

```
setupId, timestamp, direction, state_reached, outcome,
  rejectReason,          // null | zoneTooWide | belowMinTargetR | dailyCapReached
                         // | outsideWindow | positionOpen | noRefinedZone
  sessionId, minutesSinceOpen,
  preOpenDirection, preOpenRangeAtr, preOpenSwept, sweepTicks, sweepReclaimBars,
  londonDirection, londonRangeAtr,
  agreesWithLondon, opposesPreOpen,
  zoneWidthAtr, zoneTimeframe, zoneAgeBars, retracementPct, impulseAtr,
  pocDistanceTicks, hvnInPath, lvnInPath,
  rvol, rsi, atrRegime, dayOfWeek,
  entry, stop, target, contracts, riskUsd, targetR, realisedR, pnlUsd
```

`state_reached` matters: a setup that swept but never got its BOS is a different failure from
one that armed and never filled. Recording where each setup died is what makes the funnel in
§6 possible.

---

## 5. Interfaces the other modules must satisfy

```
01-session-engine   → sessionId, inEntryWindow, minutesSinceOpen, newExchangeDay,
                      preOpen*/london*/ib*/on*/pd* levels
02-orderblock-engine→ activeZones : array<Zone>, onBosDetected(direction, zone),
                      refineZone(zone) → Zone
03-liquidity-map    → trackedLevels, onSweep(level, direction),
                      poc, hvnBins, lvnBins, nearestLvn(direction)
04-risk-engine      → stopPrice(zone, dir), sizePosition(entry, stop, dayPnl),
                      targetPrice(entry, stop, dir), tradingHalted
```

These signatures are the contract. A module changing its output shape is a spec change, which
is a head-of-engineering decision — not something an implementer resolves locally.

---

## 6. Ordering of Phase 5 measurements

Deliberate, because measuring in the wrong order wastes effort on a system that may not clear
its first hurdle:

1. **Setup frequency.** How many setups per day survive all three OB qualifiers, inside the
   window? Report *before any P&L*. The whole daily target rests on this number
   (`00-concept.md` §5), and if it is below ~1/day the target is unreachable no matter how
   good the entries are.
2. **The funnel.** Sweeps detected → BOS follow-through → armed → filled → won. Where setups
   die tells you which stage to work on.
3. **Baseline P&L**, direction-agnostic, costs applied, in-sample and out-of-sample separate.
4. **Attribute slices** — only the pre-registered set, out-of-sample confirmation required.
5. **Variant comparisons:** `REQUIRE_SWEEP` on/off · 15m vs 5m-refined entry · 50% vs
   proximal-edge entry · scale-out on/off · afternoon window on/off · the four target modes.

Steps 1 and 2 are cheap and can invalidate the concept before any tuning happens. Run them
first.

---

## 7. Test cases for the Python reference

1. Full happy path: sweep → BOS → armed → 50% touched → order with correct size
2. Sweep, then no BOS within `BOS_MAX_BARS` → reset to Idle, no trade
3. Sweep, BOS, then close through the distal edge before the 50% → reset, no trade
4. Armed when the session window closes → reset, no trade
5. Armed when the daily cap is reached → reset, rejection logged as `dailyCapReached`
6. Second sweep while armed → ignored, dropped-setup counter increments
7. `REQUIRE_SWEEP = false` → BOS alone advances from Idle
8. Attribute row written for every setup including rejected ones, with correct
   `state_reached` and `rejectReason`
9. **Repainting regression:** bar-by-bar state sequence identical to full-history processing
10. Signal on the same bar as a daily reset → reset applied first, then evaluated

---

## 8. Open items

1. `BOS_MAX_BARS` — how long after a sweep the structure break may arrive. No default yet;
   measure the distribution on fixtures before choosing.
2. "Internal" structure break: the trader said *internal*, implying a minor swing rather than
   a major one. Needs a concrete definition — probably a smaller `PIVOT_LEFT`/`PIVOT_RIGHT`
   than the one used for major structure, but this should be checked against their charts.
3. Whether an armed setup should survive across the session boundary when the window closes
   mid-setup. Currently it resets.
