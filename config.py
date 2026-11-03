"""Experiment settings. Edit these to change what gets run."""

# Ports (local only)
HTTP_PORT = 8000
COAP_PORT = 5683
MQTT_PORT = 1884          # own broker instance, avoids clashing with a system mosquitto

PROTOCOLS = ["http", "coap", "mqtt"]
ENCODINGS = ["json", "cbor"]

MESSAGES_PER_RUN = 200   # messages each simulated sensor sends per run
SEND_INTERVAL_S = 0.05    # pause between messages
ACK_TIMEOUT_S = 15        # give up on a message after this long
REPETITIONS = 3           # repeated runs per combination (report mean ± std)

# Network profiles applied to the loopback interface with `tc netem`.
# NOTE: netem on `lo` delays packets in BOTH directions, so round-trip delay
# is about 2x the delay below. Values are rough approximations of typical
# mobile links. If you cite them in a paper, cite a source for the numbers.
# "auto" = use tc netem if the kernel supports it, else the NFQUEUE emulator (emulator.py)
EMULATOR = "auto"

PROFILES = {
    "baseline": None,
    "emu_zero": "delay 0ms",   # calibration: emulator switched on but adding nothing
    "4g":    "delay 25ms 5ms distribution normal loss 0.5%",
    "3g":    "delay 100ms 20ms distribution normal loss 1.5% rate 1mbit",
    "2g":    "delay 250ms 50ms distribution normal loss 3% rate 100kbit",
    "lossy": "delay 10ms loss 10%",
}
