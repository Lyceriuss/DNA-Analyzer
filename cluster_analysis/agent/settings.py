"""Ask's settings, chosen by whoever sets Ask up (data/output/agent/settings.json, on this machine).

    share_results   false (default; the page calls it Restricted mode, on): the model gets the question and public
                    research only, and the summary is assembled on this machine from readings written for everyone;
                    personal tools tell it only what kind of result was shown. true (Restricted mode off): the person's interpreted results for the items a question touches (a gene's
                    activity type, a score's band and direction, the genotype a finding applies to) go to the model
                    the user connected, so it can weave them into the summary. Never the DNA file, never anything the
                    question doesn't touch. Restricted by default since 2026-11-26 (the user's choice).
    A child's results (Inheritance) follow the same mode: the child is worked out on this machine from the two
                    profiles picked in Ask, so it has no switch of its own.
    provider        which model Ask runs on: "anthropic" (API key), "claude-code" (its login), or one of models.PROVIDERS
                    (OpenAI, Google Gemini, Mistral, OpenRouter, a custom OpenAI-compatible server) by API key. None:
                    the first that is set up (an Anthropic key, then Claude Code).
    model, small_model, base_url    for the OpenAI-compatible providers: the model the user picked from the
                    provider's list, the one for the short readings (default: the same), a custom server's URL.

Connecting a model is the user's own setup (their API key or their Claude Code login), so what it receives is their
decision too; docs/architecture/agent.md, "What is sent", states it.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "data", "output", "agent", "settings.json")
DEFAULTS = {"share_results": False, "provider": None, "model": None, "small_model": None, "base_url": None}
TEXT = ("provider", "model", "small_model", "base_url")


def get():
    d = dict(DEFAULTS)
    if os.path.exists(PATH):
        try:
            with open(PATH, encoding="utf-8") as f:
                d.update({k: v for k, v in json.load(f).items()
                          if k in DEFAULTS and (isinstance(v, str) or v is None if k in TEXT else isinstance(v, type(DEFAULTS[k])))})
        except (OSError, ValueError):
            pass
    return d


def _save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return d


def set(**kw):
    d = get()
    d.update({k: bool(v) for k, v in kw.items() if k in DEFAULTS and isinstance(DEFAULTS[k], bool)})
    d.update({k: (str(v).strip()[:300] or None) if v is not None else None for k, v in kw.items() if k in TEXT})
    return _save(d)

