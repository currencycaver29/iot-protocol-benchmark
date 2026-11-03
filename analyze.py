"""Turns results/summary.csv into charts and a Markdown table.
Usage: python analyze.py   -> results/charts/*.png and results/summary_table.md
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "charts")
COLORS = {"http": "#2a78d6", "mqtt": "#eb6834", "coap": "#1baf7a"}   # fixed per protocol
PROTOS = ["http", "mqtt", "coap"]
LABELS = {"http": "HTTP", "mqtt": "MQTT", "coap": "CoAP"}
PROFILE_ORDER = ["baseline", "4g", "3g", "2g", "lossy"]   # charts
TABLE_ORDER = ["baseline", "emu_zero", "4g", "3g", "2g", "lossy"]

plt.rcParams.update({
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e", "xtick.color": "#52514e",
    "ytick.color": "#52514e", "axes.grid": True, "axes.axisbelow": True,
    "grid.color": "#e6e5e0", "grid.linewidth": 0.8, "axes.grid.axis": "y",
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
})


def grouped_bar(df, metric, ylabel, title, fname, enc="json", fmt="{:.0f}"):
    d = df[df.encoding == enc]
    profiles = [p for p in PROFILE_ORDER if p in d.profile.unique()]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    width = 0.8 / len(PROTOS)
    for k, proto in enumerate(PROTOS):
        vals = [d[(d.profile == p) & (d.protocol == proto)][metric].mean() for p in profiles]
        xs = [i + (k - 1) * width for i in range(len(profiles))]
        bars = ax.bar(xs, vals, width * 0.92, color=COLORS[proto], label=LABELS[proto])
        for b, v in zip(bars, vals):
            if pd.notna(v):
                ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=7, color="#52514e",
                            xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(profiles)), profiles)
    ax.set_ylabel(ylabel); ax.set_title(title, loc="left", fontsize=11, pad=24)
    ax.margins(y=0.12)
    ax.legend(frameon=False, ncols=3, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.tight_layout(); fig.savefig(os.path.join(OUT, fname), dpi=200); plt.close(fig)


def main():
    df = pd.read_csv(os.path.join(RES, "summary.csv"))
    os.makedirs(OUT, exist_ok=True)
    df["delivery_pct"] = df.delivery_ratio * 100

    grouped_bar(df, "oneway_median_ms", "ms", "Median one-way latency (JSON)", "latency_median.png", fmt="{:.1f}")
    grouped_bar(df, "oneway_p95_ms", "ms", "95th-percentile one-way latency (JSON)", "latency_p95.png", fmt="{:.1f}")
    grouped_bar(df, "delivery_pct", "% delivered", "Messages delivered (JSON)", "delivery.png")
    grouped_bar(df, "wire_bytes_per_msg", "bytes / message", "Bytes on the wire per message (JSON)", "wire_bytes.png")
    grouped_bar(df, "server_cpu_ms_per_msg", "CPU ms / message", "Server CPU per message (JSON)", "server_cpu.png", fmt="{:.2f}")

    # JSON vs CBOR: wire bytes per protocol, baseline profile
    if {"json", "cbor"} <= set(df.encoding):
        b = df[df.profile == "baseline"] if "baseline" in set(df.profile) else df
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for k, enc in enumerate(["json", "cbor"]):
            vals = [b[(b.protocol == p) & (b.encoding == enc)].wire_bytes_per_msg.mean() for p in PROTOS]
            xs = [i + (k - 0.5) * 0.38 for i in range(len(PROTOS))]
            bars = ax.bar(xs, vals, 0.35, color=["#52514e", "#8a8984"][k], label=enc.upper())
            for bb, v in zip(bars, vals):
                ax.annotate(f"{v:.0f}", (bb.get_x() + bb.get_width() / 2, bb.get_height()),
                            ha="center", va="bottom", fontsize=7, color="#52514e",
                            xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(range(len(PROTOS)), [LABELS[p] for p in PROTOS])
        ax.set_ylabel("bytes / message"); ax.margins(y=0.12)
        ax.legend(frameon=False, ncols=2, loc="lower left", bbox_to_anchor=(0, 1.0))
        ax.set_title("JSON vs CBOR: bytes on the wire per message", loc="left", fontsize=11, pad=24)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "json_vs_cbor.png"), dpi=200); plt.close(fig)

    cols = ["delivery_pct", "oneway_median_ms", "oneway_p95_ms", "rtt_median_ms",
            "payload_bytes", "wire_bytes_per_msg", "server_cpu_ms_per_msg", "server_peak_rss_mb"]
    agg = df.groupby(["profile", "protocol", "encoding"])[cols].agg(["mean", "std"]).round(2)
    agg.columns = [f"{a}_{b}" for a, b in agg.columns]
    agg = agg.reset_index()
    agg["profile"] = pd.Categorical(agg.profile, [p for p in TABLE_ORDER if p in set(agg.profile)])
    agg = agg.sort_values(["profile", "protocol", "encoding"])
    agg.to_csv(os.path.join(RES, "summary_aggregated.csv"), index=False)
    with open(os.path.join(RES, "summary_table.md"), "w") as f:
        f.write(agg[["profile", "protocol", "encoding"] + [c + "_mean" for c in cols]].to_markdown(index=False))
    print(f"Charts in {OUT}\nTable in {os.path.join(RES, 'summary_table.md')}")


if __name__ == "__main__":
    main()
