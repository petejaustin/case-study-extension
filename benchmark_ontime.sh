#!/bin/bash

# Benchmark Script for ontime solver
# Usage: bash benchmark_ontime.sh <games_dir> <ontime_binary> [timeout] [output_file]

set -eu
shopt -s nullglob

if [ $# -lt 2 ]; then
  echo "Usage: $0 <games_dir> <ontime_binary> [timeout_seconds] [output_file]" >&2
  exit 1
fi

games_dir="$1"
ontime_binary="$2"
timeout_sec="${3:-300}"

script_dir="$(cd "$(dirname "$0")" && pwd)"
if [ $# -ge 4 ]; then
  output_file="$4"
else
  output_file="$script_dir/ontime_results.json"
fi

results="[\n"
first=1

# Extract metadata from .tg file
extract_metadata() {
  local file="$1"
  local time_bound="" targets=""
  
  while IFS= read -r line; do
    if [[ "$line" =~ ^//\ time_bound:\ ([0-9]+) ]]; then
      time_bound="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^//\ targets:\ (.+) ]]; then
      targets="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^node ]]; then
      # Stop at first node declaration
      break
    fi
  done < "$file"
  
  echo "$time_bound $targets"
}

# Count vertices and edges in .tg file
count_tg() {
  local file="$1"
  local edges=0 vertices=0
  while IFS= read -r line; do
    if [[ "$line" =~ ^node ]]; then
      vertices=$((vertices+1))
    elif [[ "$line" =~ ^edge ]]; then
      edges=$((edges+1))
    fi
  done < "$file"
  echo "$vertices $edges"
}

# Parse solver output time
parse_time() {
  local output="$1"
  local fallback="$2"

  if printf "%s\n" "$output" | grep -q "Time to solve:"; then
    local t unit
    t=$(printf "%s\n" "$output" | grep "Time to solve:" | awk '{print $4}')
    unit=$(printf "%s\n" "$output" | grep "Time to solve:" | awk '{print $5}')
    if [ "$unit" = "ms" ]; then
      awk "BEGIN { printf \"%.9f\\n\", $t/1000 }" | sed 's/^\./0./'
    else
      printf "%.9f\n" "$t" | sed 's/^\./0./'
    fi
  elif printf "%s\n" "$output" | grep -q "^Time:"; then
    val=$(printf "%s\n" "$output" | grep "^Time:" | awk '{print $2}' | sed 's/s//')
    printf "%.9f\n" "$val" | sed 's/^\./0./'
  else
    printf "%.9f\n" "$fallback" | sed 's/^\./0./'
  fi
}

# Solver execution function
run_solver() {
  local game="$1"
  local game_name vertices edges start end elapsed output status time_val rc
  local time_bound targets

  game_name=$(basename "$game" .tg)

  # Extract metadata
  set -- $(extract_metadata "$game")
  time_bound=$1
  targets=$2
  
  if [ -z "$time_bound" ] || [ -z "$targets" ]; then
    echo "Warning: Missing metadata in $game_name, skipping"
    return
  fi

  # Count vertices and edges
  set -- $(count_tg "$game")
  vertices=$1
  edges=$2

  start=$(date +%s.%N)
  if output=$(timeout "$timeout_sec" "$ontime_binary" --time-only --target-set "$targets" --time-to-reach "$time_bound" "$game" 2>&1); then
    end=$(date +%s.%N)
    elapsed=$(echo "$end - $start" | bc | sed 's/^\./0./')
    status="success"
    time_val=$(parse_time "$output" "$elapsed")
  else
    rc=$?
    if [ $rc -eq 124 ]; then
      status="timeout"
      time_val="$timeout_sec"
    else
      status="failed"
      time_val="null"
    fi
  fi

  [ $first -eq 0 ] && results+=",\n"
  first=0

  json="  {\"solver\":\"ontime\",\"game\":\"$game_name\""
  json+=",\"status\":\"$status\",\"time\":$time_val,\"vertices\":$vertices,\"edges\":$edges"
  json+=",\"time_bound\":$time_bound,\"targets\":\"$targets\",\"timestamp\":$(date +%s)}"
  results+="$json"

  echo "Processed $game_name with ontime ($status, ${vertices}v, ${edges}e, t=$time_bound)"
}

# Process all .tg files
echo "Starting ontime benchmark..."
echo "Games directory: $games_dir"
echo "Ontime binary: $ontime_binary"
echo "Timeout: ${timeout_sec}s"
echo "Output file: $output_file"
echo ""

tg_files=("$games_dir"/*.tg)
total_games=${#tg_files[@]}

if [ $total_games -eq 0 ]; then
  echo "No .tg files found in $games_dir"
  exit 1
fi

echo "Found $total_games .tg files to process"
echo ""

processed=0
for game in "${tg_files[@]}"; do
  [ -f "$game" ] || continue
  run_solver "$game"
  processed=$((processed+1))
  if [ $((processed % 50)) -eq 0 ]; then
    echo "Progress: $processed/$total_games games processed"
  fi
done

results+="\n]"
printf "%b\n" "$results" > "$output_file"
echo ""
echo "Benchmark completed!"
echo "Processed $processed games"
echo "Results written to $output_file"
