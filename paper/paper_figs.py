"""IEEE-sized vector figures for the IoT paper, from results/summary.csv."""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); O = os.path.join(H, "figs")
d = pd.read_csv(os.path.join(H, "..", "results", "summary.csv"))
m = d.groupby(["profile", "protocol", "encoding"]).mean(numeric_only=True)
s = d.groupby(["profile", "protocol", "encoding"]).std(numeric_only=True)
COL = {"http": "#2a78d6", "mqtt": "#eb6834", "coap": "#1baf7a"}; LAB = {"http": "HTTP", "mqtt": "MQTT", "coap": "CoAP"}
PROTOS = ["http", "mqtt", "coap"]; PROF = ["baseline", "4g", "3g", "2g", "lossy"]
PLAB = {"baseline": "Baseline", "4g": "4G-like", "3g": "3G-like", "2g": "2G-like", "lossy": "Lossy"}
INK2 = "#52514e"
plt.rcParams.update({"font.size": 7, "font.family": "serif", "axes.edgecolor": "#8a8984", "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})

fig, axes = plt.subplots(1, 2, figsize=(7.16, 2.3))
for ax, col, title in [(axes[0], "oneway_median_ms", "(a) Median one-way latency"), (axes[1], "oneway_p95_ms", "(b) 95th-percentile one-way latency")]:
    w = 0.27
    for k, p in enumerate(PROTOS):
        vals = [m.loc[(pr, p, "json"), col] for pr in PROF]
        err = [s.loc[(pr, p, "json"), col] for pr in PROF]
        xs = np.arange(len(PROF)) + (k - 1) * w
        ax.bar(xs, vals, w * 0.9, color=COL[p], label=LAB[p], yerr=err, error_kw=dict(lw=0.6, capsize=1.2, ecolor=INK2))
        for x, v in zip(xs, vals):
            ax.text(x, v * 1.25, f"{v:.0f}" if v >= 10 else f"{v:.1f}", ha="center", fontsize=4.8, color=INK2, rotation=90)
    ax.set_yscale("log"); ax.set_ylim(0.5, 20000); ax.set_xticks(range(len(PROF)), [PLAB[p] for p in PROF])
    ax.set_ylabel("ms (log scale)"); ax.set_title(title, loc="left", fontsize=7.5)
    ax.grid(axis="y", color="#e6e5e0", lw=0.5); ax.set_axisbelow(True)
axes[0].legend(frameon=False, ncols=3, fontsize=6, loc="upper left")
fig.tight_layout(); fig.savefig(f"{O}/fig_latency.pdf"); plt.close(fig)

fig, ax = plt.subplots(figsize=(3.5, 1.9))
w = 0.36
for k, enc in enumerate(["json", "cbor"]):
    vals = [m.loc[("baseline", p, enc), "wire_bytes_per_msg"] for p in PROTOS]
    xs = np.arange(3) + (k - 0.5) * w
    bars = ax.bar(xs, vals, w * 0.9, color=["#52514e", "#a9a8a2"][k], label=enc.upper())
    for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v + 12, f"{v:.0f}", ha="center", fontsize=5.5, color=INK2)
ax.set_xticks(range(3), [LAB[p] for p in PROTOS]); ax.set_ylabel("bytes on the wire per message")
ax.margins(y=0.15); ax.grid(axis="y", color="#e6e5e0", lw=0.5); ax.set_axisbelow(True); ax.legend(frameon=False, fontsize=6)
fig.tight_layout(); fig.savefig(f"{O}/fig_bytes.pdf"); plt.close(fig)
print(sorted(os.listdir(O)))
