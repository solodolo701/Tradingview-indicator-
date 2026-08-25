# 03 — Liquidity map

**Status:** draft for sign-off.
**Depends on:** `01-session-engine` (reference levels).
**Consumed by:** `05-signal-composition` (sweep detection gates the state machine),
`04-risk-engine` (`opposingOb` and `nextLvn` targets).

---

## 1. Scope — and an honest limit

**Pine Script cannot read Level 2, DOM, or order book data.** TradingView's DOM panel is a
separate broker-fed widget that scripts cannot access. Every "order book heatmap" in the
public script library infers from OHLCV rather than observing resting liquidity.

So this module is a **liquidity *proxy***, built from two independent sources:

1. **Structural levels** where stops predictably cluster — swing points, session extremes,
   equal highs/lows
2. **Traded volume distribution** — where volume actually transacted, as POC / HVN / LVN

Both are genuinely useful. Neither is a resting-order queue. Any documentation implying
otherwise misleads a reader about what they are trading with, and `doc-writer` is instructed
accordingly.

---

## 2. Structural levels

Tracked as sweep candidates, each with a "swept" flag:

| Level | Source |
|---|---|
| Prior day high / low / close | `01-session-engine` |
| Overnight high / low | Globex open → RTH open |
| Initial Balance high / low | 08:30–09:30, frozen at 09:30 |
| Pre-open high / low | `PREOPEN_WINDOW` |
| London high / low | `LONDON_WINDOW` |
| Confirmed swing highs / lows | `ta.pivothigh` / `ta.pivotlow` |
| **Equal highs / equal lows** | See §2.1 |

### 2.1 Equal highs and lows

Where stops pool most densely, and the trader's blue dotted lines mark exactly this.

```
equalHighs(pivots):
    group pivot highs whose prices lie within EQ_TOLERANCE_TICKS of each other
    and which occur within EQ_LOOKBACK_BARS
    require at least EQ_MIN_TOUCHES members
    level = mean of the group
```

Default tolerance 2 ticks (0.50 points on MES), minimum 2 touches.

---

## 3. Sweep detection

The first stage of the entry state machine (`05-signal-composition`), and the mechanism the
trader described: liquidity is taken, *then* the real move begins.

```
isSweep(level, direction):
    // Price must exceed the level and close back on the origin side.
    // A close beyond it is a break, not a sweep — the distinction is the whole point.
    if direction == SWEEP_HIGH
        penetrated = high > level + SWEEP_MIN_TICKS * mintick
        rejected   = close < level
    else
        penetrated = low  < level - SWEEP_MIN_TICKS * mintick
        rejected   = close > level

    return penetrated and rejected and inSweepWindow()
```

**Sweep versus break is the critical distinction.** Exceeding a level and closing back
through it means the level held and the stops beyond it were consumed — fuel removed from a
move against the subsequent trade. Exceeding it and closing beyond means the level failed.
Same penetration, opposite meaning. A rule that conflates them will produce a system that
enters against genuine breakouts.

**Terminology alignment — this is the trader's "SFP".** The trader marks these on the chart
as `sfp` (Swing Failure Pattern): price takes out a prior swing's liquidity and fails to hold
beyond it. That is exactly the `penetrated and rejected` condition above, so the spec and the
trader's vocabulary already agree. Use "sweep / SFP" interchangeably in code comments and
reports so the mapping stays obvious to them.

The trader applies it on **5m** as well as 15m, against swing points rather than only against
session levels — so `trackedLevels` must include confirmed pivots from both timeframes, not
just the §2 session set.

`SWEEP_MIN_TICKS` (default 2) filters noise that merely grazes a level.
`SWEEP_MAX_BARS` (default 3) bounds how long the reclaim may take.

---

## 4. Volume profile

Anchored **from the last confirmed swing to the current bar**, automating the trader's manual
anchoring (`00-concept.md` §4) so the profile never goes stale — the failure visible in the
first screenshot, where the profile described a regime price had already left.

### 4.1 Construction

```
buildProfile(anchorBar, currentBar):
    binSize = (rangeHigh - rangeLow) / PROFILE_BINS
    for each bar in [anchorBar, currentBar]
        intrabars = request.security_lower_tf(PROFILE_LTF)
        for each intrabar
            distribute its volume into the bin containing its close
            // Close-based, not spread across the bar's range: simpler, deterministic,
            // and matches how TradingView's own profiles behave closely enough.
    return bins
```

Anchor re-selection: on each newly *confirmed* pivot, re-anchor. Pivot confirmation lags by
`PIVOT_RIGHT` bars, so **the anchor moves late — and that is correct.** Re-anchoring the
instant a bar prints a new extreme would mean the profile depends on a swing not yet
confirmed, which is repainting.

### 4.2 Classification

```
poc = bin with maximum volume

hvn = bins with volume >= HVN_THRESHOLD_PCT of POC volume   (default 70%)
lvn = bins with volume <= LVN_THRESHOLD_PCT of POC volume   (default 25%)

valueArea = bins around POC accumulating VALUE_AREA_PCT of total volume (default 70%)
```

### 4.3 Use

| Node | Role | Effect |
|---|---|---|
| **POC** | Confluence | POC within `POC_CONFLUENCE_TICKS` of an OB → strongest zone |
| **VAL / VAH** | Confluence | Value area edge within `POC_CONFLUENCE_TICKS` of an OB → confluence |
| **HVN** | Barrier | An HVN between entry and target → **downgrade or veto** |
| **LVN** | Path / target | An LVN between entry and target → price travels fast; also a `nextLvn` target |

**Value area edges are confluence levels in their own right**, not merely a byproduct of the
value-area calculation. The trader identifies OB-plus-**value-area-low** overlap as a setup
that works, distinct from OB-plus-POC. That is mechanically sensible: VAL and VAH are the
boundaries between accepted and rejected price, so they mark where the market has previously
decided a level was too cheap or too dear — a different statement from POC, which marks where
it transacted most.

Tag `valDistanceTicks` and `vahDistanceTicks` alongside `pocDistanceTicks` so Phase 5 can
determine whether POC-confluence and value-edge-confluence carry different weight. They may
well not — but assuming they are the same thing would hide it either way.

The HVN rule comes from a specific observed case (`00-concept.md` §4): price cleared an OB's
50%, which read as continuation, but an HVN built during the prior downtrend capped the
rally. **So the profile can override the OB read, not merely confirm it.** That makes it an
independent input with veto power rather than a tiebreaker.

Whether HVN opposition should *veto* or merely *downgrade* is unresolved. It enters as a
tagged attribute (`00-concept.md` §2.2) and is promoted to a veto only if the data supports
it.

---

## 5. Parameters

| Name | Default | Notes |
|---|---|---|
| `EQ_TOLERANCE_TICKS` | 2 | Equal high/low grouping |
| `EQ_MIN_TOUCHES` | 2 | |
| `EQ_LOOKBACK_BARS` | 100 | |
| `SWEEP_MIN_TICKS` | 2 | Minimum penetration |
| `SWEEP_MAX_BARS` | 3 | Bars allowed for the reclaim |
| `PROFILE_BINS` | 50 | Resolution vs. compute cost |
| `PROFILE_LTF` | `1` | Minutes, for intrabar volume |
| `HVN_THRESHOLD_PCT` | 70 | Of POC volume |
| `LVN_THRESHOLD_PCT` | 25 | Of POC volume |
| `VALUE_AREA_PCT` | 70 | |
| `POC_CONFLUENCE_TICKS` | 8 | POC-to-OB distance counting as overlap |
| `MAX_PROFILE_BOXES` | 100 | Drawing budget |

---

## 6. Pine implementation notes

**This is the most compute-expensive module.** `request.security_lower_tf()` is capped on
total intrabars; 1-minute resolution across a long anchor range will hit the ceiling and
return truncated arrays. **Truncation is silent** — check returned array sizes and degrade
explicitly (coarser `PROFILE_LTF`, or a shorter anchor range) rather than quietly computing a
profile from partial data.

**Drawing budget.** 50 bins as boxes, plus zone boxes from `02-orderblock-engine`, against a
500-box ceiling. Budget both modules together, recycle rather than accumulate, and consider
rendering the profile only when `PROFILE_VISIBLE` is on — the *values* are needed for logic
whether or not the boxes are drawn.

**Never let a signal depend on a drawing's geometry.** Boxes are display; the bin array is
truth.

---

## 7. Test cases for the Python reference

1. Sweep: price exceeds a level by ≥ `SWEEP_MIN_TICKS` and closes back → detected
2. Break: price exceeds and closes beyond → **not** a sweep
3. Graze below `SWEEP_MIN_TICKS` → not a sweep
4. Reclaim later than `SWEEP_MAX_BARS` → not a sweep
5. Equal highs within tolerance → grouped into one level at the mean
6. Equal highs outside tolerance → separate levels
7. Profile on a known bar set → POC lands in the expected bin
8. HVN/LVN classification against hand-computed thresholds
9. Re-anchoring occurs only on *confirmed* pivots, never on an unconfirmed extreme
10. **Repainting regression:** bar-by-bar profile state matches full-history state at every
    bar

---

## 8. Open items

1. Volume distribution within an intrabar: close-based (specced) versus spread across the
   bar's range. Close-based is simpler and deterministic; the alternative is closer to a true
   profile. Worth a comparison if profile-derived signals prove to matter.
2. HVN as veto or as score penalty (§4.3).
3. Whether to anchor from the last swing *or* maintain a second session-anchored profile in
   parallel. The trader uses both manual anchorings; only swing-anchoring is specced here.
