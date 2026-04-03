"""Background producer/consumer pipeline for indexing .txt files (content step is a no-op for now)."""

from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path

from indexing.file_index_store import FileIndexStore


def _noop_index_file(path: Path) -> None:
    """Placeholder for future chunking / embeddings. Must stay fast and side-effect free for now."""
    try:
        if path.is_file():
            path.stat()
    except OSError:
        pass


class IndexingPipeline:
    """Producer thread scans indexed folders on an interval; consumer runs the index job (no-op)."""

    def __init__(self, store: FileIndexStore, scan_interval_sec: float = 3.0) -> None:
        self._store = store
        self._scan_interval_sec = scan_interval_sec
        self._queue: queue.Queue[int] = queue.Queue()
        self._stop = threading.Event()
        self._producer_t: threading.Thread | None = None
        self._consumer_t: threading.Thread | None = None

    def start(self) -> None:
        for fid in self._store.list_incomplete_file_ids():
            self._queue.put(fid)
        self._producer_t = threading.Thread(
            target=self._producer_loop,
            name="indexing-producer",
            daemon=True,
        )
        self._consumer_t = threading.Thread(
            target=self._consumer_loop,
            name="indexing-consumer",
            daemon=True,
        )
        self._producer_t.start()
        self._consumer_t.start()

    def stop(self, join_timeout_sec: float = 5.0) -> None:
        self._stop.set()
        if self._producer_t:
            self._producer_t.join(timeout=join_timeout_sec)
        if self._consumer_t:
            self._consumer_t.join(timeout=join_timeout_sec)

    def notify_folder_added(self, folder_id: int) -> None:
        """Scan the new folder and enqueue files that need work."""
        ids = self._store.scan_folder_for_changes(folder_id)
        for fid in ids:
            self._queue.put(fid)

    def _producer_loop(self) -> None:
        while not self._stop.is_set():
            for folder_id in self._store.list_folder_ids():
                if self._stop.is_set():
                    break
                try:
                    ids = self._store.scan_folder_for_changes(folder_id)
                    for fid in ids:
                        self._queue.put(fid)
                except Exception:
                    traceback.print_exc()
            self._stop.wait(self._scan_interval_sec)

    def _consumer_loop(self) -> None:
        while not self._stop.is_set():
            try:
                file_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                path = self._store.acquire_index_slot(file_id)
                if path is None:
                    continue
                _noop_index_file(path)
                self._store.finish_index_file(file_id)
            except Exception:
                traceback.print_exc()


__all__ = ["IndexingPipeline"]
