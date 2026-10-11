"""Correlate independent FC04, bridge decoding, real receipt, SQL and APIs."""
import argparse,json,time,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
import psycopg
from demo_probe_modbus import probe
from demo_runtime import request,ROOT
if __name__=='__main__':
    import demo_runtime
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url',default='http://127.0.0.1:8001')
    parser.add_argument('--database-url',default='host=127.0.0.1 port=55433 user=h06_test dbname=h06_demo')
    parser.add_argument('--evidence-directory',type=Path,default=ROOT/'docs/hackathon_readiness/execution/evidence/h06')
    args=parser.parse_args();demo_runtime.BASE=args.api_url.rstrip('/')
    args.evidence_directory.mkdir(parents=True,exist_ok=True)
    attempts=[]
    for attempt in range(5):
        record=probe('127.0.0.1',1502,'H06-SIM-05',1)
        snapshot=record['acquisition']['snapshot_id']
        attempts.append(dict(asset=record['transformer_id'],snapshot=snapshot,
                             timestamp=record['timestamp'],sequence=record['acquisition']['sequence'],
                             observed_at=datetime.now(timezone.utc).isoformat(),receipt=None))
        (args.evidence_directory/'trace-attempts.json').write_text(json.dumps(attempts,indent=2))
        receipt=None
        for _ in range(10):
            try:receipt=request('/api/v1/ingestion/receipts/'+snapshot);break
            except OSError:time.sleep(1)
        attempts[-1]['receipt']=receipt
        (args.evidence_directory/'trace-attempts.json').write_text(json.dumps(attempts,indent=2))
        if receipt and receipt['receipt_status']=='COMMITTED':break
    assert receipt and receipt['payload_hash']==snapshot
    with psycopg.connect(args.database_url) as connection:
        sql=connection.execute('SELECT t.transformer_id,t.timestamp,t.payload_hash,t.active_power_total,t.acquisition,a.timestamp,a.health_index,a.rul,a.fault_risk,a.prediction_confidence FROM telemetry t JOIN analytics a ON a.telemetry_id=t.id WHERE t.payload_hash=%s',(snapshot,)).fetchone()
        assert sql and sql[2]==snapshot and sql[3]==record['active_power_total']
        assert sql[4]['sequence']==record['acquisition']['sequence'] and sql[4]['map_version']=='fictional-lv-v1'
        assert sql[5]==sql[1] and sql[7]['rul_value'] is not None and sql[8] is None and sql[9] is None
        from datetime import datetime,timedelta
        start=datetime.fromisoformat(record['timestamp']);query=urllib.parse.urlencode({'from':start.isoformat(),'to':(start+timedelta(seconds=1)).isoformat(),'limit':5})
        telemetry=request('/api/v1/transformers/H06-SIM-05/telemetry?'+query)['items'][0]
        analytics=request('/api/v1/transformers/H06-SIM-05/analytics?'+query)['items'][0]
        assert telemetry['active_power_total']==record['active_power_total'] and telemetry['acquisition']['snapshot_id']==snapshot
        assert analytics['rul']['rul_value']==sql[7]['rul_value']
    data=dict(probe=record,receipt=receipt,sql={'asset':sql[0],'event_time':sql[1].isoformat(),'payload_hash':sql[2],'active_power_total':sql[3],'analytics_time':sql[5].isoformat(),'health_index':sql[6],'rul':sql[7],'fault_risk':sql[8],'prediction_confidence':sql[9]},telemetry_api=telemetry,analytics_api=analytics)
    directory=args.evidence_directory;directory.mkdir(parents=True,exist_ok=True)
    (directory/'modbus-sql-trace.json').write_text(json.dumps(data,indent=2))
    print(json.dumps({'asset':sql[0],'timestamp':record['timestamp'],'sequence':record['acquisition']['sequence'],'snapshot':snapshot,'power_kw':record['active_power_total'],'rul_hours':sql[7]['rul_value'],'receipt':'COMMITTED'}))
