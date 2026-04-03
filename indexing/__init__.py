"""File indexing package — metadata, storage, and background indexing pipeline."""

from indexing.file_index_store import AddFolderResult, FileIndexStore
from indexing.pipeline import IndexingPipeline

__all__ = ["AddFolderResult", "FileIndexStore", "IndexingPipeline"]
