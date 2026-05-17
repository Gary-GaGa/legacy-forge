# The Seven Pillars

The Harness exists to make multi-agent legacy refactoring survivable over many months. Seven concerns must each have a dedicated layer — leave any one out and the system collapses under its own weight after a few weeks.

| # | Pillar | Concretely lives in | Status |
|---|--------|---------------------|--------|
| 1 | Context Engineering | `forge.agents.base` (input shape), `prompts/<agent>/<v>.md` + `<v>.meta.yaml` | shipped |
| 2 | Tool Ergonomics | `forge.llm.provider` (messages + tool_calls), `forge.agents.base` Input/Output schemas | shipped (message-based protocol; tool execution path not yet exercised) |
| 3 | Evals | `forge.evals.runner`, `evals/cases/`, `.github/workflows/eval.yml` | partial — `expect.compiles` and `custom_checks` are declared but inert |
| 4 | Observability | `forge.tracer`, `forge trace ls`, `.forge/trace.sqlite` | shipped |
| 5 | Sandbox & Permissions | `forge.worktree`, `worktrees/`, lease file + cross-process flock | shipped at the lease layer; network egress + perm tiers not yet |
| 6 | Orchestration & Loop Control | `forge.orchestrator`, `forge.budget`, per-agent caps in prompt meta, repair loop in agent `run` | partial — `default_pipeline()` phases all `run=None`; the abstraction works (tested with wired phases) but no real phase is shipped |
| 7 | Memory & Provenance | `forge.memory.store` (L2 KV), `forge.provenance` (`.forge-trail.yaml`) | partial — L1/L3/L4 not yet; provenance PR hook not yet enforced |

## Non-negotiables

- **Every LLM call is traced.** No span, no call.
- **Every generated file should have a `.forge-trail.yaml`.** The PR hook that enforces this is not yet shipped — until it is, this is convention, not a hard gate.
- **Every agent should run inside a worktree lease.** The orchestrator's dispatch path that enforces this is not yet shipped.
- **Every prompt change goes through CI eval.** Score regression blocks merge.
- **Every budget cap is enforced before the next LLM round-trip.** Caps are loaded per-agent from prompt meta; the agent loop calls `bail_if_exhausted()` after every LLM tick.
- **No silent fallback on malformed model output.** Agents must raise `AgentOutputError` after exhausting their repair attempts, not return the input unchanged.

## What this is not

Not an LLM provider. Not an agent framework you import to "build agents". It is the floor those things sit on. Swap providers, swap agent shapes — the Harness contract stays.
