"""Ask conversations: the turns of one session, so a follow-up question knows what came before.

    data/output/agent/sessions/<id>.json      the turns (question, reading and plan, tool calls, the person's results
                                              for the screen, views, the explanation, the readings picked for them)

What a follow-up sends the model (context()): the earlier questions, the readings and plans, the tool calls with
their public arguments, and the model's own explanations and follow-up suggestions. Never the person's results, the
readings picked for them or anything shown only on their screen. When the person points at something on the screen
("Ask about this" on a study or a gene), its public id comes with the question, as if they had typed it.
The ledger (what the public tools returned: papers, refs, texts) carries over, so later answers can cite it.
"""
import json
import os
import re
import secrets
import time

from cluster_analysis.agent import facts

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, "data", "output", "agent", "sessions")


class Session:
    def __init__(self, sid=None, person=None):
        self.id = sid or (time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
        self.person = person
        self.turns = []
        self.ledger = facts.Ledger()

    @property
    def path(self):
        return os.path.join(DIR, self.id + ".json")

    @classmethod
    def load(cls, sid):
        if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", sid or ""):
            raise ValueError("No such conversation.")
        with open(os.path.join(DIR, sid + ".json"), encoding="utf-8") as f:
            d = json.load(f)
        s = cls(d["id"], d["person"])
        s.turns = d["turns"]
        s.ledger = facts.Ledger.from_json(d["ledger"])
        return s

    def save(self):
        os.makedirs(DIR, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"id": self.id, "person": self.person, "turns": self.turns, "ledger": self.ledger.to_json()}, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def context(self, share=False):
        """The conversation so far, for the model: nothing from the person's screen unless sharing is on, when the
        earlier summaries (which weave the person's results) come too."""
        if not self.turns:
            return ""
        out = ["The conversation so far (the person's own results were shown to them, not to you):"]
        for i, t in enumerate(self.turns, 1):
            out.append(f"\nTurn {i}. Question: {t['question']}")
            u = t.get("understood") or {}
            if u.get("reading"):
                out.append(f"Your reading: {u['reading']}")
            calls = [f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)})" for c in t.get("calls", []) if c["name"] not in ("understand", "answer")]
            if calls:
                out.append("Tools you used: " + "; ".join(calls[:20]))
            a = t.get("answer") or {}
            if share and a.get("summary"):
                out.append(f"Your summary: {a['summary']}")
            if a.get("explanation"):
                out.append(f"Your explanation: {a['explanation']}")
            if a.get("followups"):
                out.append("Follow-ups you suggested: " + " | ".join(a["followups"]))
        return "\n".join(out)


def listing():
    if not os.path.isdir(DIR):
        return []
    out = []
    for name in sorted(os.listdir(DIR), reverse=True)[:30]:
        if name.endswith(".json"):
            try:
                with open(os.path.join(DIR, name), encoding="utf-8") as f:
                    d = json.load(f)
                if d["turns"]:
                    out.append({"id": d["id"], "person": d["person"], "question": d["turns"][0]["question"], "turns": len(d["turns"])})
            except (OSError, ValueError, KeyError):
                continue
    return out
