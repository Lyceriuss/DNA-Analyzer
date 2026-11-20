"""Token use and what it would cost on the API, split the way it is billed.

    u = cost.new()
    u = cost.add(u, cost.of("claude-sonnet-5-5", msg.usage))   # an SDK usage object or a stream-json usage dict

Keys: input (fresh, full price), cache_read, cache_write, output, usd. A cache read is billed at a small fraction of
fresh input, so a turn that re-reads its context on every tool call is far cheaper than its raw token count suggests.
On a Claude Code login the tokens come out of the plan's usage instead; usd is then what the same turn costs on the
API.
"""

# USD per million tokens: input, output, cache read (Claude API reference, November 2026). A cache write (5-minute
# lifetime) is 1.25 times the input price. Haiku's price is for prompts of 100k tokens or fewer.
PRICES = {"sonnet": (2.00, 10.00, 0.10), "haiku": (0.10, 0.50, 0.01), "opus": (4.00, 20.00, 0.20)}
WRITE = 1.25
KEYS = ("input", "cache_read", "cache_write", "output")


def new():
    return {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "usd": 0.0}


def _family(model):
    m = (model or "").lower()
    return next((k for k in PRICES if k in m), None)


def of(model, u):
    """One response's usage as our record."""
    get = (lambda k: (u.get(k) or 0)) if isinstance(u, dict) else (lambda k: (getattr(u, k, None) or 0))
    out = {"input": get("input_tokens"), "cache_read": get("cache_read_input_tokens"),
           "cache_write": get("cache_creation_input_tokens"), "output": get("output_tokens")}
    p = PRICES.get(_family(model))
    out["usd"] = round((out["input"] * p[0] + out["cache_write"] * p[0] * WRITE + out["cache_read"] * p[2]
                        + out["output"] * p[1]) / 1e6, 6) if p else 0.0
    return out


def add(a, b):
    """The sum of two records (older records with only input and output count as they are)."""
    r = {k: (a or {}).get(k, 0) + (b or {}).get(k, 0) for k in KEYS}
    r["usd"] = round((a or {}).get("usd", 0.0) + (b or {}).get("usd", 0.0), 6)
    return r


def total_in(u):
    return sum((u or {}).get(k, 0) for k in ("input", "cache_read", "cache_write"))
