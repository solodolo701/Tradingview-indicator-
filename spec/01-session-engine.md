# 01 — Session engine

**Status:** draft for sign-off.
**Depends on:** nothing. This is the base layer.
**Consumed by:** every other module.

Replaces what the original plan called the "trend engine". The trader's bias is
session-structural rather than indicator-derived (`00-concept.md` §2), so this module owns
time, sessions, and the reference levels those sessions produce.

---

## 1. Timezone — the non-negotiable

Every time computation uses **`"America/Chicago"`** explicitly. Never a fixed UTC offset,
never the chart's default timezone, never the trader's local time.

The trader's charts display local European time (UTC+2 summer). `15:30 local = 08:30 Chicago`
= the RTH open. But Europe and the US switch DST on different dates — the US on the second
Sunday of March and first Sunday of November, Europe on the last Sundays of March and
October — so for roughly three weeks a year the gap is **5 hours, not 6**. A window hard-coded
to local time would be silently one hour wrong across those weeks and would misclassify every
setup in them. Exchange-timezone handling removes the problem entirely.

```pine
inWindow = not na(time(timeframe.period, "0830-0930", "America/Chicago"))
```

---

## 2. Session definitions

| Window | Chicago | Local (summer) | Role |
|---|---|---|---|
| Globex open | 17:00 | 00:00 | Session start |
| Asia | 19:00–02:00 | 02:00–09:00 | **Excluded from entries** |
| London | 02:00–08:30 | 09:00–15:30 | Sets the continuation direction |
| Pre-open | 06:00–08:30 | 13:00–15:30 | The push measured for the reversal setup |
| **NY first hour** | **08:30–09:30** | **15:30–16:30** | **Primary window** (= Initial Balance) |
| Lunch | 11:00–13:00 | 18:00–20:00 | Excluded — chop, high false-breakout rate |
| Afternoon | 13:00–15:00 | 20:00–22:00 | Optional second window, off by default |
| RTH close | 15:00 | 22:00 | Flatten if `FLATTEN_AT_CLOSE` |
| Maintenance halt | 16:00–17:00 | 23:00–00:00 | No data |

---

## 3. Parameters

| Name | Default | Notes |
|---|---|---|
| `TZ` | `America/Chicago` | Constant. Not user-editable. |
| `PRIMARY_WINDOW` | `0830-0930` | Entry window |
| `USE_AFTERNOON` | `false` | Enables `AFTERNOON_WINDOW` |
| `AFTERNOON_WINDOW` | `1300-1500` | Candidate second window (`00-concept.md` §5) |
| `EXCLUDE_ASIA` | `true` | Blocks entries 19:00–02:00 |
| `PREOPEN_WINDOW` | `0600-0830` | Measured for the reversal setup |
| `LONDON_WINDOW` | `0200-0830` | Measured for the continuation setup |
| `FLATTEN_AT_CLOSE` | `true` | Close open positions at RTH close |
| `IB_MINUTES` | 60 | Initial Balance length |

---

## 4. Outputs

Exported for other modules and for attribute tagging (`00-concept.md` §2.2):

```
sessionId        : enum  { asia, london, preopen, nyFirstHour, lunch, afternoon, postClose }
inEntryWindow    : bool  // primary, or afternoon when enabled; and not Asia
minutesSinceOpen : int   // signed; negative before 08:30
newExchangeDay   : bool  // 17:00 CT boundary, drives the daily P&L reset

preOpenHigh, preOpenLow     : float
preOpenDirection            : int    // sign of (close at 08:30 − open at 06:00)
preOpenRangeAtr             : float  // range ÷ ATR

londonHigh, londonLow       : float
londonDirection             : int
londonRangeAtr              : float

ibHigh, ibLow               : float  // finalised at 09:30
onHigh, onLow               : float  // Globex open → RTH open
pdHigh, pdLow, pdClose      : float  // prior RTH day
```

**All of these are levels the liquidity map treats as sweep candidates** (`03-liquidity-map`)
and all are recorded as trade attributes. `preOpenDirection` and `londonDirection` are the
two attributes that will eventually decide the deferred bias rule — they are *measured and
tagged now*, and deliberately do not gate anything yet (`00-concept.md` §2.1).

---

## 5. Correctness requirements

**Session levels must finalise before use, and must never be revised afterwards.** `ibHigh`
is undefined until 09:30 and fixed from then on. A running high that keeps updating within the
window would let a signal at 08:45 depend on a level not known until 09:30 — repainting, and
the kind that inflates backtests convincingly.

```pine
// Correct: freeze at window end
var float ibHigh = na
if inIb
    ibHighRunning := math.max(nz(ibHighRunning, high), high)
if ibJustEnded
    ibHigh := ibHighRunning        // published only once, then immutable
```

**Prior-day levels** come from `request.security` on the daily timeframe with
`lookahead=barmerge.lookahead_off` **and** an explicit `[1]` offset, so only the *completed*
prior day is visible.

**Holidays and shortened sessions.** CME half-days (the day after Thanksgiving, Christmas Eve)
close at 12:00 CT. A window defined as `1300-1500` simply will not match on those days, which
is correct behaviour — but `FLATTEN_AT_CLOSE` must key on the actual session end rather than
a hard-coded 15:00, or positions will be carried through a close. Do not hard-code the
holiday calendar; derive from whether the session is open.

**Weekend gap.** Sunday 17:00 opens a new exchange day with no Friday continuation.
`newExchangeDay` must fire correctly across it.

---

## 6. Test cases

1. `15:30 local (UTC+2)` resolves to `08:30 Chicago` and sets `inEntryWindow = true`
2. Same instant during the March DST mismatch — still `08:30 Chicago`, still in window
3. Asia timestamps produce `inEntryWindow = false` when `EXCLUDE_ASIA`
4. `ibHigh` is `na` before 09:30, fixed after, and never changes on later bars
5. `newExchangeDay` fires once at 17:00 CT, including across the weekend gap
6. Prior-day levels reference the completed prior session, never the current one
7. A CME half-day: afternoon window does not match; `FLATTEN_AT_CLOSE` fires at the real close
8. `minutesSinceOpen` is negative pre-open, zero at 08:30, positive after

---

## 7. Open items

1. `USE_AFTERNOON` defaults off. It is one of the two candidate remedies for the frequency
   constraint (`00-concept.md` §5), so the on/off comparison is a headline Phase 5 result.
2. Whether the London *direction* should be measured as net change, as the position of the
   close within the session range, or by structure. Tagged as an attribute; the definition
   still needs pinning before the reference implementation.
