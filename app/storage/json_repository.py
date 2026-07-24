import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable


class JsonRepository:
    """Small replaceable persistence boundary for a JSON collection."""

    _locks: dict[Path, Lock] = {}

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]\n", encoding="utf-8")
        self.lock = self._locks.setdefault(path, Lock())

    def _read_unlocked(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write_unlocked(self, records: list[dict[str, Any]]) -> None:
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read_unlocked()

    def replace_all(self, records: list[dict[str, Any]]) -> None:
        with self.lock:
            self._write_unlocked(records)

    def append(
        self, record: dict[str, Any], max_records: int | None = None
    ) -> dict[str, Any]:
        with self.lock:
            records = self._read_unlocked()
            records.append(record)
            if max_records is not None and max_records > 0:
                records = records[-max_records:]
            self._write_unlocked(records)
        return record

    def upsert(self, record: dict[str, Any], key: str = "id") -> dict[str, Any]:
        with self.lock:
            records = self._read_unlocked()
            value = record.get(key)
            for index, existing in enumerate(records):
                if existing.get(key) == value:
                    records[index] = record
                    break
            else:
                records.append(record)
            self._write_unlocked(records)
        return record

    def find(self, record_id: str) -> dict[str, Any] | None:
        return next((record for record in self.all() if record.get("id") == record_id), None)

    def delete(
        self,
        record_id: str,
        key: str = "id",
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any] | None:
        with self.lock:
            records = self._read_unlocked()
            for index, record in enumerate(records):
                if record.get(key) != record_id:
                    continue
                if predicate is not None and not predicate(record):
                    return None
                deleted = records.pop(index)
                self._write_unlocked(records)
                return deleted
        return None
