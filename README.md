# legacy-forge

An AI-agent Harness for migrating legacy Java/JEE projects to modern Java (17/21) + Angular.

> Forge: a place where old metal is reshaped into new tools — under heat, hammer, and discipline.

## Why this exists

Legacy refactoring with AI agents fails in predictable ways: agents hallucinate APIs, drift from observed behavior, burn tokens in loops, or quietly produce "looks right" code that breaks at runtime. **legacy-forge is the scaffolding (the Harness) that makes a multi-agent refactor survivable** — not the agents themselves.

The agents that do the actual code translation (Java Lang Migrator, Framework Migrator, API Extractor, Angular Scaffolder, …) live on top of this Harness. The Harness gives them: context budgets, structured tools, evals, traces, sandboxed worktrees, multi-dimensional budget caps, memory, and a provenance trail.

## The 7 Pillars

1. **Context Engineering** — what the agent sees, in what order, within what budget
2. **Tool Ergonomics** — small structured toolboxes, dry-run by default, actionable errors
3. **Evals** — every agent ships with golden cases; prompt changes go through CI
4. **Observability** — every LLM call traced; replay any run
5. **Sandbox & Permissions** — agents work in disposable worktrees with a 3-tier permission model
6. **Orchestration** — phase DAG + per-task worktree leases, no two agents on the same file
7. **Memory & Provenance** — 4-layer memory; every generated file carries a `.forge-trail` lineage

See [docs/seven-pillars.md](docs/seven-pillars.md) for the long form.

## Status

**Skeleton.** Tracer, eval runner, worktree manager, and orchestrator scaffolding are in place; agents are stubs. The first concrete agent target is the Java Lang Migrator (Java 7 → 21 language-level rewrite) — it will exercise the full pillar set end-to-end and become the template for the rest.

## Layout

```
legacy-forge/
├── forge/                  # the Harness core
│   ├── cli.py              # `forge ...` entry point
│   ├── orchestrator.py     # phase DAG + agent dispatch
│   ├── tracer.py           # SQLite-backed LLM call trace
│   ├── worktree.py         # git worktree lease manager
│   ├── budget.py           # multi-dim budget (tokens × $ × wallclock × iter)
│   ├── provenance.py       # .forge-trail.yaml writer
│   ├── agents/             # Agent ABC + per-role agents (stubs)
│   ├── evals/              # eval runner + case schema
│   └── memory/             # L1–L4 memory layers
├── prompts/                # versioned prompts (one dir per agent)
├── evals/                  # golden cases & fixtures (test data, not code)
├── cookbook/               # migration knowledge: javax→jakarta, deprecated APIs, …
├── docs/                   # architecture, runbook, seven pillars
└── tests/                  # Harness self-tests
```

## Quick start

```powershell
# Requires Python 3.11+
pip install -e .

forge --help
forge trace ls
forge worktree create my-task
forge eval run java-lang-migrator
```

## Not yet implemented

This is the bare skeleton. The following are stubs awaiting a target codebase:

- Concrete agent implementations (the 10 agents from the design doc)
- LLM provider adapters beyond the trace shape
- Network egress whitelist (sandbox layer)
- CI workflow (eval-as-code) — wired structurally, no real cases yet
- Cookbook content beyond the javax→jakarta seed

## License

TBD.
