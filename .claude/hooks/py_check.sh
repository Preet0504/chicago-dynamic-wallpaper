#!/bin/zsh
# PostToolUse(Write|Edit): keep render/ and tools/ Python importable for concurrently running agents.
f=$(jq -r '.tool_response.filePath // .tool_input.file_path // empty')
case "$f" in
  */wallpapers/render/*.py|*/wallpapers/tools/*.py) ;;
  *) exit 0 ;;
esac
err=$(/Users/preetpatel/Documents/wallpapers/.venv/bin/python -m py_compile "$f" 2>&1) || {
  echo "py_compile failed for $f — other agents import this file, fix it now:" >&2
  echo "$err" >&2
  exit 2
}
exit 0
