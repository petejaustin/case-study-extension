# Repository Summary

## Purpose

This repository provides a reproducible framework for temporal-game growth experiments.
It creates benchmark instances where one chosen game characteristic is varied while others
stay mostly fixed, then summarizes solver performance across that axis.

## Growth facets implemented

- Edge density (`m / n`)
- Horizon (time bound)
- Temporal-constraint complexity
- Periodicity hardness (via modulo sets with increasing LCM)

## Main scripts

- `generate_growth_sweeps.py`
  - Generates paired game sets for:
    - Temporis (`.dot`)
    - Ontime (`.tg`)
  - Writes a manifest (`growth_manifest.json` or custom name) containing exact generation metadata.

- `analyze_growth_sweeps.py`
  - Reads consolidated benchmark results + manifest.
  - Produces grouped metrics by `solver -> axis -> level`.
  - Reports success/timeout/failed counts and mean/median/p90 solve time.

## Typical experiment flow

1. Generate instances for selected axis (`--axes ...`).
2. Benchmark Temporis and Ontime on generated instances.
3. Consolidate outputs into one results JSON.
4. Analyze with `analyze_growth_sweeps.py` for per-level growth trends.

## Current example in this repo

`examples/horizon_500` contains a horizon-only corpus with 498 paired games, intended as a
small, practical starting point for growth analysis.
