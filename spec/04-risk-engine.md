# 04 — Risk engine

**Status:** draft for sign-off. First module to implement, ahead of the OB engine.
**Depends on:** a zone (bounds + timeframe) and a direction from the signal layer.
**Consumed by:** `05-signal-composition`, both entry scripts.

---

## Why this module comes first

Analysis in `00-concept.md` §5 established that the live trade failed on stop *placement*,
not on entry logic: the stop sat exactly on the order block's distal edge, the most likely
price on the chart to be traded through. Any backtest of any entry rule under that condition
fails regardless of merit, because the stop rather than the rule decides the outcome.

So stop placement and sizing must be **derived properties**, never hand-set inputs. This
module owns that derivation and is the precondition for evaluating anything else.

---

## 1. Principles

1. **The stop clears the zone that generated the entry, on that zone's own timeframe.**
   A 15m entry uses a 15m-derived stop; a nested 5m entry uses a 5m-derived stop. Mixing
   them is the specific error that produced the failing trade (`00-concept.md` §3.2).
2. **Size is derived from stop distance.** Never fixed, never hand-entered.
3. **The daily cap cannot be breached by construction**, not merely by a halt check fired
   after the fact.
4. **One position at a time.** No pyramiding, no simultaneous longs and shorts. This keeps
   the risk accounting exact and is how the trader operates.

---

## 2. Parameters

| Name | Default | Range | Notes |
|---|---|---|---|
| `POINT_VALUE` | 5.0 | — | MES. ES is 50.0. Not an input — derive from `syminfo.pointvalue`. |
| `RISK_PER_TRADE` | 100.00 | 25–200 | USD |
| `MAX_DAILY_LOSS` | 200.00 | 50–1000 | USD, positive number |
| `DAILY_TARGET` | 450.00 | 100–2000 | USD |
| `ATR_LEN` | 14 | 5–50 | Computed on the *zone's* timeframe |
| `ATR_BUFFER_MULT` | 0.5 | 0.1–2.0 | Stop buffer beyond the zone edge |
| `MIN_STOP_TICKS` | 8 | 4–40 | Floor. Prevents an absurd stop from a degenerate zone. |
| `MAX_STOP_ATR` | 3.0 | 1.0–6.0 | Zones needing a wider stop are skipped, not shrunk. |
| `MAX_CONTRACTS` | 10 | 1–50 | Hard ceiling regardless of maths |
| `DAILY_RESET` | `exchangeDay` | fixed | **Settled.** CME 17:00 CT boundary. |
| `TARGET_MODE` | `opposingOb` | see §6 | **Settled default.** Variants still compared. |
| `TARGET_R` | 3.0 | 1.0–10.0 | Only when `TARGET_MODE = rMultiple` |
| `MIN_TARGET_R` | 1.5 | 0.5–5.0 | Skip if the target yields less than this. See §6.1. |
| `SCALE_OUT` | `false` | bool | See §6.2 |
| `SCALE_OUT_R` | 1.5 | 0.5–5.0 | Partial exit level |
| `SCALE_OUT_PCT` | 50 | 10–90 | Percent of position closed at the partial |

Every one of these is an input with `group=`, `tooltip=`, `minval` and `maxval` per house
style. No magic numbers in the logic.

---

## 3. Stop placement

```
stopPrice(zone, direction, zoneTimeframe):
    atr    = ta.atr(ATR_LEN)  evaluated on zoneTimeframe   // NOT the chart timeframe
    buffer = ATR_BUFFER_MULT * atr

    raw = direction == LONG
            ? zone.low  - buffer
            : zone.high + buffer

    // Enforce the floor, measured from the entry
    entry = (zone.high + zone.low) / 2
    if abs(entry - raw) < MIN_STOP_TICKS * syminfo.mintick
        raw = direction == LONG
                ? entry - MIN_STOP_TICKS * syminfo.mintick
                : entry + MIN_STOP_TICKS * syminfo.mintick

    return raw
```

**The buffer is not comfort padding.** A wick into the zone extreme is normal behaviour for a
level that ultimately holds. The buffer's job is to place the stop beyond the range of that
normal test, which is why it scales with ATR rather than being a fixed tick count.

`zoneTimeframe` must be the timeframe the zone was detected on. When the 5m refinement is
active, both the zone bounds and the ATR come from 5m.

---

## 4. Position sizing

```
sizePosition(entry, stop, dayPnl):
    stopPoints = abs(entry - stop)

    // Reject zones too wide to trade inside the risk budget.
    // Never shrink the stop to make a trade fit — that reintroduces the original defect.
    if stopPoints > MAX_STOP_ATR * atr
        return SKIP

    // The daily cap is enforced here, structurally.
    // dayPnl is negative when down; remaining shrinks as losses accumulate.
    remaining  = MAX_DAILY_LOSS + math.min(0, dayPnl)
    riskBudget = math.min(RISK_PER_TRADE, remaining)

    if riskBudget <= 0
        return SKIP                      // daily cap reached

    riskPerContract = stopPoints * POINT_VALUE
    contracts       = math.floor(riskBudget / riskPerContract)
    contracts       = math.min(contracts, MAX_CONTRACTS)

    if contracts < 1
        return SKIP                      // stop too wide for the budget

    return contracts
```

Two properties worth stating explicitly:

**The cap cannot be breached.** Because `riskBudget` is clamped to what remains of the daily
allowance, a second trade after a $120 loss risks at most $80. The cap is a consequence of
the sizing arithmetic rather than a halt that fires afterwards. Gap risk through the stop is
the only way to exceed it, and that must be reported as such rather than treated as a bug.

**A skip is a valid, correct outcome.** When a zone is too wide, the answer is no trade — not
a tighter stop. Tightening the stop to make the trade fit is precisely the failure this
module exists to prevent, and it must not appear anywhere in the implementation.

---

## 5. Daily guardrails

```
// Reset. DAILY_RESET = exchangeDay uses the CME session day (17:00 CT boundary);
// rthOpen resets at 08:30 CT instead.
newDay = DAILY_RESET == "exchangeDay"
            ? ta.change(time("D")) != 0
            : crossedTime(08:30, "America/Chicago")

var float dayStartEquity = strategy.netprofit
if newDay
    dayStartEquity := strategy.netprofit

dayPnl = strategy.netprofit - dayStartEquity     // realised only

lossLockout   = dayPnl <= -MAX_DAILY_LOSS
targetReached = dayPnl >=  DAILY_TARGET
tradingHalted = lossLockout or targetReached

if tradingHalted and strategy.position_size != 0
    strategy.close_all(comment = lossLockout ? "daily loss cap" : "daily target")
```

**Realised P&L (`netprofit`), not mark-to-market equity.** Open-trade risk is already bounded
by §4, so an unrealised drawdown mid-trade should not halt a position that is still working
its plan. Using `equity` would close trades on noise. This choice must be stated in every
report, since the two produce visibly different results.

⚠️ **`DAILY_RESET` is a genuine open question with real consequences.** `exchangeDay` (the
17:00 CT boundary) is standard P&L accounting. `rthOpen` matches how the trader actually
experiences a trading day. They disagree for any position spanning the boundary. Default is
`exchangeDay`; both get tested.

---

## 6. Exits

### 6.1 Target — open, specced as variants

`TARGET_MODE` is a testable enum, not a decision made in advance:

| Mode | Rule |
|---|---|
| `rMultiple` | `entry ± TARGET_R × stopDistance` — default, simplest to evaluate |
| `nextLvn` | The nearest low-volume node in the trade's direction |
| `opposingOb` | The next untested order block on the opposite side |
| `priorSwing` | The prior swing high/low, ± a fixed offset |

`00-concept.md` §8.5 records the live example's target at 7651.00 against a swing low of
7657.75 — **6.75 points beyond the low**, so that trade required the low to break rather
than merely be tested. `priorSwing` with a positive offset models that (a sweep target);
with a negative offset it takes profit before the level. **They are materially different
bets and both need measuring.**

**`opposingOb` is the settled default, and it carries a consequence:** the target distance
is *variable*, set by structure rather than by a chosen multiple. Some setups will present an
opposing block close enough that the reward does not justify the risk. Hence `MIN_TARGET_R`:

```
targetR = abs(target - entry) / abs(entry - stop)
if targetR < MIN_TARGET_R
    return SKIP
```

Two things follow. First, **skipping on poor R:R is a second legitimate reason to pass on a
setup**, alongside a zone too wide to size (§4) — both are cases where the correct action is
no trade. Second, because R now varies per trade, the "4.5R/day" framing from
`00-concept.md` §5 becomes an average rather than a per-trade constant, and reports must give
the **distribution of realised R**, not just its mean.

Where no opposing block exists within a reasonable distance, fall back to `rMultiple` at
`TARGET_R`. The fallback rate is itself worth reporting — if it fires on most trades, the
default is not really `opposingOb`.

### 6.2 Scale-out — optional mode

`00-concept.md` §5 identified frequency, not per-trade expectancy, as the constraint on the
daily target. Scaling out is one of the two candidate remedies:

```
if SCALE_OUT and not partialTaken and R_achieved >= SCALE_OUT_R
    strategy.close(qty_percent = SCALE_OUT_PCT, comment = "partial")
    partialTaken := true
    moveStopToBreakeven()
```

This raises effective win rate and smooths the daily distribution, which matters
disproportionately when a −$200 cap can end the day. It also lowers average R per trade.
Off by default; the on/off comparison is a headline Phase 5 result.

**Breakeven move:** only after the partial fills, never before. Moving to breakeven on an
unrealised threshold converts winners into scratches at exactly the noise frequency this
module is built to avoid.

---

## 7. Edge cases the implementation must handle

| Case | Required behaviour |
|---|---|
| Zone width 0 or negative | Reject the zone; log it. Indicates an upstream bug. |
| `stopPoints` rounds to 0 ticks | `MIN_STOP_TICKS` floor applies |
| Stop wider than `MAX_STOP_ATR × atr` | SKIP — never shrink the stop |
| `contracts` computes to 0 | SKIP |
| Remaining daily budget < 1 contract's risk | SKIP, and halt for the day |
| Signal fires while a position is open | Ignore. One position at a time. |
| Signal fires on the same bar as a daily reset | Reset first, then evaluate |
| Gap through the stop | Fill at the gap; report the overshoot. Not a bug. |
| ATR is `na` (insufficient history) | SKIP until ATR is valid |
| Position open when the target halt triggers | `close_all`, and it counts toward the day |

---

## 8. Test cases for the Python reference

Each becomes a pytest case in `tests/test_risk_engine.py`:

1. **The live example.** Zone 7677.50–7684.00, short, ATR 5.0, buffer 0.5×. Expect entry
   7680.75, stop 7686.50, distance 5.75 pt, **3 contracts**, risk $86.25.
2. **The historical failure reproduced.** Same zone, stop forced to 7684.00. Assert the
   engine *never* produces this — stop must always exceed `zone.high`.
3. **5m nesting.** Zone 7681.00–7684.00, ATR 2.5. Expect a tighter stop and **5 contracts**.
4. **Budget erosion.** `dayPnl = −120`. Assert `riskBudget = 80` and size reduces accordingly.
5. **Cap reached.** `dayPnl = −200`. Assert SKIP.
6. **Cap cannot be breached.** Random zone widths and a random loss sequence; assert
   cumulative realised loss never exceeds `MAX_DAILY_LOSS` absent a gap.
7. **Zone too wide.** Stop distance > `MAX_STOP_ATR × atr`. Assert SKIP, not a shrunk stop.
8. **Degenerate zone.** Width below `MIN_STOP_TICKS`. Assert the floor applies.
9. **Daily reset.** `dayPnl` returns to 0 across the boundary, under both `DAILY_RESET` modes.
10. **Scale-out.** At `SCALE_OUT_R`, assert `SCALE_OUT_PCT` closes and the stop moves to
    breakeven — and that it does *not* move before the partial fills.

---

## 9. Sign-off status

**Settled:**

- `RISK_PER_TRADE = 100` — two full-size losers before lockout
- `DAILY_RESET = exchangeDay` — CME 17:00 CT boundary
- `TARGET_MODE = opposingOb` as the default, with `MIN_TARGET_R` guarding thin setups

**Consequence of $100/two attempts, recorded so it is not a surprise later.** With only two
attempts before lockout, a losing first trade removes half the day's capacity and shrinks the
second trade's size to whatever the remaining budget allows. Two early losses end the day
regardless of what the market does afterwards. That is a deliberate choice of larger size per
trade over more attempts, and it makes **sequence risk** a first-order concern rather than a
footnote: the *order* in which winners and losers arrive now materially affects monthly
results. Phase 5 must report the distribution of days ended by the cap, not merely the count.

**Remaining calibration (not blocking implementation):**

`ATR_BUFFER_MULT = 0.5` is an estimate. It should be calibrated empirically against how far
price typically wicks past a zone that goes on to hold — measurable directly from the fixture
data. Doing that measurement *before* the first backtest is legitimate calibration against
zone behaviour; adjusting it afterwards to improve P&L is curve-fitting. The distinction
matters and the report must state which was done.
