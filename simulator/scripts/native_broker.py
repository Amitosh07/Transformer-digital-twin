"""Explicit native H06 loopback broker fallback (amqtt 0.11.3), no retained demo data."""
import asyncio
from amqtt.broker import Broker
async def main():
    broker=Broker({'listeners':{'default':{'type':'tcp','bind':'127.0.0.1:51885','max_connections':100}},'plugins':{'amqtt.plugins.authentication.AnonymousAuthPlugin':{'allow_anonymous':True}}})
    await broker.start()
    try:await asyncio.Event().wait()
    finally:await broker.shutdown()
if __name__=='__main__':asyncio.run(main())
