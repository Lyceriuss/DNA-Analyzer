"""Measures what Ask's token-saving measures save, from the recorded turns (data/output/agent/sessions/*.json) and by
re-running their recorded tool calls. Writes docs/outreach/ask_tokens.json and ask_tokens.png. Token counts and prices
only; no genotype leaves this script.

Per turn, from the recorded usage (cost.of's split of fresh input, cache read, cache write, output):
  actual          as billed: Sonnet 5.5, cache reads at a tenth of the input price
  no caching      every input token at the full input price
  Opus            the same turn on Opus 5.5 (no caching), the model the earlier research agent uses
Per tool call, by re-running it here:
  clipped         what the model got: facts.clip (empty fields dropped, 24,000 characters at most); personal tools
                  give only the result's shape when sharing is off
  raw             the tool's full result as plain JSON, and for personal tools the full result cards
A tool result stays in the context for every later step of the turn, so a call's extra tokens count once per
remaining step."""
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from cluster_analysis.agent import cost, facts, tools  # noqa: E402

P = cost.PRICES
turns = []
for f in sorted(glob.glob("data/output/agent/sessions/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    for t in d.get("turns", []):
        u = t.get("tokens") or {}
        if u.get("cache_read") is None:
            continue
        turns.append({"person": d["person"], "calls": t.get("calls") or [], "u": u, "model": t.get("model")})


def usd(inp, read, write, out, fam, cached=True):
    p = P[fam]
    if not cached:
        return (inp + read + write) * p[0] / 1e6 + out * p[1] / 1e6
    return (inp * p[0] + write * p[0] * cost.WRITE + read * p[2] + out * p[1]) / 1e6


# Tool results: clipped (as sent) against raw, re-run from the cache
chars_sent = chars_raw = 0
n_calls = 0
for t in turns[-12:]:   # the newest turns: the current tool set
    ctx = tools.new_context(t["person"], share=True)
    steps = [c for c in t["calls"] if c["name"] not in ("understand", "answer")]
    for i, c in enumerate(steps):
        kind, fn, schema, _ = tools.TOOLS.get(c["name"], (None,) * 4)
        if kind not in (tools.PUBLIC, tools.PERSONAL):
            continue
        try:
            before = len(ctx["cards"])
            raw = fn(ctx, **{k: v for k, v in c["args"].items() if k in schema["properties"]})
        except Exception as e:  # noqa: BLE001
            continue
        sent = facts.clip(raw)
        full = json.dumps(raw, ensure_ascii=False, indent=1)
        if kind == tools.PERSONAL:
            full += json.dumps(ctx["cards"][before:], ensure_ascii=False, indent=1)
        later = max(1, len(steps) - i)       # the result is re-read on every later step
        chars_sent += len(sent) * later
        chars_raw += len(full) * later
        n_calls += 1

ratio = chars_raw / chars_sent if chars_sent else 1.0
sampled = min(12, len(turns))
# The extra input tokens per turn raw results would add: their extra characters, re-read on each later step,
# at about 4 characters a token, averaged over the re-run turns
extra = (chars_raw - chars_sent) / 4 / sampled
rows = []
for t in turns:
    u = t["u"]
    i, r, w, o = u["input"], u["cache_read"], u["cache_write"], u["output"]
    rows.append({"actual": usd(i, r, w, o, "sonnet"), "no_cache": usd(i, r, w, o, "sonnet", cached=False),
                 "no_cache_raw_tools": usd(i + extra, r, w, o, "sonnet", cached=False),
                 "opus_no_cache_raw_tools": usd(i + extra, r, w, o, "opus", cached=False),
                 "tokens_in": i + r + w, "tokens_out": o})

avg = {k: sum(x[k] for x in rows) / len(rows) for k in rows[0]}
out = {"turns": len(rows), "tool_calls_rerun": n_calls, "tool_raw_over_clipped": round(ratio, 2),
       "extra_input_tokens_per_turn_raw_tools": round(extra), "average": avg}
json.dump(out, open("docs/outreach/ask_tokens.json", "w"), indent=1)
print(json.dumps(out, indent=1))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
labels = ["As built\n(Sonnet, cached,\nclipped tools)", "Without\nprompt caching", "...and raw\ntool results", "...and Opus\ninstead of Sonnet"]
vals = [avg["actual"], avg["no_cache"], avg["no_cache_raw_tools"], avg["opus_no_cache_raw_tools"]]
fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=200)
bars = ax.bar(labels, vals, color=["#0f766e", "#9aa5b1", "#7b8794", "#52606d"], width=0.62)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v, f"${v:.3f}\n({v / vals[0]:.1f}x)" if v / vals[0] >= 1.5 else f"${v:.3f}",
            ha="center", va="bottom", fontsize=8, color="#1d2430")
ax.set_ylabel("USD per Ask turn (API prices)", fontsize=8.5)
ax.set_title(f"Average cost of one Ask turn, {len(rows)} recorded turns", fontsize=9.5, loc="left", color="#1d2430")
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(labelsize=8)
ax.set_ylim(0, max(vals) * 1.22)
fig.tight_layout()
fig.savefig("docs/outreach/ask_tokens.png")
print("chart written")
