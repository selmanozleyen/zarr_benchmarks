#!/usr/bin/env python3
"""Compare zarrs-python builds against each other on the read benchmarks.

Each arm is a Python interpreter with one zarrs-python build installed:

    ARMS="main=/venvs/main/bin/python two-stage=/venvs/two-stage/bin/python:16:16" \
        uv run run_benchmark_arms

An optional `:READ:DECODE[:READ_AHEAD_BYTES]` suffix sets `codec_pipeline.read_workers`,
`codec_pipeline.decode_workers` and `codec_pipeline.read_ahead_bytes` for that arm (empty fields
keep the default); a build without those settings ignores them.
Repetitions are interleaved across arms (arm order shuffled per repetition) so a drifting
machine hits every arm alike. BEST_OF repetitions per arm; each case reports the best (as the
other benchmarks do) and the median with its 20th-80th percentile spread, since on a noisy
machine the best of a few runs is decided by one lucky run.
"""

import math
import os
import random
import re
import subprocess
import tempfile

import numpy as np
import pandas as pd

from zarr_benchmarks import clear_cache, time_args

READ = "./src/zarr_benchmarks/zarrs_python_benchmark_read.py"
ROUNDTRIP = "./src/zarr_benchmarks/zarrs_python_benchmark_roundtrip.py"
IMAGES = [
    "data/benchmark.zarr",
    "data/benchmark_compress.zarr",
    "data/benchmark_compress_shard.zarr",
]
CONCURRENCY = [1, 2, 4, 8]


def parse_arms(spec: str) -> list[tuple[str, str, dict[str, str]]]:
    arms = []
    for entry in spec.split():
        name, rest = entry.split("=", 1)
        python, *fields = rest.split(":")
        names = ("ZARRS_READ_WORKERS", "ZARRS_DECODE_WORKERS", "ZARRS_READ_AHEAD_BYTES")
        env = {name: value for name, value in zip(names, fields) if value}
        arms.append((name, python, env))
    return arms


def cases() -> list[tuple[str, str, list[str]]]:
    out = [("read_all", image, ["--read_all"]) for image in IMAGES]
    for image in IMAGES:
        for c in CONCURRENCY:
            out.append((f"chunks c={c}", image, ["--concurrent_chunks", str(c)]))
    for c in CONCURRENCY:
        out.append((f"subchunks c={c}", IMAGES[2], ["--subchunks", "--concurrent_chunks", str(c)]))
    out += [("roundtrip", image, []) for image in IMAGES]
    return out


def run_once(python: str, env: dict[str, str], label: str, flags: list[str], image: str) -> dict:
    clear_cache(image)
    with tempfile.TemporaryDirectory(dir="data") as output:
        args = [ROUNDTRIP, image, output] if label == "roundtrip" else [READ, *flags, image]
        p = subprocess.run(
            time_args() + [python, *args], capture_output=True, text=True, env={**os.environ, **env}
        )
    wall = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\d+):([\d.]+)", p.stderr)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", p.stderr)
    decoded = re.search(r"(?:Decoded|Round trip) in ([\d.]+)ms", p.stdout)
    pools = re.search(r"^pools: (.*)$", p.stdout, re.M)
    if p.returncode != 0 or not (wall and rss and decoded):
        print(p.stdout, p.stderr)
        return {"wall": math.nan, "decoded": math.nan, "rss": math.nan, "pools": "FAILED"}
    return {
        "wall": int(wall.group(1)) * 60 + float(wall.group(2)),
        "decoded": float(decoded.group(1)) / 1e3,
        "rss": int(rss.group(1)) / 1e6,
        "pools": pools.group(1) if pools else "?",
    }


def main():
    arms = parse_arms(os.environ["ARMS"])
    best_of = int(os.environ.get("BEST_OF", "5"))
    names = [a[0] for a in arms]
    rows = []
    for label, image, flags in cases():
        got = {name: [] for name in names}
        for rep in range(best_of):
            for name, python, env in random.sample(arms, len(arms)):
                r = run_once(python, env, label, flags, image)
                print(f"{label:14s} {image:36s} {name:12s} rep {rep}  {r}", flush=True)
                got[name].append(r)
        row = {"case": label, "image": os.path.basename(image)}
        for name in names:
            decoded = [r["decoded"] for r in got[name]]
            row[f"{name} median (s)"] = np.nanmedian(decoded)
            row[f"{name} p20 (s)"] = np.nanpercentile(decoded, 20)
            row[f"{name} p80 (s)"] = np.nanpercentile(decoded, 80)
            row[f"{name} decoded (s)"] = np.nanmin(decoded)
            row[f"{name} wall (s)"] = np.nanmin([r["wall"] for r in got[name]])
            row[f"{name} memory (GB)"] = np.nanmin([r["rss"] for r in got[name]])
            row[f"{name} pools"] = got[name][-1]["pools"]
        base = row[f"{names[0]} decoded (s)"]
        for name in names[1:]:
            row[f"{name} time / {names[0]} time"] = row[f"{name} decoded (s)"] / base
            row[f"{names[0]} / {name} median speedup"] = (
                row[f"{names[0]} median (s)"] / row[f"{name} median (s)"]
            )
        rows.append(row)
        print(pd.DataFrame([row]).to_string(index=False), flush=True)

    df = pd.DataFrame(rows)
    os.makedirs("measurements", exist_ok=True)
    df.to_csv("measurements/benchmark_arms.csv", index=False)
    df.to_markdown("measurements/benchmark_arms.md", index=False, floatfmt=".03f")
    print(df.to_markdown(index=False, floatfmt=".03f"))


if __name__ == "__main__":
    main()
