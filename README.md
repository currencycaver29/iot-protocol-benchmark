# MQTT vs CoAP vs HTTP for IoT messaging under poor networks (JSON vs CBOR)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23885253.svg)](https://doi.org/10.5281/zenodo.23885253)

**Paper:** *MQTT, CoAP and HTTP Under Constrained Networks: A Reproducible Benchmark with JSON and CBOR Encodings*. Divij Karanam, 2026. Preprint on Zenodo: https://doi.org/10.5281/zenodo.23885253 ([PDF in this repo](paper/main.pdf))

<details><summary>Cite</summary>

```bibtex
@misc{karanam2026iot,
  author    = {Karanam, Divij},
  title     = {MQTT, CoAP and HTTP Under Constrained Networks: A Reproducible Benchmark with JSON and CBOR Encodings},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.23885253},
  url       = {https://doi.org/10.5281/zenodo.23885253}
}
```
</details>

Simulated sensor nodes send readings to a local server over each protocol.
The network is degraded on purpose to mimic 4G, 3G, 2G and lossy links, and the
scripts record latency, delivery rate, bytes on the wire, and server CPU and memory.

## Run it

```
bash setup.sh                       # once
source .venv/bin/activate
python run_all.py baseline          # quick check (no root needed)
python run_all.py                   # everything (needs sudo for tc/iptables)
python analyze.py                   # charts -> results/charts/, table -> results/summary_table.md
```

`run_all.py` appends to `results/summary.csv`. Delete it before a fresh full run.

## Files

| File | What it does |
|---|---|
| `config.py` | All settings: message count, repetitions, network profiles, emulator backend |
| `payload.py` | Fake sensor reading + JSON/CBOR encoding |
| `client.py` | The "sensor node": sends N messages, records round-trip time to acknowledgment |
| `servers/` | HTTP (Flask on waitress), CoAP (aiocoap), MQTT (Mosquitto broker + paho subscriber). Each logs one-way latency per message |
| `emulator.py` | Userspace network emulator (delay, jitter, loss, rate) on Linux NFQUEUE, used when the kernel has no `netem` |
| `netem.sh` | Manual helper for `tc netem` |
| `run_all.py` | Runs every profile × protocol × encoding × repetition and collects the metrics |
| `analyze.py` | Charts + summary table |

## How each metric is measured

- **One-way latency**: the sender puts `time.time()` in the message, and the receiver subtracts it on arrival. Sender and receiver share one clock (same machine). For MQTT this spans client → broker → subscriber (two hops).
- **RTT**: the time from sending until the acknowledgment arrives: HTTP response, CoAP ACK (confirmable message), MQTT QoS 1 PUBACK from the broker.
- **Delivery ratio**: unique message IDs received ÷ sent.
- **Wire bytes per message**: change in loopback `tx_bytes` during the run ÷ messages. Includes headers, TCP ACKs and retransmissions, plus a 14-byte loopback pseudo-Ethernet header per packet. MQTT counts both hops through the broker.
- **Server CPU / memory**: psutil reads CPU time and peak RSS of the receiving processes (MQTT: broker + subscriber).

## Network emulation

`config.EMULATOR = "auto"` uses `tc netem` on `lo` when the kernel supports it, otherwise
`emulator.py`: iptables sends benchmark traffic (ports 8000, 1884, 5683) to NFQUEUE,
and a Python process holds each packet for the configured delay (normal jitter), drops
it with the configured probability, and enforces the rate limit on one shared FIFO
queue. Like netem on `lo`, the impairment applies to packets in **both directions**,
so round-trip delay ≈ 2× the configured delay. The `emu_zero` profile (emulator on, 0 ms)
measures the emulator's own overhead.

## Fairness fixes (found while testing and worth knowing)

The first version of this benchmark made HTTP look about 4× slower than it really is on slow links. Packet captures showed why:

1. **No keep-alive.** Flask's development server closes the TCP connection after every request, so each message paid a new TCP handshake. Fixed by serving the app with waitress and sending an explicit `Content-Length`.
2. **Split request.** `requests` writes the headers and the body separately. Nagle's algorithm then makes the body wait one round trip for the headers' ACK. Fixed by using `http.client` with `TCP_NODELAY` on a persistent connection.
3. **TCP autocorking.** When the emulator delays packets on the same host, Linux holds small writes until the previous packet leaves the host, which a real network would not do. `run_all.py` sets `net.ipv4.tcp_autocorking=0` while impairments are active and restores it afterwards.

For the same reason, `TCP_NODELAY` is enabled on every TCP endpoint: the HTTP client and server, both MQTT clients, and the broker (`set_tcp_nodelay true`).

## Limitations

- Single machine, loopback, emulated impairments: not real radios or real mobile networks.
- The profile values are illustrative approximations of typical 2G/3G/4G conditions, not measurements of a specific operator.
- Python implementations (aiocoap, paho, waitress) are not what an embedded device runs, so CPU numbers describe these libraries.
- Delivery is measured with each protocol's reliability features on (TCP retransmission; CoAP confirmable messages; MQTT QoS 1), so "loss" mostly shows up as extra latency rather than missing messages.

## Data notes (what was rerun and why)

- **Localhost traffic contamination.** In the environment used for the published results, the outbound HTTPS proxy runs on `127.0.0.1`, so unrelated downloads made during the benchmark were counted in loopback `tx_bytes`. Every run that overlapped such activity (all `lossy` runs and repetition 3 of `2g`) was discarded and repeated. The original rows are kept in `results/summary_original_with_contaminated_runs.csv`. **When you run this yourself, keep other localhost traffic (downloads through a local proxy, etc.) off during runs.**
- **MQTT subscription race.** The first version of `mqtt_subscriber.py` reported READY before the broker confirmed the subscription. Under 10% loss this let message #0 be published before the subscription existed, in one run. The subscriber now waits for SUBACK, and all six `lossy` MQTT runs were repeated. The superseded rows are in `results/superseded_lossy_mqtt_subscribe_race.csv`.
- **Unconfirmed CoAP messages.** In the `lossy` profile, 7 of 1,200 CoAP messages reached the server but were never acknowledged to the client within `ACK_TIMEOUT_S` (15 s). They count as delivered (`delivered`) but not acknowledged (`acked`).

## Environment of the published run

4 vCPU Intel Xeon @ 2.80 GHz, 15 GB RAM, Linux 6.18 (no netem, so the NFQUEUE emulator was used), Python 3.13,
paho-mqtt 2.1.0, aiocoap 0.4.17, Flask 3.1.3, waitress 3.0.2, cbor2 6.2.0, Mosquitto 2.0.18, NetfilterQueue 1.1.0.
