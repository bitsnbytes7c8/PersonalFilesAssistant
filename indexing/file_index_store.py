"""SQLite-backed registry of folders and .txt files with persisted indexing state."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from indexing.states import COMPLETED, NOT_STARTED, STARTED, compute_folder_state


@dataclass(frozen=True)
class AddFolderResult:
    ok: bool
    folder_path: str | None = None
    folder_id: int | None = None
    txt_files_stored: int = 0
    error: str | None = None


def _is_strict_descendant(path: Path, ancestor: Path) -> bool:
    """True if ``path`` is a directory strictly inside ``ancestor`` (not equal)."""
    try:
        resolved_path = path.resolve()
        resolved_ancestor = ancestor.resolve()
        if resolved_path == resolved_ancestor:
            return False
        resolved_path.relative_to(resolved_ancestor)
        return True
    except ValueError:
        return False


def _file_mtime_ns(path: Path) -> int | None:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return None


class FileIndexStore:
    """Folders and .txt file paths with per-row state and aggregate folder state."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS indexed_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL DEFAULT (datetime('now')),
                    state TEXT NOT NULL DEFAULT 'NOT_STARTED'
                );

                CREATE TABLE IF NOT EXISTS pending_txt_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    folder_id INTEGER NOT NULL REFERENCES indexed_folders(id) ON DELETE CASCADE,
                    added_at TEXT NOT NULL DEFAULT (datetime('now')),
                    state TEXT NOT NULL DEFAULT 'NOT_STARTED',
                    mtime_ns INTEGER
                );

                CREATE INDEX IF NOT EXISTS idx_pending_txt_folder
                    ON pending_txt_files(folder_id);
                """
            )
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        def cols(table: str) -> set[str]:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return {r[1] for r in rows}

        fc = cols("indexed_folders")
        if "state" not in fc:
            conn.execute(
                "ALTER TABLE indexed_folders ADD COLUMN state TEXT NOT NULL DEFAULT 'NOT_STARTED'"
            )

        tc = cols("pending_txt_files")
        if "state" not in tc:
            conn.execute(
                "ALTER TABLE pending_txt_files ADD COLUMN state TEXT NOT NULL DEFAULT 'NOT_STARTED'"
            )
        if "mtime_ns" not in tc:
            conn.execute("ALTER TABLE pending_txt_files ADD COLUMN mtime_ns INTEGER")

    @staticmethod
    def _collect_txt_paths(root: Path) -> list[Path]:
        paths: list[Path] = []
        for p in root.rglob("*.txt"):
            try:
                if p.is_file():
                    paths.append(p.resolve())
            except OSError:
                continue
        return sorted(set(paths), key=lambda x: str(x))

    def _update_folder_row_state(self, conn: sqlite3.Connection, folder_id: int) -> None:
        rows = conn.execute(
            "SELECT state FROM pending_txt_files WHERE folder_id = ?",
            (folder_id,),
        ).fetchall()
        states = [str(r["state"]) for r in rows]
        folder_state = compute_folder_state(states)
        conn.execute(
            "UPDATE indexed_folders SET state = ? WHERE id = ?",
            (folder_state, folder_id),
        )

    def add_folder(self, folder: str | Path) -> AddFolderResult:
        try:
            raw = Path(folder).expanduser()
            resolved = raw.resolve(strict=True)
        except FileNotFoundError:
            return AddFolderResult(ok=False, error="Path does not exist.")
        except OSError as e:
            return AddFolderResult(ok=False, error=str(e))

        if not resolved.is_dir():
            return AddFolderResult(ok=False, error="Path is not a directory.")

        folder_key = str(resolved)
        txt_paths = self._collect_txt_paths(resolved)

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT id, path FROM indexed_folders").fetchall()

                for row in rows:
                    existing_path = Path(row["path"])
                    if _is_strict_descendant(resolved, existing_path):
                        return AddFolderResult(
                            ok=False,
                            error=(
                                "This folder is already covered by an indexed parent: "
                                f"{row['path']}"
                            ),
                        )

                redundant_ids: list[int] = []
                for row in rows:
                    existing_path = Path(row["path"])
                    if _is_strict_descendant(existing_path, resolved):
                        redundant_ids.append(int(row["id"]))
                if redundant_ids:
                    placeholders = ",".join("?" * len(redundant_ids))
                    conn.execute(
                        f"DELETE FROM indexed_folders WHERE id IN ({placeholders})",
                        redundant_ids,
                    )

                try:
                    conn.execute(
                        "INSERT INTO indexed_folders (path, state) VALUES (?, ?)",
                        (folder_key, NOT_STARTED),
                    )
                except sqlite3.IntegrityError:
                    return AddFolderResult(
                        ok=False,
                        error="This folder is already in the list (duplicate).",
                    )

                row = conn.execute(
                    "SELECT id FROM indexed_folders WHERE path = ?",
                    (folder_key,),
                ).fetchone()
                if row is None:
                    return AddFolderResult(
                        ok=False,
                        error="Failed to register folder after update.",
                    )
                folder_id = int(row["id"])

                for fp in txt_paths:
                    mtime = _file_mtime_ns(fp)
                    try:
                        conn.execute(
                            """
                            INSERT INTO pending_txt_files (path, folder_id, state, mtime_ns)
                            VALUES (?, ?, ?, ?)
                            """,
                            (str(fp), folder_id, NOT_STARTED, mtime),
                        )
                    except sqlite3.IntegrityError:
                        pass

                self._update_folder_row_state(conn, folder_id)

        return AddFolderResult(
            ok=True,
            folder_path=folder_key,
            folder_id=folder_id,
            txt_files_stored=len(txt_paths),
        )

    def get_folder_path(self, folder_id: int) -> str | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT path FROM indexed_folders WHERE id = ?",
                    (folder_id,),
                ).fetchone()
        return str(row["path"]) if row else None

    def scan_folder_for_changes(self, folder_id: int) -> list[int]:
        """Scan disk vs DB for one folder; return file ids that need indexing (enqueued by caller)."""
        to_index: list[int] = []
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT path FROM indexed_folders WHERE id = ?",
                    (folder_id,),
                ).fetchone()
                if row is None:
                    return []
                root = Path(row["path"])
                if not root.is_dir():
                    return []

                on_disk: dict[str, Path] = {}
                for p in self._collect_txt_paths(root):
                    on_disk[str(p)] = p

                db_rows = conn.execute(
                    "SELECT id, path, mtime_ns FROM pending_txt_files WHERE folder_id = ?",
                    (folder_id,),
                ).fetchall()
                db_by_path = {str(r["path"]): r for r in db_rows}

                for path_str, row in list(db_by_path.items()):
                    if path_str not in on_disk:
                        conn.execute("DELETE FROM pending_txt_files WHERE id = ?", (row["id"],))
                        del db_by_path[path_str]

                for path_str, disk_path in on_disk.items():
                    mtime = _file_mtime_ns(disk_path)
                    if path_str not in db_by_path:
                        try:
                            cur = conn.execute(
                                """
                                INSERT INTO pending_txt_files (path, folder_id, state, mtime_ns)
                                VALUES (?, ?, ?, ?)
                                """,
                                (path_str, folder_id, NOT_STARTED, mtime),
                            )
                            fid = int(cur.lastrowid)
                            to_index.append(fid)
                        except sqlite3.IntegrityError:
                            pass
                    else:
                        r = db_by_path[path_str]
                        fid = int(r["id"])
                        old_mtime = r["mtime_ns"]
                        stored = int(old_mtime) if old_mtime is not None else None
                        if mtime is not None and stored != mtime:
                            conn.execute(
                                """
                                UPDATE pending_txt_files
                                SET state = ?, mtime_ns = ?
                                WHERE id = ?
                                """,
                                (NOT_STARTED, mtime, fid),
                            )
                            to_index.append(fid)

                self._update_folder_row_state(conn, folder_id)

        return to_index

    def list_folder_ids(self) -> list[int]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT id FROM indexed_folders ORDER BY id").fetchall()
        return [int(r["id"]) for r in rows]

    def list_folders(self) -> list[dict[str, Any]]:
        """Folder rows with file counts and completion stats for the UI."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        f.id,
                        f.path,
                        f.added_at,
                        f.state,
                        COUNT(p.id) AS file_total,
                        COALESCE(SUM(CASE WHEN p.state = 'COMPLETED' THEN 1 ELSE 0 END), 0)
                            AS files_completed,
                        COALESCE(SUM(CASE WHEN p.state = 'STARTED' THEN 1 ELSE 0 END), 0)
                            AS files_started,
                        COALESCE(SUM(CASE WHEN p.state = 'NOT_STARTED' THEN 1 ELSE 0 END), 0)
                            AS files_not_started
                    FROM indexed_folders f
                    LEFT JOIN pending_txt_files p ON p.folder_id = f.id
                    GROUP BY f.id, f.path, f.added_at, f.state
                    ORDER BY f.path ASC
                    """
                ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["id"] = int(d["id"])
            d["file_total"] = int(d["file_total"] or 0)
            d["files_completed"] = int(d["files_completed"] or 0)
            d["files_started"] = int(d["files_started"] or 0)
            d["files_not_started"] = int(d["files_not_started"] or 0)
            out.append(d)
        return out

    def acquire_index_slot(self, file_id: int) -> Path | None:
        """Mark NOT_STARTED as STARTED; skip missing rows and already COMPLETED files."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT path, state, folder_id FROM pending_txt_files WHERE id = ?",
                    (file_id,),
                ).fetchone()
                if row is None:
                    return None
                if row["state"] == COMPLETED:
                    return None
                folder_id = int(row["folder_id"])
                if row["state"] == NOT_STARTED:
                    conn.execute(
                        "UPDATE pending_txt_files SET state = ? WHERE id = ?",
                        (STARTED, file_id),
                    )
                    self._update_folder_row_state(conn, folder_id)
                return Path(row["path"])

    def finish_index_file(self, file_id: int) -> None:
        """Set COMPLETED and refresh mtime from disk after successful index."""
        path: Path | None = None
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT path FROM pending_txt_files WHERE id = ?",
                    (file_id,),
                ).fetchone()
                if row:
                    path = Path(row["path"])
                mtime = _file_mtime_ns(path) if path else None
                conn.execute(
                    """
                    UPDATE pending_txt_files
                    SET state = ?, mtime_ns = COALESCE(?, mtime_ns)
                    WHERE id = ?
                    """,
                    (COMPLETED, mtime, file_id),
                )
                row2 = conn.execute(
                    "SELECT folder_id FROM pending_txt_files WHERE id = ?",
                    (file_id,),
                ).fetchone()
                if row2:
                    self._update_folder_row_state(conn, int(row2["folder_id"]))

    def list_incomplete_file_ids(self) -> list[int]:
        """Files that still need indexing (resume after restart)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id FROM pending_txt_files
                    WHERE state != ?
                    ORDER BY id
                    """,
                    (COMPLETED,),
                ).fetchall()
        return [int(r["id"]) for r in rows]


__all__ = ["AddFolderResult", "FileIndexStore"]
