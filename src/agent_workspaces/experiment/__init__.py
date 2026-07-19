"""Experiments — fan-out best-of-N on top of Crucible.

The atomic unit of a self-improvement loop: propose N solutions, run each in its own
isolated + reproducible sandbox, score against a HELD-OUT grader (so a candidate
can't win by gaming the visible tests), and rank. The two-number score
(in-sandbox vs held-out) makes reward-hacking visible instead of rewarded.

    runner.run_experiment(...)   dispatches to:
      scripted.run_scripted(...)   no Docker / no API key — reliable stage demo
      docker_runner.run_docker(...) real: Claude + containers + external grader
"""
