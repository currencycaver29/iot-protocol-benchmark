"""Shared receive logger: writes one CSV line per message the server receives."""
import csv, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from payload import decode


class Sink:
    def __init__(self, path):
        self.f = open(path, "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(["id", "encoding", "payload_bytes", "one_way_ms"])
        self.f.flush()

    def record(self, data: bytes, encoding: str):
        now = time.time()
        r = decode(data, encoding)
        self.w.writerow([r["id"], encoding, len(data), round((now - r["ts"]) * 1000, 3)])
        self.f.flush()
