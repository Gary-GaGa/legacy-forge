# Evals

Golden cases for every agent. Without these the Harness has no idea whether a prompt change made things better or worse.

## Layout

```
evals/
├── fixtures/           # input artefacts (legacy code snippets, JSPs, …)
│   └── struts_action_simple.java
└── cases/
    └── <agent-name>/
        └── <case-id>.yaml
```

Case schema lives in `forge/evals/case.py`.

## What makes a good case

- **Small.** A case should fit in a screen. Big fixtures hide bugs.
- **Targeted.** Each case asserts ONE behaviour. Stack them, don't combine.
- **Both happy and adversarial.** "What if the import is already jakarta?" is as important as "what if it's javax?"
- **Stable.** Don't depend on LLM creativity in the expected output — assert structural properties (contains / not_contains / compiles).

## Target counts

| Agent | Min cases before unleashing on real code |
|-------|-----------------------------------------|
| Java Lang Migrator | 20 |
| Framework Migrator | 30 (more permutations) |
| API Extractor | 15 |
| Angular Scaffolder | 15 |

These are minimums, not targets.
