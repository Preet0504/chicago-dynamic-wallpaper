#!/usr/bin/env python3
"""Measure token usage and API-equivalent cost of agent runs from Claude Code transcripts.

  python3 tools/cost.py --agents ID [ID ...]        # specific subagents
  python3 tools/cost.py --since "2026-11-14T16:40"  # every subagent started after a time
  python3 tools/cost.py --main --since ...          # the orchestrator (main session) too
Writes nothing; prints a table (+ JSON with --json, pipe into benchmark/costs.json).
"""
import json, glob, os, sys

PROJ = os.path.expanduser("~/.claude/projects/-Users-preetpatel-Documents-wallpapers")
SESSION = "1acc4d69-8d7c-45c6-91c0-db5ed59de9b5"
# $ per 1M tokens: input, output, cache read; cache writes = 1.25x (5m) / 2x (1h) input
PRICES = {"opus": (4.0, 20.0, 0.20), "sonnet": (2.0, 10.0, 0.10), "haiku": (0.10, 0.50, 0.01),
          "fable": (8.0, 40.0, 0.20)}


def price_for(model):
    for k, v in PRICES.items():
        if k in (model or ""):
            return v
    return PRICES["opus"]


def summarize(path, since=None, until=None):
    seen, tot = {}, dict(input=0, output=0, cache_read=0, cache_w5m=0, cache_w1h=0, cost=0.0, msgs=0)
    first = last = None
    models = set()
    for line in open(path):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message")
        ts = d.get("timestamp")
        if not isinstance(m, dict) or not m.get("usage") or m.get("role") != "assistant":
            continue
        if since and ts and ts < since:
            continue
        if until and ts and ts > until:
            continue
        seen[m.get("id") or d.get("uuid")] = (m, ts)
    for mid, (m, ts) in seen.items():
        u = m["usage"]; model = m.get("model", "")
        models.add(model)
        pin, pout, pread = price_for(model)
        cc = u.get("cache_creation") or {}
        w5 = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) if not cc else 0)
        w1 = cc.get("ephemeral_1h_input_tokens", 0)
        tot["input"] += u.get("input_tokens", 0); tot["output"] += u.get("output_tokens", 0)
        tot["cache_read"] += u.get("cache_read_input_tokens", 0); tot["cache_w5m"] += w5; tot["cache_w1h"] += w1
        tot["cost"] += (u.get("input_tokens", 0) * pin + u.get("output_tokens", 0) * pout +
                        u.get("cache_read_input_tokens", 0) * pread + w5 * pin * 1.25 + w1 * pin * 2) / 1e6
        tot["msgs"] += 1
        first = min(first or ts, ts) if ts else first; last = max(last or ts, ts) if ts else last
    tot.update(models=sorted(models), first=first, last=last)
    return tot


def agent_meta(path):
    meta = path.replace(".jsonl", ".meta.json")
    try:
        return json.load(open(meta)).get("description", "")
    except Exception:
        return ""


def main(a):
    since = a[a.index("--since") + 1] if "--since" in a else None
    until = a[a.index("--until") + 1] if "--until" in a else None
    paths = []
    sub = os.path.join(PROJ, SESSION, "subagents")
    if "--agents" in a:
        ids = [x for x in a[a.index("--agents") + 1:] if not x.startswith("--")]
        paths = [os.path.join(sub, "agent-%s.jsonl" % i) for i in ids]
    else:
        paths = sorted(glob.glob(os.path.join(sub, "agent-*.jsonl")))
    rows = []
    for p in paths:
        s = summarize(p, since, until)
        if s["msgs"]:
            rows.append(dict(name=os.path.basename(p)[6:-6], desc=agent_meta(p), **s))
    if "--main" in a:
        s = summarize(os.path.join(PROJ, SESSION + ".jsonl"), since, until)
        rows.append(dict(name="orchestrator", desc="main session", **s))
    total = sum(r["cost"] for r in rows)
    for r in rows:
        print("%-20s %-38s msgs %4d  in %8d  out %8d  cache_r %10d  cache_w %9d  $%7.2f  %s" % (
            r["name"][:20], r["desc"][:38], r["msgs"], r["input"], r["output"], r["cache_read"],
            r["cache_w5m"] + r["cache_w1h"], r["cost"], ",".join(r["models"])))
    print("TOTAL $%.2f" % total)
    if "--json" in a:
        print(json.dumps(dict(rows=rows, total=total), indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
