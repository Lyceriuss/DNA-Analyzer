"""Ask's settings, chosen by whoever sets Ask up (data/output/agent/settings.json, on this machine).

    share_results   true (default): the person's interpreted results for the items a question touches (a gene's
                    activity type, a score's band and direction, the genotype a finding applies to) go to the model
                    the user connected, so it can weave them into the summary. Never the DNA file, never anything the
                    question doesn't touch. false: the model gets only the kind of result shown, and the summary is
                    assembled on this machine from readings written for everyone (the earlier, blind mode).

Connecting a model is the user's own setup (their API key or their Claude Code login), so what it receives is their
decision too; docs/architecture/agent.md, "What is sent", states it.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "data", "output", "agent", "settings.json")
DEFAULTS = {"share_results": True}


def get():
    d = dict(DEFAULTS)
    if os.path.exists(PATH):
        try:
            with open(PATH, encoding="utf-8") as f:
                d.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
    return d


def set(**kw):
    d = get()
    d.update({k: bool(v) for k, v in kw.items() if k in DEFAULTS})
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return d
