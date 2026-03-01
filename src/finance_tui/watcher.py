"""File watcher for live-reloading Obsidian transaction files."""

import threading
import time
from pathlib import Path

from textual.message import Message
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class DataChanged(Message):
    """Posted when transaction files change on disk."""

    def __init__(self, path: str):
        super().__init__()
        self.path = path


class _DebouncedHandler(FileSystemEventHandler):
    """Debounced FSEvent handler that calls a callback after 500ms of quiet."""

    def __init__(self, callback, debounce_sec: float = 0.5):
        super().__init__()
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._last_path = ""
        # Track paths we've written ourselves to avoid infinite loops
        self._ignore_paths: set[str] = set()

    def ignore_path(self, path: str):
        """Mark a path to be ignored for the next change event."""
        with self._lock:
            self._ignore_paths.add(str(Path(path).resolve()))

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".md"):
            return

        resolved = str(Path(event.src_path).resolve())
        with self._lock:
            if resolved in self._ignore_paths:
                self._ignore_paths.discard(resolved)
                return

        self._last_path = event.src_path
        self._schedule()

    def on_created(self, event):
        self.on_modified(event)

    def _schedule(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_sec, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self):
        self._callback(self._last_path)


class FileWatcher:
    """Watches the Obsidian finance directory for changes."""

    def __init__(self, watch_dir: Path, app):
        self._watch_dir = watch_dir
        self._app = app
        self._observer: Observer | None = None
        self._handler = _DebouncedHandler(self._on_change)

    def start(self):
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self._watch_dir), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def ignore_next_change(self, path: str):
        """Prevent our own writes from triggering a reload."""
        self._handler.ignore_path(path)

    def _on_change(self, path: str):
        self._app.post_message(DataChanged(path))
