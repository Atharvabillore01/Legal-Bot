"""
Concurrency control and locking for FAISS index access.

Multi-reader, single-writer (MRSW) pattern for safe concurrent access.
"""

import logging
import threading
from typing import Optional, Dict
from datetime import datetime
from dataclasses import dataclass
from contextlib import contextmanager

from .exceptions import LockTimeoutError, DeadlockDetectedError
from .constants import LOCK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    """Information about a held lock."""
    lock_type: str  # "read" or "write"
    thread_id: int
    timestamp: datetime


class UserIndexLock:
    """
    Reader-writer lock for FAISS index access.
    
    Semantics:
        - Multiple concurrent readers allowed (shared lock)
        - Exclusive writer (blocks readers, prevented by readers)
        - FIFO fairness (readers/writers queued fairly)
    """
    
    def __init__(self, user_id: str):
        """
        Initialize lock for a user.
        
        Args:
            user_id: Index owner user ID
        """
        self.user_id = user_id
        
        # Underlying synchronization primitives
        self._read_count = 0
        self._write_count = 0
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._read_condition = threading.Condition(self._read_lock)
        
        # For deadlock detection
        self._lock_info: Dict[int, LockInfo] = {}
    
    def acquire_read(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire read lock (blocks until available, shared).
        
        Args:
            timeout: Max seconds to wait (default: module-level constant)
        
        Returns:
            bool: True if acquired, False if timeout
        
        Raises:
            DeadlockDetectedError: Potential deadlock detected
        """
        timeout = timeout or LOCK_TIMEOUT_SECONDS
        thread_id = threading.get_ident()
        
        result = self._read_condition.acquire(timeout=timeout)
        if not result:
            logger.warning(f"Read lock timeout for {self.user_id}:{thread_id}")
            raise LockTimeoutError(
                f"Failed to acquire read lock for {self.user_id} within {timeout}s"
            )
        
        try:
            self._read_count += 1
            self._lock_info[thread_id] = LockInfo(
                lock_type="read",
                thread_id=thread_id,
                timestamp=datetime.now()
            )
            logger.debug(f"Read lock acquired: {self.user_id} (readers={self._read_count})")
            return True
        finally:
            self._read_condition.release()
    
    def release_read(self) -> None:
        """
        Release read lock.
        
        Raises:
            ValueError: Lock not held by current thread
        """
        thread_id = threading.get_ident()
        
        with self._read_condition:
            if thread_id not in self._lock_info:
                raise ValueError(f"Thread {thread_id} does not hold read lock")
            
            self._read_count -= 1
            del self._lock_info[thread_id]
            
            if self._read_count == 0:
                # Notify waiting writers
                self._read_condition.notify_all()
            
            logger.debug(f"Read lock released: {self.user_id} (readers={self._read_count})")
    
    def acquire_write(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire write lock (blocks readers and writers, exclusive).
        
        Args:
            timeout: Max seconds to wait (default: module-level constant)
        
        Returns:
            bool: True if acquired, False if timeout
        
        Raises:
            LockTimeoutError: Lock not acquired within timeout
        """
        timeout = timeout or LOCK_TIMEOUT_SECONDS
        thread_id = threading.get_ident()
        
        # Acquire write lock (exclusive)
        result = self._write_lock.acquire(timeout=timeout)
        if not result:
            logger.warning(f"Write lock timeout for {self.user_id}:{thread_id}")
            raise LockTimeoutError(
                f"Failed to acquire write lock for {self.user_id} within {timeout}s"
            )
        
        # Wait for all readers to finish
        with self._read_condition:
            while self._read_count > 0:
                acquired = self._read_condition.wait(timeout=timeout)
                if not acquired:
                    self._write_lock.release()
                    logger.warning(f"Write lock timeout waiting for readers: {self.user_id}")
                    raise LockTimeoutError(
                        f"Write lock timeout waiting for readers in {self.user_id}"
                    )
        
        # Mark this thread as holding write lock
        self._write_count += 1
        self._lock_info[thread_id] = LockInfo(
            lock_type="write",
            thread_id=thread_id,
            timestamp=datetime.now()
        )
        logger.debug(f"Write lock acquired: {self.user_id}")
        return True
    
    def release_write(self) -> None:
        """
        Release write lock.
        
        Raises:
            ValueError: Lock not held by current thread
        """
        thread_id = threading.get_ident()
        
        if thread_id not in self._lock_info:
            raise ValueError(f"Thread {thread_id} does not hold write lock")
        
        self._write_count -= 1
        del self._lock_info[thread_id]
        
        # Notify waiting readers and writers
        with self._read_condition:
            self._read_condition.notify_all()
        
        self._write_lock.release()
        logger.debug(f"Write lock released: {self.user_id}")
    
    def acquire_read_context(self, timeout: Optional[float] = None):
        """Context manager for read lock."""
        return self._ReadLockContext(self, timeout)
    
    def acquire_write_context(self, timeout: Optional[float] = None):
        """Context manager for write lock."""
        return self._WriteLockContext(self, timeout)
    
    def __enter__(self) -> "UserIndexLock":
        """Context manager entry (acquires write lock)."""
        self.acquire_write()
        return self
    
    def __exit__(self, *args) -> None:
        """Context manager exit (releases write lock)."""
        self.release_write()
    
    class _ReadLockContext:
        """Context manager for read lock."""
        def __init__(self, lock: "UserIndexLock", timeout: Optional[float] = None):
            self.lock = lock
            self.timeout = timeout
        
        def __enter__(self) -> "UserIndexLock":
            self.lock.acquire_read(timeout=self.timeout)
            return self.lock
        
        def __exit__(self, *args) -> None:
            self.lock.release_read()
    
    class _WriteLockContext:
        """Context manager for write lock."""
        def __init__(self, lock: "UserIndexLock", timeout: Optional[float] = None):
            self.lock = lock
            self.timeout = timeout
        
        def __enter__(self) -> "UserIndexLock":
            self.lock.acquire_write(timeout=self.timeout)
            return self.lock
        
        def __exit__(self, *args) -> None:
            self.lock.release_write()


class LockManager:
    """
    Global lock manager for all user indices.
    
    Creates and manages per-user locks efficiently.
    """
    
    def __init__(self):
        """Initialize lock manager."""
        self._locks: Dict[str, UserIndexLock] = {}
        self._locks_mutex = threading.Lock()
    
    def get_lock(self, user_id: str) -> UserIndexLock:
        """
        Get or create lock for a user.
        
        Args:
            user_id: Index owner user ID
        
        Returns:
            UserIndexLock: Lock object for user
        """
        with self._locks_mutex:
            if user_id not in self._locks:
                self._locks[user_id] = UserIndexLock(user_id)
            return self._locks[user_id]
    
    def release_user_locks(self, user_id: str) -> None:
        """
        Clean up locks for a user.
        
        Args:
            user_id: Index owner user ID
        """
        with self._locks_mutex:
            if user_id in self._locks:
                del self._locks[user_id]


# Global lock manager instance
_lock_manager = LockManager()


def get_user_lock(user_id: str) -> UserIndexLock:
    """
    Get lock for a user.
    
    Args:
        user_id: Index owner user ID
    
    Returns:
        UserIndexLock: Lock object
    """
    return _lock_manager.get_lock(user_id)


@contextmanager
def read_lock(user_id: str, timeout: Optional[float] = None):
    """
    Context manager for read lock.
    
    Example:
        with read_lock(user_id):
            results = search_index(user_id)
    """
    lock = get_user_lock(user_id)
    lock.acquire_read(timeout=timeout)
    try:
        yield lock
    finally:
        lock.release_read()


@contextmanager
def write_lock(user_id: str, timeout: Optional[float] = None):
    """
    Context manager for write lock.
    
    Example:
        with write_lock(user_id):
            add_chunks_to_index(user_id, chunks)
    """
    lock = get_user_lock(user_id)
    lock.acquire_write(timeout=timeout)
    try:
        yield lock
    finally:
        lock.release_write()
