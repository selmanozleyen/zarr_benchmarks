#!/usr/bin/env python3

import os
import timeit
import click

import zarr
from zarr.storage import LocalStore, FsspecStore

import zarrs
zarr.config.set({
    "threading.num_workers": None,
    "array.write_empty_chunks": False,
    "codec_pipeline": {
        'batch_size': 1,
        "path": "zarrs.ZarrsCodecPipeline",
        "validate_checksums": True,
        "store_empty_chunks": False,
        "chunk_concurrent_minimum": 4,
        "chunk_concurrent_maximum": None,
    }
})
# Two-stage builds size their read and decode pools from these; other builds ignore them.
for key, var in (("read_workers", "ZARRS_READ_WORKERS"), ("decode_workers", "ZARRS_DECODE_WORKERS")):
    if os.environ.get(var):
        zarr.config.set({f"codec_pipeline.{key}": int(os.environ[var])})

@click.command()
@click.argument('path', type=str)
@click.argument('output', type=str)
def main(path, output):
    if path.startswith("http"):
        store = FsspecStore.from_url(url=path) # broken with zarr-python 3.0.0a0
    else:
        store = LocalStore(path, read_only=True)

    dataset = zarr.open(store=store, mode='r')
    dataset_out = zarr.create(store=LocalStore(output), mode='w', shape=dataset.shape, chunks=dataset.chunks, dtype=dataset.dtype, codecs=dataset.metadata.codecs)

    start_time = timeit.default_timer()

    dataset_out[:] = dataset[:]

    elapsed = timeit.default_timer() - start_time
    elapsed_ms = elapsed * 1000.0

    print(f"Round trip in {elapsed_ms:.2f}ms")
    pool_sizes = getattr(getattr(zarrs, "_internal", None), "pool_sizes", None)
    print(f"pools: {pool_sizes() if pool_sizes else 'single pool'} zarrs {zarrs.__version__}")

if __name__ == "__main__":
    main()
