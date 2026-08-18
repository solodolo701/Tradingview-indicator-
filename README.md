# ES Trend + Order Block

A TradingView Pine Script v6 **indicator and strategy pair** for ES / MES intraday trading,
combining a trend engine, an order block engine, and a liquidity-proxy map, under hard daily
P&L guardrails.

> **Status: Phase 0 — harness complete, no trading logic implemented yet.**
> The concept research and specification come next. Nothing here is tradeable.

---

## What this is

| Component | What it does |
|---|---|
| **Trend engine** | Volatility-adaptive directional bias with a chop filter |
| **Order block engine** | Detects, tracks, and mitigates supply/demand zones |
| **Liquidity map** | Volume-at-price and stop-cluster levels, rendered as graded zones |
| **Risk engine** | Position sizing plus a −$200 daily loss cap and a +$400–500 daily target |

Two entry scripts share one set of Pine libraries, so the indicator you watch and the
strategy you backtest produce identical signals.

## What this is not

**The liquidity map is a proxy, not a real order book heatmap.** Pine Script has no access to
Level 2 / DOM data — TradingView's DOM panel is a separate broker-fed widget that scripts
cannot read. The map is inferred from OHLCV: volume-at-price, prior-session levels, and
stop-cluster geometry. That is genuinely useful, but it is not Bookmap. Anything claiming a
true liquidity heatmap in Pine is inferring, not observing.

---

## Instrument and risk math

| | ES | MES |
|---|---|---|
| Point value | $50 | $5 |
| Tick (0.25) | $12.50 | $1.25 |

With a $200 daily loss cap and two losers before lockout, per-trade risk is ~$100. On ES that
buys a **2-point stop** — inside intraday noise, not viable. On MES it buys a **20-point
stop** at 1 contract, or 10 points at 2. **MES is the correct instrument for these
guardrails.** See `.claude/skills/es-market-context/SKILL.md` for the full breakdown.

The +$450/day target on $100 risk units is 4.5R per day. That is an aggressive bar, and
whether it is reachable is an open question the backtest has to answer — not an assumption
the code is built around.

---

## Repository layout

```
spec/         Trading rules — the source of truth. Prose and pseudocode, no code.
src/lib/      Pine libraries: trend, order blocks, liquidity, risk.
src/*.pine    The indicator() and strategy() entry scripts.
reference/    Python reference implementation + OHLCV fixtures.
tests/        pytest over the reference; tests/parity/ diffs Pine against Python.
reports/      One versioned file per backtest run.
.claude/      Subagent definitions and project skills.
```

**Why a Python reference implementation:** Pine has no unit test framework, and order block
mitigation logic is where subtle bugs hide invisibly. The rules are implemented once in
Python, tested with pytest, then ported to Pine and verified by diffing signal timestamps.

---

## Setup: connecting TradingView Desktop

The [TradingView MCP](https://github.com/solodolo701/Tradingview-MCP) drives TradingView
Desktop over Chrome DevTools Protocol, which lets Claude write Pine, compile it, read errors,
and step through replay.

**This must run on your own machine, in a local Claude Code session.** CDP is bound to
`127.0.0.1` by design and the MCP server refuses to start if the port is externally
reachable — so a cloud/web Claude session cannot reach it, and should not be made to. Cloud
sessions handle specs, code authoring, and review; the compile/backtest loop runs locally.

**Requirements:** TradingView Desktop on a paid plan (Essential or higher for replay),
Node.js 18+, Claude Code.

**1. Install the MCP**
```bash
curl -fsSL https://raw.githubusercontent.com/solodolo701/tradingview-mcp/main/install.sh | bash
```
Clones to `~/tradingview-mcp`, installs dependencies, generates a `TV_MCP_TOKEN`, and writes
the server entry into `~/.claude/.mcp.json`.

**2. Launch TradingView with the debug port enabled**

| OS | Command |
|---|---|
| macOS | `~/tradingview-mcp/scripts/launch_tv_secure.sh` (or `npm run tv:launch`) |
| Linux | `./scripts/launch_tv_secure.sh` |
| Windows | `scripts\launch_tv_secure.bat` |

TradingView must be started *by this script*. An instance launched normally has no debug port,
and the MCP will not find it.

**3. Keep the scope at `pine`**

`TV_MCP_MODE=pine` is the default and covers everything this project needs — chart reads,
Pine write/compile/save, and replay control. `full` additionally allows drawings, alerts, and
UI automation; this project does not need it, so leave it off.

**4. Restart Claude Code, then verify**
```bash
npm run tv -- tv_health_check
```

**5. Clone this repo locally** and work from there.

> Automated interaction with TradingView may conflict with their Terms of Service. That call
> is yours.

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/            # reference implementation tests
```

Conventions, delegation model, and the definition of done are in [`CLAUDE.md`](CLAUDE.md).

---

## Roadmap

- [x] **Phase 0** — Harness: structure, conventions, skills, agent definitions
- [ ] **Phase 1** — Research spike: order block definitions, ES session structure
- [ ] **Phase 2** — Specification (sign-off gate before any code)
- [ ] **Phase 3** — Python reference implementation + tests
- [ ] **Phase 4** — Pine implementation, module by module
- [ ] **Phase 5** — Parity verification + walk-forward backtest
- [ ] **Phase 6** — Iterate, or report honestly that the targets need adjusting
