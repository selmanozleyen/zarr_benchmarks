#!/usr/bin/env python3

import numpy as np
import timeit
import asyncio
import click
from functools import wraps

import tensorstore as ts

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapper

def axis0_indices(extent, random, unsorted, strided):
    """Indices along axis 0 for a random-access read, drawn afresh on every run."""
    rng = np.random.default_rng()
    if strided:
        return np.arange(rng.integers(strided), extent, strided)
    indices = rng.choice(extent, min(random, extent), replace=False)
    return indices if unsorted else np.sort(indices)


@click.command()
@coro
@click.argument('path', type=str)
@click.option('--concurrent_chunks', type=int, default=None, help='Number of concurrent async chunk reads. Ignored if --read-all is set')
@click.option('--subchunks', is_flag=True, show_default=True, default=False, help='Reader inner-chunk-by-inner-chunk. Ignored if --read-all is set')
@click.option('--read_all', is_flag=True, show_default=True, default=False, help='Read the entire array in one operation.')
@click.option('--random', 'random_k', type=int, default=None, help='Read this many random indices along axis 0 (sorted unless --unsorted).')
@click.option('--unsorted', is_flag=True, show_default=True, default=False, help='With --random, keep the indices in random order.')
@click.option('--strided', type=int, default=None, help='Read every STRIDED-th index along axis 0, from a random offset.')
async def main(path, concurrent_chunks, subchunks, read_all, random_k, unsorted, strided):
    if path.startswith("http"):
        kvstore = {
            'driver': 'http',
            'base_url': path,
        }
    else:
        kvstore = {
            'driver': 'file',
            'path': path,
        }

    dataset_future = ts.open({
        'driver': 'zarr3',
        'kvstore': kvstore,
        # 'context': {
        #     'cache_pool': {
        #         'total_bytes_limit': 100_000_000
        #     }
        # },
        # 'recheck_cached_data': 'open',
    })
    dataset = dataset_future.result()
    print(dataset)

    domain_shape = dataset.domain.shape
    if subchunks:
        chunk_shape = dataset.chunk_layout.read_chunk.shape
    else:
        chunk_shape = dataset.chunk_layout.write_chunk.shape # shard or chunk shape

    print("Domain shape", domain_shape)
    print("Chunk shape", chunk_shape)
    num_chunks =[(domain + chunk_shape - 1) // chunk_shape for (domain, chunk_shape) in zip(domain_shape, chunk_shape)]
    print("Number of chunks", num_chunks)

    async def chunk_read(chunk_index):
        chunk_slice = [ts.Dim(inclusive_min=index*cshape, exclusive_max=min(index * cshape + cshape, dshape)) for (index, cshape, dshape) in zip(chunk_index, chunk_shape, domain_shape)]
        # print("Reading", chunk_index)
        return await dataset[ts.IndexDomain(chunk_slice)].read()
        # print("Read", chunk_index)

    indices = None
    if random_k or strided:
        indices = axis0_indices(domain_shape[0], random_k, unsorted, strided)
        print("Indices", len(indices), "of", domain_shape[0])

    start_time = timeit.default_timer()
    if indices is not None:
        print((await dataset[indices].read()).shape)
    elif read_all:
        print(dataset.read().result().shape)
    elif concurrent_chunks is None:
        async with asyncio.TaskGroup() as tg:
            for chunk_index in np.ndindex(*num_chunks):
                tg.create_task(chunk_read(chunk_index))
    elif concurrent_chunks == 1:
        for chunk_index in np.ndindex(*num_chunks):
            chunk_slice = [ts.Dim(inclusive_min=index*cshape, exclusive_max=min(index * cshape + cshape, dshape)) for (index, cshape, dshape) in zip(chunk_index, chunk_shape, domain_shape)]
            await dataset[ts.IndexDomain(chunk_slice)].read()
    else:
        # TODO: Not sure if this is the fastest API for this
        semaphore = asyncio.Semaphore(concurrent_chunks)
        async def chunk_read_concurrent_limit(chunk_index):
            async with semaphore:
                return await chunk_read(chunk_index)
        async with asyncio.TaskGroup() as tg:
            for chunk_index in np.ndindex(*num_chunks):
                tg.create_task(chunk_read_concurrent_limit(chunk_index))

    elapsed = timeit.default_timer() - start_time
    elapsed_ms = elapsed * 1000.0
    print(f"Decoded in {elapsed_ms:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())
