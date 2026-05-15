# Runbook

Operational playbook for humans running legacy-forge.

## First-time setup

```powershell
# Python 3.11+
pip install -e ".[dev]"

# Smoke test
forge --version
forge phases
```

## Starting a refactor

1. Clone the legacy repo somewhere else; do NOT put it inside `legacy-forge/`.
2. Configure target legacy path in `.forge/config.yaml` (not yet implemented — coming with the first concrete agent).
3. Run phase 0 manually first; review the inventory before unleashing later phases.

## When something goes wrong

| Symptom | First check |
|---------|------------|
| Agent appears stuck | `forge trace ls` → look for runs with `errors > 0` or wallclock blown |
| Cost spike | `forge trace ls` → which run, which agent; check prompt version |
| File mysteriously modified | look for sibling `<file>.forge-trail.yaml` — agent + prompt version + source refs |
| Worktree won't delete | `forge worktree gc` to reclaim stale leases |
| Eval suddenly fails after prompt change | revert prompt, re-run eval to confirm; bisect the prompt diff |

## Don't

- Don't manually edit `.forge/trace.sqlite` — break replay, break audit.
- Don't commit `.forge/`, `worktrees/`, or any `.forge-trail.yaml` from a worktree that wasn't reviewed.
- Don't raise budget caps to "just get this run through". Find the actual blocker.
