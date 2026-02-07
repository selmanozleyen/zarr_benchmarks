#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { Command } from "commander";
import * as zarr from "zarrita";
import FileSystemStore from "@zarrita/storage/fs";

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

const program = new Command();
program
  .argument("<input_path>", "Path to input Zarr V3 array")
  .argument("<output_path>", "Path to output Zarr V3 array")
  .parse(process.argv);

const inputPath = program.args[0];
const outputPath = program.args[1];

// Open input array
const inputStore = new FileSystemStore(inputPath);
const inputArr = await zarr.open(inputStore, { kind: "array" });
const metadata = await readMetadata(inputPath);

// Create output array with same metadata
const outputStore = new FileSystemStore(outputPath);
const outputArr = await zarr.create(outputStore, {
  shape: metadata.shape,
  chunk_shape: metadata.chunk_grid.configuration.chunk_shape,
  data_type: metadata.data_type,
  codecs: metadata.codecs,
  fill_value: metadata.fill_value,
  chunk_separator:
    metadata.chunk_key_encoding?.configuration?.separator || "/",
});

// Determine chunk shape for iteration (use outer shard shape)
const chunkShape = metadata.chunk_grid.configuration.chunk_shape;
const domainShape = inputArr.shape;
const numChunks = domainShape.map((dim, i) =>
  Math.ceil(dim / chunkShape[i])
);

console.log("Domain shape", domainShape);
console.log("Chunk shape", chunkShape);
console.log("Number of chunks", numChunks);

const startTime = performance.now();

// Check if sharded (zarrita.js does not support set on sharded arrays)
const isSharded = metadata.codecs.some((c) => c.name === "sharding_indexed");
if (isSharded) {
  console.error("zarrita.js does not support writing sharded arrays");
  process.exit(1);
}

// Copy chunk by chunk
const allIndices = ndindex(numChunks);
for (const chunkIndex of allIndices) {
  const selection = chunkIndex.map((idx, dim) =>
    zarr.slice(idx * chunkShape[dim], (idx + 1) * chunkShape[dim])
  );
  const chunk = await zarr.get(inputArr, selection);
  await zarr.set(outputArr, selection, chunk);
}

const elapsedMs = performance.now() - startTime;
console.log(`Round trip in ${elapsedMs.toFixed(2)}ms`);
