# Prompts

Prompts are code. They live here, versioned alongside the agent that uses them.

## Layout

```
prompts/
└── <agent-name>/
    ├── v1.md          # the prompt body
    ├── v1.meta.yaml   # model, temperature, expected I/O schema reference
    └── v2.md          # supersedes v1; v1 stays for replay
```

## Rules

- **Never delete a prompt version.** Past traces reference them by id.
- **A prompt change is a PR.** CI must run the agent's eval suite; regression blocks merge.
- **Variables use `{{name}}`.** The Harness fills them at render time — no `f""` formatting inside prompt files.
- **The system block is stable; the user block is dynamic.** Keep stable content first so the prompt cache stays warm.

The first concrete prompt will live at `prompts/java-lang-migrator/v1.md`.
