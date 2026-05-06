#!/usr/bin/env python3
"""
Generate temporal games for benchmarking temporis and ontime solvers.
Creates up to 4500 games total: 15 games each for vertex counts 10, 20, 30, ..., 3000
"""

import argparse
import os
import random
import shutil

def generate_temporis_game(vertices, game_id):
    """Generate a DOT format game for temporis"""
    # Generate random time bound (5 to vertices//2)
    time_bound = random.randint(5, max(10, vertices // 2))
    
    # Pick a random target vertex
    target = f"v{random.randint(0, vertices-1)}"
    
    # Start DOT file
    content = f"// Benchmark game {game_id} - {vertices} vertices\n"
    content += f"// time_bound: {time_bound}\n"
    content += f"// targets: {target}\n"
    content += "digraph G {\n"
    
    # Add vertices
    for i in range(vertices):
        player = random.randint(0, 1)
        if f"v{i}" == target:
            content += f'    v{i} [name="v{i}", player={player}, target=1];\n'
        else:
            content += f'    v{i} [name="v{i}", player={player}];\n'
    
    content += "\n"
    
    # Add edges (ensure connectivity)
    edges_added = set()
    
    # First ensure every vertex has at least one outgoing edge
    for i in range(vertices):
        target_vertex = random.randint(0, vertices-1)
        if (i, target_vertex) not in edges_added:
            # Generate temporal constraint occasionally
            if random.random() < 0.3:  # 30% chance of constraint
                constraint_type = random.choice([">=", "<", "mod"])
                if constraint_type == ">=":
                    val = random.randint(1, 5)
                    constraint = f't >= {val}'
                elif constraint_type == "<":
                    val = random.randint(5, 15)
                    constraint = f't < {val}'
                else:  # mod
                    mod_val = random.randint(2, 5)
                    remainder = random.randint(0, mod_val-1)
                    constraint = f't mod {mod_val} == {remainder}'
                
                content += f'    v{i} -> v{target_vertex} [constraint="{constraint}"];\n'
            else:
                content += f'    v{i} -> v{target_vertex};\n'
            edges_added.add((i, target_vertex))
    
    # Add some additional random edges
    extra_edges = random.randint(vertices // 2, vertices)
    for _ in range(extra_edges):
        src = random.randint(0, vertices-1)
        dst = random.randint(0, vertices-1)
        if (src, dst) not in edges_added:
            content += f'    v{src} -> v{dst};\n'
            edges_added.add((src, dst))
    
    content += "}\n"
    return content

def generate_ontime_game(vertices, game_id):
    """Generate a TG format game for ontime"""
    # Generate random time bound (5 to vertices//2)
    time_bound = random.randint(5, max(10, vertices // 2))
    
    # Pick a random target vertex
    target = f"v{random.randint(0, vertices-1)}"
    
    # Start TG file
    content = f"// Benchmark game {game_id} - {vertices} vertices\n"
    content += f"// time_bound: {time_bound}\n"
    content += f"// targets: {target}\n"
    
    # Add nodes
    for i in range(vertices):
        owner = random.randint(0, 1)  # 0 or 1 for ontime
        content += f'node v{i}: owner[{owner}]\n'
    
    content += "\n"
    
    # Add edges (ensure connectivity)
    edges_added = set()
    
    # First ensure every vertex has at least one outgoing edge
    for i in range(vertices):
        target_vertex = random.randint(0, vertices-1)
        if (i, target_vertex) not in edges_added:
            # Generate temporal constraint occasionally
            if random.random() < 0.3:  # 30% chance of constraint
                constraint_type = random.choice([">=", "<", "mod"])
                if constraint_type == ">=":
                    val = random.randint(1, 5)
                    constraint = f'(>= t {val})'
                elif constraint_type == "<":
                    val = random.randint(5, 15)
                    constraint = f'(< t {val})'
                else:  # mod
                    mod_val = random.randint(2, 5)
                    remainder = random.randint(0, mod_val-1)
                    constraint = f'(= (mod t {mod_val}) {remainder})'
                
                content += f'edge v{i} -> v{target_vertex}: {constraint}\n'
            else:
                content += f'edge v{i} -> v{target_vertex}\n'
            edges_added.add((i, target_vertex))
    
    # Add some additional random edges
    extra_edges = random.randint(vertices // 2, vertices)
    for _ in range(extra_edges):
        src = random.randint(0, vertices-1)
        dst = random.randint(0, vertices-1)
        if (src, dst) not in edges_added:
            content += f'edge v{src} -> v{dst}\n'
            edges_added.add((src, dst))
    
    return content

def main():
    """Generate benchmark games for both solvers"""
    parser = argparse.ArgumentParser(description="Generate temporal benchmark games")
    parser.add_argument(
        "--output-dir", default=".",
        help="Directory in which to create temporis_games/ and ontime_games/ (default: current directory)"
    )
    parser.add_argument(
        "--count", type=int, default=None,
        help="Maximum number of games to generate (default: all 4500)"
    )
    args = parser.parse_args()

    # Set random seed for reproducible results
    random.seed(42)

    # Create directories
    temporis_dir = os.path.join(args.output_dir, "temporis_games")
    ontime_dir   = os.path.join(args.output_dir, "ontime_games")
    
    # Clean and create directories
    for directory in [temporis_dir, ontime_dir]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)
    
    # Generate games: 15 games each for vertex counts 10, 20, 30, ..., 3000
    vertex_counts = list(range(10, 3010, 10))  # [10, 20, 30, ..., 3000]
    games_per_size = 15
    total_to_generate = args.count if args.count is not None else len(vertex_counts) * games_per_size
    
    print(f"Generating {total_to_generate} temporal benchmark games...")
    print("=" * 55)
    
    game_id = 1
    
    for vertices in vertex_counts:
        progress = (game_id - 1) / total_to_generate * 100
        print(f"[{progress:5.1f}%] Generating {vertices:4d} vertex games... ", end="", flush=True)
        
        for i in range(games_per_size):
            if game_id > total_to_generate:
                break

            # Generate temporis game (.dot)
            temporis_content = generate_temporis_game(vertices, game_id)
            temporis_file = f"{temporis_dir}/test{game_id:05d}.dot"
            with open(temporis_file, 'w') as f:
                f.write(temporis_content)
            
            # Generate ontime game (.tg)
            ontime_content = generate_ontime_game(vertices, game_id)
            ontime_file = f"{ontime_dir}/test{game_id:05d}.tg"
            with open(ontime_file, 'w') as f:
                f.write(ontime_content)
            
            game_id += 1
        
        print("✓")

        if game_id > total_to_generate:
            break
    
    generated = game_id - 1
    print("=" * 55)
    print(f"Generated {generated} temporal benchmark games")
    print(f"Temporis games (.dot): {temporis_dir}/")
    print(f"Ontime games (.tg):    {ontime_dir}/")
    print(f"  - test00001.dot/.tg through test{generated:05d}.dot/.tg")

if __name__ == "__main__":
    main()
