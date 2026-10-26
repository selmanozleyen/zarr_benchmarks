"""Turn a zarrs-python worktree into a benchmark-only build on zarrs perf/direct_b2b_decode.

    python bench_only_b2b.py <worktree>

zarrs main has zarrs_storage 0.5; the released zarrs_opendal and zarrs_object_store need 0.4,
and the zarrs repo no longer carries them. So the HTTP and obstore stores go; the filesystem
store, the only one the benchmarks use, is untouched. Applied identically to every arm.
"""
import pathlib
import re
import sys

REV = "2a9a113cca3c828ebf2796102db021f72eac0c8c"
root = pathlib.Path(sys.argv[1])

cargo = (root / "Cargo.toml").read_text()
cargo = re.sub(r"(?m)^#.*\n(?=zarrs = )", "", cargo)  # the old pin's comment
cargo = re.sub(
    r'(?m)^zarrs = \{[^}]*\}',
    f'# BENCHMARK-ONLY BUILD: zarrs perf/direct_b2b_decode (main 2026-10-04 + 6 commits); no HTTP or\n'
    f'# obstore stores, whose adapters need zarrs_storage 0.4.\n'
    f'zarrs = {{ git = "https://github.com/zarrs/zarrs", rev = "{REV}", features = ["async", "zlib", "pcodec", "bz2"] }}',
    cargo,
)
for dep in ("opendal", "zarrs_opendal", "pyo3-object_store", "zarrs_object_store"):
    cargo = re.sub(rf"(?m)^{dep} = .*\n", "", cargo)
cargo = re.sub(r"(?s)\n# zarrs_opendal and zarrs_object_store.*?\[patch\.crates-io\].*?\n(?=\[|\Z)", "\n", cargo)
cargo = re.sub(r"(?s)\n#[^\n]*0\.24 RELEASE: delete this.*?\[patch\.crates-io\]\n[^\n]*\n", "\n", cargo)
cargo = re.sub(r"(?m)^\[patch\.crates-io\]\nzarrs_storage = .*\n", "", cargo)
(root / "Cargo.toml").write_text(cargo.rstrip() + "\n")

store = (root / "src/store.rs").read_text()
for old, new in [
    ("use opendal::Builder;\n", ""),
    ("use pyo3_object_store::PyExternalObjectStore;\n", ""),
    ("mod http;\nmod obstore;\n", ""),
    ("pub use self::http::HttpStoreConfig;\npub use self::obstore::ObStoreConfig;\n", ""),
    ("    Http(HttpStoreConfig),\n    ObStore(ObStoreConfig),\n", ""),
    ("            StoreKind::Http(_config) => (),\n            StoreKind::ObStore(_config) => (),\n", ""),
    ("            StoreKind::Http(config) => config.try_into(),\n            StoreKind::ObStore(config) => config.try_into(),\n", ""),
]:
    assert old in store, old
    store = store.replace(old, new)
store = re.sub(
    r'(?s)            "FsspecStore" => \{.*?\n            \}\n            "ObjectStore" => \{.*?\n            \}\n',
    '            "FsspecStore" | "ObjectStore" => {\n'
    '                return Err(PyErr::new::<PyNotImplementedError, _>(format!(\n'
    '                    "{name} stores are not in this benchmark build"\n'
    '                )));\n'
    '            }\n',
    store,
)
store = re.sub(r"(?s)\nfn opendal_builder_to_sync_store<B: Builder>\(.*\Z", "\n", store)
store = store.replace("use std::{collections::HashMap, sync::Arc};", "")
store = store.replace(
    "use zarrs::storage::{\n    ReadableWritableListableStorage, storage_adapter::async_to_sync::AsyncToSyncStorageAdapter,\n};",
    "use zarrs::storage::ReadableWritableListableStorage;",
)
store = store.replace("use crate::{runtime::tokio_block_on, utils::PyErrExt};\n", "")
store = store.replace("    exceptions::{PyNotImplementedError, PyValueError},", "    exceptions::PyNotImplementedError,")
store = store.replace("    Borrowed, Bound, FromPyObject, PyAny, PyErr, PyResult,", "    Borrowed, FromPyObject, PyAny, PyErr, PyResult,")
(root / "src/store.rs").write_text(store)
for f in ("http.rs", "obstore.rs"):
    (root / "src/store" / f).unlink(missing_ok=True)
print("bench-only:", root)
