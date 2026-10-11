"""Read-only assertions and aggregate measurements from a captured H07 run."""
import json
import sys
from pathlib import Path


def main(directory):
    p = Path(directory)
    final = json.loads((p / 'final-isolation.json').read_text())
    summary = json.loads((p / 'summary.json').read_text())
    rows = summary['per_asset']
    assert len(rows) == 25 and len({r['asset'] for r in rows}) == 25
    assert all(r['accepted_total_post_run'] == r['analytics_total_post_run'] == r['unique_sequences'] for r in rows)
    assert rows[0]['trip_rows'] > 0 and all(r['trip_rows'] == 0 for r in rows[1:])
    hashes = set()
    states = []
    for i, (asset, entry) in enumerate(final.items()):
        checkpoint = entry['checkpoint']
        assert checkpoint['transformer_id'] == asset
        for record in entry['telemetry_rows']:
            assert record['hash'] == record['acquisition']['snapshot_id']
            assert record['hash'] not in hashes
            assert record['analytics_timestamp'] == record['timestamp']
            hashes.add(record['hash'])
        state = checkpoint['state']
        assert state['maintenance_persistence']['payload']['trip_latched'] == (i == 0)
        assert state['synthetic_degradation']['payload']['transformer_id'] == asset
        states.append(state['synthetic_degradation'])
    assert len({json.dumps(s, sort_keys=True) for s in states}) == 3
    for mode in ('switch', 'outage', 'replay'):
        assert json.loads((p / f'judging-{mode}.json').read_text())['passed']
    logs = []
    for line in (p / 'transformer-h06-20261009-h07-bridge-dfb1b1-logs.txt').read_text().splitlines():
        try:
            item = json.loads(line)
            if 'spool_usage' in item:
                logs.append(item)
        except json.JSONDecodeError:
            pass
    memory = {}
    for line in (p / 'measurements.jsonl').read_text().splitlines():
        sample = json.loads(line)
        for row in sample.get('containers', '').splitlines():
            item = json.loads(row)
            memory.setdefault(item['Name'], []).append(item['MemUsage'])
    result = dict(
        assertion_status='PASS', isolated_hashes=len(hashes),
        committed_in_measured_window=sum(r['committed_in_window'] for r in rows),
        accepted_post_run=sum(r['accepted_total_post_run'] for r in rows),
        observed_spool_peak=max(x['spool_usage'][0] for x in logs),
        last_bridge_log=logs[-1], memory_samples=memory,
        limitations=['Assertions verify captured evidence, not a completed 30-minute soak.',
                     'Receipt committed_at is the persisted timestamp, not independently measured SQL commit wall time.'])
    (p / 'evidence-assertions.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in ('last_bridge_log', 'memory_samples')}))


if __name__ == '__main__':
    main(sys.argv[1])
