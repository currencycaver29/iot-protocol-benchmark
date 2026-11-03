"""Fills main_template.tex with numbers from results/summary.csv -> main.tex."""
import json, os, runpy
import pandas as pd
H = os.path.dirname(os.path.abspath(__file__))
num = runpy.run_path(os.path.join(H, "..", "article", "fill_article.py"))["num"]
d = pd.read_csv(os.path.join(H, "..", "results", "summary.csv"))
m = d.groupby(["profile", "protocol", "encoding"]).mean(numeric_only=True)
PL = {"baseline": "Baseline", "4g": "4G-like", "3g": "3G-like", "2g": "2G-like", "lossy": "Lossy"}
LAB = {"http": "HTTP", "mqtt": "MQTT", "coap": "CoAP"}
rows = []
for p in ["baseline", "4g", "3g", "2g", "lossy"]:
    for i, pr in enumerate(["coap", "http", "mqtt"]):
        r = m.loc[(p, pr, "json")]
        f = lambda v: f"{v:,.1f}" if v < 100 else f"{v:,.0f}"
        rows.append(f"{PL[p] if i == 0 else ''} & {LAB[pr]} & {f(r.oneway_median_ms)} & {f(r.oneway_p95_ms)} & {f(r.rtt_median_ms)} & {r.wire_bytes_per_msg:.0f} \\\\")
    if p != "lossy": rows.append("\\addlinespace[2pt]")
author = json.load(open(f"{H}/author.json")) if os.path.exists(f"{H}/author.json") else {}
fill = {**num, "TABLE_RESULTS": "\n".join(rows), "AUTHOR": author.get("name", "Author Name"),
        "EMAIL_LINE": f"\\\\ {author['email']}" if author.get("email") else "",
        "REPO_URL": (f"at \\url{{{author['repo']}}}" if author.get("repo") else
                     "in the Zenodo record of this preprint")}
t = open(f"{H}/main_template.tex").read()
for k, v in fill.items(): t = t.replace(f"<<{k}>>", str(v).replace(",", "{,}") if k.startswith("l_") or k.endswith("_b") else str(v))
assert "<<" not in t, [l for l in t.splitlines() if "<<" in l][:3]
open(f"{H}/main.tex", "w").write(t); print("main.tex written")
