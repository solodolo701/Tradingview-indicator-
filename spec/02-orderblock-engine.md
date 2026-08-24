# 02 — Order block engine

**Status:** draft for sign-off. The largest and most intricate module.
**Depends on:** `01-session-engine` (ATR context, timeframe handling).
**Consumed by:** `05-signal-composition`, `04-risk-engine` (zone bounds → stop).

---

## 1. Definition

An order block is the **candle cluster at the origin of an impulsive leg**, bounded
**wick to wick** (candle high to candle low), from which price departed with displacement
and to which price may later return.

- **Bearish OB** (supply): the cluster before an impulsive move *down*. Traded short on return.
- **Bullish OB** (demand): the cluster before an impulsive move *up*. Traded long on return.

**Entry is the 50% level:** `(zoneHigh + zoneLow) / 2`.

Wick-to-wick bounds are the trader's stated convention. They produce a wider zone than a
body-based definition, so the 50% sits deeper, fills more often, and carries a wider stop.
That trade-off is fixed. Do not silently re-litigate it in code.

---

## 2. Qualification — all three required

A candle cluster is only an order block if **all three** hold. This is strict by design and
will substantially reduce setup count.

### 2.1 Displacement

The leg out of the zone contains at least one candle whose **body** exceeds a threshold:

```
displacement = |close - open| >= DISPLACEMENT_ATR_MULT * atr(ATR_LEN)
```

Body, not range — a long wick with a small body is rejection, not displacement, and the two
mean opposite things about who won the bar.

### 2.2 Unfilled imbalance (FVG)

The impulse must leave a three-candle gap that price has not since filled:

```
bullish FVG at bar i:   low[i-1]  > high[i+1]
bearish FVG at bar i:   high[i-1] < low[i+1]
```

"Unfilled" is evaluated **at the moment the zone is created**, and the fill state is tracked
forward. `FVG_FILL_MODE` decides what counts as filled: `touch` (any trade into the gap) or
`full` (the gap fully traversed). Default `full`.

### 2.3 Break of structure

The impulse must take out a prior swing point in its direction:

```
bearish OB: the leg closes below the most recent confirmed swing low
bullish OB: the leg closes above the most recent confirmed swing high
```

Swing points from `ta.pivotlow` / `ta.pivothigh` with `PIVOT_LEFT` / `PIVOT_RIGHT`.

⚠️ **Pivots confirm late, and this is the single biggest repainting risk in the module.**
A pivot with `PIVOT_RIGHT = 3` is only knowable 3 bars after it printed. Any structure test
must use pivots **confirmed as of the evaluating bar** — never a pivot the script can see in
hindsight. Getting this wrong produces a backtest that looks excellent and is fiction. It is
explicitly covered by parity testing against the Python reference, whose bar-by-bar causal
construction cannot express the bug.

---

## 3. Zone construction

```
findZone(impulseStartBar, direction):
    // Walk back from the displacement candle to collect the origin cluster
    lastOpposing = the last candle before the impulse whose direction opposes it
                   (bearish OB → last up-close candle; bullish OB → last down-close candle)

    if ZONE_MODE == "singleCandle"
        cluster = [lastOpposing]
    else  // "cluster" — default
        cluster = lastOpposing plus contiguous same-direction neighbours,
                  up to MAX_CLUSTER_BARS

    zoneHigh = max(high) over cluster
    zoneLow  = min(low)  over cluster
    return Zone(zoneHigh, zoneLow, direction, bar, timeframe)
```

`ZONE_MODE` defaults to `cluster`, matching the multi-candle zones on the trader's charts
(`00-concept.md` §3b). `singleCandle` is the stricter ICT convention and is a backtest
variant.

---

## 4. Lifecycle

```
CREATED ──price returns to 50%──> TESTED ──close beyond distal edge──> INVALIDATED
   │                                 │
   │                                 └──MAX_TESTS reached──> EXHAUSTED
   └──age > MAX_ZONE_BARS──> EXPIRED
```

**Invalidation is a `close` beyond the distal edge.** Wicks through do not kill the zone —
settled in `00-concept.md` §3. This is deliberately forgiving: a wick into and through a zone
extreme is normal behaviour for a level that ultimately holds, and it is the same reasoning
that puts the stop beyond the edge in `04-risk-engine`. The two rules must stay consistent;
if one changes, so does the other.

**`MAX_TESTS`** defaults to 1. A zone that has already been traded into once has had its
resting orders consumed and is not the same zone on a second visit.

**`MAX_ZONE_BARS`** prevents zones from months back from triggering. Default 200 bars
(~2 sessions on 15m).

---

## 5. Multi-timeframe nesting

The 5m refinement is what makes the sizing work (`00-concept.md` §3.2), and it is the highest
-value feature in this module.

```
refineZone(zone15m):
    if not USE_MTF_REFINEMENT
        return zone15m

    candidates = zones detected on REFINE_TF that are
                   (a) fully contained within zone15m
                   (b) the same direction
                   (c) themselves passing all three qualifiers on REFINE_TF

    if candidates is empty
        return REFINE_FALLBACK == "useHtf" ? zone15m : SKIP

    return the candidate nearest the 15m zone's proximal edge
```

**The stop then derives from the *returned* zone's timeframe**, including its ATR
(`04-risk-engine` §3). This is the whole point: entering on a 15m zone while stopping at 5m
width clears no zone at all, and is the specific error that produced the failing trade.

`REFINE_FALLBACK` defaults to `useHtf` — no 5m zone means trade the 15m zone at 15m sizing,
rather than skip. The fallback rate must be reported; if it fires on most setups, MTF
refinement is not really active.

---

## 6. Parameters

| Name | Default | Range | Notes |
|---|---|---|---|
| `ATR_LEN` | 14 | 5–50 | Per timeframe |
| `DISPLACEMENT_ATR_MULT` | 1.5 | 0.5–4.0 | §2.1. Drives setup count more than anything else. |
| `FVG_FILL_MODE` | `full` | `touch`\|`full` | §2.2 |
| `PIVOT_LEFT` | 3 | 1–10 | §2.3 |
| `PIVOT_RIGHT` | 3 | 1–10 | Confirmation lag — see the repainting warning |
| `ZONE_MODE` | `cluster` | `cluster`\|`singleCandle` | §3 |
| `MAX_CLUSTER_BARS` | 5 | 1–20 | §3 |
| `MAX_TESTS` | 1 | 1–5 | §4 |
| `MAX_ZONE_BARS` | 200 | 20–1000 | §4 |
| `USE_MTF_REFINEMENT` | `true` | bool | §5 |
| `REFINE_TF` | `5` | — | Minutes |
| `REFINE_FALLBACK` | `useHtf` | `useHtf`\|`skip` | §5 |
| `MAX_ACTIVE_ZONES` | 20 | 5–100 | Drawing budget — see §8 |

---

## 7. Outputs

```
type Zone
    float  top
    float  bottom
    float  midpoint        // the entry level
    int    direction       // +1 bullish, −1 bearish
    int    createdBar
    string timeframe       // "15" or "5" — determines which ATR the stop uses
    int    testCount
    bool   invalidated
    box    drawing

activeZones : array<Zone>   // sorted by distance from price
```

Attributes exported for tagging (`00-concept.md` §2.2): zone width in ATR, bars since
formation, retracement depth into the impulse at entry, impulse leg size in ATR.

---

## 8. Pine implementation notes

**Drawing budget.** `max_boxes_count = 500`, and `MAX_ACTIVE_ZONES` bounds live zones. Recycle
explicitly — never rely on the cap to clean up, because exceeding it deletes the oldest
drawings silently with no error:

```pine
if array.size(zones) >= MAX_ACTIVE_ZONES
    Zone old = array.shift(zones)
    box.delete(old.drawing)
```

**Lower-timeframe access.** Use `request.security_lower_tf()` for 5m data from a 15m chart.
It returns arrays per chart bar and is subject to an intrabar budget; deep history plus fine
resolution will hit it. Test the actual limit against a real fixture before assuming the
refinement works across a full backtest window.

**No `barstate.islast` in detection logic.** Fine for cosmetic redraws, never for whether a
zone exists.

---

## 9. Test cases for the Python reference

1. Hand-built bearish OB: cluster, displacement, FVG, BOS all present → zone created with
   expected bounds and midpoint
2. Displacement below threshold → no zone
3. Displacement present, no FVG → no zone
4. Displacement and FVG, no BOS → no zone (all three are required)
5. Large wick, small body → rejected by §2.1's body test
6. Wick through the distal edge → zone survives
7. **Close** through the distal edge → invalidated
8. Second return after `MAX_TESTS = 1` → exhausted, no signal
9. Age beyond `MAX_ZONE_BARS` → expired
10. **Repainting regression:** feed bars one at a time; assert the zone set at bar *i* is
    identical to the zone set at bar *i* when the full history is processed. Any pivot
    lookahead bug fails this.
11. MTF: a 5m zone nested inside a 15m zone → refined zone returned, `timeframe = "5"`
12. MTF: no nested zone → `useHtf` returns the 15m zone; `skip` returns none
13. FVG filled before the return → `full` vs `touch` modes disagree as specified

---

## 10. Open items

1. **`DISPLACEMENT_ATR_MULT = 1.5` is the most consequential unvalidated number in the
   project.** It determines how many setups exist per day, and the daily target depends
   entirely on that count (`00-concept.md` §5). Measure setup frequency across the fixture
   window at several values *before* the first P&L backtest. Choosing it by frequency and
   zone quality is calibration; choosing it by resulting P&L is curve-fitting.
2. `MAX_CLUSTER_BARS = 5` is an estimate — check against the trader's hand-drawn zones.
3. Whether a zone should also require the impulse to originate inside a session window, or
   whether zones formed overnight are tradeable during the NY window. Currently the latter:
   zones form at any time, entries are gated by session.
