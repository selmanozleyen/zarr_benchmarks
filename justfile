binstall:
	curl -L --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash

# Install zarrs_tools
build_zarrs:
	cargo binstall -y zarrs_tools@0.8.1

# Build ExZarr Elixir benchmark (requires Elixir + Mix)
build_exzarr:
	cd exzarr_benchmark && mix deps.get && mix escript.build

# Build zarr-java benchmarks (requires Java 21+ and Gradle)
build_zarr_java:
	cd zarr_java_benchmark && ./gradlew shadowJar shadowJarRoundtrip

# Install zarrita.js dependencies (requires Node.js)
build_zarrita_js:
	cd zarrita_js_benchmark && npm install

# Build all new implementations
build_all: build_zarrs build_exzarr build_zarr_java build_zarrita_js

generate_data:
	./generate_benchmark_array.rs data/benchmark.zarr
	./generate_benchmark_array.rs --compress data/benchmark_compress.zarr
	./generate_benchmark_array.rs --compress --subchunk-shape 64,64,64 data/benchmark_compress_shard.zarr

benchmark_read_all:
	uv run run_benchmark_read_all

benchmark_read_chunks:
	uv run run_benchmark_read_chunks

benchmark_read_subchunks:
	uv run run_benchmark_read_subchunks

benchmark_roundtrip:
	uv run run_benchmark_roundtrip

plot:
	uv run plot_benchmarks

benchmark_all: benchmark_read_all benchmark_read_chunks benchmark_read_subchunks benchmark_roundtrip
