"""Configuration hot-reload module for dynamic configuration updates."""

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigReloadError(Exception):
    """Configuration reload error."""

    pass


class ConfigChangeListener:
    """Listener for configuration changes."""

    def __init__(self, callback: Callable[[dict[str, Any]], None]):
        """Initialize listener.

        Args:
            callback: Callback function to call on config change
        """
        self.callback = callback

    def on_change(self, changes: dict[str, Any]) -> None:
        """Handle configuration change.

        Args:
            changes: Dictionary of changed configuration values
        """
        try:
            self.callback(changes)
        except Exception as e:
            logger.error(f"Error in config change callback: {e}")


class ConfigFileWatcher(FileSystemEventHandler):
    """Watch configuration files for changes."""

    def __init__(self, config_path: Path, on_change: Callable[[], None]):
        """Initialize watcher.

        Args:
            config_path: Path to configuration file
            on_change: Callback when file changes
        """
        self.config_path = config_path
        self.on_change = on_change
        self.last_modified = 0.0

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification event.

        Args:
            event: File modification event
        """
        if event.is_directory:
            return

        event_path = Path(event.src_path)
        if event_path == self.config_path:
            # Debounce rapid changes
            import time
            current_time = time.time()
            if current_time - self.last_modified > 1.0:
                self.last_modified = current_time
                logger.info(f"Configuration file changed: {event_path}")
                self.on_change()


class ConfigReloader:
    """Handle configuration hot-reload."""

    def __init__(self, config_path: Path):
        """Initialize reloader.

        Args:
            config_path: Path to configuration file to watch
        """
        self.config_path = config_path
        self.listeners: list[ConfigChangeListener] = []
        self.observer: Observer | None = None
        self.reload_lock = threading.Lock()
        self._previous_config: dict[str, Any] | None = None

    def add_listener(self, listener: ConfigChangeListener) -> None:
        """Add configuration change listener.

        Args:
            listener: Listener to add
        """
        self.listeners.append(listener)

    def remove_listener(self, listener: ConfigChangeListener) -> None:
        """Remove configuration change listener.

        Args:
            listener: Listener to remove
        """
        if listener in self.listeners:
            self.listeners.remove(listener)

    def start_watching(self) -> None:
        """Start watching configuration file for changes."""
        if not self.config_path.exists():
            logger.warning(f"Configuration file does not exist: {self.config_path}")
            return

        try:
            self.observer = Observer()
            watcher = ConfigFileWatcher(self.config_path, self._on_config_change)
            self.observer.schedule(watcher, str(self.config_path.parent), recursive=False)
            self.observer.start()
            logger.info(f"Started watching configuration file: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to start configuration watcher: {e}")
            raise ConfigReloadError(f"Failed to start watcher: {e}")

    def stop_watching(self) -> None:
        """Stop watching configuration file."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped watching configuration file")

    def _on_config_change(self) -> None:
        """Handle configuration file change."""
        with self.reload_lock:
            try:
                logger.info("Reloading configuration...")
                self._notify_listeners()
            except Exception as e:
                logger.error(f"Error reloading configuration: {e}")

    def _notify_listeners(self) -> None:
        """Notify all listeners of configuration change."""
        for listener in self.listeners:
            listener.on_change({})

    async def reload_async(self) -> None:
        """Reload configuration asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._on_config_change)


class ConfigSnapshot:
    """Snapshot of configuration state for rollback."""

    def __init__(self, config_data: dict[str, Any], timestamp: float):
        """Initialize snapshot.

        Args:
            config_data: Configuration data
            timestamp: Snapshot timestamp
        """
        self.config_data = config_data.copy()
        self.timestamp = timestamp

    def restore(self) -> dict[str, Any]:
        """Restore configuration from snapshot.

        Returns:
            Configuration data
        """
        return self.config_data.copy()


class ConfigRollbackManager:
    """Manage configuration rollback."""

    def __init__(self, max_snapshots: int = 10):
        """Initialize rollback manager.

        Args:
            max_snapshots: Maximum number of snapshots to keep
        """
        self.max_snapshots = max_snapshots
        self.snapshots: list[ConfigSnapshot] = []

    def create_snapshot(self, config_data: dict[str, Any]) -> None:
        """Create configuration snapshot.

        Args:
            config_data: Configuration data to snapshot
        """
        import time
        snapshot = ConfigSnapshot(config_data, time.time())
        self.snapshots.append(snapshot)

        # Keep only max_snapshots
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)

        logger.info(f"Created configuration snapshot (total: {len(self.snapshots)})")

    def rollback_to_previous(self) -> dict[str, Any] | None:
        """Rollback to previous configuration snapshot.

        Returns:
            Previous configuration data or None if no snapshots available
        """
        if len(self.snapshots) < 2:
            logger.warning("Not enough snapshots for rollback")
            return None

        # Remove current snapshot and get previous
        self.snapshots.pop()
        previous = self.snapshots[-1]
        logger.info("Rolled back to previous configuration")
        return previous.restore()

    def rollback_to_snapshot(self, index: int) -> dict[str, Any] | None:
        """Rollback to specific snapshot.

        Args:
            index: Snapshot index

        Returns:
            Configuration data or None if index is invalid
        """
        if index < 0 or index >= len(self.snapshots):
            logger.error(f"Invalid snapshot index: {index}")
            return None

        snapshot = self.snapshots[index]
        logger.info(f"Rolled back to snapshot {index}")
        return snapshot.restore()

    def list_snapshots(self) -> list[dict[str, Any]]:
        """List all available snapshots.

        Returns:
            List of snapshot metadata
        """
        return [
            {
                "index": i,
                "timestamp": snapshot.timestamp,
            }
            for i, snapshot in enumerate(self.snapshots)
        ]
