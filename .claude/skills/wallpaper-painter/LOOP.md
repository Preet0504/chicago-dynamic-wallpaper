# Iteration loop (orchestrator ↔ agents)

The orchestrator (main session) runs this loop. Agents keep their context between rounds: the orchestrator
continues the same agent with SendMessage instead of starting a new one, so nobody re-reads the codebase.

```
round k:
  1. MODIFY   season-modifier, weather-modifier, time-modifier work in parallel on the files they own.
              Self-review: 2 quick rounds (not more — the critic and checker do the deep review).
  2. RENDER   finalizer  → .venv/bin/python render/benchmark.py  → benchmark/run-N/
  3. REVIEW   checker    → scores.json + punchlist.md          (parallel)
              realism-critic → realism.md                       (parallel)
  4. POLISH   detail-orienter fixes small local defects from punchlist/realism; routes the rest.
  5. ROUTE    orchestrator writes benchmark/run-N/feedback/<agent>.md (merged punchlist + realism issues for that
              agent) and SendMessages each owner: "round k+1: read feedback/<agent>.md, fix, report".
  6. STOP when: overall score >= 4.2 AND no realism verdict 'reject' AND no criterion below 3
                or after 3 rounds, or when a round improves the overall score by < 0.1 (plateau).
```

## Rules for agents in the loop

- Read ONLY your own feedback file plus the renders it cites; don't re-read everything each round.
- Read crops, not every full frame. Downscale images you inspect when full resolution isn't needed.
- Report in under 15 lines: what you changed, which feedback items are fixed / not fixed (and why), preview paths.
- One mflux (AI) process at a time on this Mac (16 GB RAM). If one is running (`pgrep -f mflux-generate`), wait.
- Never run install.sh, never change the desktop wallpaper.

## Cost accounting

Every round, the finalizer runs `python3 tools/cost.py --since <round start>` and saves it to
benchmark/run-N/cost.txt. Hooks log SubagentStart/SubagentStop events to benchmark/agent_log.jsonl.
