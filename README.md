# Temporal Games Growth Study

This repository generates and analyzes temporal-game benchmark suites that isolate
specific growth facets:

1. Edge density growth
2. Horizon (time bound) growth
3. Constraint complexity growth
4. Periodicity hardness growth

## What this repo does

The workflow is:

1. Generate paired game corpora for both solvers (`.dot` for Temporis, `.tg` for Ontime).
2. Benchmark both solvers on the same generated instances.
3. Consolidate solver outputs into one JSON file.
4. Summarize performance by axis and level (success rate, timeout rate, mean/median/p90 time).

This lets you measure how runtime and robustness change as one selected game property grows.

## Files

- `generate_growth_sweeps.py`: controlled corpus generator for all 4 facets (or selected axes)
- `analyze_growth_sweeps.py`: post-processing grouped by `solver -> axis -> level`

## Prerequisites

### Required Software
```bash
# C++ Build Tools
sudo apt install cmake build-essential

# Python 3 with plotting libraries
sudo apt install python3 python3-pip
pip3 install matplotlib numpy

# Rust (for Ontime)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source .cargo/env

# Boost Libraries (for Temporis/GGG)
sudo apt install libboost-all-dev
```

### Repository Setup
```bash
# Clone required repositories
git clone https://github.com/gamegraphgym/ggg.git
git clone https://github.com/petejaustin/ontime.git
git clone https://github.com/petejaustin/temporis.git 
git clone https://github.com/petejaustin/case-study-extension
```

### 1. Build GGG (Game Graph Gym)
```bash
cd ggg
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DTOOLS_ALL=ON
cmake --build build -j$(nproc)
```

### 2. Build Temporis Solvers
```bash
cd temporis
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build

# Verify builds
ls temporis/build/temporis_solvers/temporis
ls temporis/build/temporis_solvers/temporis_static_expansion
```

### 3. Build Ontime
```bash
cd ontime
cargo build --release

# Verify build
ls ontime/target/release/ontime
```

- Built solver binaries:
	- `temporis` and/or `temporis_static_expansion`
	- `ontime`
- Existing benchmark helpers from the parent case-study directory:
	- `../benchmark_ontime.sh`
	- `../consolidate_results.py`
	- `../ggg/extra/scripts/benchmark.sh`

> If your folder layout differs, update the command paths below.

## End-to-end guide (steps 4-7)

The commands below use the ~500-game horizon example corpus already configured in this repo.

### 4) Generate the corpus

Run from this repository directory:

```bash
python3 generate_growth_sweeps.py \
	--output-dir examples/horizon_500 \
	--axes horizon \
	--replicates 83 \
	--vertices 300 \
	--manifest-name horizon_manifest.json \
	--clean
```

Expected total: `6 horizon levels × 83 replicates = 498` paired games.

### 5) Benchmark Temporis on generated `.dot` games

```bash
bash ../ggg/extra/scripts/benchmark.sh \
	examples/horizon_500/temporis_games \
	/ABSOLUTE/PATH/TO/temporis/build/temporis_solvers \
	--time 300 \
	-o examples/horizon_500/temporis_results.json \
	--solvers temporis,temporis_static_expansion
```

Adjust solver list as needed.

### 6) Benchmark Ontime on generated `.tg` games

```bash
bash ../benchmark_ontime.sh \
	examples/horizon_500/ontime_games \
	/ABSOLUTE/PATH/TO/ontime/target/release/ontime \
	300 \
	examples/horizon_500/ontime_results.json
```

### 7) Consolidate + summarize

Consolidate all solver outputs:

```bash
python3 ../consolidate_results.py \
	examples/horizon_500/temporis_results.json \
	examples/horizon_500/ontime_results.json \
	-o examples/horizon_500/full_results.json
```

Then generate growth summary:

```bash
python3 analyze_growth_sweeps.py \
	examples/horizon_500/full_results.json \
	examples/horizon_500/horizon_manifest.json \
	-o examples/horizon_500/horizon_summary.json
```

## Outputs you should expect

- `examples/horizon_500/temporis_results.json`
- `examples/horizon_500/ontime_results.json`
- `examples/horizon_500/full_results.json`
- `examples/horizon_500/horizon_summary.json`

`horizon_summary.json` contains grouped metrics per solver and horizon level, including:

- `success_rate`
- `timeout_rate`
- `mean_time`
- `median_time`
- `p90_time`

## Optional: run a different facet

Change `--axes` to one of:

- `edge_density`
- `horizon`
- `constraint_complexity`
- `periodicity_hardness`

or generate all four by omitting `--axes`.
