"""Userspace network emulator (delay, jitter, loss, rate) built on Linux NFQUEUE.

Use this when your kernel has no `netem` (some VMs/containers). It mimics
`tc netem` on loopback: one shared FIFO queue for all benchmark traffic, both
directions. Packets are never reordered.

Usage (as root):  python emulator.py "delay 100ms 20ms distribution normal loss 1.5% rate 1mbit"
run_all.py starts/stops it automatically and adds the iptables rules.
"""
import sys, time, random, heapq, select, signal
from netfilterqueue import NetfilterQueue

QUEUE_NUM = 0


def parse(rule):
    t = rule.split()
    delay = jitter = loss = rate = 0.0
    i = 0
    while i < len(t):
        if t[i] == "delay":
            delay = float(t[i + 1].rstrip("ms")) / 1000; i += 2
            if i < len(t) and t[i].endswith("ms"):
                jitter = float(t[i].rstrip("ms")) / 1000; i += 1
        elif t[i] == "loss":
            loss = float(t[i + 1].rstrip("%")) / 100; i += 2
        elif t[i] == "rate":
            v = t[i + 1]
            mult = 1e6 if v.endswith("mbit") else 1e3 if v.endswith("kbit") else 1
            rate = float(v.rstrip("mkbit")) * mult; i += 2
        elif t[i] == "distribution":
            i += 2                     # jitter is always normal-distributed here
        else:
            raise ValueError(f"unknown token {t[i]}")
    return delay, jitter, loss, rate


def main():
    delay, jitter, loss, rate = parse(sys.argv[1])
    heap, seq = [], 0
    state = {"link_free": 0.0, "last_release": 0.0}

    def on_packet(pkt):
        nonlocal seq
        if loss and random.random() < loss:
            pkt.drop(); return
        now = time.monotonic()
        release = now + (max(0.0, random.gauss(delay, jitter)) if jitter else delay)
        if rate:                                    # serialization on a shared link
            start = max(release, state["link_free"])
            state["link_free"] = start + pkt.get_payload_len() * 8 / rate
            release = state["link_free"]
        release = max(release, state["last_release"])   # keep FIFO order
        state["last_release"] = release
        pkt.retain()
        heapq.heappush(heap, (release, seq, pkt)); seq += 1

    nfq = NetfilterQueue()
    nfq.bind(QUEUE_NUM, on_packet, max_len=20000)
    fd = nfq.get_fd()
    running = [True]
    signal.signal(signal.SIGTERM, lambda *a: running.__setitem__(0, False))
    print("EMULATOR READY", flush=True)
    try:
        while running[0]:
            timeout = max(0.0, heap[0][0] - time.monotonic()) if heap else 0.2
            if select.select([fd], [], [], timeout)[0]:
                nfq.run(block=False)
            now = time.monotonic()
            while heap and heap[0][0] <= now:
                heapq.heappop(heap)[2].accept()
    finally:
        for _, _, p in heap:
            p.accept()
        nfq.unbind()


if __name__ == "__main__":
    main()
