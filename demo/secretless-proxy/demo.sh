#!/usr/bin/env bash
# One-shot demo: starts the eval API + the secretless proxy, then runs the
# untrusted agent through all four beats. The agent is launched with a SCRUBBED
# environment (env -i) so "the agent has no secret" is provably true, not staged.
set -uo pipefail
cd "$(dirname "$0")"

PYBIN="$(command -v python3)"
PYDIR="$(dirname "$PYBIN")"

cleanup() { kill "${API_PID:-}" "${PROXY_PID:-}" 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT

echo "=== starting services ============================================"
# -u (unbuffered) so [api]/[proxy] lines interleave live with [agent] output.
"$PYBIN" -u fake_api.py &  API_PID=$!
"$PYBIN" -u proxy.py    &  PROXY_PID=$!
sleep 1

echo
echo "=== running untrusted agent (scrubbed env: no secrets inherited) =="
# env -i wipes the environment; we re-add only PATH/HOME so python still runs.
# HTTP_PROXY is the ONLY way out of the box. No ANTHROPIC_API_KEY, no tokens.
env -i PATH="$PYDIR:/usr/bin:/bin" HOME="$HOME" \
    HTTP_PROXY="http://127.0.0.1:8080" http_proxy="http://127.0.0.1:8080" \
    "$PYBIN" -u agent.py

echo
echo "=== done ========================================================="
