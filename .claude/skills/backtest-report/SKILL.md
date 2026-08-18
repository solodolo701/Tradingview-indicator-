---
name: backtest-report
description: The standard format and honesty rules for every backtest report in this project. Load before running a backtest or writing anything into reports/.
---

# Backtest report standard

Every backtest run gets a file at `reports/YYYY-MM-DD-<variant>.md`. Files are never
overwritten — a new run is a new file. The history of what was tried is part of the record,
including the runs that failed.

---

## Honesty rules

1. **No number without costs.** Commission and slippage applied, and stated in the header.
2. **In-sample and out-of-sample reported separately.** Never blended into one figure. An
   in-sample-only result is not evidence of anything.
3. **State the actual window tested.** If TradingView's bar cap truncated it, say so, with
   the real start date.
4. **Report the daily P&L distribution, not the average.** The average hides the shape, and
   the shape is what determines whether the −$200 cap is survivable.
5. **Never re-tune parameters to reach the target and report only the winning run.** If you
   tested 12 variants, the report says 12 variants were tested. Reporting only the best is
   how curve-fitting gets laundered into a strategy.
6. **A losing or mediocre result is a valid, complete report.** File it.

---

## Template

```markdown
# Backtest — <variant name>
**Date run:** YYYY-MM-DD · **Script:** src/es_confluence_strategy.pine @ <git sha>

## Configuration
| | |
|---|---|
| Symbol / timeframe | MES1! / 5m |
| Window requested | 2025-01-01 → 2025-06-30 |
| Window actually tested | (state if truncated by bar cap) |
| In-sample split | 2025-01-01 → 2025-04-30 |
| Out-of-sample split | 2025-05-01 → 2025-06-30 |
| Contracts | 2 MES |
| Commission | $0.60/side cash_per_contract |
| Slippage | 1 tick |
| Initial capital | $25,000 |
| Daily loss cap / target | −$200 / +$450 |

## Results

| Metric | In-sample | Out-of-sample |
|---|---|---|
| Net P&L | | |
| Total trades | | |
| Win rate | | |
| Profit factor | | |
| Max drawdown ($ / %) | | |
| Avg win / avg loss (R) | | |
| Largest win / largest loss | | |
| Avg trades per day | | |

## Daily P&L distribution (out-of-sample)

| | |
|---|---|
| Mean daily P&L | |
| Median daily P&L | |
| Best / worst day | |
| Days hitting +$450 target | N of M (x%) |
| Days hitting −$200 loss cap | N of M (x%) |
| Green days / red days | |

## Guardrail behaviour
- How often the loss cap halted trading, and whether it prevented worse days
- How often the target locked in gains, and what was left on the table
- Any day where the cap was breached (a bug if so — a gap through the stop is the
  only legitimate cause, and it must be named)

## Overfitting checks
- [ ] ≥30 trades in each split
- [ ] Out-of-sample performance within ~50% of in-sample
- [ ] Removing the single best trade does not flip the result to a loss
- [ ] ±20% on each key parameter does not collapse the result
- [ ] No parameter sits on a sharp performance cliff

## Variants tested this session
List every configuration tried, including the ones that lost. Not just this one.

## Verdict
One paragraph. Does this work, does it not, or is the sample too small to say?
Say which. "Inconclusive, needs more data" is an acceptable and often correct verdict.
```

---

## Metrics worth more than net P&L

- **Profit factor** — gross profit ÷ gross loss. Below 1.3 net of costs is fragile.
- **Max drawdown in R** — more portable across position sizes than a dollar figure.
- **Trade count** — under 30 per split, treat conclusions as noise.
- **Best-trade dependency** — if removing the top trade kills the edge, there is no edge.
- **Daily P&L distribution** — a system averaging +$200/day via one +$2000 day and nine
  −$50 days is a very different thing to trade than a steady +$200/day, even though the
  average matches.
