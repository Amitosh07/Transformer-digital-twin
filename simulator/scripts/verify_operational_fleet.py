"""Bounded real FC04 -> MQTT -> SQL receipt/API verification; no writes/reset.

Run with the established simulator/backend development dependencies installed.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import urllib.error
import psycopg
from simulator.modbus_bridge import SnapshotPoller

ROOT = Path(__file__).resolve().parents[2]


def verify_identities(args):
    """Run ONLY after stopping source and settling/stopping bridge delivery."""
    from ml.pipeline.identity import payload_hash
    saved = json.loads(args.evidence.read_text(encoding='utf-8'))
    asset = next(iter(saved['assets']))
    record = saved['assets'][asset][0]['modbus']
    ids = list(saved['assets'])
    def post(value):
        request = urllib.request.Request(args.api_url.rstrip('/')+'/api/v1/telemetry',
            data=json.dumps(value).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,json.load(exc)
    with psycopg.connect(args.database_url,autocommit=True) as db:
        def state():
            return db.execute('SELECT x.transformer_id,md5(x.checkpoint::text),'
                '(SELECT count(*) FROM telemetry t WHERE t.transformer_id=x.transformer_id),'
                '(SELECT count(*) FROM analytics a WHERE a.transformer_id=x.transformer_id),'
                '(SELECT count(*) FROM alerts a WHERE a.transformer_id=x.transformer_id),'
                '(SELECT count(*) FROM maintenance_records m WHERE m.transformer_id=x.transformer_id) '
                'FROM ml_checkpoints x WHERE transformer_id=ANY(%s) ORDER BY transformer_id',(ids,)).fetchall()
        before = state()
        exact = post(record)
        assert exact[0] == 200 and exact[1]['duplicate'] and exact[1]['ingestion_outcome'] == 'EXACT_RETRY'
        assert exact[1]['forward_state_advanced'] is False
        changed = copy.deepcopy(record)
        changed['oil_temp_trip'] = 1-record['oil_temp_trip']
        changed['acquisition']['snapshot_id'] = payload_hash(changed)
        conflict = post(changed)
        assert conflict[0] == 409, conflict
        after = state()
        assert before == after, 'Accepted effects/checkpoint changed; establish the documented quiescent barrier'
    output = args.evidence.with_name('retry.json')
    output.write_text(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(),asset=asset,
        snapshot=record['acquisition']['snapshot_id'],exact_retry=exact,changed_duplicate=conflict,
        before=before,after=after,accepted_effects_and_checkpoints_unchanged=True),indent=2,default=str),encoding='utf-8')
    print('PASS real SQL: exact retry 200 / EXACT_RETRY / no forward advance; changed contact 409; all ten accepted effects/checkpoints unchanged')


def verify(args):
    fleet = json.loads((ROOT/'simulator/config/operational-fleet.json').read_text())
    ids = [a['transformer_id'] for a in fleet['assets']]
    def guard():
        free = shutil.disk_usage(ROOT).free
        if free < args.minimum_free_gib * 1024**3:
            # Stop only new acquisition; retain bridge delivery and all data.
            subprocess.run(['docker','compose','-f','docker-compose.operational-existing.yml',
                '--profile','primary','stop','--timeout','10','modbus-simulator'], cwd=ROOT, check=True)
            raise RuntimeError('Disk guard stopped source generation; pending delivery remains preserved')
        return free
    def get(path):
        with urllib.request.urlopen(args.api_url.rstrip('/')+path, timeout=10) as r:
            return json.load(r)
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'disk_free_before':guard(), 'assets':{}}
    registry = get('/api/v1/transformers?limit=50')
    assert registry['total'] == 10 and [a['id'] for a in registry['items']] == ids
    result['registry'] = registry
    result['historical_registry_total'] = get('/api/v1/transformers?scope=all&limit=1')['total']
    with psycopg.connect(args.database_url) as db:
        for round_index in range(2):
            if round_index:
                time.sleep(6)
            snapshots = []
            for item in fleet['assets']:
                guard()
                poller = SnapshotPoller(dict(transformer_id=item['transformer_id'], unit_id=item['unit_id'],
                    host=args.modbus_host, port=args.modbus_port, expected_interval_seconds=5),'KA-BLR-SIM-GW')
                try: record = poller.poll().model_dump(mode='json')
                finally: poller.close()
                snapshots.append(record)
            for record in snapshots:
                guard()
                asset = record['transformer_id']; snapshot = record['acquisition']['snapshot_id']
                deadline = time.monotonic() + args.receipt_timeout
                while True:
                    guard()
                    try:
                        receipt = get('/api/v1/ingestion/receipts/'+snapshot)
                        break
                    except urllib.error.HTTPError as exc:
                        if exc.code != 404 or time.monotonic() >= deadline: raise
                    time.sleep(1)
                assert receipt['receipt_status'] == 'COMMITTED'
                assert receipt['payload_hash'] == receipt['accepted_payload_hash'] == snapshot
                assert receipt['transformer_id'] == asset
                counts = db.execute('SELECT count(*),count(a.id) FROM telemetry t LEFT JOIN analytics a ON a.telemetry_id=t.id WHERE t.transformer_id=%s AND t.payload_hash=%s', (asset,snapshot)).fetchone()
                assert counts == (1,1), counts
                latest = get('/api/v1/transformers/'+asset+'/latest')
                assert latest['telemetry']['transformer_id'] == latest['analytics']['transformer_id'] == asset
                assert latest['telemetry']['acquisition']['source_kind'] == 'SIMULATED'
                rows = result['assets'].setdefault(asset,[])
                if rows:
                    assert record['timestamp'] > rows[-1]['modbus']['timestamp']
                    assert record['current_l1'] != rows[-1]['modbus']['current_l1']
                rows.append(dict(modbus=record, receipt=receipt, telemetry_analytics_counts=counts, latest=latest))
        result['rul'] = {a:get('/api/v1/transformers/'+a+'/rul') for a in ids}
        result['energy'] = {a:get('/api/v1/transformers/'+a+'/energy?window=1h&anchor=latest') for a in ids}
        result['database_counts'] = db.execute('SELECT t.transformer_id,count(*),count(a.id),min(t.timestamp),max(t.timestamp) FROM telemetry t LEFT JOIN analytics a ON a.telemetry_id=t.id WHERE t.transformer_id=ANY(%s) GROUP BY t.transformer_id ORDER BY t.transformer_id',(ids,)).fetchall()
        result['checkpoints'] = db.execute('SELECT transformer_id,count(*) FROM ml_checkpoints WHERE transformer_id=ANY(%s) GROUP BY transformer_id',(ids,)).fetchall()
    result['disk_free_after'] = guard()
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'result':'PASS','assets':len(result['assets']),'correlated_snapshots':20,'evidence':str(args.evidence),'disk_free_after':result['disk_free_after']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url',default='http://127.0.0.1:8001')
    parser.add_argument('--modbus-host',default='127.0.0.1')
    parser.add_argument('--modbus-port',type=int,default=1502)
    parser.add_argument('--database-url',default='host=127.0.0.1 port=55433 user=transformer password=transformer dbname=transformer')
    parser.add_argument('--receipt-timeout',type=int,default=120)
    parser.add_argument('--minimum-free-gib',type=float,default=2.75)
    parser.add_argument('--evidence',type=Path,default=ROOT/'docs/hackathon_readiness/execution/evidence/operational-ten/live.json')
    parser.add_argument('--identity-test',action='store_true',help='Source and settled bridge must already be stopped; preserve all accepted data')
    args = parser.parse_args()
    (verify_identities if args.identity_test else verify)(args)
