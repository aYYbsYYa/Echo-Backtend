import json
from pathlib import Path
from threading import Lock
from typing import Any


class JsonRepository:
    """Small replaceable persistence boundary for a JSON collection."""

    _locks: dict[Path, Lock] = {}

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]\n", encoding="utf-8")
        self.lock = self._locks.setdefault(path, Lock())

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return json.loads(self.path.read_text(encoding="utf-8"))

    def replace_all(self, records: list[dict[str, Any]]) -> None:
        with self.lock:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(self.path)

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        records = self.all()
        records.append(record)
        self.replace_all(records)
        return record

    def find(self, record_id: str) -> dict[str, Any] | None:
        return next((record for record in self.all() if record.get("id") == record_id), None)
