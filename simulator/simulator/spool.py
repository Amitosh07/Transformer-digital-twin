"""Bounded durable single-owner SQLite spool. PUBACK never removes a row.

SQLite is local delivery storage, not proof of backend PostgreSQL transactions.
Quarantine counts toward capacity; overflow applies acquisition backpressure.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3
import time
from threading import RLock
from functools import wraps

def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._mutex:
            return method(self, *args, **kwargs)
    return call

from ml.pipeline.identity import payload_hash, serialize, utc


class SpoolFull(RuntimeError):
    pass


class DurableSpool:
    def __init__(self, directory, max_records=10000, max_bytes=16777216):
        if max_records <= 0 or max_bytes < 1024:
            raise ValueError("invalid spool capacity")
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        self._mutex = RLock()
        self.max_records, self.max_bytes = max_records, max_bytes
        owner_path = path / "owner.lock"
        self.owner = owner_path.open("r+b" if owner_path.exists() else "w+b")
        if owner_path.stat().st_size == 0:
            self.owner.write(b"0")
            self.owner.flush()
        self.owner.seek(0)
        try:
            import os
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.owner.close()
            raise RuntimeError("spool already has a bridge owner") from None
        self.db = sqlite3.connect(path / "delivery.sqlite3", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
        # Bound physical pages too (payload cap plus conservative index/row
        # allowance). DELETE-mode rollback journal is transient and bounded.
        self.db.execute(f"PRAGMA max_page_count={max(256, (2*max_bytes+1024*max_records)//page_size)}")
        self.db.execute("""CREATE TABLE IF NOT EXISTS entries (
            snapshot TEXT PRIMARY KEY, asset TEXT NOT NULL, event_time TEXT NOT NULL,
            hash TEXT NOT NULL, payload TEXT NOT NULL, size INTEGER NOT NULL,
            state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            pubacks INTEGER NOT NULL DEFAULT 0, reason TEXT, next_attempt REAL NOT NULL DEFAULT 0,
            UNIQUE(asset,event_time))""")
        self.db.execute("CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY,value INTEGER NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS watermarks (asset TEXT PRIMARY KEY,event_time TEXT NOT NULL,hash TEXT NOT NULL)")
        self.db.commit()

    @synchronized
    def increment(self, name):
        self.db.execute("INSERT INTO counters VALUES (?,1) ON CONFLICT(name) DO UPDATE SET value=value+1", (name,))

    @synchronized
    def record_counter(self, name):
        with self.db:
            self.increment(name)

    @synchronized
    def counters(self):
        return dict(self.db.execute("SELECT name,value FROM counters").fetchall())

    @synchronized
    def usage(self):
        return tuple(self.db.execute("SELECT COUNT(*),COALESCE(SUM(size),0) FROM entries").fetchone())

    @synchronized
    def enqueue(self, record):
        payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
        digest = payload_hash(payload)
        snapshot = (payload.get("acquisition") or {}).get("snapshot_id")
        if snapshot != digest:
            raise ValueError("snapshot ID must match frozen semantic hash")
        asset, event_time = payload["transformer_id"], utc(payload["timestamp"])
        watermark = self.db.execute("SELECT * FROM watermarks WHERE asset=?", (asset,)).fetchone()
        if watermark and event_time <= watermark["event_time"]:
            if event_time == watermark["event_time"] and digest == watermark["hash"]:
                return "EXACT_RETRY"
            with self.db:
                self.increment("conflicted" if event_time == watermark["event_time"] else "late_source")
            return "CONFLICT" if event_time == watermark["event_time"] else "REJECTED_LATE"
        existing = self.db.execute("SELECT * FROM entries WHERE snapshot=? OR (asset=? AND event_time=?)", (snapshot, asset, event_time)).fetchone()
        if existing:
            if existing["hash"] == digest:
                return "EXACT_RETRY"
            # Preserve the original payload, quarantine the identity and visibly
            # reject the new value. No stale record is silently returned.
            with self.db:
                self.db.execute("UPDATE entries SET state='QUARANTINED',reason='LOCAL_SEMANTIC_CONFLICT' WHERE snapshot=?", (existing["snapshot"],))
                self.increment("conflicted")
            return "CONFLICT"
        encoded = serialize(payload)
        size = len(encoded.encode("utf-8"))
        count, used = self.usage()
        if count >= self.max_records or used + size > self.max_bytes:
            with self.db:
                self.increment("backpressure")
            raise SpoolFull("spool full; stop acquisition, do not drop old observations")
        with self.db:
            self.db.execute("INSERT INTO entries(snapshot,asset,event_time,hash,payload,size,state) VALUES(?,?,?,?,?,?,'PENDING')", (snapshot, asset, event_time, digest, encoded, size))
            self.increment("acquired")
        return "QUEUED"

    @synchronized
    def pending(self, limit=25, now=None):
        # One earliest observation per asset; do not let newer rows overtake a
        # pending or quarantined observation and become late at the backend.
        rows = self.db.execute("""SELECT e.* FROM entries e WHERE state='PENDING' AND next_attempt<=?
            AND NOT EXISTS(SELECT 1 FROM entries older WHERE older.asset=e.asset AND older.event_time<e.event_time)
            ORDER BY event_time,snapshot LIMIT ?""", (time.time() if now is None else now, limit))
        return [dict(row) for row in rows]

    @synchronized
    def attempt(self, snapshot):
        with self.db:
            self.db.execute("UPDATE entries SET attempts=attempts+1 WHERE snapshot=?", (snapshot,))

    @synchronized
    def outcome(self, snapshot, reason, *, puback=False, quarantine=False, retry_seconds=1):
        with self.db:
            self.db.execute("UPDATE entries SET reason=?,pubacks=pubacks+?,state=?,next_attempt=? WHERE snapshot=?",
                (reason[:128], int(puback), "QUARANTINED" if quarantine else "PENDING", time.time()+retry_seconds, snapshot))
            if quarantine:
                self.increment("conflicted")

    @synchronized
    def committed(self, snapshot):
        with self.db:
            row = self.db.execute("SELECT * FROM entries WHERE snapshot=?", (snapshot,)).fetchone()
            if row is None:
                return
            self.db.execute("INSERT INTO watermarks VALUES(?,?,?) ON CONFLICT(asset) DO UPDATE SET event_time=excluded.event_time,hash=excluded.hash", (row["asset"],row["event_time"],row["hash"]))
            self.db.execute("DELETE FROM entries WHERE snapshot=?", (snapshot,))
            self.increment("committed")

    @synchronized
    def can_acquire(self, reserve_bytes=8192):
        count, used = self.usage()
        return count < self.max_records and used + reserve_bytes <= self.max_bytes

    @synchronized
    def close(self):
        self.db.close()
        self.owner.close()
