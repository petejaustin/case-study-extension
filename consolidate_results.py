#!/usr/bin/env python3
"""
General consolidation script for temporal solver benchmark results.
Combines results from any number of JSON files into a unified analysis.
"""

import json
import sys
import statistics
import time
import argparse
from pathlib import Path

def load_results(json_file):
    """Load benchmark results from JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            # Extract results array from the benchmark JSON structure
            if isinstance(data, dict) and 'results' in data:
                return data['results']
            elif isinstance(data, list):
                return data
            else:
                print(f"Error: Unexpected JSON structure in {json_file}")
                return None
    except FileNotFoundError:
        print(f"Error: Could not find {json_file}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file}")
        return None

def analyze_results(results, solver_name):
    """Analyze benchmark results for a single solver."""
    if not results:
        return None
    
    # Extract timing data
    successful_results = [result for result in results if result['status'] == 'success']
    times = [result['time'] for result in successful_results]
    vertices = [result['vertices'] for result in successful_results if 'vertices' in result]
    
    if not times:
        return {
            'solver': solver_name,
            'total_games': len(results),
            'successful': 0,
            'failed': len(results),
            'timeouts': sum(1 for r in results if r.get('status') == 'timeout'),
            'success_rate': 0.0
        }
    
    # Calculate statistics
    analysis = {
        'solver': solver_name,
        'total_games': len(results),
        'successful': len(times),
        'failed': len(results) - len(times),
        'timeouts': sum(1 for r in results if r.get('status') == 'timeout'),
        'success_rate': len(times) / len(results) * 100,
        'times': {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'min': min(times),
            'max': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0.0
        }
    }
    
    # Add vertex statistics if available
    if vertices:
        analysis['vertex_counts'] = {
            'min': min(vertices),
            'max': max(vertices),
            'unique': sorted(set(vertices))
        }
        
        # Calculate performance by vertex count
        vertex_performance = {}
        for result in successful_results:
            if 'vertices' in result:
                v_count = result['vertices']
                if v_count not in vertex_performance:
                    vertex_performance[v_count] = []
                vertex_performance[v_count].append(result['time'])
        
        # Summarize by vertex count
        vertex_summary = {}
        for v_count, v_times in vertex_performance.items():
            vertex_summary[v_count] = {
                'count': len(v_times),
                'mean_time': statistics.mean(v_times),
                'median_time': statistics.median(v_times),
                'min_time': min(v_times),
                'max_time': max(v_times)
            }
        
        analysis['performance_by_vertices'] = vertex_summary
    
    return analysis

def extract_solver_names_from_json(results):
    """Extract unique solver names from JSON results."""
    if not results:
        return []
    
    solver_names = set()
    for result in results:
        if 'solver' in result and result['solver']:
            solver_names.add(result['solver'])
    
    return list(solver_names)

def extract_solver_name(filepath):
    """Extract a reasonable solver name from the file path."""
    path = Path(filepath)
    
    # Common patterns to extract solver names
    filename = path.stem
    
    # Remove common prefixes/suffixes
    name = filename.replace('_results', '').replace('consolidated_', '').replace('benchmark_', '')
    
    # Handle specific patterns
    if 'backwards' in name:
        return 'Temporis Backwards'
    elif 'static' in name or 'expansion' in name:
        return 'Temporis Static Expansion'
    elif 'ontime' in name:
        return 'Ontime'
    elif 'temporis' in name:
        return 'Temporis'
    else:
        # Capitalize and clean up
        return name.replace('_', ' ').title()

def main():
    """Main consolidation function."""
    parser = argparse.ArgumentParser(
        description="General consolidation script for temporal solver benchmark results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Consolidate two solvers
  python3 consolidate_results.py results1.json results2.json -o combined.json
  
  # Consolidate three solvers with custom names
  python3 consolidate_results.py \\
    temporis_backwards.json:"Temporis Backwards" \\
    temporis_static.json:"Temporis Static" \\
    ontime.json:"Ontime" \\
    -o analysis.json
  
  # Auto-detect names from many files
  python3 consolidate_results.py *.json -o all_results.json
        """
    )
    
    parser.add_argument('input_files', nargs='+',
                       help='Input JSON files. Format: file.json or file.json:"Custom Name"')
    parser.add_argument('-o', '--output', required=True,
                       help='Output JSON filename')
    parser.add_argument('--timeout', type=int, default=600,
                       help='Original timeout value for metadata (default: 600)')
    
    args = parser.parse_args()
    
    if len(args.input_files) < 1:
        print("Error: At least 1 input file is required")
        sys.exit(1)
    
    print(f"General Temporal Solver Benchmark Consolidation")
    print("=" * 55)
    print(f"Consolidating {len(args.input_files)} result file(s)")
    
    # Parse input files and names
    file_configs = []
    for input_spec in args.input_files:
        if ':' in input_spec and not (len(input_spec) > 2 and input_spec[1] == ':'):  # Handle Windows paths
            # Custom name specified
            filepath, custom_name = input_spec.rsplit(':', 1)
            custom_name = custom_name.strip('"\'')
        else:
            # Load results first to check for solver names in JSON
            filepath = input_spec
            temp_results = load_results(filepath)
            
            if temp_results:
                solver_names_in_json = extract_solver_names_from_json(temp_results)
                if len(solver_names_in_json) == 1:
                    # Single solver in file, use its name
                    custom_name = solver_names_in_json[0]
                elif len(solver_names_in_json) > 1:
                    # Multiple solvers in file, use filename as base
                    custom_name = extract_solver_name(filepath)
                    print(f"Warning: Multiple solvers found in {filepath}: {solver_names_in_json}")
                    print(f"Using filename-based name: {custom_name}")
                else:
                    # No solver names in JSON, fall back to filename
                    custom_name = extract_solver_name(filepath)
            else:
                # Failed to load, use filename
                custom_name = extract_solver_name(filepath)
        
        file_configs.append({
            'path': filepath,
            'name': custom_name
        })
    
    # Load and analyze all results
    all_results = []
    all_analyses = {}
    total_games = 0
    
    for config in file_configs:
        filepath = config['path']
        solver_name = config['name']
        
        print(f"Loading results from: {filepath}")
        results = load_results(filepath)
        
        if not results:
            print(f"Failed to load {filepath}, skipping...")
            continue

        # Check if file contains multiple solvers
        solver_names_in_file = extract_solver_names_from_json(results)
        
        if len(solver_names_in_file) > 1:
            # Handle multiple solvers separately
            print(f"Processing {len(solver_names_in_file)} solvers from file: {solver_names_in_file}")
            
            for individual_solver in solver_names_in_file:
                # Filter results for this specific solver
                solver_results = [r for r in results if r.get('solver') == individual_solver]
                
                if solver_results:
                    print(f"Analyzing {individual_solver} performance...")
                    analysis = analyze_results(solver_results, individual_solver)
                    
                    if analysis:
                        all_analyses[individual_solver] = analysis
                        
                        # Add results with original solver names preserved
                        for result in solver_results:
                            result_copy = result.copy()
                            # Keep original solver name
                            all_results.append(result_copy)
        else:
            # Single solver or use file-based name
            print(f"Analyzing {solver_name} performance...")
            analysis = analyze_results(results, solver_name)
            
            if analysis:
                all_analyses[solver_name] = analysis
                
                # Add solver name to each result
                for result in results:
                    result_copy = result.copy()
                    result_copy['solver'] = solver_name
                    all_results.append(result_copy)
            
            if total_games == 0:
                total_games = len(results)  # Assume all solvers tested same games
    
    if not all_results:
        print("Error: No valid results loaded")
        sys.exit(1)
    
    # Create consolidated report
    consolidated = {
        "benchmark_info": {
            "timestamp": time.time(),
            "games_dir": "consolidated_temporal_analysis",
            "total_tests": len(all_results),
            "solvers_tested": len(all_analyses),
            "games_tested": total_games,
            "timeout_seconds": args.timeout,
            "consolidation_metadata": {
                "source_files": [config['path'] for config in file_configs],
                "solver_names": list(all_analyses.keys()),
                "analysis_timestamp": time.time()
            }
        },
        "results": all_results,
        "analysis": all_analyses
    }
    
    # Save consolidated results
    with open(args.output, 'w') as f:
        json.dump(consolidated, f, indent=2)
    
    # Print summary
    print(f"\n" + "=" * 55)
    print("CONSOLIDATED ANALYSIS SUMMARY")
    print("=" * 55)
    print(f"Total results combined: {len(all_results)}")
    print(f"Unique games: {total_games}")
    print(f"Solvers analyzed: {len(all_analyses)}")
    print("")
    
    # Print individual solver performance
    mean_times = {}
    for solver_name, analysis in all_analyses.items():
        print(f"{solver_name} Performance:")
        print(f"  Success rate: {analysis['success_rate']:.1f}%")
        print(f"  Mean time: {analysis['times']['mean']:.6f}s")
        print(f"  Median time: {analysis['times']['median']:.6f}s")
        if analysis.get('timeouts', 0) > 0:
            print(f"  Timeouts: {analysis['timeouts']}")
        print("")
        
        mean_times[solver_name] = analysis['times']['mean']
    
    # Overall comparison
    if len(mean_times) > 1:
        fastest_solver = min(mean_times.keys(), key=lambda k: mean_times[k])
        slowest_solver = max(mean_times.keys(), key=lambda k: mean_times[k])
        
        print(f"Overall Comparison:")
        print(f"  Fastest solver: {fastest_solver} ({mean_times[fastest_solver]:.6f}s)")
        print(f"  Slowest solver: {slowest_solver} ({mean_times[slowest_solver]:.6f}s)")
        print(f"  Speed difference: {mean_times[slowest_solver] / mean_times[fastest_solver]:.2f}x")
        print("")
        
        print(f"Rankings by mean time:")
        for i, (solver, time_val) in enumerate(sorted(mean_times.items(), key=lambda x: x[1]), 1):
            print(f"  {i}. {solver}: {time_val:.6f}s")
        print("")
    
    print(f"GGG-compatible results saved to: {args.output}")
    print(f"  Format: Compatible with GGG plotting scripts")

if __name__ == "__main__":
    main()
