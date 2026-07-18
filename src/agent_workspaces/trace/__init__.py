"""Trace — record every execution so the sandbox can die but the trajectory lives.

Outputs stream to the client while a complete execution trace persists externally.
When the sandbox is destroyed, the trace remains available for replay, debugging,
and evaluation. This is what makes runs auditable and lets you build eval sets from
real agent behavior. See recorder.py.
"""
