"""Measure a reproducible ETL run and report runtime resource metrics.

Usage:
    python scripts/benchmark.py --limit 100000 --truncate --skip-indexes
    python scripts/benchmark.py --truncate
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Allow `python scripts/benchmark.py` from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows
    resource = None

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark the IDS ETL pipeline and print JSON metrics."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--truncate", action="store_true")
    parser.add_argument("--skip-indexes", action="store_true")
    args = parser.parse_args()

    from src.config import DEFAULT_CHUNK_SIZE
    from src.pipeline import run_pipeline

    chunk_size = args.chunk_size or DEFAULT_CHUNK_SIZE
    started = time.perf_counter()
    stats = run_pipeline(
        limit=args.limit,
        chunk_size=chunk_size,
        truncate=args.truncate,
        skip_indexes=args.skip_indexes,
    )
    elapsed_seconds = time.perf_counter() - started

    peak_rss_mb = None
    if resource is not None:
        # Linux reports kilobytes; macOS reports bytes.
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if peak_rss > 10_000_000:
            peak_rss_mb = peak_rss / (1024 * 1024)
        else:
            peak_rss_mb = peak_rss / 1024

    result = {
        "rows_read": stats.rows_read,
        "rows_loaded": stats.rows_loaded,
        "rows_dropped": stats.total_dropped(),
        "chunk_size": chunk_size,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rows_per_second": round(
            stats.rows_loaded / elapsed_seconds if elapsed_seconds else 0, 2
        ),
        "peak_rss_mb": round(peak_rss_mb, 2) if peak_rss_mb is not None else None,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
