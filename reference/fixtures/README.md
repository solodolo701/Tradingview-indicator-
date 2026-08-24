# Fixtures — ES / MES OHLCV exports

Market data exported from TradingView via the MCP, used by the Python reference
implementation and the Pine↔Python parity harness. **Committed to the repo** so tests are
reproducible — anyone running `pytest` gets identical results.

Nothing downstream can be tested without these. This is the gate on Phase 3.

---

## Prerequisites

Run these steps in a **local Claude Code session on your own machine**. The MCP drives
TradingView Desktop over CDP on `127.0.0.1:9222`; a cloud session cannot reach it, and the
port must not be exposed to change that.

1. TradingView Desktop launched via `~/tradingview-mcp/scripts/launch_tv_secure.sh`
   (a normally-started instance has no debug port)
2. `TV_MCP_MODE=pine` — the default, and sufficient
3. Verify: `npm run tv -- tv_health_check`

---

## What to export

| File | Symbol | TF | Window | Purpose |
|---|---|---|---|---|
| `mes_15m_is.csv` | `MES1!` | 15m | ~3 months | In-sample: development and calibration |
| `mes_5m_is.csv` | `MES1!` | 5m | same dates | MTF refinement (`02` §5) |
| `mes_15m_oos.csv` | `MES1!` | 15m | ~1 month, **later** | Out-of-sample: touched once, at the end |
| `mes_5m_oos.csv` | `MES1!` | 5m | same dates | |
| `mes_1m_sample.csv` | `MES1!` | 1m | ~2 weeks | Volume profile intrabars (`03` §4) |

**Export the out-of-sample window now, then do not look at it.** Its only value is being
unseen. Exporting it later, after in-sample results are known, invites unconscious selection
of a favourable period.

The 1m file is large and only needs to cover a fortnight — it exists to check whether
`request.security_lower_tf` can actually sustain the profile resolution `03` assumes, which
is a real risk worth testing early.

### Windows

Pick contiguous periods, in this order, with no overlap:

```
in-sample     2026-04-01 → 2026-06-30      (development)
out-of-sample 2026-07-01 → 2026-07-31      (sealed until Phase 5)
```

Adjust to what your plan actually holds. `MES1!` is a continuous contract and **rolls
quarterly**, which prints a price gap at each roll — a window spanning one will contain a
phantom move. Note any roll date inside your window; the backtest report must mention it.

---

## Export procedure

Per file:

```
chart_set_symbol("MES1!")
chart_set_timeframe("15")
data_get_ohlcv(bars = <as many as the plan allows>)
```

Then write the result to `reference/fixtures/<name>.csv`.

**Check the bar count you actually received.** TradingView caps history by subscription tier
(roughly 5k–20k bars). On 15m, 10k bars is around 26 RTH days. If `data_get_ohlcv` returns
fewer bars than requested, the window was truncated — record the real start date in
`manifest.md` rather than the one you asked for. A truncated window silently reported as full
is the most common way a backtest ends up describing a different period than it claims.

---

## Format

Header row required, UTC epoch milliseconds, one bar per line, oldest first:

```csv
time,open,high,low,close,volume
1743508800000,7681.25,7684.00,7677.50,7680.75,12483
```

- `time` — bar **open** time, UTC ms. The Python reference converts to `America/Chicago`
  for all session logic; fixtures stay in UTC so there is exactly one conversion point.
- Prices at full tick precision (0.25 increments). Do not round.
- No gaps within a session. Gaps *between* sessions are expected and correct.

---

## manifest.md

Record for every export, so a stale or truncated fixture cannot masquerade as a good one:

```markdown
| File | Symbol | TF | Bars | First bar (UTC) | Last bar (UTC) | Exported | Rolls in window |
|---|---|---|---|---|---|---|---|
| mes_15m_is.csv | MES1! | 15 | 6240 | 2026-04-01T13:30Z | 2026-06-30T20:00Z | 2026-08-24 | 2026-06-19 |
```

---

## Validation

Before committing, `tests/test_fixtures.py` asserts:

1. Header present and columns correctly typed
2. `time` strictly increasing, no duplicates
3. `high >= max(open, close)` and `low <= min(open, close)` on every bar
4. All prices are exact multiples of 0.25
5. Bar spacing equals the timeframe within a session
6. `volume >= 0`
7. 5m and 15m files cover the same date range
8. Bar count matches `manifest.md`

Rule 3 catches feed corruption, and rule 4 catches a symbol that is not actually MES. Both
have caused silent, hard-to-trace failures in projects like this one.
