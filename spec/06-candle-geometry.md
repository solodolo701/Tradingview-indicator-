# 06 — Candle geometry

**Status:** draft for sign-off.
**Depends on:** nothing — pure per-bar arithmetic.
**Consumed by:** `02-orderblock-engine` (displacement), `03-liquidity-map` (SFP rejection),
`05-signal-composition` (attribute tagging).

---

## 1. Why measurements, not named patterns

The natural question — "is there a candle pattern here we can implement?" — has a better
answer than a pattern name.

**A named candlestick pattern is a threshold on a continuous variable, with the threshold
chosen by tradition rather than by evidence.** "Bullish engulfing" means *this* body fully
contains the prior body — a boolean cut through a continuous quantity (body overlap ratio) at
the arbitrary value 1.0. A bar overlapping 97% is called nothing and behaves almost
identically. The naming discards information and adds a threshold nobody measured.

So this module defines the underlying **continuous measurements** and tags them. Phase 5 then
finds the thresholds that actually separate winners from losers — or finds that none does,
which is equally worth knowing. If it turns out that `bodyRatio > 0.7 AND closePosition >
0.85` predicts outcomes, that is a discovered rule with a measured threshold. It may even
coincide with a named pattern, which would be a pleasant confirmation rather than the
starting assumption.

The alternative — implementing a dozen named patterns as booleans — is a well-trodden route
to a noisy system, because each pattern is a low-information binary and twelve of them
invite exactly the multiple-comparisons fishing that `00-concept.md` §2.2 exists to prevent.

**This module is measurement only. It contains no rules and gates nothing.** The single
exception already in use is `DISPLACEMENT_ATR_MULT` in `02-orderblock-engine` §2.1, which is
a threshold on `bodyAtr` below.

---

## 2. Definitions

For a bar with `open`, `high`, `low`, `close`:

```
range        = high - low
body         = abs(close - open)
upperWick    = high - max(open, close)
lowerWick    = min(open, close) - low
direction    = sign(close - open)                    // +1, 0, −1
```

Normalised — these are what get tagged, since raw point values are not comparable across
volatility regimes:

| Metric | Formula | Reads as |
|---|---|---|
| `bodyRatio` | `body / range` | 1.0 = marubozu, conviction. 0.0 = doji, indecision. |
| `bodyAtr` | `body / atr(ATR_LEN)` | Displacement in volatility units |
| `rangeAtr` | `range / atr(ATR_LEN)` | Expansion vs contraction |
| `closePosition` | `(close - low) / range` | 1.0 = closed on the high, 0.0 = on the low |
| `upperWickRatio` | `upperWick / range` | Rejection from above |
| `lowerWickRatio` | `lowerWick / range` | Rejection from below |
| `bodyOverlap` | `overlap(body, body[1]) / body[1]` | ≥1.0 is what "engulfing" names |
| `gapAtr` | `(open - close[1]) / atr` | Session or news gap |

Guard `range == 0` — it occurs on halted or untraded bars. Return `na`, never divide.

**`closePosition` is the single most informative one-number summary of a bar.** It captures
who won the bar regardless of where it opened, and it subsumes most of what the classic
single-bar patterns are gesturing at — hammer, shooting star, and marubozu are all
statements about `closePosition` combined with `bodyRatio`.

---

## 3. Where these already matter

**Displacement** (`02` §2.1) uses `bodyAtr`, deliberately not `rangeAtr`. A long wick with a
small body is *rejection*; a large body is *displacement*. The two mean opposite things about
who won the bar, and using range would conflate them.

**SFP rejection** (`03` §3) has a natural geometric signature: for a swept high, a large
`upperWickRatio` with a low `closePosition`. The current sweep rule is purely price-based —
penetrate and close back — and does not consult the candle's shape at all. Whether adding a
rejection-strength requirement improves it is a clean, isolated experiment:

```
sweepQuality = swept high ?  upperWickRatio × (1 - closePosition)
                          :  lowerWickRatio × closePosition
```

Tag it; do not gate on it yet.

**Impulse strength** for the leg out of an OB — the sum of `bodyAtr` across the leg's bars,
and the fraction of those bars closing in the leg's direction.

---

## 4. Attributes added to the tagging set

Appended to `00-concept.md` §2.2, recorded on the **SFP bar** and on the **entry bar**:

```
sfp_bodyRatio, sfp_closePosition, sfp_upperWickRatio, sfp_lowerWickRatio,
sfp_bodyAtr, sfp_rangeAtr, sfp_sweepQuality,
entry_bodyRatio, entry_closePosition, entry_bodyAtr,
impulse_bodyAtrSum, impulse_directionalBarPct,
ob_avgBodyRatio            // across the zone's candles
```

These are **pre-registered now**, before any results are seen, under the same discipline as
the rest of the attribute set. Adding candle metrics later, after seeing which trades won,
would be precisely the fishing expedition the framework is built to prevent.

---

## 5. Parameters

| Name | Default | Notes |
|---|---|---|
| `ATR_LEN` | 14 | Shared with other modules; must match |

No thresholds. This module measures; it does not decide.

---

## 6. Test cases

1. Marubozu (`open == low`, `close == high`) → `bodyRatio = 1.0`, `closePosition = 1.0`
2. Doji (`open == close`) → `bodyRatio = 0.0`; `closePosition` still valid
3. `high == low` → all ratios `na`, no division error
4. Hammer shape → high `lowerWickRatio`, high `closePosition`
5. Shooting star → high `upperWickRatio`, low `closePosition`
6. Bar fully containing the prior body → `bodyOverlap >= 1.0`
7. `bodyAtr` scales correctly as ATR changes across regimes
8. `sweepQuality` is high for a strong rejection, near zero for a bar closing at its extreme

---

## 7. Open items

1. Whether `sweepQuality` should eventually gate SFP detection or remain an attribute.
   Decided by Phase 5, not in advance.
2. Whether the trader's eye is picking up something these metrics do not capture — bar
   *sequence* rather than individual bars, for instance. Resolving that needs a zoomed 5m
   or 15m screenshot where individual candles are legible; the metrics above are readable
   from data regardless, so this does not block.
