"""Repeat a few of Lachlan's cases N times per build, alternating, cold; medians and spread.

    python noise.py N name=/path/to/python ... -- case ...    (run from zarr_benchmarks/)

Each arm prints median ms, p20-p80, and the first arm's median over its own.
"""
import re
import statistics
import subprocess
import sys

CASES = {
    "read_all_uncompressed": ["read", "--read_all", "data/benchmark.zarr"],
    "read_all_compressed": ["read", "--read_all", "data/benchmark_compress.zarr"],
    "read_all_sharded": ["read", "--read_all", "data/benchmark_compress_shard.zarr"],
    "chunks_c2_uncompressed": ["read", "--concurrent_chunks", "2", "data/benchmark.zarr"],
    "chunks_c4_compressed": ["read", "--concurrent_chunks", "4", "data/benchmark_compress.zarr"],
    "roundtrip_uncompressed": ["roundtrip", "data/benchmark.zarr", "data/_rt_out"],
    "random64_compressed": ["read", "--random", "64", "data/benchmark_compress.zarr"],
    "unsorted64_compressed": ["read", "--random", "64", "--unsorted", "data/benchmark_compress.zarr"],
    "strided16_compressed": ["read", "--strided", "16", "data/benchmark_compress.zarr"],
    "random64_sharded": ["read", "--random", "64", "data/benchmark_compress_shard.zarr"],
    "random8192_rows": ["read", "--random", "8192", "data/benchmark_rows_shard.zarr"],
}
SCRIPT = {
    "read": "src/zarr_benchmarks/zarrs_python_benchmark_read.py",
    "roundtrip": "src/zarr_benchmarks/zarrs_python_benchmark_roundtrip.py",
}


def run(python, case):
    kind, *args = CASES[case]
    subprocess.run("sync && sudo -n /usr/sbin/purge", shell=True, check=True)
    p = subprocess.run([python, SCRIPT[kind], *args], capture_output=True, text=True)
    m = re.search(r"(?:Decoded|Round trip) in ([\d.]+)ms", p.stdout)
    if not m:
        raise SystemExit(f"{case} on {python}: no timing\n{p.stdout}\n{p.stderr[-2000:]}")
    subprocess.run(["rm", "-rf", "data/_rt_out"])
    return float(m.group(1))


def main():
    n = int(sys.argv[1])
    sep = sys.argv.index("--")
    arms = dict(a.split("=", 1) for a in sys.argv[2:sep])
    for case in sys.argv[sep + 1:]:
        times = {name: [] for name in arms}
        for _ in range(n):
            for name, python in arms.items():
                times[name].append(run(python, case))
        base = statistics.median(next(iter(times.values())))
        spread = lambda t: f"{sorted(t)[len(t) // 5]:.0f}-{sorted(t)[-1 - len(t) // 5]:.0f}"
        cells = "  ".join(f"{name} {statistics.median(t):7.1f} ({spread(t)}) {base / statistics.median(t):.2f}x"
                          for name, t in times.items())
        print(f"{case:24s} {cells}", flush=True)


if __name__ == "__main__":
    main()
