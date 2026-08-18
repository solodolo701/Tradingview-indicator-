---
name: pinescript-v6
description: Pine Script v6 reference, correctness traps, and this project's house style. Load before writing, editing, or reviewing any .pine file, and before answering any question about what Pine can or cannot do.
---

# Pine Script v6 — reference and traps

This is the working reference for the ES trend + order block project. It covers the things
that actually cause bugs, not the whole language.

---

## 1. What Pine cannot do

Know these before designing anything. Each one has killed a feature idea in this project:

| Not available | Consequence |
|---|---|
| **Level 2 / DOM / order book data** | No real liquidity heatmap. Every "order book" script in the public library infers from OHLCV. Our liquidity map is explicitly a *proxy*. |
| **Tick data** (most plans) | Intrabar analysis is limited to `request.security_lower_tf`, itself capped. |
| **Cross-script state** | Two indicators cannot share variables. Shared logic means a Pine `library()`. |
| **Arbitrary history depth** | `max_bars_back` caps lookback (default 5000 on series). Deep history needs an explicit `max_bars_back=` and costs compute. |
| **Unlimited drawings** | 500 boxes / 500 labels / 500 lines maximum. Beyond that the oldest are *silently deleted*. |
| **File or network I/O** | No fetching external data. Everything comes from the chart's data feed. |
| **True multi-symbol portfolio logic** | `request.security` gets other symbols' data, but `strategy()` trades one instrument. |

---

## 2. Repainting — the ones that bite

Repainting means historical signals differ from what was actually available in real time.
In a backtest it manufactures profit that does not exist. Treat every instance as a bug.

**`request.security` lookahead.** Always:
```pine
htfClose = request.security(syminfo.tickerid, "60", close[1],
     lookahead = barmerge.lookahead_off)
```
`lookahead_on` leaks future data into historical bars. Using `close[1]` on the higher
timeframe additionally guarantees you only see *confirmed* HTF bars.

**Unconfirmed real-time bars.** On the live bar, `close` moves. A signal computed from the
live `close` may appear and disappear. Either gate on `barstate.isconfirmed`, or accept it
knowingly for a visual-only element — never for a strategy entry.

**Mutable historical drawings.** Extending a box's right edge each bar is fine visually, but
never let a *signal* depend on a drawing's current geometry — the geometry changed after the
fact.

**`calc_on_every_tick=true`** makes real-time and historical behaviour diverge. Off, always,
in this project.

---

## 3. Drawing object management

The hard trap: exceeding the cap deletes your oldest drawings with no error.

```pine
//@version=6
indicator("...", overlay = true, max_boxes_count = 500, max_labels_count = 500)

var array<box> obBoxes = array.new<box>()

// Recycle rather than grow without bound
if array.size(obBoxes) >= MAX_ZONES
    box.delete(array.shift(obBoxes))
array.push(obBoxes, box.new(...))
```

Always delete explicitly when a zone is invalidated. Do not rely on the cap to clean up.

---

## 4. User-defined types — the right shape for order blocks

v6 UDTs are the correct structure for zone tracking. Do not use parallel arrays:

```pine
type OrderBlock
    int    barIdx
    float  top
    float  bottom
    bool   bullish
    bool   mitigated
    int    touches
    box    zoneBox

var array<OrderBlock> blocks = array.new<OrderBlock>()
```

`var` initialises once on the first bar. `varip` persists across ticks within a bar — almost
never what you want here, and it breaks backtest/live parity.

---

## 5. Strategy declaration — the mandatory form

A `strategy()` without these produces numbers that are not real:

```pine
//@version=6
strategy("ES Trend + OB",
     overlay              = true,
     initial_capital      = 25000,
     default_qty_type     = strategy.fixed,
     commission_type      = strategy.commission.cash_per_contract,
     commission_value     = 0.60,          // MES, per side
     slippage             = 1,             // ticks
     process_orders_on_close = true,
     calc_on_every_tick   = false,
     max_boxes_count      = 500,
     max_labels_count     = 500)
```

- `slippage` is in **ticks**, not points or currency.
- `commission_value` with `cash_per_contract` is **per side**, so double it for round-turn.
- `process_orders_on_close=true` fills at the signal bar's close instead of the next bar's
  open. Realistic for a bar-close strategy; state which convention a report used.

---

## 6. Session and time handling for futures

ES trades nearly 24h, and session choice changes results materially.

```pine
// RTH only, Chicago time, weekdays
inRth = not na(time(timeframe.period, "0830-1500", "America/Chicago"))

// New session detection — for daily P&L guardrail resets
newDay = ta.change(time("D")) != 0
```

Use `"America/Chicago"` (CME time) explicitly. Never rely on exchange-default timezone —
it varies by data feed and silently breaks DST handling.

---

## 7. Daily P&L guardrail pattern

The core of this project's risk engine:

```pine
var float dayStartEquity = strategy.equity
if ta.change(time("D")) != 0
    dayStartEquity := strategy.equity

float dayPnl = strategy.equity - dayStartEquity
bool  lossLockout   = dayPnl <= -MAX_DAILY_LOSS
bool  targetReached = dayPnl >=  DAILY_TARGET
bool  tradingHalted = lossLockout or targetReached

if tradingHalted and strategy.position_size != 0
    strategy.close_all(comment = lossLockout ? "daily loss cap" : "daily target")
```

Note `strategy.equity` includes open position P&L; `strategy.netprofit` counts closed trades
only. For a *realised*-P&L cap use `netprofit`; for a *mark-to-market* cap use `equity`.
They behave differently — pick deliberately and document which.

---

## 8. Libraries

```pine
//@version=6
library("ObEngine", overlay = true)

export detectOrderBlock(float impulseAtrMult) =>
    // ...
```

- Exported function parameters need explicit types.
- Libraries must be **published** (private is fine) before another script can `import` them.
  In development, this means a publish step in the compile loop — plan for it.
- Import: `import username/ObEngine/1 as ob`

---

## 9. Common v5 → v6 gotchas

| v5 | v6 |
|---|---|
| `study(...)` | `indicator(...)` |
| `iff(c, a, b)` | `c ? a : b` |
| `transp=` argument | use `color.new(col, transparency)` |
| implicit int→float in some ops | v6 is stricter; cast explicitly |
| `array.new_float()` | `array.new<float>()` |

v6 also made boolean `na` handling stricter — a `na` bool in a condition is an error, not
`false`. Guard with `nz()` or explicit `na()` checks.

---

## 10. House style (enforced by the `pine-lint` agent)

- `//@version=6` first line, declaration second.
- Explicit types where not obvious: `float atrVal = ...`.
- `camelCase` variables/functions, `SCREAMING_SNAKE` constants.
- Inputs: `group=` and `tooltip=` on every one; `minval`/`maxval` on numerics.
- No magic numbers in logic — promote to input or named constant.
- Lines under 120 chars.
- Every drawing object recycled or deleted.
