#!/usr/bin/env python3
"""Random access along axis 0: sorted, unsorted and strided indices, per implementation.

The other read benchmarks read whole arrays or whole chunks in order. This one reads a set of
indices along axis 0 (slabs of the 3-D images, rows of the 2-D one) in one call, the access
of a data loader drawing samples. Indices are drawn afresh on every run, after the clock-free
setup, so no run is served from the page cache of the one before.
"""

import math
import re
import subprocess

import numpy as np
import pandas as pd

from zarr_benchmarks import clear_cache, time_args

IMPLEMENTATIONS = {
    "tensorstore_python": "./src/zarr_benchmarks/tensorstore_python_benchmark_read.py",
    "zarr_python": "./src/zarr_benchmarks/zarr_python_benchmark_read.py",
    "zarrs_python": "./src/zarr_benchmarks/zarrs_python_benchmark_read.py",
}

CASES = [
    (image, pattern, flags)
    for image in ["data/benchmark.zarr", "data/benchmark_compress.zarr", "data/benchmark_compress_shard.zarr"]
    for pattern, flags in [
        ("random 64", ["--random", "64"]),
        ("unsorted 64", ["--random", "64", "--unsorted"]),
        ("strided 16", ["--strided", "16"]),
    ]
] + [
    ("data/benchmark_rows_shard.zarr", pattern, flags)
    for pattern, flags in [
        ("random 8192", ["--random", "8192"]),
        ("unsorted 8192", ["--random", "8192", "--unsorted"]),
        ("strided 128", ["--strided", "128"]),
    ]
]
BEST_OF = 5


def measure(script, flags, image):
    clear_cache(image)
    p = subprocess.run(time_args() + [script, *flags, image], capture_output=True, text=True)
    wall = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\d+):([\d.]+)", p.stderr)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", p.stderr)
    if p.returncode != 0 or not (wall and rss):
        print(p.stdout, p.stderr)
        return math.nan, math.nan
    return int(wall.group(1)) * 60 + float(wall.group(2)), int(rss.group(1)) / 1e6


def main():
    rows = []
    for image, pattern, flags in CASES:
        times, memories = [], []
        for implementation, script in IMPLEMENTATIONS.items():
            got = []
            for i in range(BEST_OF):
                print(implementation, image, pattern, i, flush=True)
                got.append(measure(script, flags, image))
            times.append(np.nanmin([g[0] for g in got]))
            memories.append(np.nanmin([g[1] for g in got]))
        rows.append([image, pattern, *times, *memories])

    columns_markdown = ["Image", "Pattern"]
    for metric in ["Time (s)", "Memory (GB)"]:
        for k, implementation in enumerate(IMPLEMENTATIONS):
            columns_markdown.append((metric if k == 0 else "") + "<br>" + implementation.replace("_", "<br>"))
    df = pd.DataFrame(rows, columns=columns_markdown)
    df.to_csv("measurements/benchmark_read_random.csv", index=False)
    df.to_markdown("measurements/benchmark_read_random.md", index=False, floatfmt=".02f")
    print(df.to_markdown(index=False, floatfmt=".02f"))


if __name__ == "__main__":
    main()
