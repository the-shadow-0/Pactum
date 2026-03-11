"""
Tests for the Snapshot Store — save, load, list, diff, prefix matching.
"""

import pytest
import json
import os

from pactum.snapshot.store import SnapshotStore
from pactum.core.exceptions import SnapshotNotFoundError


class TestSnapshotStore:
    def test_save_and_load(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        data = {"contract": {"name": "test"}, "inputs": {"q": "hello"}, "outputs": {"r": "world"}}

        snapshot_id = store.save(data)
        assert len(snapshot_id) == 16

        loaded = store.load(snapshot_id)
        assert loaded["inputs"] == {"q": "hello"}
        assert loaded["outputs"] == {"r": "world"}
        assert loaded["snapshot_id"] == snapshot_id

    def test_content_addressed(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        data1 = {"contract": {"name": "test"}, "inputs": {"q": "a"}}
        data2 = {"contract": {"name": "test"}, "inputs": {"q": "b"}}

        id1 = store.save(data1)
        id2 = store.save(data2)
        assert id1 != id2

    def test_list_snapshots(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        store.save({"contract": {"name": "c1"}, "inputs": {}})
        store.save({"contract": {"name": "c2"}, "inputs": {}})

        snapshots = store.list()
        assert len(snapshots) == 2
        names = {s["contract_name"] for s in snapshots}
        assert "c1" in names
        assert "c2" in names

    def test_list_empty(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        assert store.list() == []

    def test_diff(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        id1 = store.save({"contract": {"name": "test"}, "inputs": {"q": "a"}, "outputs": {"r": "1"}})
        id2 = store.save({"contract": {"name": "test"}, "inputs": {"q": "b"}, "outputs": {"r": "2"}})

        diff = store.diff(id1, id2)
        assert "differences" in diff
        assert "inputs" in diff["differences"]

    def test_not_found(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        with pytest.raises(SnapshotNotFoundError):
            store.load("nonexistent1234")

    def test_prefix_match(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        data = {"contract": {"name": "test"}, "inputs": {}, "unique_field": "prefix_test"}
        snapshot_id = store.save(data)

        # Load with 6-character prefix
        loaded = store.load(snapshot_id[:6])
        assert loaded["unique_field"] == "prefix_test"

    def test_delete(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        snapshot_id = store.save({"contract": {"name": "test"}, "inputs": {}})

        assert store.delete(snapshot_id)
        with pytest.raises(SnapshotNotFoundError):
            store.load(snapshot_id)

    def test_delete_nonexistent(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        assert not store.delete("nonexistent1234")

    def test_metadata_added(self, tmp_path):
        store = SnapshotStore(str(tmp_path / "snaps"))
        snapshot_id = store.save({"contract": {"name": "test"}, "inputs": {}})

        loaded = store.load(snapshot_id)
        assert "timestamp" in loaded
        assert "pactum_version" in loaded
        assert loaded["pactum_version"] == "0.1.0"
