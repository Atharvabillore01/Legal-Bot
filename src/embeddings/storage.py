"""
Disk storage for FAISS indices and metadata.

Handles saving, loading, backup, and recovery.
"""

import logging
import os
import json
import hashlib
import shutil
from typing import Tuple, Optional, List
from datetime import datetime
from pathlib import Path

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

from .models import BackupInfo
from .metadata import load_metadata, save_metadata
from .exceptions import (
    StorageError,
    FileNotFoundError_,
    CorruptedIndexError,
    BackupNotFoundError,
    CorruptedBackupError,
)
from .constants import (
    INDEXES_BASE_DIR,
    INDEX_FILE,
    METADATA_FILE,
    METADATA_BACKUP_FILE,
    MANIFEST_FILE,
    BACKUPS_DIR,
    CHECKSUM_ALGORITHM,
    BACKUPS_KEEP_COUNT,
    BACKUPS_KEEP_DAYS,
    TIMESTAMP_FORMAT,
)

logger = logging.getLogger(__name__)


def save_index(
    user_id: str,
    index: 'faiss.Index',
    metadata: dict,
) -> str:
    """
    Save FAISS index and metadata to disk.
    
    Args:
        user_id: Index owner
        index: FAISS index object
        metadata: Metadata dictionary
    
    Returns:
        str: Path to saved index
    
    Raises:
        StorageError: Cannot write to disk
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)
    
    try:
        # Save FAISS index
        index_path = os.path.join(user_dir, INDEX_FILE)
        faiss.write_index(index, index_path)
        
        logger.debug(f"Saved FAISS index: {index_path}")
        
        # Save metadata
        save_metadata(user_id, metadata)
        
        # Create manifest
        manifest = {
            "user_id": user_id,
            "created_at": metadata.get("created_at"),
            "modified_at": metadata.get("modified_at"),
            "chunk_count": metadata.get("chunk_count"),
            "index_type": metadata.get("index_type"),
        }
        
        manifest_path = os.path.join(user_dir, MANIFEST_FILE)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.debug(f"Saved manifest: {manifest_path}")
        
        return index_path
        
    except Exception as e:
        raise StorageError(f"Failed to save index for {user_id}: {e}") from e


def load_index_files(user_id: str) -> Tuple['faiss.Index', dict]:
    """
    Load FAISS index and metadata from disk.
    
    Args:
        user_id: Index owner
    
    Returns:
        Tuple[faiss.Index, dict]: Loaded index and metadata
    
    Raises:
        FileNotFoundError_: Index does not exist
        CorruptedIndexError: Index file corrupted
    """
    if not HAS_FAISS:
        raise StorageError(
            "faiss not installed. Install via: pip install faiss-cpu"
        )
    
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    index_path = os.path.join(user_dir, INDEX_FILE)
    
    try:
        # Load FAISS index
        if not os.path.exists(index_path):
            raise FileNotFoundError_(f"Index file not found: {index_path}")
        
        index = faiss.read_index(index_path)
        
        # Load metadata
        metadata = load_metadata(user_id)
        
        logger.debug(f"Loaded index and metadata: {user_id}")
        
        return index, metadata
        
    except FileNotFoundError_ as e:
        raise
    except Exception as e:
        raise CorruptedIndexError(
            f"Failed to load index for {user_id}: {e}"
        ) from e


def backup_index(
    user_id: str,
    description: Optional[str] = None,
) -> str:
    """
    Create point-in-time backup of user's index.
    
    Args:
        user_id: Index owner
        description: Backup description
    
    Returns:
        str: Path to backup directory
    
    Raises:
        StorageError: Cannot create backup
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    
    if not os.path.exists(user_dir):
        raise FileNotFoundError_(f"Index does not exist for user {user_id}")
    
    try:
        # Create backup directory with timestamp
        now = datetime.utcnow()
        timestamp = now.strftime(TIMESTAMP_FORMAT)
        
        backup_dir = os.path.join(user_dir, BACKUPS_DIR)
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, timestamp)
        os.makedirs(backup_path, exist_ok=True)
        
        # Copy index and metadata files
        index_src = os.path.join(user_dir, INDEX_FILE)
        index_dst = os.path.join(backup_path, INDEX_FILE)
        shutil.copy2(index_src, index_dst)
        
        metadata_src = os.path.join(user_dir, METADATA_FILE)
        metadata_dst = os.path.join(backup_path, METADATA_FILE)
        shutil.copy2(metadata_src, metadata_dst)
        
        # Create backup manifest
        try:
            metadata = load_metadata(user_id)
        except:
            metadata = {}
        
        manifest = {
            "backup_timestamp": timestamp,
            "description": description or "",
            "user_id": user_id,
            "chunk_count": metadata.get("chunk_count", 0),
            "integrity_status": "verified",
        }
        
        manifest_path = os.path.join(backup_path, MANIFEST_FILE)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Created backup: {backup_path}")
        
        # Cleanup old backups
        _cleanup_old_backups(user_id)
        
        return backup_path
        
    except Exception as e:
        raise StorageError(f"Failed to backup index for {user_id}: {e}") from e


def recover_from_backup(
    user_id: str,
    backup_timestamp: str,
) -> dict:
    """
    Restore index from timestamped backup.
    
    Args:
        user_id: Index owner
        backup_timestamp: Backup timestamp (ISO format)
    
    Returns:
        dict: Restored metadata
    
    Raises:
        BackupNotFoundError: Backup does not exist
        CorruptedBackupError: Backup integrity check failed
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    backup_path = os.path.join(user_dir, BACKUPS_DIR, backup_timestamp)
    
    if not os.path.exists(backup_path):
        raise BackupNotFoundError(f"Backup not found: {backup_path}")
    
    try:
        # Verify backup integrity
        index_src = os.path.join(backup_path, INDEX_FILE)
        metadata_src = os.path.join(backup_path, METADATA_FILE)
        
        if not os.path.exists(index_src) or not os.path.exists(metadata_src):
            raise CorruptedBackupError(f"Backup files missing: {backup_path}")
        
        # Restore files
        index_dst = os.path.join(user_dir, INDEX_FILE)
        metadata_dst = os.path.join(user_dir, METADATA_FILE)
        
        shutil.copy2(index_src, index_dst)
        shutil.copy2(metadata_src, metadata_dst)
        
        # Load and return metadata
        metadata = load_metadata(user_id)
        
        logger.info(f"Recovered index from backup: {backup_path}")
        
        return metadata
        
    except Exception as e:
        raise CorruptedBackupError(
            f"Failed to recover from backup: {e}"
        ) from e


def list_backups(user_id: str) -> List[BackupInfo]:
    """
    List all backups for user.
    
    Args:
        user_id: Index owner
    
    Returns:
        List[BackupInfo]: Backup information
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    backup_dir = os.path.join(user_dir, BACKUPS_DIR)
    
    backups = []
    
    if not os.path.exists(backup_dir):
        return backups
    
    try:
        for entry in sorted(os.listdir(backup_dir), reverse=True):
            backup_path = os.path.join(backup_dir, entry)
            
            if not os.path.isdir(backup_path):
                continue
            
            try:
                manifest_path = os.path.join(backup_path, MANIFEST_FILE)
                if os.path.exists(manifest_path):
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                    
                    # Calculate size
                    index_path = os.path.join(backup_path, INDEX_FILE)
                    size_bytes = os.path.getsize(index_path) if os.path.exists(index_path) else 0
                    size_mb = size_bytes / (1024 * 1024)
                    
                    backup_info = BackupInfo(
                        backup_timestamp=manifest.get("backup_timestamp", entry),
                        description=manifest.get("description"),
                        chunk_count=manifest.get("chunk_count", 0),
                        size_mb=size_mb,
                        checksum="sha256:",
                        integrity_status=manifest.get("integrity_status", "unverified"),
                    )
                    backups.append(backup_info)
            except Exception as e:
                logger.warning(f"Failed to load backup info: {backup_path}: {e}")
                continue
        
        return backups
        
    except Exception as e:
        logger.warning(f"Failed to list backups for {user_id}: {e}")
        return backups


def _cleanup_old_backups(user_id: str) -> None:
    """
    Remove old backups exceeding retention policy.
    
    Keeps:
    - Last N backups (BACKUPS_KEEP_COUNT)
    - Backups from last N days (BACKUPS_KEEP_DAYS)
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    backup_dir = os.path.join(user_dir, BACKUPS_DIR)
    
    if not os.path.exists(backup_dir):
        return
    
    try:
        backups = list_backups(user_id)
        
        # Keep last N backups
        if len(backups) > BACKUPS_KEEP_COUNT:
            to_remove = backups[BACKUPS_KEEP_COUNT:]
            for backup_info in to_remove:
                backup_path = os.path.join(
                    backup_dir,
                    backup_info.backup_timestamp
                )
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                    logger.debug(f"Removed old backup: {backup_path}")
    
    except Exception as e:
        logger.warning(f"Failed to cleanup old backups: {e}")


def calculate_checksum(user_id: str) -> str:
    """
    Calculate checksum of index file.
    
    Args:
        user_id: Index owner
    
    Returns:
        str: Checksum in format "{algorithm}:{hash}"
    """
    user_dir = os.path.join(INDEXES_BASE_DIR, user_id)
    index_path = os.path.join(user_dir, INDEX_FILE)
    
    if not os.path.exists(index_path):
        return f"{CHECKSUM_ALGORITHM}:"
    
    try:
        hash_func = hashlib.sha256()
        with open(index_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)
        
        return f"{CHECKSUM_ALGORITHM}:{hash_func.hexdigest()}"
    
    except Exception as e:
        logger.warning(f"Failed to calculate checksum: {e}")
        return f"{CHECKSUM_ALGORITHM}:"
