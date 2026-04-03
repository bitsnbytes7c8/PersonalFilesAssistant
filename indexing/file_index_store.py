"""SQLite-backed registry of chosen folders and discovered .txt paths (indexing is a no-op for now)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AddFolderResult:
    ok: bool
    folder_path: str | None = None
    txt_files_stored: int = 0
    error: str | None = None


class FileIndexStore:
    """Remembers which folders you added and which .txt files exist under them (recursive).

    Actual content indexing is intentionally not implemented yet; only paths are persisted.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS indexed_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS pending_txt_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    folder_id INTEGER NOT NULL REFERENCES indexed_folders(id) ON DELETE CASCADE,
                    added_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_pending_txt_folder
                    ON pending_txt_files(folder_id);
                """
            )

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

        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO indexed_folders (path) VALUES (?)",
                    (folder_key,),
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
            assert row is not None
            folder_id = int(row["id"])

            for fp in txt_paths:
                try:
                    conn.execute(
                        "INSERT INTO pending_txt_files (path, folder_id) VALUES (?, ?)",
                        (str(fp), folder_id),
                    )
                except sqlite3.IntegrityError:
                    # Same file reachable from another folder scan — keep one row
                    pass

        return AddFolderResult(
            ok=True,
            folder_path=folder_key,
            txt_files_stored=len(txt_paths),
        )

    def list_folders(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, path, added_at FROM indexed_folders ORDER BY path ASC"
            ).fetchall()
        return [dict(r) for r in rows]


__all__ = ["AddFolderResult", "FileIndexStore"]
