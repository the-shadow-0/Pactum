"""
Pactum Snapshot Store — content-addressed, Git-friendly storage
for execution traces and artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional


class SnapshotStore:
    """
    Content-addressed store for execution snapshots.

    Snapshots are stored as JSON files using SHA-256 content hashing.
    Storage layout: {path}/{id[:2]}/{id[2:]}.json
    """

    def __init__(self, path: str = ".pactum/snapshots"):
        self._path = os.path.abspath(path)

    def _ensure_dir(self) -> None:
        """Ensure the snapshot store directory exists."""
        os.makedirs(self._path, exist_ok=True)

    def _snapshot_path(self, snapshot_id: str) -> str:
        """Get file path for a snapshot ID."""
        prefix = snapshot_id[:2]
        remainder = snapshot_id[2:]
        dir_path = os.path.join(self._path, prefix)
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, f"{remainder}.json")

    def _compute_id(self, data: dict) -> str:
        """Compute a content-addressed SHA-256 ID for snapshot data."""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def save(self, snapshot_data: dict) -> str:
        """
        Save a snapshot and return its content-addressed ID.

        Args:
            snapshot_data: dict with keys like 'contract', 'inputs', 'outputs',
                          'trace', 'seed', 'config', 'timestamp'.

        Returns:
            Snapshot ID (16-char hex string).
        """
        self._ensure_dir()

        # Add metadata
        snapshot_data.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        snapshot_data.setdefault("pactum_version", "0.1.0")

        snapshot_id = self._compute_id(snapshot_data)
        snapshot_data["snapshot_id"] = snapshot_id

        path = self._snapshot_path(snapshot_id)
        with open(path, "w") as f:
            json.dump(snapshot_data, f, indent=2, default=str)

        return snapshot_id

    def load(self, snapshot_id: str) -> dict:
        """
        Load a snapshot by ID.

        Args:
            snapshot_id: The snapshot ID (full or prefix match).

        Returns:
            Snapshot data dict.

        Raises:
            FileNotFoundError if snapshot not found.
        """
        # Try exact match first
        path = self._snapshot_path(snapshot_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)

        # Try prefix match
        matches = self._find_by_prefix(snapshot_id)
        if len(matches) == 1:
            with open(matches[0], "r") as f:
                return json.load(f)
        elif len(matches) > 1:
            ids = [os.path.basename(m).replace(".json", "") for m in matches]
            raise ValueError(f"Ambiguous snapshot prefix '{snapshot_id}', matches: {ids}")

        from pactum.core.exceptions import SnapshotNotFoundError
        raise SnapshotNotFoundError(snapshot_id)

    def _find_by_prefix(self, prefix: str) -> list[str]:
        """Find snapshot files matching a prefix."""
        matches = []
        if not os.path.exists(self._path):
            return matches

        for dirpath, _, filenames in os.walk(self._path):
            for fn in filenames:
                if fn.endswith(".json"):
                    # Reconstruct the full ID
                    parent = os.path.basename(dirpath)
                    full_id = parent + fn.replace(".json", "")
                    if full_id.startswith(prefix):
                        matches.append(os.path.join(dirpath, fn))
        return matches

    def list(self) -> list[dict[str, Any]]:
        """
        List all snapshots with metadata.

        Returns:
            List of dicts with 'snapshot_id', 'timestamp', 'contract_name'.
        """
        snapshots = []
        if not os.path.exists(self._path):
            return snapshots

        for dirpath, _, filenames in os.walk(self._path):
            for fn in filenames:
                if fn.endswith(".json"):
                    filepath = os.path.join(dirpath, fn)
                    try:
                        with open(filepath, "r") as f:
                            data = json.load(f)
                        snapshots.append({
                            "snapshot_id": data.get("snapshot_id", "unknown"),
                            "timestamp": data.get("timestamp", "unknown"),
                            "contract_name": data.get("contract", {}).get("name", "unknown"),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue

        # Sort by timestamp descending
        snapshots.sort(key=lambda s: s["timestamp"], reverse=True)
        return snapshots

    def diff(self, id1: str, id2: str) -> dict:
        """
        Compute a structural diff between two snapshots.

        Returns:
            Dict describing differences in inputs, outputs, trace, etc.
        """
        snap1 = self.load(id1)
        snap2 = self.load(id2)

        diffs = {}
        for key in set(list(snap1.keys()) + list(snap2.keys())):
            if key in ("snapshot_id", "timestamp", "pactum_version"):
                continue
            v1 = snap1.get(key)
            v2 = snap2.get(key)
            if v1 != v2:
                diffs[key] = {"snapshot_1": v1, "snapshot_2": v2}

        return {
            "snapshot_1": id1,
            "snapshot_2": id2,
            "differences": diffs,
        }

    def delete(self, snapshot_id: str) -> bool:
        """Delete a snapshot by ID. Returns True if deleted."""
        path = self._snapshot_path(snapshot_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    @property
    def path(self) -> str:
        return self._path
