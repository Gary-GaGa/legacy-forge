# The Seven Pillars

The Harness exists to make multi-agent legacy refactoring survivable over many months. Seven concerns must each have a dedicated layer — leave any one out and the system collapses under its own weight after a few weeks.

| # | Pillar | Concretely lives in |
|---|--------|---------------------|
| 1 | Context Engineering | `forge.agents.base` (input shape), `prompts/<agent>/` (versioned) |
| 2 | Tool Ergonomics | `forge.agents.base` Input/Output schemas (pydantic) |
| 3 | Evals | `forge.evals.runner`, `evals/cases/`, `.github/workflows/eval.yml` |
| 4 | Observability | `forge.tracer`, `forge trace ls`, `.forge/trace.sqlite` |
| 5 | Sandbox & Permissions | `forge.worktree`, `worktrees/`, lease file `.forge/worktree-leases.json` |
| 6 | Orchestration & Loop Control | `forge.orchestrator`, `forge.budget` |
| 7 | Memory & Provenance | `forge.memory.store` (L2), `forge.provenance` (`.forge-trail.yaml`) |

## Non-negotiables

- **Every LLM call is traced.** No span, no call.
- **Every generated file has a `.forge-trail.yaml`.** No trail, the file is rejected at PR time.
- **Every agent runs inside a worktree lease.** No lease, the orchestrator refuses to dispatch.
- **Every prompt change goes through CI eval.** Score regression blocks merge.
- **Every budget cap is enforced before the next LLM round-trip.** No "just one more iteration".

## What this is not

Not an LLM provider. Not an agent framework you import to "build agents". It is the floor those things sit on. Swap providers, swap agent shapes — the Harness contract stays.
