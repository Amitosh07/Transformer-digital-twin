import cProfile,io,json,pstats,time
from datetime import timedelta,datetime
from app.db.session import SessionLocal
from app.schemas.transformer import TransformerOut
from app.services.query_service import require_transformer
from app.services.analytics_resources import runtime_transformer
from app.repositories.processing_repo import checkpoint
from ml.pipeline import PipelineSession
from ml.pipeline.identity import payload_hash
from ml.pipeline.session import decode
asset='H06-SIM-05'
with SessionLocal() as db:
 t=time.perf_counter();cp=checkpoint(db,asset);tf=runtime_transformer(TransformerOut.model_validate(require_transformer(db,asset)));sql_seconds=time.perf_counter()-t
record=decode(cp['state']['history']['payload'])['records'][-1].copy()
record['timestamp']=(datetime.fromisoformat(cp['committed_event_time'].replace('Z','+00:00'))+timedelta(seconds=5)).isoformat()
record['acquisition']=dict(record['acquisition']);record['acquisition']['snapshot_id']=None;record['acquisition']['snapshot_id']=payload_hash(record)
s=PipelineSession();times={};pr=cProfile.Profile();pr.enable()
for name,call in [('import',lambda:s.import_checkpoint(cp,tf)),('export',lambda:s.export_checkpoint(asset)),('prepare',lambda:s.prepare(tf,record))]:
 t=time.perf_counter();v=call();times[name]=time.perf_counter()-t
 if name=='prepare':s.discard(v)
pr.disable();output=io.StringIO();pstats.Stats(pr,stream=output).sort_stats('cumulative').print_stats(16)
print(json.dumps(dict(asset=asset,sql_read_seconds=sql_seconds,checkpoint_bytes=len(json.dumps(cp)),history_rows=len(decode(cp['state']['history']['payload'])['records']),timings=times,profile=output.getvalue(),read_only=True)))
