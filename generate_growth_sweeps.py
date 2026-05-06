#!/usr/bin/env python3
"""
Generate controlled temporal-game benchmark suites for growth experiments.

Explores four parameter axes (one-at-a-time):
  1) edge density
  2) horizon (time bound)
  4) temporal-constraint complexity
  5) periodicity hardness (LCM of modulo guards)

Outputs paired game sets for Temporis (.dot) and Ontime (.tg), plus a manifest:
  - temporis_games/*.dot
  - ontime_games/*.tg
  - growth_manifest.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


# -------------------------------
# Experiment defaults
# -------------------------------
DEFAULT_EDGE_DENSITIES = [1.5, 2.5, 4.0, 6.0, 8.0]   # interpreted as avg out-degree (m/n)
DEFAULT_HORIZONS = [10, 25, 50, 100, 200, 400]
DEFAULT_COMPLEXITIES = ["simple", "mixed", "complex"]
DEFAULT_PERIODICITY = {
    "low": [2, 3],           # LCM = 6
    "medium": [4, 6, 9],     # LCM = 36
    "high": [5, 7, 11],      # LCM = 385
    "extreme": [7, 11, 13],  # LCM = 1001
}


@dataclass
class GameConfig:
    axis: str
    level: str
    rep: int
    rng_seed: int
    vertices: int
    edges: int
    horizon: int
    constraint_density: float
    complexity: str
    periodicity_label: str
    periodicity_moduli: Sequence[int]


def lcm(values: Sequence[int]) -> int:
    out = 1
    for v in values:
        out = abs(out * v) // math.gcd(out, v)
    return out


def level_tag(level: object) -> str:
    if isinstance(level, float):
        return str(level).replace(".", "p")
    return str(level).replace(" ", "_")


def build_edge_set(vertices: int, edges: int, rng: random.Random) -> List[Tuple[int, int]]:
    """Build a directed graph edge set with guaranteed >=1 outgoing per vertex."""
    if edges < vertices:
        edges = vertices

    edge_set = set()

    # Ensure each vertex has one outgoing edge.
    for src in range(vertices):
        dst = rng.randrange(vertices)
        edge_set.add((src, dst))

    # Add remaining edges uniformly.
    while len(edge_set) < edges:
        src = rng.randrange(vertices)
        dst = rng.randrange(vertices)
        edge_set.add((src, dst))

    return list(edge_set)


def choose_constraint_kind(complexity: str, rng: random.Random) -> str:
    if complexity == "simple":
        return rng.choice(["ge", "lt"])
    if complexity == "mixed":
        # Moderate use of modulo constraints.
        return rng.choices(["ge", "lt", "mod"], weights=[0.35, 0.35, 0.30], k=1)[0]
    # complex
    return rng.choices(["ge", "lt", "mod"], weights=[0.15, 0.15, 0.70], k=1)[0]


def build_constraint(
    complexity: str,
    periodicity_moduli: Sequence[int],
    periodicity_forced: bool,
    horizon: int,
    rng: random.Random,
) -> Tuple[str, int, int | None]:
    """
    Return abstract constraint tuple:
      ("ge", value, None)
      ("lt", value, None)
      ("mod", modulus, remainder)
    """
    if periodicity_forced:
        mod = rng.choice(list(periodicity_moduli))
        rem = rng.randrange(mod)
        return ("mod", mod, rem)

    kind = choose_constraint_kind(complexity, rng)

    if kind == "ge":
        if complexity == "simple":
            value = rng.randint(1, max(3, min(20, horizon // 2)))
        elif complexity == "mixed":
            value = rng.randint(1, max(10, horizon))
        else:
            value = rng.randint(1, max(50, 3 * horizon))
        return ("ge", value, None)

    if kind == "lt":
        if complexity == "simple":
            value = rng.randint(3, max(8, horizon + 5))
        elif complexity == "mixed":
            value = rng.randint(5, max(20, 2 * horizon))
        else:
            value = rng.randint(10, max(100, 5 * horizon))
        return ("lt", value, None)

    # kind == "mod"
    if complexity == "simple":
        mod = rng.choice([2, 3])
    elif complexity == "mixed":
        mod = rng.choice([2, 3, 4, 5, 6])
    else:
        mod = rng.choice(list(periodicity_moduli) + [8, 9, 10, 12, 14, 15, 16])

    rem = rng.randrange(mod)
    return ("mod", mod, rem)


def format_dot_constraint(c: Tuple[str, int, int | None]) -> str:
    kind, a, b = c
    if kind == "ge":
        return f't >= {a}'
    if kind == "lt":
        return f't < {a}'
    return f't mod {a} == {b}'


def format_tg_constraint(c: Tuple[str, int, int | None]) -> str:
    kind, a, b = c
    if kind == "ge":
        return f'(>= t {a})'
    if kind == "lt":
        return f'(< t {a})'
    return f'(= (mod t {a}) {b})'


def make_game_pair(cfg: GameConfig, base_name: str, out_temporis: str, out_ontime: str) -> Dict[str, object]:
    rng = random.Random(cfg.rng_seed)

    vertices = cfg.vertices
    edges = cfg.edges

    owners = [rng.randint(0, 1) for _ in range(vertices)]
    target = rng.randrange(vertices)

    edge_list = build_edge_set(vertices, edges, rng)

    # Select constrained edges.
    constrained_count = int(round(cfg.constraint_density * len(edge_list)))
    constrained_count = max(0, min(constrained_count, len(edge_list)))
    constrained_idx = set(rng.sample(range(len(edge_list)), constrained_count)) if constrained_count > 0 else set()

    periodicity_forced = cfg.axis == "periodicity_hardness"

    constraints_by_edge_idx: Dict[int, Tuple[str, int, int | None]] = {}
    for i in constrained_idx:
        constraints_by_edge_idx[i] = build_constraint(
            complexity=cfg.complexity,
            periodicity_moduli=cfg.periodicity_moduli,
            periodicity_forced=periodicity_forced,
            horizon=cfg.horizon,
            rng=rng,
        )

    # ----- DOT (Temporis)
    dot_lines: List[str] = []
    dot_lines.append(f"// axis: {cfg.axis}")
    dot_lines.append(f"// level: {cfg.level}")
    dot_lines.append(f"// replicate: {cfg.rep}")
    dot_lines.append(f"// rng_seed: {cfg.rng_seed}")
    dot_lines.append(f"// time_bound: {cfg.horizon}")
    dot_lines.append(f"// targets: v{target}")
    dot_lines.append(f"// constraint_density: {cfg.constraint_density:.3f}")
    dot_lines.append(f"// complexity: {cfg.complexity}")
    dot_lines.append(
        f"// periodicity: {cfg.periodicity_label} (moduli={list(cfg.periodicity_moduli)}, lcm={lcm(cfg.periodicity_moduli)})"
    )
    dot_lines.append("digraph G {")

    for v in range(vertices):
        if v == target:
            dot_lines.append(f'    v{v} [name="v{v}", player={owners[v]}, target=1];')
        else:
            dot_lines.append(f'    v{v} [name="v{v}", player={owners[v]}];')

    dot_lines.append("")
    for i, (src, dst) in enumerate(edge_list):
        if i in constraints_by_edge_idx:
            con = format_dot_constraint(constraints_by_edge_idx[i])
            dot_lines.append(f'    v{src} -> v{dst} [constraint="{con}"];')
        else:
            dot_lines.append(f"    v{src} -> v{dst};")

    dot_lines.append("}")

    # ----- TG (Ontime)
    tg_lines: List[str] = []
    tg_lines.append(f"// axis: {cfg.axis}")
    tg_lines.append(f"// level: {cfg.level}")
    tg_lines.append(f"// replicate: {cfg.rep}")
    tg_lines.append(f"// rng_seed: {cfg.rng_seed}")
    tg_lines.append(f"// time_bound: {cfg.horizon}")
    tg_lines.append(f"// targets: v{target}")
    tg_lines.append(f"// constraint_density: {cfg.constraint_density:.3f}")
    tg_lines.append(f"// complexity: {cfg.complexity}")
    tg_lines.append(
        f"// periodicity: {cfg.periodicity_label} (moduli={list(cfg.periodicity_moduli)}, lcm={lcm(cfg.periodicity_moduli)})"
    )

    for v in range(vertices):
        tg_lines.append(f"node v{v}: owner[{owners[v]}]")

    tg_lines.append("")
    for i, (src, dst) in enumerate(edge_list):
        if i in constraints_by_edge_idx:
            con = format_tg_constraint(constraints_by_edge_idx[i])
            tg_lines.append(f"edge v{src} -> v{dst}: {con}")
        else:
            tg_lines.append(f"edge v{src} -> v{dst}")

    dot_path = os.path.join(out_temporis, f"{base_name}.dot")
    tg_path = os.path.join(out_ontime, f"{base_name}.tg")

    with open(dot_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dot_lines) + "\n")

    with open(tg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tg_lines) + "\n")

    return {
        "game": base_name,
        "dot_path": dot_path,
        "tg_path": tg_path,
        "axis": cfg.axis,
        "level": cfg.level,
        "replicate": cfg.rep,
        "rng_seed": cfg.rng_seed,
        "vertices": cfg.vertices,
        "edges": cfg.edges,
        "edge_density": cfg.edges / cfg.vertices,
        "horizon": cfg.horizon,
        "constraint_density": cfg.constraint_density,
        "complexity": cfg.complexity,
        "periodicity_label": cfg.periodicity_label,
        "periodicity_moduli": list(cfg.periodicity_moduli),
        "periodicity_lcm": lcm(cfg.periodicity_moduli),
        "target": f"v{target}",
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate parameter-sweep temporal benchmark suite")

    p.add_argument("--output-dir", default=".", help="Where to create ontime_games/ and temporis_games/")
    p.add_argument("--vertices", type=int, default=400, help="Fixed vertex count for sweeps (default: 400)")
    p.add_argument("--replicates", type=int, default=12, help="Replicates per level (default: 12)")
    p.add_argument("--base-seed", type=int, default=1337, help="Base seed used to derive per-instance seeds")

    p.add_argument("--base-horizon", type=int, default=50, help="Baseline horizon for non-horizon sweeps")
    p.add_argument("--base-edge-density", type=float, default=4.0, help="Baseline m/n for non-density sweeps")
    p.add_argument("--base-constraint-density", type=float, default=0.35, help="Baseline constrained-edge ratio")
    p.add_argument(
        "--axes",
        nargs="+",
        choices=["edge_density", "horizon", "constraint_complexity", "periodicity_hardness"],
        default=["edge_density", "horizon", "constraint_complexity", "periodicity_hardness"],
        help=(
            "Which sweep axes to generate. "
            "Default: all four axes. Example: --axes horizon"
        ),
    )

    p.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing ontime_games/temporis_games in output-dir before generation",
    )
    p.add_argument(
        "--manifest-name",
        default="growth_manifest.json",
        help="Name for manifest file (default: growth_manifest.json)",
    )

    return p.parse_args()


def main() -> None:
    args = parse_args()

    out_temporis = os.path.join(args.output_dir, "temporis_games")
    out_ontime = os.path.join(args.output_dir, "ontime_games")

    if args.clean:
        for d in [out_temporis, out_ontime]:
            if os.path.exists(d):
                shutil.rmtree(d)

    os.makedirs(out_temporis, exist_ok=True)
    os.makedirs(out_ontime, exist_ok=True)

    manifest_entries: List[Dict[str, object]] = []

    base_edges = max(args.vertices, int(round(args.base_edge_density * args.vertices)))

    instance_idx = 0

    selected_axes = set(args.axes)

    # 1) Edge density sweep
    if "edge_density" in selected_axes:
        for i, density in enumerate(DEFAULT_EDGE_DENSITIES):
            edges = max(args.vertices, int(round(density * args.vertices)))
            for rep in range(1, args.replicates + 1):
                instance_idx += 1
                seed = args.base_seed * 1_000_000 + 10_000 * i + rep
                lvl = f"d{level_tag(density)}"
                base_name = f"ed_{lvl}_n{args.vertices:04d}_m{edges:05d}_r{rep:02d}"

                cfg = GameConfig(
                    axis="edge_density",
                    level=str(density),
                    rep=rep,
                    rng_seed=seed,
                    vertices=args.vertices,
                    edges=edges,
                    horizon=args.base_horizon,
                    constraint_density=args.base_constraint_density,
                    complexity="mixed",
                    periodicity_label="medium",
                    periodicity_moduli=DEFAULT_PERIODICITY["medium"],
                )
                manifest_entries.append(make_game_pair(cfg, base_name, out_temporis, out_ontime))

    # 2) Horizon sweep
    if "horizon" in selected_axes:
        for i, horizon in enumerate(DEFAULT_HORIZONS):
            for rep in range(1, args.replicates + 1):
                instance_idx += 1
                seed = args.base_seed * 1_000_000 + 100_000 + 10_000 * i + rep
                lvl = f"h{horizon}"
                base_name = f"hz_{lvl}_n{args.vertices:04d}_m{base_edges:05d}_r{rep:02d}"

                cfg = GameConfig(
                    axis="horizon",
                    level=str(horizon),
                    rep=rep,
                    rng_seed=seed,
                    vertices=args.vertices,
                    edges=base_edges,
                    horizon=horizon,
                    constraint_density=args.base_constraint_density,
                    complexity="mixed",
                    periodicity_label="medium",
                    periodicity_moduli=DEFAULT_PERIODICITY["medium"],
                )
                manifest_entries.append(make_game_pair(cfg, base_name, out_temporis, out_ontime))

    # 4) Constraint complexity sweep
    if "constraint_complexity" in selected_axes:
        for i, complexity in enumerate(DEFAULT_COMPLEXITIES):
            for rep in range(1, args.replicates + 1):
                instance_idx += 1
                seed = args.base_seed * 1_000_000 + 200_000 + 10_000 * i + rep
                lvl = f"c_{complexity}"
                base_name = f"cx_{lvl}_n{args.vertices:04d}_m{base_edges:05d}_r{rep:02d}"

                # Slightly increase constrained edge share for "complex" to amplify effect.
                cden = args.base_constraint_density
                if complexity == "complex":
                    cden = min(1.0, max(cden, 0.60))

                cfg = GameConfig(
                    axis="constraint_complexity",
                    level=complexity,
                    rep=rep,
                    rng_seed=seed,
                    vertices=args.vertices,
                    edges=base_edges,
                    horizon=args.base_horizon,
                    constraint_density=cden,
                    complexity=complexity,
                    periodicity_label="medium",
                    periodicity_moduli=DEFAULT_PERIODICITY["medium"],
                )
                manifest_entries.append(make_game_pair(cfg, base_name, out_temporis, out_ontime))

    # 5) Periodicity hardness sweep
    if "periodicity_hardness" in selected_axes:
        periodicity_items = list(DEFAULT_PERIODICITY.items())
        for i, (label, moduli) in enumerate(periodicity_items):
            for rep in range(1, args.replicates + 1):
                instance_idx += 1
                seed = args.base_seed * 1_000_000 + 300_000 + 10_000 * i + rep
                lvl = f"p_{label}"
                base_name = f"pd_{lvl}_n{args.vertices:04d}_m{base_edges:05d}_r{rep:02d}"

                cfg = GameConfig(
                    axis="periodicity_hardness",
                    level=label,
                    rep=rep,
                    rng_seed=seed,
                    vertices=args.vertices,
                    edges=base_edges,
                    horizon=args.base_horizon,
                    constraint_density=1.0,  # force modulo everywhere in this axis
                    complexity="complex",
                    periodicity_label=label,
                    periodicity_moduli=moduli,
                )
                manifest_entries.append(make_game_pair(cfg, base_name, out_temporis, out_ontime))

    manifest = {
        "experiment": "temporal_growth_sweeps",
        "axes": sorted(selected_axes),
        "defaults": {
            "vertices": args.vertices,
            "replicates_per_level": args.replicates,
            "base_horizon": args.base_horizon,
            "base_edge_density": args.base_edge_density,
            "base_constraint_density": args.base_constraint_density,
            "edge_densities": DEFAULT_EDGE_DENSITIES,
            "horizons": DEFAULT_HORIZONS,
            "complexities": DEFAULT_COMPLEXITIES,
            "periodicity": {
                k: {"moduli": v, "lcm": lcm(v)} for k, v in DEFAULT_PERIODICITY.items()
            },
        },
        "instances": manifest_entries,
        "count": len(manifest_entries),
    }

    manifest_path = os.path.join(args.output_dir, args.manifest_name)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Generated growth sweep benchmark set")
    print(f"  temporis games: {out_temporis}")
    print(f"  ontime games:   {out_ontime}")
    print(f"  manifest:       {manifest_path}")
    print(f"  total games:    {len(manifest_entries)}")


if __name__ == "__main__":
    main()
