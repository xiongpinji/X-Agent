"""Run X-Agent load tests with SLO validation.

Executes Locust in headless mode, parses CSV output, and validates
results against configured SLO targets.

Usage:
    python benchmarks/load_test/run_load_test.py --profile smoke
    python benchmarks/load_test/run_load_test.py --profile stress --host http://localhost:8000
    python benchmarks/load_test/run_load_test.py --profile normal --skip-slo
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.load_test.config import (  # noqa: E402
    CSV_OUTPUT_DIR,
    DEFAULT_HOST,
    DEFAULT_PROFILE,
    LOCUSTFILE_PATH,
    PROFILES,
    SLO,
    LoadTestResult,
)


def run_locust(profile: str, host: str, csv_prefix: str) -> int:
    """Run locust in headless mode and return exit code."""
    cfg = PROFILES[profile]
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        LOCUSTFILE_PATH,
        "--host",
        host,
        "--users",
        str(cfg["users"]),
        "--spawn-rate",
        str(cfg["spawn_rate"]),
        "--run-time",
        str(cfg["duration"]),
        "--headless",
        "--csv",
        csv_prefix,
        "--only-summary",
    ]
    print(f"\n{'='*70}")
    print(f"  Running load test: profile={profile}")
    print(f"  Users={cfg['users']}  SpawnRate={cfg['spawn_rate']}  Duration={cfg['duration']}")
    print(f"  Host: {host}")
    print(f"  CSV output: {csv_prefix}_stats.csv")
    print(f"{'='*70}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def parse_stats_csv(csv_path: str) -> LoadTestResult | None:
    """Parse the locust *_stats.csv aggregate row."""
    path = Path(csv_path)
    if not path.exists():
        print(f"[WARN] Stats file not found: {csv_path}")
        return None

    result = LoadTestResult(profile="")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # The aggregate row has Name == "Aggregated"
            if row.get("Name", "").strip().lower() == "aggregated":
                result.total_requests = int(row.get("Request Count", 0))
                result.total_failures = int(row.get("Failure Count", 0))
                result.avg_response_time_ms = float(row.get("Average Response Time", 0))
                result.max_response_time_ms = float(row.get("Max Response Time", 0))
                result.requests_per_second = float(row.get("Requests/s", 0))
                # Percentile columns
                result.p95_response_time_ms = float(row.get("95%", 0))
                result.p99_response_time_ms = float(row.get("99%", 0))
                break

    if result.total_requests > 0:
        result.error_rate_percent = (
            result.total_failures / result.total_requests
        ) * 100.0

    return result


def validate_slo(result: LoadTestResult) -> None:
    """Check result against SLO targets; populate violations."""
    violations: list[str] = []

    if result.p95_response_time_ms > SLO["p95_latency_ms"]:
        violations.append(
            f"P95 latency {result.p95_response_time_ms:.1f}ms > {SLO['p95_latency_ms']}ms"
        )
    if result.p99_response_time_ms > SLO["p99_latency_ms"]:
        violations.append(
            f"P99 latency {result.p99_response_time_ms:.1f}ms > {SLO['p99_latency_ms']}ms"
        )
    if result.error_rate_percent > SLO["error_rate_percent"]:
        violations.append(
            f"Error rate {result.error_rate_percent:.2f}% > {SLO['error_rate_percent']}%"
        )
    if result.requests_per_second < SLO["min_throughput_rps"]:
        violations.append(
            f"Throughput {result.requests_per_second:.1f} rps < {SLO['min_throughput_rps']} rps"
        )

    result.slo_violations = violations
    result.slo_passed = len(violations) == 0


def print_report(result: LoadTestResult) -> None:
    """Print a human-readable report."""
    print(f"\n{'='*70}")
    print("  LOAD TEST RESULTS")
    print(f"{'='*70}")
    print(f"  Profile          : {result.profile}")
    print(f"  Total requests   : {result.total_requests}")
    print(f"  Total failures   : {result.total_failures}")
    print(f"  Error rate       : {result.error_rate_percent:.3f}%")
    print(f"  Avg response     : {result.avg_response_time_ms:.1f} ms")
    print(f"  P95 response     : {result.p95_response_time_ms:.1f} ms")
    print(f"  P99 response     : {result.p99_response_time_ms:.1f} ms")
    print(f"  Max response     : {result.max_response_time_ms:.1f} ms")
    print(f"  Throughput       : {result.requests_per_second:.1f} rps")
    print(f"{'='*70}")

    if result.slo_passed:
        print("  SLO STATUS: ✅ PASSED")
    else:
        print("  SLO STATUS: ❌ FAILED")
        for v in result.slo_violations:
            print(f"    - {v}")
    print(f"{'='*70}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="X-Agent Load Test Runner")
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        default=DEFAULT_PROFILE,
        help=f"Load test profile (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Target host URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--skip-slo",
        action="store_true",
        help="Skip SLO validation (useful for exploratory testing)",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Path to write JSON result file",
    )
    args = parser.parse_args()

    # Prepare output directory
    output_dir = PROJECT_ROOT / CSV_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    csv_prefix = str(output_dir / f"{args.profile}_{timestamp}")

    # Run locust
    exit_code = run_locust(args.profile, args.host, csv_prefix)

    # Parse results
    stats_csv = f"{csv_prefix}_stats.csv"
    result = parse_stats_csv(stats_csv)

    if result is None:
        print("[ERROR] Could not parse load test results.")
        return 1

    result.profile = args.profile

    # SLO validation
    if not args.skip_slo:
        validate_slo(result)
    else:
        result.slo_passed = True  # Skip

    # Report
    print_report(result)

    # Optional JSON output
    json_path = args.json_output or str(output_dir / f"{args.profile}_{timestamp}_result.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"  JSON result saved: {json_path}")

    # Exit code: non-zero if SLO failed
    if not result.slo_passed:
        return 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
