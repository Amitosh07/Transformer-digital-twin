from concurrent.futures import ThreadPoolExecutor
from simulator.spool import DurableSpool


def test_cross_thread_counters_are_atomic_and_durable(tmp_path):
    spool = DurableSpool(tmp_path)
    def write(_):
        for _ in range(100):
            spool.record_counter('received')
            assert spool.usage() == (0, 0)
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(write, range(4)))
    assert spool.counters()['received'] == 400
    spool.close()
    reopened = DurableSpool(tmp_path)
    assert reopened.counters()['received'] == 400
    assert reopened.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    reopened.close()


def test_pending_receipt_poll_does_not_inherit_transport_backoff(tmp_path):
    import time
    from simulator.modbus_bridge import DeliveryWorker
    from simulator.generator import SyntheticGenerator
    from datetime import datetime, timezone
    from types import SimpleNamespace
    spool = DurableSpool(tmp_path)
    row = SyntheticGenerator().generate(datetime(2026,10,10,tzinfo=timezone.utc),1)[0]
    spool.enqueue(row)
    snapshot = spool.pending()[0]['snapshot']
    with spool.db:
        spool.db.execute('UPDATE entries SET attempts=15 WHERE snapshot=?', (snapshot,))
    worker = DeliveryWorker(spool, SimpleNamespace(publish_payload=lambda _: {'broker_acknowledged':True}),
        SimpleNamespace(outcome=lambda _: 'NOT_YET_COMMITTED'), backoff=1, max_backoff=30)
    before = time.time()
    worker.flush()
    entry = dict(spool.db.execute('SELECT * FROM entries WHERE snapshot=?',(snapshot,)).fetchone())
    assert before + 1 <= entry['next_attempt'] < time.time() + 1.1
    assert spool.counters().get('committed',0) == 0
    assert spool.usage()[0] == 1
    spool.close()
