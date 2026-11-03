"""CoAP receiver (aiocoap). Usage: python coap_server.py <log.csv>"""
import os, sys, asyncio
# IPv4-friendly transport (the default needs IPv6, which some setups lack)
os.environ.setdefault("AIOCOAP_SERVER_TRANSPORT", "simplesocketserver")
import aiocoap, aiocoap.resource as resource
from sink import Sink
import config

sink = Sink(sys.argv[1])


class Data(resource.Resource):
    async def render_post(self, request):
        enc = "cbor" if request.opt.content_format == 60 else "json"
        sink.record(request.payload, enc)
        return aiocoap.Message(code=aiocoap.CHANGED)


async def main():
    root = resource.Site()
    root.add_resource(["data"], Data())
    await aiocoap.Context.create_server_context(root, bind=("127.0.0.1", config.COAP_PORT))
    await asyncio.get_running_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
