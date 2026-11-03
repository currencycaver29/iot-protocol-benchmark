"""Fake sensor readings plus JSON / CBOR encoding."""
import json, random, time
import cbor2

CONTENT_TYPES = {"json": "application/json", "cbor": "application/cbor"}
COAP_FORMATS = {"json": 50, "cbor": 60}   # CoAP Content-Format numbers (RFC 7252 / 7049)


def make_reading(msg_id: int, node_id: str = "node-1") -> dict:
    return {
        "id": msg_id,
        "node": node_id,
        "ts": time.time(),                       # send time, used for one-way latency
        "temp_c": round(random.uniform(20, 40), 2),
        "humidity": round(random.uniform(30, 90), 2),
        "pm25": random.randint(5, 300),
        "battery_v": round(random.uniform(3.3, 4.2), 3),
    }


def encode(reading: dict, encoding: str) -> bytes:
    if encoding == "json":
        return json.dumps(reading, separators=(",", ":")).encode()
    if encoding == "cbor":
        return cbor2.dumps(reading)
    raise ValueError(encoding)


def decode(data: bytes, encoding: str) -> dict:
    return json.loads(data) if encoding == "json" else cbor2.loads(data)
