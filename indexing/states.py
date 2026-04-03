"""Indexing state constants for folders and .pdf files."""

from __future__ import annotations

NOT_STARTED = "NOT_STARTED"
STARTED = "STARTED"
COMPLETED = "COMPLETED"

ALL_FILE_STATES = (NOT_STARTED, STARTED, COMPLETED)
ALL_FOLDER_STATES = (NOT_STARTED, STARTED, COMPLETED)


def compute_folder_state(file_states: list[str]) -> str:
    """Derive folder state from child file states.

    NOT_STARTED: every file is NOT_STARTED (including an empty folder).
    COMPLETED: every file is COMPLETED (vacuously true if there are zero files).
    STARTED: any other mix.
    """
    if not file_states:
        return COMPLETED
    if all(s == NOT_STARTED for s in file_states):
        return NOT_STARTED
    if all(s == COMPLETED for s in file_states):
        return COMPLETED
    return STARTED


__all__ = [
    "ALL_FILE_STATES",
    "ALL_FOLDER_STATES",
    "COMPLETED",
    "NOT_STARTED",
    "STARTED",
    "compute_folder_state",
]
