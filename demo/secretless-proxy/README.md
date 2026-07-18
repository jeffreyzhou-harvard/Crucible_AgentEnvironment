# Secretless egress proxy — the security plane for autoresearch sandboxes

An autoresearch loop runs an agent unattended for hours: it edits code, runs
experiments, and queries an eval / experiment-tracking service to score each run.
That agent is running untrusted code (from a repo or a paper it was told to
reproduce). Two things must be true no matter what it does:

1. **It can never leak the credential** it uses to reach the eval service —
   because it never has it.
2. **It can never phone home** — a prompt-injected agent can't exfiltrate results
   to an attacker's server.

> "The safest secret is one the agent can never access." — NeoSigma, *Agent Workspaces*

## The one idea

The agent's box has **zero secrets**. The credential lives in exactly one place:
the **proxy**, which sits *outside* the box. Every outbound request the agent
makes goes through that proxy, which does two jobs:

- **Allowlist** the destination (drop anything unapproved).
- **Inject** the real credential at the last moment, on the way out.

Because an HTTP-proxied client never resolves or dials the target itself — it
hands the whole URL to the proxy — the proxy owns all routing and the allowlist
is **unbypassable from inside the box**.

## Run it

```bash
./demo.sh
```

No setup, no keys, stdlib only. Reads top-to-bottom as one interleaved
`[agent]` / `[proxy]` / `[api]` log.

## The four beats (your narration)

| # | What happens | Line to say |
|---|--------------|-------------|
| 1 | Agent scans its own env for secrets → **NONE** | "The agent literally has no key to leak." |
| 2 | Approved call via proxy → **200 + data** | "It still gets its job done — the proxy added the key on the way out." |
| 3 | Agent bypasses proxy, hits API directly → **401** | "On its own, it can't authenticate to anything." |
| 4 | Prompt-injected POST to `exfil.attacker` → **403** | "Even hijacked, it can't phone home." |

## The three files, one job each

- `fake_api.py` — the real eval service. Returns data only with the right key, else 401.
- `proxy.py` — **the star.** Holds the secret, enforces the allowlist, injects the key. The only file that touches `SECRET` on the agent side.
- `agent.py` — the untrusted agent. No secret anywhere. Everything routes through the proxy.

## How this maps to the repo

This is a runnable distillation of the security plane defined in
`src/agent_workspaces/security/`:

- `proxy.py` ↔ `credential_proxy.py` (`CredentialProxy.attach` injects the key)
- allowlist in `proxy.py` ↔ `network_policy.py` (`NetworkPolicy.apply` egress control)

Next steps to make it "real": swap the hardcoded token for a throwaway live API
key (beat 2 hits a real service), persist an egress audit log of every allow/block
decision, and add HTTPS via a `CONNECT` tunnel restricted to allowlisted hosts.
