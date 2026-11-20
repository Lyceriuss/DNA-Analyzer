"""The Ask tools as an MCP server: what Claude Code uses in the explorer's Ask tab, and any MCP client can use.

    python -m cluster_analysis.agent mcp                         # stdio

In the Ask tab, converse.py starts Claude Code with this server and DNA_TURN_FILE: the turn's shared context (the
person, the conversation's ledger). Every tool call runs here (tools.py) and the turn file is updated after each one,
so the person's results, views and the answer reach the tab without passing through Claude: personal tools return
only the shape of what was shown.

Used on its own (no DNA_TURN_FILE), DNA_PERSON names the profile the personal tools read; their results are kept in
data/output/agent/mcp_turn.json.
"""
import json
import os
from typing import Literal

from mcp.server.mcpserver import MCPServer

from cluster_analysis.agent import converse, facts, tools

TURN = os.environ.get("DNA_TURN_FILE") or os.path.join(tools.providers.ROOT, "data", "output", "agent", "mcp_turn.json")


def _load():
    d = {}
    if os.path.exists(TURN):
        with open(TURN, encoding="utf-8") as f:
            d = json.load(f)
    ctx = tools.new_context(d.get("person") or os.environ.get("DNA_PERSON"), share=d.get("share"))
    if d.get("ledger"):
        ctx["ledger"] = facts.Ledger.from_json(d["ledger"])
    for k in ("cards", "views", "findings"):
        ctx[k] = d.get(k) or []
    ctx["understood"], ctx["answer"] = d.get("understood"), d.get("answer")
    ctx["spent"], ctx["rejections"], ctx["outward"] = d.get("spent", 0), d.get("rejections", 0), d.get("outward", 0)
    ctx["outward_args"] = d.get("outward_args") or []
    ctx["lookup_args"], ctx["trace"], ctx["question"] = d.get("lookup_args") or [], d.get("trace") or [], d.get("question")
    return ctx


CTX = _load()


def _save():
    os.makedirs(os.path.dirname(TURN), exist_ok=True)
    out = {"person": CTX["person"], "share": CTX["share"], "ledger": CTX["ledger"].to_json(), "cards": CTX["cards"], "views": CTX["views"],
           "findings": CTX["findings"], "understood": CTX["understood"], "answer": CTX["answer"],
           "spent": CTX.get("spent", 0), "rejections": CTX.get("rejections", 0), "outward": CTX.get("outward", 0),
           "outward_args": CTX.get("outward_args", []), "lookup_args": CTX.get("lookup_args", []), "trace": CTX.get("trace", []),
           "question": CTX.get("question")}
    tmp = TURN + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, TURN)


server = MCPServer("dna", instructions=converse.system_prompt(CTX["share"]))
PY = {"string": "str", "integer": "int", "array": "list[str]"}


def _register(name, schema, desc):
    """A typed wrapper per tool, so the MCP schema shows its real parameters."""
    params, names = [], []
    # Required parameters first: Python allows no required parameter after an optional one
    for k, spec in sorted(schema["properties"].items(), key=lambda kv: kv[0] not in schema["required"]):
        t = f"Literal[{', '.join(map(repr, spec['enum']))}]" if spec.get("enum") else PY[spec["type"]]
        params.append(f"{k}: {t}" if k in schema["required"] else f"{k}: {t} | None = None")
        names.append(k)
    src = (f"def {name}({', '.join(params)}):\n"
           f"    args = {{k: v for k, v in dict({', '.join(f'{n}={n}' for n in names)}).items() if v is not None}}\n"
           f"    text, err = tools.call(CTX, {name!r}, args)\n"
           f"    _save()\n"
           f"    return ('NOT ACCEPTED: ' + text) if err else text\n")
    ns = {"tools": tools, "CTX": CTX, "_save": _save, "Literal": Literal}
    exec(src, ns)
    server.add_tool(ns[name], name=name, description=desc)


for _name, (_kind, _fn, _schema, _desc) in tools.TOOLS.items():
    _register(_name, _schema, _desc)


def main():
    server.run("stdio")
