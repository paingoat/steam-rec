"""Save/load numpy & scipy arrays through the Store (SILO or local) via a temp file."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
from scipy import sparse

from steam_rec.storage.store import Store


def put_npy(store: Store, key: str, arr: np.ndarray) -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.npy"
        np.save(p, arr)
        store.put_file(p, key)


def get_npy(store: Store, key: str) -> np.ndarray:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.npy"
        store.get_file(key, p)
        return np.load(p)


def put_npz(store: Store, key: str, m: sparse.spmatrix) -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.npz"
        sparse.save_npz(p, m.tocsr())
        store.put_file(p, key)


def get_npz(store: Store, key: str) -> sparse.csr_matrix:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "a.npz"
        store.get_file(key, p)
        return sparse.load_npz(io.BytesIO(p.read_bytes())).tocsr()
