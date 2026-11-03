"""Simulated sensor node. Sends MESSAGES_PER_RUN readings and records the
acknowledged round-trip time for each one.

Usage: python client.py <http|coap|mqtt> <json|cbor> <out.csv>
"""
import os, sys, csv, time, asyncio
os.environ.setdefault("AIOCOAP_CLIENT_TRANSPORT", "simple6")   # works without IPv6
import config
from payload import make_reading, encode, CONTENT_TYPES, COAP_FORMATS


def send_http(enc, n):
    # http.client with one persistent connection (keep-alive) and TCP_NODELAY.
    # http.client sends headers + body in a single write, unlike `requests`,
    # which splits them and costs an extra round trip on slow links.
    import http.client, socket
    conn = http.client.HTTPConnection("127.0.0.1", config.HTTP_PORT, timeout=config.ACK_TIMEOUT_S)

    def connect():
        conn.connect()
        conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    connect()
    for i in range(n):
        body = encode(make_reading(i), enc)
        t0 = time.perf_counter()
        try:
            conn.request("POST", "/data", body=body, headers={"Content-Type": CONTENT_TYPES[enc]})
            r = conn.getresponse(); r.read()
            if r.status >= 300:
                raise RuntimeError(r.status)
            yield i, len(body), (time.perf_counter() - t0) * 1000, 1
        except Exception:
            conn.close()
            try: connect()
            except Exception: pass
            yield i, len(body), None, 0
        time.sleep(config.SEND_INTERVAL_S)
    conn.close()


def send_coap(enc, n):
    import aiocoap
    results = []

    async def run():
        ctx = await aiocoap.Context.create_client_context()
        uri = f"coap://127.0.0.1:{config.COAP_PORT}/data"
        for i in range(n):
            body = encode(make_reading(i), enc)
            msg = aiocoap.Message(code=aiocoap.POST, uri=uri, payload=body,
                                  content_format=COAP_FORMATS[enc])  # confirmable by default
            t0 = time.perf_counter()
            try:
                await asyncio.wait_for(ctx.request(msg).response, config.ACK_TIMEOUT_S)
                results.append((i, len(body), (time.perf_counter() - t0) * 1000, 1))
            except Exception:
                results.append((i, len(body), None, 0))
            await asyncio.sleep(config.SEND_INTERVAL_S)
        await ctx.shutdown()

    asyncio.run(run())
    yield from results


def send_mqtt(enc, n):
    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="node-1")
    c.connect("127.0.0.1", config.MQTT_PORT)
    import socket
    c.socket().setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    c.loop_start()
    topic = f"sensors/node-1/{enc}"
    for i in range(n):
        body = encode(make_reading(i), enc)
        t0 = time.perf_counter()
        info = c.publish(topic, body, qos=1)    # QoS 1 = wait for broker PUBACK
        try:
            info.wait_for_publish(timeout=config.ACK_TIMEOUT_S)
            ok = info.is_published()
        except Exception:
            ok = False
        yield i, len(body), ((time.perf_counter() - t0) * 1000 if ok else None), int(ok)
        time.sleep(config.SEND_INTERVAL_S)
    c.loop_stop()
    c.disconnect()


SENDERS = {"http": send_http, "coap": send_coap, "mqtt": send_mqtt}

if __name__ == "__main__":
    proto, enc, out = sys.argv[1:4]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "payload_bytes", "rtt_ms", "acked"])
        for row in SENDERS[proto](enc, config.MESSAGES_PER_RUN):
            w.writerow([row[0], row[1], "" if row[2] is None else round(row[2], 3), row[3]])
