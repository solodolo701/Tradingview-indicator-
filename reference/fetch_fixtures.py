#!/usr/bin/env python3
"""
Fetch ES OHLCV fixtures from Yahoo Finance — no TradingView subscription required.

    pip install yfinance pandas
    python reference/fetch_fixtures.py

Writes CSVs to reference/fixtures/ in the format specified by its README, plus a
manifest recording exactly what was retrieved.

WHY YAHOO, AND WHAT IT IS NOT
-----------------------------
TradingView's chart-data export needs a paid plan, and the free tier limits both
history and futures data. Yahoo gives us enough to answer the question that
currently blocks everything: how often does the setup actually fire?

Known limitations, which the manifest repeats so no later reader misses them:

  * Sub-hourly history is capped at ~60 days (7 days for 1m). Enough for setup
    frequency and structure; NOT enough for a walk-forward validation.
  * `ES=F` is Yahoo's continuous front-month series. Rolls appear as price gaps.
  * Volume is less reliable than exchange data. Anything volume-derived — the
    profile, POC/HVN/LVN, RVOL — should be treated as provisional on this source.
  * Bars may differ slightly from TradingView's for the same period.

So: fine for measuring frequency and validating logic. **Not a source for
quoting P&L.** Before any number is reported as a result, re-run on
exchange-quality data — Databento, the Tradovate API, or a TradingView export.

ES vs MES: the price series is identical, only the multiplier differs ($50 vs
$5). ES=F has better data, so structure is measured on ES and MES point value is
applied in the risk maths. See spec/04-risk-engine.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.exit("pip install yfinance pandas")

SYMBOL = "ES=F"
OUT_DIR = Path(__file__).parent / "fixtures"

# (interval, period, output stem). Yahoo caps: 1m → 7d, sub-hourly → 60d.
TARGETS = [
    ("15m", "60d", "es_15m"),
    ("5m", "60d", "es_5m"),
    ("1m", "7d", "es_1m_sample"),
]

# Fraction of each series held back, untouched, for out-of-sample validation.
OOS_FRACTION = 0.25


def fetch(interval: str, period: str) -> pd.DataFrame:
    df = yf.download(
        SYMBOL, period=period, interval=interval, progress=False, auto_adjust=False
    )
    if df.empty:
        raise RuntimeError(f"No data returned for {SYMBOL} {interval}")

    # yfinance returns a MultiIndex column frame for a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )[["open", "high", "low", "close", "volume"]]

    # UTC epoch milliseconds — fixtures stay in UTC so there is exactly one
    # timezone conversion point, in the session engine. See spec/01.
    idx = df.index
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df.insert(0, "time", (idx.astype("int64") // 1_000_000))

    df = df.dropna().reset_index(drop=True)
    df["volume"] = df["volume"].astype("int64")
    return df


def validate(df: pd.DataFrame, name: str) -> list[str]:
    """Mirrors the checks in fixtures/README.md. Warnings, not failures —
    Yahoo data is imperfect and we want it visible rather than silently dropped."""
    warnings = []

    if not df["time"].is_monotonic_increasing:
        warnings.append("timestamps not strictly increasing")
    if df["time"].duplicated().any():
        warnings.append(f"{int(df['time'].duplicated().sum())} duplicate timestamps")

    bad_hl = (df["high"] < df[["open", "close"]].max(axis=1)) | (
        df["low"] > df[["open", "close"]].min(axis=1)
    )
    if bad_hl.any():
        warnings.append(f"{int(bad_hl.sum())} bars with impossible high/low")

    # ES trades in 0.25 increments. A failure here usually means the wrong symbol.
    off_tick = ((df[["open", "high", "low", "close"]] * 4) % 1 != 0).any(axis=1)
    if off_tick.any():
        warnings.append(f"{int(off_tick.sum())} bars not on a 0.25 tick")

    if (df["volume"] < 0).any():
        warnings.append("negative volume")
    if (df["volume"] == 0).sum() > len(df) * 0.1:
        warnings.append(f"{int((df['volume'] == 0).sum())} zero-volume bars")

    return [f"{name}: {w}" for w in warnings]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, all_warnings = [], []

    for interval, period, stem in TARGETS:
        print(f"Fetching {SYMBOL} {interval} ({period})...", flush=True)
        try:
            df = fetch(interval, period)
        except Exception as exc:  # noqa: BLE001 — report and continue
            print(f"  FAILED: {exc}")
            continue

        all_warnings += validate(df, stem)

        split = int(len(df) * (1 - OOS_FRACTION))
        parts = (
            [(f"{stem}_is", df.iloc[:split]), (f"{stem}_oos", df.iloc[split:])]
            if stem != "es_1m_sample"
            else [(stem, df)]
        )

        for part_name, part in parts:
            path = OUT_DIR / f"{part_name}.csv"
            part.to_csv(path, index=False)
            first = pd.to_datetime(part["time"].iloc[0], unit="ms", utc=True)
            last = pd.to_datetime(part["time"].iloc[-1], unit="ms", utc=True)
            rows.append(
                f"| {part_name}.csv | {SYMBOL} | {interval} | {len(part)} | "
                f"{first:%Y-%m-%d %H:%M}Z | {last:%Y-%m-%d %H:%M}Z |"
            )
            print(f"  {path.name}: {len(part)} bars, {first:%Y-%m-%d} → {last:%Y-%m-%d}")

    manifest = OUT_DIR / "manifest.md"
    manifest.write_text(
        "# Fixture manifest\n\n"
        f"Source: Yahoo Finance via yfinance. Generated by `reference/fetch_fixtures.py`.\n"
        f"Out-of-sample split: last {OOS_FRACTION:.0%} of each series.\n\n"
        "| File | Symbol | TF | Bars | First (UTC) | Last (UTC) |\n"
        "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
        "## Provenance warning\n\n"
        "Yahoo continuous front-month data. Volume is less reliable than exchange\n"
        "data, so volume-derived signals (profile, POC/HVN/LVN, RVOL) are provisional.\n"
        "Suitable for measuring setup frequency and validating logic. **Not a source\n"
        "for quoted P&L** — re-run on exchange-quality data before reporting results.\n\n"
        + ("## Validation warnings\n\n" + "\n".join(f"- {w}" for w in all_warnings) + "\n"
           if all_warnings else "## Validation\n\nNo warnings.\n")
    )

    print(f"\nManifest: {manifest}")
    if all_warnings:
        print("\nWarnings:")
        for w in all_warnings:
            print(f"  - {w}")

    print(
        "\nThe *_oos.csv files are held back for out-of-sample validation.\n"
        "Do not inspect or tune against them — their only value is being unseen."
    )


if __name__ == "__main__":
    main()
