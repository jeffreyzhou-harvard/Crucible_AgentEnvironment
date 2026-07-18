"""Data plane — optimizes for REPRODUCIBILITY.

Every run starts from an identical, representative data state and can safely mutate
it without affecting any other run. Achieved with copy-on-write branching off a
shared read-only reference snapshot. See:

    provisioner.py — make datasets available to a sandbox; the plane's interface
    branching.py   — copy-on-write branch/merge/discard off a reference snapshot
    health.py      — verify data is ready + correct before handing over the sandbox
"""
