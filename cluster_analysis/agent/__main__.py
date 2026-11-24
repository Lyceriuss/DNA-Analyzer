"""The research agent.

    python -m cluster_analysis.agent index                     # build the local research index (once, a few minutes)
    python -m cluster_analysis.agent ask "QUESTION" [--lang sv] [--person XY]
                                                               # run the agent; prints the steps, then the answer filled
                                                               # in for --person (on this machine)
    python -m cluster_analysis.agent fill ANSWER_ID --person XY
    python -m cluster_analysis.agent quick "QUESTION" --person XY   # the quick answer: no model, under a minute
    python -m cluster_analysis.agent list                      # the saved answers
    python -m cluster_analysis.agent mcp                       # the tools as an MCP server (stdio)

The explorer's Ask tab (explorer serve) does the same in the page.
"""
import argparse
import json
import sys


def show(ev):
    k = ev["type"]
    if k == "tool":
        print(f"\n→ {ev['name']}({json.dumps(ev['input'], ensure_ascii=False)})", flush=True)
    elif k == "tool_done" and not ev["ok"]:
        print(f"  ✗ {ev['error']}", flush=True)
    elif k == "thinking":
        print(ev["text"], end="", flush=True)
    elif k == "check":
        print(f"\n✓ answer accepted" if not ev["problems"] else "\n✗ answer check:\n  - " + "\n  - ".join(ev["problems"]), flush=True)
    elif k == "error":
        print(f"\n✗ {ev['message']}", flush=True)
    elif k == "end":
        print(f"\ntokens: {ev['usage']}", flush=True)


def print_fill(aid, person):
    from cluster_analysis.agent import answer
    doc, f = answer.load(aid), answer.fill(aid, person)
    a = doc["answer"]
    print(f"\n# {a['title']}\n\n{a['summary']}\n")
    for g in a["groups"]:
        print(f"## {g['title']}")
        for v in g["variants"]:
            r = f["reads"][v["rsid"]]
            print(f"- {v['gene']} {v['rsid']} ({v['strength']}): {person} {r['genotype'] or '–'}, "
                  f"{r['copies'] if r['copies'] is not None else '?'} × {v['effect_allele']}. {r['reading'] or r['why_none']}")
    print("\n## Practice")
    for p in f["practice"]:
        if p["applies"]:
            print(f"- {p['text']}")
    print("\n## Limits")
    for x in a["limits"]:
        print(f"- {x}")


def print_quick(r):
    print(f"kind: {', '.join(r['kinds'])} · {r['seconds']} s · matched: " + "; ".join(f"{i['type']}:{i['label']}" for i in r["items"][:6]))
    print()
    for s in r["verdict"]:
        print("> " + s)
    for c in r["cards"][:12]:
        print()
        print(f"[{c['provider']}] {c['title']} · {c['level']}" + (f" · {c['value']}" if c["value"] is not None else ""))
        print(f"  {c['headline']}")
        for x in c["rows"][:4]:
            print(f"   - {x['label']}: {x['value']}" + (f" ({x['note']})" if x.get("note") else ""))
        for x in (c.get("advice") or [])[:4]:
            print(f"   * {x['label']}: {x['value'][:140]} ({x['note']})")
        for u in c["unknown"][:1]:
            print(f"  unknown: {u}")
        for s in (c.get("studies") or [])[:2]:
            if "error" in s:
                print(f"  study search failed: {s['error']}")
                continue
            print(f"  study [{s['type']}, {s['year']}] {s['title'][:90]}")
            print(f"     » {s['sentences'][0][:200]}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--lang", default="en", choices=["en", "sv"])
    a.add_argument("--person")
    f = sub.add_parser("fill")
    f.add_argument("answer")
    f.add_argument("--person", required=True)
    qk = sub.add_parser("quick")
    qk.add_argument("question")
    qk.add_argument("--person", required=True)
    qk.add_argument("--no-studies", action="store_true")
    sub.add_parser("list")
    sub.add_parser("mcp")
    rm = sub.add_parser("remote", help="the public research tools as a remote MCP server over HTTP, with OAuth 2.1")
    rm.add_argument("--host", default="127.0.0.1")
    rm.add_argument("--port", type=int, default=8765)
    rm.add_argument("--public-url", help="where clients reach it, e.g. https://research.example.org (default http://HOST:PORT)")
    args = ap.parse_args()
    if args.cmd == "index":
        from cluster_analysis.agent import index
        index.build()
    elif args.cmd == "ask":
        from cluster_analysis.agent import run
        if not run.backend():
            sys.exit("No API key (ANTHROPIC_API_KEY, or save one in the Ask tab) and no Claude Code command line found.")
        print(f"backend: {run.backend()}")
        aid = run.ask(args.question, args.lang, emit=show)
        if not aid:
            sys.exit(1)
        print(f"\nsaved answer {aid}")
        if args.person:
            print_fill(aid, args.person)
    elif args.cmd == "quick":
        from cluster_analysis.agent import quick
        r = quick.run(args.question, args.person, studies=not args.no_studies)
        print_quick(r)
    elif args.cmd == "fill":
        print_fill(args.answer, args.person)
    elif args.cmd == "list":
        from cluster_analysis.agent import answer
        for x in answer.listing():
            print(f"{x['id']}  {x['question']}")
    elif args.cmd == "mcp":
        from cluster_analysis.agent import mcp_server
        mcp_server.main()
    elif args.cmd == "remote":
        from cluster_analysis.agent import remote
        remote.main(args.host, args.port, args.public_url)


if __name__ == "__main__":
    main()
