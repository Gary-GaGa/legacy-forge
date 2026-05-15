# Architecture

```
                 ┌──────────────────────────────────────┐
                 │             forge CLI                │
                 └──────────────────────────────────────┘
                                 │
        ┌────────────────────────┴────────────────────────┐
        │                                                 │
┌───────▼────────┐                                ┌───────▼────────┐
│  Orchestrator  │  toposorts phases, dispatches  │ Eval Runner    │
│  (phase DAG)   │  agents into worktrees         │ (cases / CI)   │
└───────┬────────┘                                └────────────────┘
        │
        │ runs an Agent in a worktree, under a Budget,
        │ with a Tracer span and Memory handle
        ▼
┌────────────────────────────────────────────────────────────────┐
│                          Agent                                 │
│  Input (pydantic) ──► LLM call(s) ──► Tools ──► Output         │
│                       │                                        │
│                       │ every call is a child span of the      │
│                       │ agent span; every patch gets a         │
│                       │ .forge-trail.yaml sidecar              │
│                       ▼                                        │
└────────────────────────────────────────────────────────────────┘
                        │
                        ▼
                ┌──────────────────┐
                │  .forge/         │
                │  trace.sqlite    │
                │  phase-mem.db    │
                │  worktree-leases │
                └──────────────────┘
```

## Phase DAG

Default pipeline (see `forge.orchestrator.default_pipeline`):

```
p0_inventory
   └─► p1_characterize
          └─► p2_compile_upgrade   (Java 7 → 11 → 17 → 21)
                 └─► p3_framework_upgrade   (javax → jakarta, Spring Boot 3, Gradle)
                        └─► p4_api_extract  (controller → REST + OpenAPI)
                               └─► p5_angular_scaffold
                                      └─► p6_verify  (dual-run, diff)
```

Each phase is a human-approval gate. Agents fan out within a phase, but phase boundaries cross human eyes.

## Decisions worth recording

- **Python for the Harness, even though codex CLI is JS.** The Harness shells out to codex (or any LLM CLI) as a subprocess. Python wins on SQLite, subprocess, and SDK ergonomics.
- **One SQLite trace DB per project, not per run.** Cross-run analysis (which prompt regressed cost?) needs everything in one place.
- **Provenance via sidecar YAML, not in-file comments.** Comments rot; sidecars can be enforced at PR time by a hook.
- **Worktree per task, not per agent.** Agents are stateless — the worktree is the unit of isolation.
