"""Persists inbox items the bot receives, before any LLM has looked at them."""

from __future__ import annotations

import shutil
from pathlib import Path

from .models import QueueItem, QueueItemStatus


class QueueStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, item_id: str) -> Path:
        return self.root / item_id

    def attachments_dir(self, item_id: str) -> Path:
        directory = self._dir(item_id) / "attachments"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save_attachment(self, item_id: str, source_path: str) -> str:
        """Copies an incoming file into this item's attachment folder, keeping arrival order."""
        directory = self.attachments_dir(item_id)
        existing = sorted(directory.iterdir())
        dest = directory / f"{len(existing):02d}{Path(source_path).suffix or '.jpg'}"
        shutil.copy(source_path, dest)
        return str(dest)

    def save(self, item: QueueItem) -> QueueItem:
        directory = self._dir(item.id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "item.json").write_text(item.model_dump_json(indent=2), encoding="utf-8")
        return item

    def load(self, item_id: str) -> QueueItem:
        path = self._dir(item_id) / "item.json"
        if not path.exists():
            raise FileNotFoundError(f"Queue item {item_id!r} not found")
        return QueueItem.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[QueueItem]:
        items = []
        for directory in sorted(self.root.iterdir()):
            path = directory / "item.json"
            if path.exists():
                items.append(QueueItem.model_validate_json(path.read_text(encoding="utf-8")))
        return sorted(items, key=lambda item: item.created_at)

    def list_by_status(self, status: QueueItemStatus) -> list[QueueItem]:
        return [item for item in self.list() if item.status == status]

    def delete(self, item_id: str) -> None:
        directory = self._dir(item_id)
        if directory.exists():
            shutil.rmtree(directory)
