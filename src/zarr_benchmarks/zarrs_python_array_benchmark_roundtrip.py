#!/usr/bin/env python3

import timeit
import click

import zarr
from zarrs import ZarrsArray


@click.command()
@click.argument("path", type=str)
@click.argument("output", type=str)
def main(path, output):
    dataset = zarr.open(path, mode="r")
    output_arr = zarr.create_array(
        store=output,
        shape=dataset.shape,
        shards=dataset.shards,
        chunks=dataset.chunks,
        dtype=dataset.dtype,
        filters=dataset.filters,
        compressors=dataset.compressors,
        serializer=dataset.serializer,
    )

    arr_in = ZarrsArray(dataset, validate_checksums=True, direct_io=True)
    arr_out = ZarrsArray(output_arr, direct_io=True)

    start_time = timeit.default_timer()

    arr_out[:] = arr_in.lazy[:]

    elapsed = timeit.default_timer() - start_time
    elapsed_ms = elapsed * 1000.0

    print(f"Round trip in {elapsed_ms:.2f}ms")


if __name__ == "__main__":
    main()
