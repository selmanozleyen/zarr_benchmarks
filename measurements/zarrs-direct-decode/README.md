# Box on zarrs with direct decode

Is box's 0.70x on compressed, unsharded random reads (`../benchmark_arms_random.md`) caused
by box or by zarrs? Apple M3 SSD, `sudo -n /usr/sbin/purge` before every run, 10 runs per
build alternating, medians, all arms in one run. Runner: `noise.py`, run from the repo root.

| build | zarrs-python (fork branch) | zarrs |
|---|---|---|
| main_old | `bd21dba` `main-on-zarrs-1e81e6b5` | `1e81e6b5` |
| main_b2b | `e1bf324` `main-on-zarrs-b2b`, benchmark-only | `2a9a113c` |
| box_old | `f1556f1` `run-selection-unify` (= `box-on-main024` code) | `1e81e6b5` |
| box_b2b | `4005155` `box-on-zarrs-b2b`, benchmark-only | `2a9a113c` |

zarrs `2a9a113c` is `perf/direct_b2b_decode` (main 2026-10-04 + 6 commits): zstd decodes
straight into the output. Upstream put it up as #476-#481 and closed them unmerged on
2026-10-09. `bench_only_b2b.py` made the benchmark-only builds: they drop the HTTP and
obstore stores, whose released adapters need zarrs_storage 0.4.

`2x2.txt`, median ms (main_old / build):

| case | main_old | main_b2b | box_old | box_b2b |
|---|---:|---:|---:|---:|
| random 64, compressed | 100.7 (1.00x) | 100.3 (1.00x) | 143.8 (0.70x) | 97.1 (1.04x) |
| random 64, sharded | 447.4 (1.00x) | 451.1 (0.99x) | 268.3 (1.67x) | 272.2 (1.64x) |

Main hands an integer selection back to zarr-python (`fallbacks 1`), so zarrs' decode never
runs for it. Box decodes those chunks with zarrs' `decode_into` (`fallbacks 0`), and on
`1e81e6b5` zstd decompresses into a temporary and copies. The regression is that copy. The
sharded gain is box's own and does not move with zarrs.

`main-vs-box.txt` is the earlier two-build run on `2a9a113c`, seven cases, from `noise.py`
before it took more than two arms.

These files were rebuilt from the session transcript on 2026-10-26, after macOS cleared the
scratchpad they were written to. The numbers are the printed output, unchanged.
