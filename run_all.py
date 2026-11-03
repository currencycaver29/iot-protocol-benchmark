"""Runs every combination of profile x protocol x encoding x repetition.

Usage:  python run_all.py              # all profiles in config.py (needs sudo for netem)
        python run_all.py baseline     # only the listed profiles
Output: results/summary.csv plus per-run raw files in results/raw/
"""
import os, sys, csv, time, subprocess, threading, socket
import psutil
import config

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "results", "raw")
SUMMARY = os.path.join(HERE, "results", "summary.csv")
PY = sys.executable


def lo_tx_bytes():
    with open("/sys/class/net/lo/statistics/tx_bytes") as f:
        return int(f.read())


SUDO = [] if os.geteuid() == 0 else ["sudo"]
_emu = {"proc": None, "rules": []}


def netem_available():
    subprocess.run(SUDO + ["tc", "qdisc", "del", "dev", "lo", "root"], stderr=subprocess.DEVNULL)
    ok = subprocess.run(SUDO + ["tc", "qdisc", "add", "dev", "lo", "root", "netem", "delay", "0ms"],
                        stderr=subprocess.DEVNULL).returncode == 0
    subprocess.run(SUDO + ["tc", "qdisc", "del", "dev", "lo", "root"], stderr=subprocess.DEVNULL)
    return ok


BACKEND = config.EMULATOR if config.EMULATOR != "auto" else ("netem" if netem_available() else "nfqueue")


def set_autocork(value):
    """Linux TCP autocorking holds small writes while an earlier packet is still
    queued on this host. An emulator that delays packets ON the host (netem or
    NFQUEUE) triggers it, which a real network would not, so it is switched off
    while impairments are active."""
    subprocess.run(SUDO + ["sysctl", "-q", "-w", f"net.ipv4.tcp_autocorking={value}"], check=False)


def impair(rule):
    """Apply a network profile (rule=None clears it) with tc netem or the NFQUEUE emulator."""
    set_autocork(1 if not rule else 0)
    # clear whatever is active
    subprocess.run(SUDO + ["tc", "qdisc", "del", "dev", "lo", "root"], stderr=subprocess.DEVNULL)
    for r in _emu["rules"]:
        subprocess.run(SUDO + ["iptables", "-D"] + r, stderr=subprocess.DEVNULL)
    _emu["rules"] = []
    if _emu["proc"]:
        _emu["proc"].terminate(); _emu["proc"].wait(timeout=10); _emu["proc"] = None
    if not rule:
        return
    if BACKEND == "netem":
        subprocess.run(SUDO + ["tc", "qdisc", "add", "dev", "lo", "root", "netem", *rule.split()], check=True)
        return
    _emu["proc"] = subprocess.Popen(SUDO + [PY, os.path.join(HERE, "emulator.py"), rule],
                                    stdout=subprocess.PIPE, text=True)
    _emu["proc"].stdout.readline()          # "EMULATOR READY"
    tcp_ports = f"{config.HTTP_PORT},{config.MQTT_PORT}"
    _emu["rules"] = [
        ["OUTPUT", "-o", "lo", "-p", "tcp", "-m", "multiport", "--ports", tcp_ports,
         "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"],
        ["OUTPUT", "-o", "lo", "-p", "udp", "--sport", str(config.COAP_PORT),
         "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"],
        ["OUTPUT", "-o", "lo", "-p", "udp", "--dport", str(config.COAP_PORT),
         "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"],
    ]
    for r in _emu["rules"]:
        subprocess.run(SUDO + ["iptables", "-I"] + r, check=True)


def wait_port(port, udp=False, timeout=20):
    if udp:                       # can't probe UDP cheaply; give the server a moment
        time.sleep(1.5); return
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), 1).close(); return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"server on port {port} did not start")


def port_busy(port, udp=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM if udp else socket.SOCK_STREAM)
    if not udp:   # ignore TIME_WAIT leftovers; still fails if something is LISTENING
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port)); return False
    except OSError:
        return True
    finally:
        s.close()


def start_servers(proto, log):
    port = {"http": config.HTTP_PORT, "coap": config.COAP_PORT, "mqtt": config.MQTT_PORT}[proto]
    if port_busy(port, udp=(proto == "coap")):
        raise RuntimeError(f"port {port} is already in use - stop the old server first")
    sd = os.path.join(HERE, "servers")
    if proto == "http":
        procs = [subprocess.Popen([PY, "http_server.py", log], cwd=sd)]
        wait_port(config.HTTP_PORT)
    elif proto == "coap":
        procs = [subprocess.Popen([PY, "coap_server.py", log], cwd=sd)]
        wait_port(config.COAP_PORT, udp=True)
    else:
        conf = os.path.join(RAW, "mosquitto.conf")
        with open(conf, "w") as f:   # TCP_NODELAY on, same as the HTTP and MQTT clients
            f.write(f"listener {config.MQTT_PORT} 127.0.0.1\nallow_anonymous true\nset_tcp_nodelay true\n")
        broker = subprocess.Popen(["mosquitto", "-c", conf],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_port(config.MQTT_PORT)
        sub = subprocess.Popen([PY, "mqtt_subscriber.py", log], cwd=sd, stdout=subprocess.PIPE, text=True)
        sub.stdout.readline()     # waits for "READY" (subscribed)
        procs = [broker, sub]
    time.sleep(0.3)
    if any(p.poll() is not None for p in procs):
        raise RuntimeError(f"{proto} server exited during startup")
    return procs


class ResourceMonitor(threading.Thread):
    """Samples server CPU time and peak memory while a run is going."""
    def __init__(self, procs):
        super().__init__(daemon=True)
        self.ps = [psutil.Process(p.pid) for p in procs]
        self.cpu0 = self._cpu()
        self.peak_rss = 0
        self.running = True

    def _cpu(self):
        return sum(p.cpu_times().user + p.cpu_times().system for p in self.ps)

    def run(self):
        while self.running:
            self.peak_rss = max(self.peak_rss, sum(p.memory_info().rss for p in self.ps))
            time.sleep(0.1)

    def stop(self):
        self.running = False
        return self._cpu() - self.cpu0, self.peak_rss


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def median(xs):
    xs = sorted(xs)
    if not xs: return ""
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))] if xs else ""


def one_run(profile, proto, enc, rep):
    tag = f"{profile}_{proto}_{enc}_r{rep}"
    srv_log, cli_log = os.path.join(RAW, f"{tag}_server.csv"), os.path.join(RAW, f"{tag}_client.csv")
    procs = start_servers(proto, srv_log)
    try:
        mon = ResourceMonitor(procs); mon.start()
        b0, t0 = lo_tx_bytes(), time.time()
        subprocess.run([PY, "client.py", proto, enc, cli_log], cwd=HERE, check=True)
        time.sleep(2)                               # let late packets arrive
        wire = lo_tx_bytes() - b0
        cpu_s, rss = mon.stop()
        duration = time.time() - t0
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=10)

    cli, srv = read_csv(cli_log), read_csv(srv_log)
    n = len(cli)
    rtts = [float(r["rtt_ms"]) for r in cli if r["rtt_ms"]]
    ows = [float(r["one_way_ms"]) for r in srv]
    delivered = len({r["id"] for r in srv})
    return {
        "profile": profile, "protocol": proto, "encoding": enc, "rep": rep,
        "sent": n, "acked": len(rtts), "delivered": delivered,
        "delivery_ratio": round(delivered / n, 4),
        "duplicates": len(srv) - delivered,
        "payload_bytes": cli[0]["payload_bytes"],
        "wire_bytes_per_msg": round(wire / n, 1),
        "oneway_median_ms": round(median(ows), 2) if ows else "",
        "oneway_p95_ms": round(pct(ows, 95), 2) if ows else "",
        "rtt_median_ms": round(median(rtts), 2) if rtts else "",
        "rtt_p95_ms": round(pct(rtts, 95), 2) if rtts else "",
        "server_cpu_ms_per_msg": round(cpu_s * 1000 / n, 3),
        "server_peak_rss_mb": round(rss / 2**20, 1),
        "duration_s": round(duration, 1),
        "emulator": BACKEND if config.PROFILES[profile] else "none",
    }


def main():
    args = sys.argv[1:]
    reps = list(range(1, config.REPETITIONS + 1))
    if "--reps" in args:                     # e.g. python run_all.py 2g --reps 3
        i = args.index("--reps")
        reps = [int(x) for x in args[i + 1].split(",")]
        args = args[:i] + args[i + 2:]
    protocols = config.PROTOCOLS
    if "--protocols" in args:                # e.g. python run_all.py lossy --protocols mqtt
        i = args.index("--protocols")
        protocols = args[i + 1].split(",")
        args = args[:i] + args[i + 2:]
    profiles = args or list(config.PROFILES)
    print(f"Network emulation backend: {BACKEND}")
    os.makedirs(RAW, exist_ok=True)
    new = not os.path.exists(SUMMARY)
    total = len(profiles) * len(protocols) * len(config.ENCODINGS) * len(reps)
    done = 0
    with open(SUMMARY, "a", newline="") as f:
        w = None
        for profile in profiles:
            rule = config.PROFILES[profile]
            print(f"\n=== profile: {profile}  ({rule or 'no impairment'}) ===")
            impair(rule)
            try:
                for rep in reps:
                    for proto in protocols:
                        for enc in config.ENCODINGS:
                            done += 1
                            print(f"[{done}/{total}] {proto:4s} {enc} rep {rep} ...", end=" ", flush=True)
                            row = one_run(profile, proto, enc, rep)
                            if w is None:
                                w = csv.DictWriter(f, fieldnames=list(row))
                                if new: w.writeheader()
                            w.writerow(row); f.flush()
                            print(f"delivered {row['delivery_ratio']:.0%}, "
                                  f"median one-way {row['oneway_median_ms']} ms, "
                                  f"{row['wire_bytes_per_msg']} B/msg on wire")
            finally:
                impair(None)
    print(f"\nDone. Results in {SUMMARY}. Next: python analyze.py")


if __name__ == "__main__":
    main()
