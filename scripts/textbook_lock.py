#!/usr/bin/env python3
"""
File locking utility for Учебник.md and other shared files.
Prevents parallel write races between agents.

Usage:
    from textbook_lock import TextbookLock
    
    with TextbookLock() as lock:
        # read-modify-write Учебник.md safely
        content = lock.read()
        # ... modify content ...
        lock.write(content)

    # Or use the context manager with a specific file
    with TextbookLock("/path/to/file.md") as lock:
        content = lock.read()
        lock.write(new_content)
"""

import os
import time
import fcntl
import errno
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


DEFAULT_TEXTBOOK = "/home/thomas/Documents/ObsidianVault/Учебник.md"
LOCK_TIMEOUT = 30  # seconds
LOCK_POLL_INTERVAL = 0.1


class TextbookLock:
    """File lock for safe concurrent access to Учебник.md."""
    
    def __init__(self, filepath: str = DEFAULT_TEXTBOOK, timeout: float = LOCK_TIMEOUT):
        self.filepath = Path(filepath)
        self.lock_path = self.filepath.with_suffix(self.filepath.suffix + ".lock")
        self.timeout = timeout
        self._lock_fd: Optional[int] = None
        self._content: str = ""
        
    def __enter__(self) -> "TextbookLock":
        self.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
        
    def acquire(self) -> None:
        """Acquire exclusive lock with timeout."""
        start = time.monotonic()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open lock file (create if needed)
        self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)
        
        while True:
            try:
                # Non-blocking exclusive lock
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return  # Lock acquired
            except BlockingIOError:
                if time.monotonic() - start >= self.timeout:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                    raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {self.timeout}s")
                time.sleep(LOCK_POLL_INTERVAL)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    if time.monotonic() - start >= self.timeout:
                        os.close(self._lock_fd)
                        self._lock_fd = None
                        raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {self.timeout}s")
                    time.sleep(LOCK_POLL_INTERVAL)
                else:
                    os.close(self._lock_fd)
                    self._lock_fd = None
                    raise
                    
    def release(self) -> None:
        """Release the lock."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self._lock_fd)
                self._lock_fd = None
                
    def read(self) -> str:
        """Read the file content (must be called after acquire)."""
        if self._lock_fd is None:
            raise RuntimeError("Lock not acquired. Call acquire() first or use context manager.")
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        if self.filepath.exists():
            with open(self.filepath, "r", encoding="utf-8") as f:
                self._content = f.read()
        else:
            self._content = ""
        return self._content
        
    def write(self, content: str) -> None:
        """Write content to file atomically (must be called after acquire)."""
        if self._lock_fd is None:
            raise RuntimeError("Lock not acquired. Call acquire() first or use context manager.")
        # Atomic write: write to temp, then rename
        tmp_path = self.filepath.with_suffix(self.filepath.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, self.filepath)
        self._content = content
        
    def read_write(self, transform_fn) -> str:
        """
        Atomic read-modify-write pattern.
        
        Args:
            transform_fn: Function that takes current content and returns new content.
            
        Returns:
            New content that was written.
        """
        content = self.read()
        new_content = transform_fn(content)
        self.write(new_content)
        return new_content


@contextmanager
def textbook_lock(filepath: str = DEFAULT_TEXTBOOK, timeout: float = LOCK_TIMEOUT):
    """Context manager for textbook locking."""
    lock = TextbookLock(filepath, timeout)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


def safe_append_line(filepath: str, line: str, after_marker: str = None) -> bool:
    """
    Safely append a line to a file, optionally after a specific marker.
    
    Args:
        filepath: Path to file
        line: Line to append (without trailing newline)
        after_marker: If provided, insert after the line containing this marker
        
    Returns:
        True if line was added, False if marker not found (when after_marker provided)
    """
    with TextbookLock(filepath) as lock:
        content = lock.read()
        lines = content.splitlines(keepends=True)
        
        if after_marker:
            # Find the line with the marker
            for i, l in enumerate(lines):
                if after_marker in l:
                    lines.insert(i + 1, line + "\n")
                    lock.write("".join(lines))
                    return True
            return False  # Marker not found
        else:
            # Append at end
            if content and not content.endswith("\n"):
                content += "\n"
            lock.write(content + line + "\n")
            return True


def safe_update_section(filepath: str, section_header: str, new_entries: list[str]) -> bool:
    """
    Safely update a section in Учебник.md by adding entries under a section header.
    
    Args:
        filepath: Path to Учебник.md
        section_header: The section header (e.g., "### 22. AI Engineering & Local LLM Tools")
        new_entries: List of entry lines to add (each should be a complete markdown line)
        
    Returns:
        True if section was found and updated, False otherwise
    """
    with TextbookLock(filepath) as lock:
        content = lock.read()
        lines = content.splitlines(keepends=True)
        
        # Find the section header
        section_idx = -1
        for i, line in enumerate(lines):
            if line.strip() == section_header.strip():
                section_idx = i
                break
                
        if section_idx == -1:
            return False
            
        # Find the next section header or end of file
        insert_idx = len(lines)
        for i in range(section_idx + 1, len(lines)):
            if lines[i].startswith("### "):
                insert_idx = i
                break
                
        # Insert new entries before the next section
        for entry in reversed(new_entries):
            lines.insert(insert_idx, entry + "\n")
            
        lock.write("".join(lines))
        return True


if __name__ == "__main__":
    # Demo/test
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_file = "/tmp/test_lock.txt"
        with TextbookLock(test_file) as lock:
            lock.write("initial\n")
            print("Wrote initial")
            time.sleep(0.5)
            content = lock.read()
            print(f"Read: {content}")
            lock.write(content + "appended\n")
            print("Appended")
        with open(test_file) as f:
            print(f"Final: {f.read()}")
        os.unlink(test_file)
        print("Lock test passed")