"""
Metadata sidecar handling: JSON mapping of FAISS IDs to chunk metadata.
"""

import logging
import json
import os
import hashlib
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path

from .models import MetadataEntry, EmbeddedChunk
from .exceptions import JSONDecodeError, FileNotFoundError_
from .constants import (
    INDEXES_BASE_DIR,
    METADATA_FILE,
    METADATA_BACKUP_FILE,
    METADATA_VERSION,
    TEXT_CHECKSUM_ALGORITHM,
)

logger = logging.getLogger(__name__)


def _get_metadata_path(user_id: str) -> str:
    """Get path to metadata.json for a user."""
    return os.path.join(INDEXES_BASE_DIR, user_id, METADATA_FILE)


def _get_metadata_backup_path(user_id: str) -> str:
    """Get path to metadata.json.bak for a user."""
    return os.path.join(INDEXES_BASE_DIR, user_id, METADATA_BACKUP_FILE)


def _compute_text_checksum(text: str) -> str:
    """
    Compute checksum of chunk text.
    
    Args:
        text: Chunk text
    
    Returns:
        str: Checksum in format "{algorithm}:{hash}"
    """
    if TEXT_CHECKSUM_ALGORITHM == "md5":
        hash_obj = hashlib.md5(text.encode())
    else:
        hash_obj = hashlib.sha256(text.encode())
    
    return f"{TEXT_CHECKSUM_ALGORITHM}:{hash_obj.hexdigest()}"


def load_metadata(user_id: str) -> dict:
    """
    Load metadata sidecar for a user's index.
    
    Args:
        user_id: Index owner user ID
    
    Returns:
        dict: Metadata structure with entries, lookup index, etc.
    
    Raises:
        FileNotFoundError_: metadata.json does not exist
        JSONDecodeError: Corrupted JSON file
    """
    metadata_path = _get_metadata_path(user_id)
    
    if not os.path.exists(metadata_path):
        raise FileNotFoundError_(
            f"Metadata file not found: {metadata_path}"
        )
    
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        logger.debug(f"Loaded metadata: {user_id}")
        return metadata
        
    except json.JSONDecodeError as e:
        raise JSONDecodeError(
            f"Failed to parse metadata JSON for {user_id}: {e}"
        ) from e
    except Exception as e:
        raise JSONDecodeError(
            f"Failed to read metadata for {user_id}: {e}"
        ) from e


def save_metadata(user_id: str, metadata: dict) -> None:
    """
    Save metadata to disk with atomic write and backup.
    
    Process:
        1. Write to temporary file
        2. Calculate checksum
        3. Atomic rename to metadata.json
        4. Keep previous version as metadata.json.bak
    
    Args:
        user_id: Index owner user ID
        metadata: Metadata dictionary
    
    Raises:
        FileNotFoundError_: Directory does not exist
        JSONDecodeError: Cannot serialize to JSON
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    metadata_path = _get_metadata_path(user_id)
    metadata_backup_path = _get_metadata_backup_path(user_id)
    temp_path = metadata_path + ".tmp"
    
    try:
        # Ensure directory exists
        os.makedirs(user_dir, exist_ok=True)
        
        # Write to temporary file
        with open(temp_path, "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.debug(f"Wrote temporary metadata: {temp_path}")
        
        # Backup existing metadata
        if os.path.exists(metadata_path):
            if os.path.exists(metadata_backup_path):
                os.remove(metadata_backup_path)
            os.rename(metadata_path, metadata_backup_path)
            logger.debug(f"Backed up previous metadata: {metadata_backup_path}")
        
        # Atomic rename
        os.rename(temp_path, metadata_path)
        logger.debug(f"Saved metadata: {metadata_path}")
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise FileNotFoundError_(f"Failed to save metadata for {user_id}: {e}") from e


def create_empty_metadata(user_id: str, index_type: str = "flat") -> dict:
    """
    Create empty metadata structure.
    
    Args:
        user_id: Index owner user ID
        index_type: 'flat' or 'ivf'
    
    Returns:
        dict: Empty metadata structure
    """
    now = datetime.utcnow().isoformat() + "Z"
    
    return {
        "version": METADATA_VERSION,
        "schema_version": METADATA_VERSION,
        "user_id": user_id,
        "embedding_model": "text-embedding-3-large",
        "embedding_dimension": 3072,
        "created_at": now,
        "modified_at": now,
        "chunk_count": 0,
        "index_type": index_type,
        "checksum": "sha256:",
        "entries": [],
        "lookup_index": {
            "chunk_id_to_faiss": {},
            "doc_id_to_chunk_ids": {},
        }
    }


def metadata_entry_from_embedded_chunk(
    embedded_chunk: EmbeddedChunk,
    faiss_id: int
) -> MetadataEntry:
    """
    Convert EmbeddedChunk to MetadataEntry with FAISS ID.
    
    Args:
        embedded_chunk: EmbeddedChunk object
        faiss_id: FAISS integer ID in index
    
    Returns:
        MetadataEntry: Metadata entry for sidecar
    """
    text_checksum = _compute_text_checksum(embedded_chunk.text)
    
    return MetadataEntry(
        faiss_id=faiss_id,
        chunk_id=embedded_chunk.chunk_id,
        doc_id=embedded_chunk.doc_id,
        doc_name=embedded_chunk.doc_name,
        chunk_index=embedded_chunk.chunk_index,
        page_number=embedded_chunk.page_number,
        section=embedded_chunk.section,
        jurisdiction=embedded_chunk.jurisdiction,
        user_id=embedded_chunk.user_id,
        has_ocr=embedded_chunk.has_ocr,
        token_count=embedded_chunk.token_count,
        uploaded_at=embedded_chunk.uploaded_at,
        embedded_at=embedded_chunk.embedded_at,
        text_checksum=text_checksum,
        text_length=len(embedded_chunk.text),
        text=embedded_chunk.text,
    )


def resolve_faiss_id(user_id: str, chunk_id: str) -> Optional[int]:
    """
    Resolve chunk_id → faiss_id via metadata.json.
    
    Args:
        user_id: Index owner user ID
        chunk_id: Chunk identifier
    
    Returns:
        Optional[int]: FAISS ID if found, None otherwise
    """
    try:
        metadata = load_metadata(user_id)
        lookup = metadata.get("lookup_index", {}).get("chunk_id_to_faiss", {})
        return lookup.get(chunk_id)
    except FileNotFoundError_:
        return None
    except Exception as e:
        logger.warning(f"Failed to resolve FAISS ID: {e}")
        return None


def resolve_chunk_ids_by_doc(user_id: str, doc_id: str) -> List[str]:
    """
    Resolve all chunk_ids for a document.
    
    Args:
        user_id: Index owner user ID
        doc_id: Document identifier
    
    Returns:
        List[str]: List of chunk IDs in document
    """
    try:
        metadata = load_metadata(user_id)
        lookup = metadata.get("lookup_index", {}).get("doc_id_to_chunk_ids", {})
        return lookup.get(doc_id, [])
    except FileNotFoundError_:
        return []
    except Exception as e:
        logger.warning(f"Failed to resolve chunk IDs: {e}")
        return []


def add_entries_to_metadata(
    user_id: str,
    entries: List[MetadataEntry],
    starting_faiss_id: int = 0,
) -> dict:
    """
    Add metadata entries to a user's metadata.
    
    Args:
        user_id: Index owner user ID
        entries: List of MetadataEntry objects
        starting_faiss_id: Starting FAISS ID (if not in entries)
    
    Returns:
        dict: Updated metadata
    """
    try:
        metadata = load_metadata(user_id)
    except FileNotFoundError_:
        metadata = create_empty_metadata(user_id)
    
    # Add entries
    for entry in entries:
        metadata["entries"].append(entry.dict())
        
        # Update lookup indices
        metadata["lookup_index"]["chunk_id_to_faiss"][entry.chunk_id] = entry.faiss_id
        
        if entry.doc_id not in metadata["lookup_index"]["doc_id_to_chunk_ids"]:
            metadata["lookup_index"]["doc_id_to_chunk_ids"][entry.doc_id] = []
        
        if entry.chunk_id not in metadata["lookup_index"]["doc_id_to_chunk_ids"][entry.doc_id]:
            metadata["lookup_index"]["doc_id_to_chunk_ids"][entry.doc_id].append(
                entry.chunk_id
            )
    
    # Update counters
    metadata["chunk_count"] = len(metadata["entries"])
    metadata["modified_at"] = datetime.utcnow().isoformat() + "Z"
    
    return metadata


def remove_entries_from_metadata(
    user_id: str,
    chunk_ids: List[str],
) -> dict:
    """
    Remove metadata entries by chunk_id.
    
    Args:
        user_id: Index owner user ID
        chunk_ids: List of chunk IDs to remove
    
    Returns:
        dict: Updated metadata
    """
    metadata = load_metadata(user_id)
    
    chunk_ids_set = set(chunk_ids)
    
    # Filter out entries
    original_count = len(metadata["entries"])
    metadata["entries"] = [
        e for e in metadata["entries"]
        if e["chunk_id"] not in chunk_ids_set
    ]
    removed_count = original_count - len(metadata["entries"])
    
    # Rebuild lookup indices
    metadata["lookup_index"]["chunk_id_to_faiss"] = {}
    metadata["lookup_index"]["doc_id_to_chunk_ids"] = {}
    
    for entry in metadata["entries"]:
        chunk_id = entry["chunk_id"]
        doc_id = entry["doc_id"]
        faiss_id = entry["faiss_id"]
        
        metadata["lookup_index"]["chunk_id_to_faiss"][chunk_id] = faiss_id
        
        if doc_id not in metadata["lookup_index"]["doc_id_to_chunk_ids"]:
            metadata["lookup_index"]["doc_id_to_chunk_ids"][doc_id] = []
        metadata["lookup_index"]["doc_id_to_chunk_ids"][doc_id].append(chunk_id)
    
    # Update counters
    metadata["chunk_count"] = len(metadata["entries"])
    metadata["modified_at"] = datetime.utcnow().isoformat() + "Z"
    
    logger.info(f"Removed {removed_count} entries from metadata for {user_id}")

    return metadata


def load_metadata_for_user(user_id: str) -> dict:
    """
    Alias for load_metadata — load metadata sidecar for a user.
    Returns empty metadata structure if not found.
    """
    try:
        return load_metadata(user_id)
    except FileNotFoundError_:
        return create_empty_metadata(user_id)
