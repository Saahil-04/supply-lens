"""Small in-process analysis store for the MVP API contract.

This deliberately avoids introducing a database for the single-process MVP. Entries
expire after a TTL and the oldest analyses are evicted when the store reaches capacity.
Use a shared persistent store before deploying multiple workers or requiring durability.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

DEFAULT_TTL_HOURS = 6
MAX_ANALYSES = 20


@dataclass
class AnalysisEntry:
    analysis_id: str
    result: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class AnalysisStore:
    def __init__(self, max_entries: int = MAX_ANALYSES, ttl_hours: int = DEFAULT_TTL_HOURS) -> None:
        self.max_entries = max_entries
        self.ttl = timedelta(hours=ttl_hours)
        self._entries: OrderedDict[str, AnalysisEntry] = OrderedDict()
        self._lock = RLock()

    def _purge_expired(self, now: datetime) -> None:
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

    def create(self, result: dict[str, Any]) -> AnalysisEntry:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired(now)
            while len(self._entries) >= self.max_entries:
                self._entries.popitem(last=False)
            analysis_id = str(uuid4())
            entry = AnalysisEntry(analysis_id, result, now, now + self.ttl)
            self._entries[analysis_id] = entry
            return entry

    def get(self, analysis_id: str) -> AnalysisEntry | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired(now)
            entry = self._entries.get(analysis_id)
            if entry is not None:
                self._entries.move_to_end(analysis_id)
            return entry


analysis_store = AnalysisStore()
