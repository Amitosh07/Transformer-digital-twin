"""Independent FC04 probe and bridge decoder correlation; no writes."""
import argparse,json
from pymodbus.client import ModbusTcpClient
from simulator.register_map import load_map,decode
from simulator.modbus_bridge import SnapshotPoller

def probe(host,port,asset,unit):
    client=ModbusTcpClient(host,port=port,timeout=3,retries=0)
    assert client.connect(), 'FC04 connection failed'
    try:
        for _ in range(5):
            before=client.read_input_registers(2,count=2,slave=unit)
            words=[]
            for offset in range(0,load_map()['register_count'],100):
                response=client.read_input_registers(offset,count=min(100,load_map()['register_count']-offset),slave=unit)
                assert not response.isError(),str(response)
                words.extend(response.registers)
            after=client.read_input_registers(2,count=2,slave=unit)
            if before.registers!=after.registers:continue
            independent=decode(words,transformer_id=asset,unit_id=unit,gateway_id='H06-DEMO-GW')
            poller=SnapshotPoller(dict(host=host,port=port,unit_id=unit,transformer_id=asset),'H06-DEMO-GW')
            try:bridge=poller.poll()
            finally:poller.close()
            if bridge.acquisition['sequence']!=independent.acquisition['sequence']:continue
            assert independent.model_dump(mode='json')==bridge.model_dump(mode='json')
            return independent.model_dump(mode='json')
        raise RuntimeError('Snapshot advanced during bounded independent probe; retry')
    finally:client.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=1502);p.add_argument('--asset',default='H06-SIM-05');p.add_argument('--unit',type=int,default=1)
    a=p.parse_args();print(json.dumps(probe(a.host,a.port,a.asset,a.unit)))
