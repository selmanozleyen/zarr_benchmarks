#!/usr/bin/env python3

import numpy as np
import timeit
import asyncio
import click
from functools import wraps
import os
import sys

import zarr
from zarr.storage import LocalStore, FsspecStore
from zarr.core.indexing import BlockIndexer
from zarr.core.buffer import default_buffer_prototype

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


def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper

@click.command()
@coro
@click.argument('path', type=str)
@click.option('--concurrent_chunks', type=int, default=None, help='Number of concurrent async chunk reads. Ignored if --read-all is set')
@click.option('--subchunks', is_flag=True, show_default=True, default=False, help='Reader inner-chunk-by-inner-chunk. Ignored if --read-all is set')
@click.option('--read_all', is_flag=True, show_default=True, default=False, help='Read the entire array in one operation.')
async def main(path, concurrent_chunks, subchunks, read_all):
    # if "benchmark_compress_shard.zarr" in path:
    #     sys.exit(1)

    if path.startswith("http"):
        store = FsspecStore.from_url(url=path) # broken with zarr-python 3.0.0a0
    else:
        store = LocalStore(path, read_only=True)

    dataset = zarr.open(store=store, mode='r')
    # Count reads handed to zarr-python's own pipeline: a fallback is not a zarrs number.
    fallbacks = [0]
    pipeline = dataset._async_array.codec_pipeline
    if getattr(pipeline, "python_impl", None) is not None:
        python_read = pipeline.python_impl.read
        async def counted(*a, **k):
            fallbacks[0] += 1
            return await python_read(*a, **k)
        object.__setattr__(pipeline.python_impl, "read", counted)

    domain_shape = dataset.shape
    if subchunks:
        chunk_shape = dataset.chunks
    else:
        chunk_shape = dataset.shards or dataset.chunks

    print("Domain shape", domain_shape)
    print("Chunk shape", chunk_shape)
    num_chunks =[(domain + chunk_shape - 1) // chunk_shape for (domain, chunk_shape) in zip(domain_shape, chunk_shape)]
    print("Number of chunks", num_chunks)

    def get_chunk_indexer(chunk_idx, chunk_shape):
        return tuple(slice(i * s, (1 + i) * s) for i, s in zip(chunk_idx, chunk_shape))

    async def chunk_read(indexer):
        return await dataset._async_array.getitem(indexer)

    start_time = timeit.default_timer()
    if read_all:
        print(dataset[:].shape)
    elif concurrent_chunks is None:
        async with asyncio.TaskGroup() as tg:
            for chunk_index in np.ndindex(*num_chunks):
                tg.create_task(chunk_read(get_chunk_indexer(chunk_index, chunk_shape)))
    elif concurrent_chunks == 1:
        for chunk_index in np.ndindex(*num_chunks):
            dataset[get_chunk_indexer(chunk_index, chunk_shape)]
    else:
        semaphore = asyncio.Semaphore(concurrent_chunks)
        async def chunk_read_concurrent_limit(chunk_index):
            async with semaphore:
                return await chunk_read(get_chunk_indexer(chunk_index, chunk_shape))
        async with asyncio.TaskGroup() as tg:
            for chunk_index in np.ndindex(*num_chunks):
                tg.create_task(chunk_read_concurrent_limit(chunk_index))

    elapsed = timeit.default_timer() - start_time
    elapsed_ms = elapsed * 1000.0
    print(f"Decoded in {elapsed_ms:.2f}ms")
    # What was built, not what was asked for: pools are sized by the first read.
    pool_sizes = getattr(getattr(zarrs, "_internal", None), "pool_sizes", None)
    print(f"pools: {pool_sizes() if pool_sizes else 'single pool'} zarrs {zarrs.__version__} fallbacks {fallbacks[0]}")

if __name__ == "__main__":
    asyncio.run(main())
