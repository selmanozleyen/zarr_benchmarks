package benchmark;

import dev.zarr.zarrjava.ZarrException;
import dev.zarr.zarrjava.v3.Array;
import dev.zarr.zarrjava.v3.ArrayMetadata;
import dev.zarr.zarrjava.v3.chunkgrid.RegularChunkGrid;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class ZarrBenchmarkRoundtrip {

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: ZarrBenchmarkRoundtrip <input_path> <output_path>");
            System.exit(1);
        }

        String inputPath = args[0];
        String outputPath = args[1];

        Array inputArray = Array.open(inputPath);
        ArrayMetadata metadata = inputArray.metadata();

        long[] shape = metadata.shape;
        int[] chunkShape = ((RegularChunkGrid) metadata.chunkGrid).configuration.chunkShape;

        System.out.println("Domain shape " + Arrays.toString(shape));
        System.out.println("Chunk shape " + Arrays.toString(chunkShape));

        // Create output array with same metadata using public metadataBuilder
        ArrayMetadata outputMetadata = Array.metadataBuilder(metadata).build();
        Array outputArray = Array.create(outputPath, outputMetadata);

        // Generate chunk offsets
        int ndim = shape.length;
        int[] numChunks = new int[ndim];
        for (int d = 0; d < ndim; d++) {
            numChunks[d] = (int) ((shape[d] + chunkShape[d] - 1) / chunkShape[d]);
        }

        List<long[]> chunkOffsets = new ArrayList<>();
        generateChunkOffsets(new long[ndim], 0, numChunks, chunkShape, shape, chunkOffsets);

        long startTime = System.nanoTime();

        // Copy chunk-by-chunk
        for (long[] offset : chunkOffsets) {
            long[] readShape = computeReadShape(offset, chunkShape, shape);
            ucar.ma2.Array data = inputArray.read(offset, readShape);
            outputArray.write(offset, data);
        }

        long elapsed = System.nanoTime() - startTime;
        double elapsedMs = elapsed / 1_000_000.0;
        System.out.printf("Round trip in %.2fms%n", elapsedMs);
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
