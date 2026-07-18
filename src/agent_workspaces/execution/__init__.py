"""Execution plane — optimizes for FIDELITY.

A complete developer workstation inside the sandbox: writable filesystem, cloned
repos, Docker support, dev tooling, and MCP servers. The goal is that a trajectory
that succeeds in the sandbox transfers to production unchanged. See:

    sandbox.py     — attach/run/destroy; the plane's public interface
    runtime.py     — the container/VM backend abstraction (docker/firecracker/k8s)
    filesystem.py  — writable FS + repo cloning
    mcp.py         — MCP servers + dev tooling wired into the sandbox
"""
