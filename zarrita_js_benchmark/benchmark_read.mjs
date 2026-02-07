#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { Command } from "commander";
import * as zarr from "zarrita";
import FileSystemStore from "@zarrita/storage/fs";

async function pool(concurrency, items, fn) {
  const executing = new Set();
  for (const item of items) {
    const p = fn(item).then(() => executing.delete(p));
    executing.add(p);
    if (executing.size >= concurrency) await Promise.race(executing);
  }
  await Promise.all(executing);
}

function ndindex(dimensions) {
  const indices = [];
  const total = dimensions.reduce((a, b) => a * b, 1);
  for (let i = 0; i < total; i++) {
    const index = [];
    let remainder = i;
    for (let d = dimensions.length - 1; d >= 0; d--) {
      index.unshift(remainder % dimensions[d]);
      remainder = Math.floor(remainder / dimensions[d]);
    }
    indices.push(index);
  }
  return indices;
}

async function readMetadata(path) {
  const raw = await readFile(join(path, "zarr.json"), "utf-8");
  return JSON.parse(raw);
}

function getShardShape(metadata) {
  const shardingCodec = metadata.codecs.find(
    (c) => c.name === "sharding_indexed"
  );
  if (shardingCodec) {
    return metadata.chunk_grid.configuration.chunk_shape;
  }
  return null;
}

function getInnerChunkShape(metadata) {
  const shardingCodec = metadata.codecs.find(
    (c) => c.name === "sharding_indexed"
  );
  if (shardingCodec) {
    return shardingCodec.configuration.chunk_shape;
  }
  return null;
}

const program = new Command();
program
  .argument("<path>", "Path to Zarr V3 array")
  .option("--read_all", "Read the entire array in one operation")
  .option(
    "--concurrent_chunks <n>",
    "Number of concurrent chunk reads",
    parseInt
  )
  .option("--subchunks", "Read inner-chunk-by-inner-chunk (for sharded arrays)")
  .parse(process.argv);

const opts = program.opts();
const arrayPath = program.args[0];

const store = new FileSystemStore(arrayPath);
const arr = await zarr.open(store, { kind: "array" });
const metadata = await readMetadata(arrayPath);

const domainShape = arr.shape;
const shardShape = getShardShape(metadata);
const innerChunkShape = getInnerChunkShape(metadata);

let chunkShape;
if (opts.subchunks) {
  // Use inner chunk shape for subchunk reading
  chunkShape = innerChunkShape || arr.chunks;
} else {
  // Use shard shape if sharded, otherwise chunk grid shape
  chunkShape = shardShape || arr.chunks;
}

console.log("Domain shape", domainShape);
console.log("Chunk shape", chunkShape);

const numChunks = domainShape.map((dim, i) =>
  Math.ceil(dim / chunkShape[i])
);
console.log("Number of chunks", numChunks);

const startTime = performance.now();

if (opts.read_all) {
  const result = await zarr.get(arr);
  console.log(result.shape);
} else {
  const allIndices = ndindex(numChunks);

  const readChunk = async (chunkIndex) => {
    const selection = chunkIndex.map((idx, dim) =>
      zarr.slice(idx * chunkShape[dim], (idx + 1) * chunkShape[dim])
    );
    await zarr.get(arr, selection);
  };

  const concurrency = opts.concurrent_chunks;
  if (concurrency === undefined || concurrency === null) {
    // Unlimited concurrency
    await Promise.all(allIndices.map(readChunk));
  } else if (concurrency === 1) {
    // Sequential
    for (const idx of allIndices) {
      await readChunk(idx);
    }
  } else {
    // Bounded concurrency
    await pool(concurrency, allIndices, readChunk);
  }
}

const elapsedMs = performance.now() - startTime;
console.log(`Decoded in ${elapsedMs.toFixed(2)}ms`);
