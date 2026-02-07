#!/usr/bin/env python3

import numpy as np
import timeit
import click
from concurrent.futures import ThreadPoolExecutor

import zarr
from zarrs import ZarrsArray


@click.command()
@click.argument('path', type=str)
@click.option('--concurrent_chunks', type=int, default=None, help='Number of concurrent chunk reads. Ignored if --read-all is set')
@click.option('--subchunks', is_flag=True, show_default=True, default=False, help='Read inner-chunk-by-inner-chunk. Ignored if --read-all is set')
@click.option('--read_all', is_flag=True, show_default=True, default=False, help='Read the entire array in one operation.')
def main(path, concurrent_chunks, subchunks, read_all):
    dataset = zarr.open(path, mode='r')
    domain_shape = dataset.shape
    if subchunks:
        chunk_shape = dataset.chunks
    else:
        chunk_shape = dataset.shards or dataset.chunks

    print("Domain shape", domain_shape)
    print("Chunk shape", chunk_shape)
    num_chunks = [(domain + cs - 1) // cs for (domain, cs) in zip(domain_shape, chunk_shape)]
    print("Number of chunks", num_chunks)

    arr = ZarrsArray(dataset, validate_checksums=True, direct_io=True)

    def get_chunk_indexer(chunk_idx):
        return tuple(slice(i * s, (1 + i) * s) for i, s in zip(chunk_idx, chunk_shape))

    def chunk_read(chunk_index):
        arr[get_chunk_indexer(chunk_index)]

    start_time = timeit.default_timer()
    if read_all:
        print(arr[:].shape)
    elif concurrent_chunks is None:
        with ThreadPoolExecutor() as executor:
            list(executor.map(chunk_read, np.ndindex(*num_chunks)))
    elif concurrent_chunks == 1:
        for chunk_index in np.ndindex(*num_chunks):
            chunk_read(chunk_index)
    else:
        with ThreadPoolExecutor(max_workers=concurrent_chunks) as executor:
            list(executor.map(chunk_read, np.ndindex(*num_chunks)))

    elapsed = timeit.default_timer() - start_time
    elapsed_ms = elapsed * 1000.0
    print(f"Decoded in {elapsed_ms:.2f}ms")

if __name__ == "__main__":
    main()
