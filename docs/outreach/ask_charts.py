"""The charts for DNA-Analyzer_Ask_MCP-LLM-feature_en.pdf, from measured data only:
  timeline.png   a research-agent run's tool calls over time (data/output/agent/runs/<run>.jsonl), showing overlap
  waterfall.png  a question's cost from a naive build down to the real one, measure by measure (ask_tokens.json)
  turns.png      where each turn's input tokens go in the example conversation (ask_example_turns.json)
    python docs/outreach/ask_charts.py [RUN_ID]"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RUN = sys.argv[1] if len(sys.argv) > 1 else "20261119-134302"
for f in ("segoeui.ttf", "segoeuib.ttf"):
    p = os.path.join(r"C:\Windows\Fonts", f)
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10.5, "xtick.labelsize": 9.6, "ytick.labelsize": 9.6, "axes.edgecolor": "#c9d1da", "axes.labelcolor": "#4a5462",
                     "xtick.color": "#4a5462", "ytick.color": "#4a5462", "axes.titleweight": "bold", "axes.titlesize": 12,
                     "axes.titlecolor": "#1d2430", "axes.titlelocation": "left", "axes.titlepad": 12})
TEAL, TEAL2, INK, MUTED, GRID = "#0f766e", "#5eb8ae", "#1d2430", "#7b8794", "#e6eaef"
SAND, ROSE, SKY = "#e0b25b", "#d97762", "#7aa7d6"


def style(ax, grid="x"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# --- 1. The timeline: when each tool call ran, and how many at once
ev = [json.loads(l) for l in open(os.path.join(ROOT, "data", "output", "agent", "runs", RUN + ".jsonl"), encoding="utf-8")]
t0 = next(e["t"] for e in ev if e["type"] == "start")
end = ev[-1]["t"] - t0
pending, bars = {}, []
for e in ev:
    if e["type"] == "tool":
        pending.setdefault(e["name"], []).append((e["t"] - t0, e.get("input") or {}))
    elif e["type"] == "tool_done" and pending.get(e["name"]):
        s, inp = pending[e["name"]].pop(0)
        bars.append((s, e["t"] - t0, e["name"], inp, e.get("ok", True)))
bars.sort()
# lanes: each call takes the first lane free at its start, so overlapping calls stack
lanes = []
placed = []
for s, f, n, inp, ok in bars:
    lane = next((i for i, last in enumerate(lanes) if last <= s), None)
    if lane is None:
        lane = len(lanes); lanes.append(0)
    lanes[lane] = f
    placed.append((lane, s, f, n, ok))
colors = {"variant": TEAL, "gene": TEAL2, "themes": SKY, "theme_genes": SKY, "trait_variants": SAND, "search_papers": ROSE,
          "read_paper": "#9c4a3c", "submit_answer": INK}
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.4, 3.9), dpi=220, sharex=True, gridspec_kw={"height_ratios": [3, 1.2], "hspace": 0.12})
for lane, s, f, n, ok in placed:
    w = max(f - s, 0.35)
    ax.barh(lane, w, left=s, height=0.62, color=colors.get(n, MUTED), alpha=1 if ok else 0.35, edgecolor="white", linewidth=0.5)
ax.set_yticks(range(len(lanes)), [f"slot {i + 1}" for i in range(len(lanes))], fontsize=9.4)
ax.invert_yaxis()
style(ax)
ax.set_title(f"One question, {len(bars)} tool calls in {end:.0f} s: lookups overlap", pad=26)
from matplotlib.patches import Patch
used = [n for n in colors if any(p[3] == n for p in placed)]
ax.legend(handles=[Patch(color=colors[n], label=n.replace("_", " ")) for n in used], ncol=len(used), fontsize=9, frameon=False,
          loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.2, handlelength=1, columnspacing=1.2)
# concurrency over time
import numpy as np
xs = np.linspace(0, end, 900)
conc = [sum(1 for _, s, f, _, _ in placed if s <= x < max(f, s + 0.35)) for x in xs]
ax2.fill_between(xs, conc, step="post", color=TEAL, alpha=0.85, linewidth=0)
ax2.set_ylabel("calls at\nonce", fontsize=9)
ax2.set_yticks(range(0, max(conc) + 1))
ax2.set_xlabel("seconds since the question")
style(ax2, grid="y")
fig.subplots_adjust(left=0.09, right=0.98, top=0.84, bottom=0.14)
fig.savefig(os.path.join(HERE, "img", "timeline.png"))
plt.close(fig)
print("timeline:", len(bars), "calls,", len(lanes), "lanes, max", max(conc), "at once")

# --- 2. The waterfall: from a naive build to the real cost of a question
tok = json.load(open(os.path.join(HERE, "ask_tokens.json")))
a = tok["average"]
steps = [("Naive build:\nOpus, no cache,\nraw tool results", a["opus_no_cache_raw_tools"], None),
         ("Sonnet instead\nof Opus", a["no_cache_raw_tools"] - a["opus_no_cache_raw_tools"], None),
         ("Compact tool\nresults", a["no_cache"] - a["no_cache_raw_tools"], None),
         ("Prompt\ncaching", a["actual"] - a["no_cache"], None),
         ("As built", a["actual"], None)]
fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=220)
level = 0
for i, (lab, v, _) in enumerate(steps):
    if i == 0 or i == len(steps) - 1:
        ax.bar(i, v, color=MUTED if i == 0 else TEAL, width=0.6)
        ax.text(i, v + 0.012, f"${v:.3f}", ha="center", va="bottom", fontsize=11, fontweight="bold", color=INK)
        level = v
    else:
        ax.bar(i, -v, bottom=level + v, color=TEAL2, width=0.6)
        ax.text(i, level + 0.012, f"\u2212${-v:.3f}", ha="center", va="bottom", fontsize=10, color=INK)
        ax.plot([i - 1 + 0.3, i - 0.3], [level, level], color="#b8c2cc", linewidth=0.8)
        level += v
ax.plot([len(steps) - 2 + 0.3, len(steps) - 1 - 0.3], [level, level], color="#b8c2cc", linewidth=0.8)
ax.set_xticks(range(len(steps)), [s[0] for s in steps], fontsize=9.4)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.1f}"))
ax.set_ylim(0, a["opus_no_cache_raw_tools"] * 1.18)
style(ax, grid="y")
ax.set_title("What one question costs, measure by measure")
ax.text(len(steps) - 1, a["actual"] + 0.07, f"{a['opus_no_cache_raw_tools'] / a['actual']:.0f}x cheaper\nthan the naive build",
        ha="center", va="bottom", color=TEAL, fontsize=10, fontweight="bold")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "img", "waterfall.png"))
plt.close(fig)

# --- 3. The example conversation: where each turn's input tokens go
ex = json.load(open(os.path.join(HERE, "ask_example_turns.json"), encoding="utf-8"))
d = json.load(open(os.path.join(ROOT, "data", "output", "agent", "sessions", "20261124-134315-1e06d1.json"), encoding="utf-8"))
fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=220)
labels = ["1  Show me the cluster\n    for ACTN3", "2  Why should I care\n    about this gene?", "3  Other muscle and\n    hormone genes"]
parts = [("read from cache", "cache_read", TEAL), ("written to cache", "cache_write", TEAL2), ("fresh input", "input", SAND),
         ("output", "output", ROSE)]
for i, t in enumerate(d["turns"]):
    u, left = t["tokens"], 0
    for lab, k, c in parts:
        ax.barh(i, u[k], left=left, color=c, height=0.58, label=lab if i == 0 else None)
        left += u[k]
    ax.text(left + 3000, i, f"{left / 1000:,.0f}k tokens \u00b7 ${u['usd']:.3f}", va="center", fontsize=10, color=INK)
ax.set_yticks(range(3), labels, fontsize=9.6)
ax.invert_yaxis()
ax.set_xlim(0, max(sum(t["tokens"][k] for k in ("cache_read", "cache_write", "input", "output")) for t in d["turns"]) * 1.32)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x / 1000:.0f}k"))
style(ax)
ax.set_title("Where each question's tokens go: almost all re-read from the cache")
ax.legend(ncol=4, fontsize=9, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.2))
fig.tight_layout()
fig.savefig(os.path.join(HERE, "img", "turns.png"))
plt.close(fig)
print("charts written")

# --- 4. Unit economics: model cost per user per month, as built and naive, at three levels of use
fig, ax = plt.subplots(figsize=(7.4, 3.2), dpi=220)
levels = [10, 50, 100]
built = [n * a["actual"] for n in levels]
naive = [n * a["opus_no_cache_raw_tools"] for n in levels]
x = np.arange(len(levels))
b1 = ax.bar(x - 0.19, naive, width=0.36, color="#b8c2cc", label="naive build (Opus, no cache, raw tools)")
b2 = ax.bar(x + 0.19, built, width=0.36, color=TEAL, label="as built")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.8, f"${b.get_height():.2f}", ha="center", va="bottom",
                fontsize=10, color=INK)
ax.set_xticks(x, [f"{n} questions a month" for n in levels], fontsize=10)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.0f}"))
ax.set_ylim(0, max(naive) * 1.18)
style(ax, grid="y")
ax.set_title("Model cost of one user per month, if we provided the model")
ax.legend(frameon=False, fontsize=9.4, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "img", "economics.png"))
plt.close(fig)
print("economics chart written")

# --- 5. Tiered inference: what one unit of work costs at each tier (measured)
tiers = [("0  Rules, no model\nmatching, cards, checks", 0.0),
         ("1  Haiku 5.5\nreadings, written once", 0.0037),
         ("2  Sonnet 5.5, medium\nthe conversation", a["actual"]),
         ("3  Opus 5.5\ndeep research agent", (1.008 + 0.936) / 2)]
fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=220)
ys = range(len(tiers))
vals = [max(v, 0.0) for _, v in tiers]
ax.barh(list(ys), vals, color=["#c9d1da", TEAL2, TEAL, "#0b4f49"], height=0.56)
for y, (lab, v) in zip(ys, tiers):
    ax.text(v + 0.012, y, "$0" if v == 0 else (f"${v:.4f}" if v < 0.01 else f"${v:.3f}"), va="center", fontsize=10.5, color=INK, fontweight="bold")
ax.set_yticks(list(ys), [t[0] for t in tiers], fontsize=9.6)
ax.invert_yaxis()
ax.set_xlim(0, 1.15)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:.2f}"))
style(ax)
ax.set_title("Tiered inference: each job on the cheapest tier that can do it")
fig.tight_layout()
fig.savefig(os.path.join(HERE, "img", "tiers.png"))
plt.close(fig)
print("tiers chart written")
