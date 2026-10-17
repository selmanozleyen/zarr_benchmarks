#!/usr/bin/env python3
"""Generate a 2-D, row-major benchmark array: many rows of a few hundred columns, sharded.

    python generate_benchmark_rows.py data/benchmark_rows_shard.zarr

The 3-D datasets from generate_benchmark_array.rs are read in boxes. This one is shaped like
a dataset read by rows (cells, samples): 1,048,576 rows x 512 uint16, zstd, 64-row inner chunks
in 4096-row shards. Values follow generate_benchmark_array.rs, so it compresses alike.
"""

import sys

import click
import numpy as np
import zarr
from zarr.codecs import ZstdCodec


@click.command()
@click.argument("output_path", type=str)
@click.option("--rows", type=int, default=1 << 20, show_default=True)
@click.option("--cols", type=int, default=512, show_default=True)
@click.option("--inner-rows", type=int, default=64, show_default=True)
@click.option("--shard-rows", type=int, default=4096, show_default=True)
def main(output_path, rows, cols, inner_rows, shard_rows):
    array = zarr.create_array(
        output_path,
        shape=(rows, cols),
        chunks=(inner_rows, cols),
        shards=(shard_rows, cols),
        dtype="uint16",
        compressors=ZstdCodec(level=0),
        fill_value=0,
        overwrite=True,
    )
    g1 = np.arange(cols, dtype=np.uint64)
    for start in range(0, rows, shard_rows):
        g0 = np.arange(start, min(start + shard_rows, rows), dtype=np.uint64)[:, None]
        array[start : start + len(g0)] = ((g1 + g0 * g0) % 65536).astype(np.uint16)
    print(f"Array successfully written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
