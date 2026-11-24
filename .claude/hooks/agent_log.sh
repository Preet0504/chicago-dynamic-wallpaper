#!/bin/zsh
# SubagentStop / SubagentStart: append the event (with timestamp) to benchmark/agent_log.jsonl
jq -c --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '. + {logged_at: $ts}' >> /Users/preetpatel/Documents/wallpapers/benchmark/agent_log.jsonl
