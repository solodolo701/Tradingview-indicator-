# ES Trend + Order Block — Project Conventions

A TradingView Pine Script v6 indicator/strategy pair for **ES / MES intraday**, combining a
trend engine, an order block engine, and a liquidity-proxy map, under hard daily P&L guardrails.

Read this file before doing anything in this repo.

---

## Non-negotiable ground rules

1. **Pine Script v6 only.** Every `.pine` file starts with `//@version=6`. No v4/v5 syntax.
2. **The indicator and the strategy must produce identical signals.** Shared logic lives in
   `src/lib/*.pine` as Pine libraries. If you fix a rule, fix it in the library — never in
   one entry script only. A backtest of logic that differs from the indicator is worthless.
3. **No lookahead. Ever.** No `request.security` without `lookahead=barmerge.lookahead_off`.
   No `barstate.islast`-dependent logic that changes historical signals. Repainting is a bug,
   not a feature.
4. **Never curve-fit to hit the P&L targets.** The daily target (+$400–500) and daily cap
   (−$200) are constraints we *encode*, not results we *manufacture*. If the honest backtest
   says the target isn't reachable, that is the finding — report it.
5. **Every backtest number is reported with commission and slippage applied.** Numbers without
   them are fiction and must not be quoted to the user.
6. **Spec before code.** No `.pine` or `.py` implementation lands before its `spec/*.md` exists
   and is signed off.

---

## Repository layout

| Path | Contents |
|---|---|
| `spec/` | The source of truth. Trading rules in prose + pseudocode, no implementation. |
| `src/lib/` | Pine libraries — the shared logic (`library()` declarations, exported functions). |
| `src/*.pine` | The two entry scripts: `indicator()` and `strategy()`. Thin — they compose libs. |
| `reference/` | Python reference implementation + OHLCV fixtures exported from TradingView. |
| `tests/` | pytest over the Python reference; `tests/parity/` compares Pine output to Python. |
| `reports/` | One file per backtest run, `YYYY-MM-DD-<variant>.md`. Never overwritten. |
| `.claude/agents/` | Subagent role definitions. |
| `.claude/skills/` | Project skills: Pine v6 reference, ES market context, backtest report format. |

---

## The MCP workflow (local sessions only)

The TradingView MCP (`solodolo701/tradingview-mcp`) drives TradingView Desktop over Chrome
DevTools Protocol on `127.0.0.1:9222`. **CDP is loopback-bound by design — never tunnel,
proxy, or otherwise expose port 9222.** That binding is the security model, and the server
refuses to start if the port is externally reachable.

Consequence: **compile and backtest work only in a Claude Code session running on the user's
own machine.** Cloud/remote sessions can write specs, author Pine and Python, and review —
they cannot compile. If you are in a cloud session, do not claim code is verified.

Tools used in this project (mode `pine` is sufficient; do not request `full`):

| Purpose | Tools |
|---|---|
| Compile loop | `pine_write` → `pine_compile` → `pine_get_errors` |
| Read results | `pine_get_output` (Strategy Tester), `data_get_study_values` |
| Data export | `data_get_ohlcv` → CSV into `reference/fixtures/` |
| Chart setup | `chart_set_symbol`, `chart_set_timeframe` |
| Visual verification | `replay_start`, `replay_step`, `replay_stop` |
| Health | `tv_health_check` |

Setup instructions live in `README.md`.

---

## Delegation model

**Opus 5 is head of engineering.** It owns architecture, the spec, every trading-logic
decision, integration, and final review. It does not do mechanical work.

Roles are defined in `.claude/agents/`. Use the right tier — over-provisioning burns tokens,
under-provisioning burns correctness:

| Work | Agent |
|---|---|
| Port a fully-specced module to Pine | `pine-implementer` (Sonnet) |
| Python reference impl + pytest | `reference-implementer` (Sonnet) |
| Run backtests, produce the report | `backtest-analyst` (Sonnet) |
| Survey literature / public scripts | `researcher` (Sonnet) |
| Boilerplate, file moves, fixtures, changelogs | `scaffolder` (Haiku) |
| Style-rule compliance pass | `pine-lint` (Haiku) |
| User-facing prose, publication description | `doc-writer` (Fable) |

### Token discipline

These rules exist so the head-of-engineering context stays clean across a long build:

1. **Specs are the interface.** Opus writes `spec/<module>.md`; the implementer reads *that
   file*, not the conversation history. Never paste a spec into an agent prompt.
2. **Agent reports are ≤300 words plus file paths.** No pasted code in a report. Ever.
3. **Bulk output goes to disk, not to context.** Raw Strategy Tester dumps → `reports/`.
   Raw research → a file. The agent returns the conclusion and the path.
4. **One module per invocation.** No agent is ever told "build the whole thing."
5. **Fix loops stay local.** A `pine-implementer` owns its compile errors. It escalates only
   after 3 failed attempts, or when the fix would require changing the spec — which is an
   Opus decision, not an implementer decision.
6. **Search fan-out is Haiku.** Only conclusions come back up.

---

## Pine house style

Enforced by `.claude/skills/pinescript-v6` and checked by the `pine-lint` agent.

- `//@version=6` first line; declaration second.
- Explicit types on every variable that isn't obvious: `float atrVal = ...`, not `atrVal = ...`.
- `camelCase` for variables and functions, `SCREAMING_SNAKE` for constants.
- Inputs grouped with `group=` and given `tooltip=`. Every input needs `minval`/`maxval`
  where a nonsense value is possible.
- Every drawing object is either recycled or deleted. `max_boxes_count`/`max_labels_count`
  set explicitly on any script that draws per-event.
- No magic numbers in logic — promote to an input or a named constant.
- `strategy()` always declares `commission_type`, `commission_value`, `slippage`,
  `initial_capital`, `process_orders_on_close=true`, `calc_on_every_tick=false`.

---

## Definition of done for a module

- [ ] `spec/<module>.md` exists and matches the implementation
- [ ] Python reference implemented, `pytest tests/` green
- [ ] Pine compiles clean via `pine_compile` — zero errors, zero warnings
- [ ] Parity verified: Pine signal timestamps == Python signal timestamps on the fixture window
- [ ] `pine-lint` reports no violations
- [ ] Visually spot-checked in `replay_step` on at least one known ES session
