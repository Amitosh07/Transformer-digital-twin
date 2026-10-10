"""Bounded, process-local attempt counters, separate from durable receipts."""
from threading import Lock

_lock = Lock()
_counts = dict.fromkeys(('received', 'validated', 'committed', 'exact_retries',
                        'conflicted', 'failed', 'late', 'ml_unavailable'), 0)


def increment(name, count=1):
    with _lock:
        _counts[name] += count


def snapshot():
    with _lock:
        return {'scope': 'PROCESS_LOCAL_VALIDATED_RECORD_ATTEMPTS', **_counts}
