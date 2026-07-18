"""Control plane — optimizes for SPEED.

Keeps warm pools of pre-provisioned sandboxes, predicts demand so environments are
ready before they're asked for, and hides cold-start latency. See:

    scheduler.py   — claim/release sandboxes; the plane's public interface
    warm_pool.py   — the pool of hot sandboxes + eviction
    intent.py      — start provisioning while the user is still composing a prompt
"""
