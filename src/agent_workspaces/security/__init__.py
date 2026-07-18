"""Security & Network plane — optimizes for ISOLATION.

Contains a broadly-capable agent without letting it exfiltrate data or escape the
sandbox. Three pillars:

    credential_proxy.py — secretless architecture: secrets never enter the sandbox
    network_policy.py   — ingress allowlist + egress policy
    isolation.py        — kernel/hardware isolation; the plane's public interface

`isolation.SecurityPlane` composes the three into a single secure()/teardown() pair.
"""
