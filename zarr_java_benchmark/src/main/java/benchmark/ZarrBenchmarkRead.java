package benchmark;

import dev.zarr.zarrjava.ZarrException;
import dev.zarr.zarrjava.v3.Array;
import dev.zarr.zarrjava.v3.ArrayMetadata;
import dev.zarr.zarrjava.v3.codec.Codec;
import dev.zarr.zarrjava.v3.codec.core.ShardingIndexedCodec;
import dev.zarr.zarrjava.v3.chunkgrid.RegularChunkGrid;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;

public class ZarrBenchmarkRead {

    public static void main(String[] args) throws Exception {
        String path = null;
        boolean readAll = false;
        Integer concurrentChunks = null;
        boolean subchunks = false;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--read-all":
                case "--read_all":
                    readAll = true;
                    break;
                case "--concurrent-chunks":
                case "--concurrent_chunks":
                    concurrentChunks = Integer.parseInt(args[++i]);
                    break;
                case "--subchunks":
                    subchunks = true;
                    break;
                default:
                    if (!args[i].startsWith("-")) {
                        path = args[i];
                    } else {
                        System.err.println("Unknown option: " + args[i]);
                        System.exit(1);
                    }
            }
        }

        if (path == null) {
            System.err.println("Usage: ZarrBenchmarkRead [--read-all] [--concurrent-chunks N] [--subchunks] <path>");
            System.exit(1);
        }

        Array array = Array.open(path);
        ArrayMetadata metadata = array.metadata();

        long[] shape = metadata.shape;
        int[] chunkShape = ((RegularChunkGrid) metadata.chunkGrid).configuration.chunkShape;

        // Detect sharding and get inner chunk shape
        int[] innerChunkShape = null;
        Optional<Codec> shardingCodec = ArrayMetadata.getShardingIndexedCodec(metadata.codecs);
        if (shardingCodec.isPresent()) {
            innerChunkShape = ((ShardingIndexedCodec) shardingCodec.get()).configuration.chunkShape;
        }

        // Determine the effective chunk shape for iteration
        int[] iterChunkShape;
        if (subchunks && innerChunkShape != null) {
            iterChunkShape = innerChunkShape;
        } else {
            iterChunkShape = chunkShape;
        }

        System.out.println("Domain shape " + Arrays.toString(shape));
        System.out.println("Chunk shape " + Arrays.toString(chunkShape));
        if (innerChunkShape != null) {
            System.out.println("Inner chunk shape " + Arrays.toString(innerChunkShape));
        }
        System.out.println("Iteration chunk shape " + Arrays.toString(iterChunkShape));

        // Compute number of chunks along each dimension
        int ndim = shape.length;
        int[] numChunks = new int[ndim];
        for (int d = 0; d < ndim; d++) {
            numChunks[d] = (int) ((shape[d] + iterChunkShape[d] - 1) / iterChunkShape[d]);
        }
        System.out.println("Number of chunks " + Arrays.toString(numChunks));

        long startTime = System.nanoTime();

        if (readAll) {
            ucar.ma2.Array data = array.read();
            System.out.println("Read shape " + Arrays.toString(data.getShape()));
        } else {
            // Generate all chunk indices
            List<long[]> chunkOffsets = new ArrayList<>();
            generateChunkOffsets(new long[ndim], 0, numChunks, iterChunkShape, shape, chunkOffsets);

            if (concurrentChunks == null || concurrentChunks > 1) {
                int parallelism = concurrentChunks != null ? concurrentChunks : chunkOffsets.size();
                ExecutorService executor = Executors.newFixedThreadPool(
                    concurrentChunks != null ? concurrentChunks : Runtime.getRuntime().availableProcessors()
                );

                List<CompletableFuture<Void>> futures = new ArrayList<>();
                Semaphore semaphore = new Semaphore(parallelism);
                for (long[] offset : chunkOffsets) {
                    long[] readShape = computeReadShape(offset, iterChunkShape, shape);
                    futures.add(CompletableFuture.runAsync(() -> {
                        try {
                            semaphore.acquire();
                            array.read(offset, readShape);
                        } catch (ZarrException | InterruptedException e) {
                            throw new RuntimeException(e);
                        } finally {
                            semaphore.release();
                        }
                    }, executor));
                }
                CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();
                executor.shutdown();
            } else {
                // Sequential: concurrent_chunks == 1
                for (long[] offset : chunkOffsets) {
                    long[] readShape = computeReadShape(offset, iterChunkShape, shape);
                    array.read(offset, readShape);
                }
            }
        }

        long elapsed = System.nanoTime() - startTime;
        double elapsedMs = elapsed / 1_000_000.0;
        System.out.printf("Decoded in %.2fms%n", elapsedMs);
    }

    private static void generateChunkOffsets(long[] current, int dim, int[] numChunks,
                                              int[] chunkShape, long[] arrayShape,
                                              List<long[]> offsets) {
        if (dim == current.length) {
            offsets.add(current.clone());
            return;
        }
        for (int i = 0; i < numChunks[dim]; i++) {
            current[dim] = (long) i * chunkShape[dim];
            generateChunkOffsets(current, dim + 1, numChunks, chunkShape, arrayShape, offsets);
        }
    }

    private static long[] computeReadShape(long[] offset, int[] chunkShape, long[] arrayShape) {
        long[] readShape = new long[offset.length];
        for (int d = 0; d < offset.length; d++) {
            readShape[d] = Math.min(chunkShape[d], arrayShape[d] - offset[d]);
        }
        return readShape;
    }
}
