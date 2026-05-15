# Cookbook

Structured migration knowledge. **Lookup tables, not RAG-only** — for deterministic transforms (javax→jakarta, Date→LocalDateTime, etc.) we want exact matches, not similarity search.

Each entry has:
- a stable id
- `last_updated` (cookbook entries decay; flag stale ones)
- `confidence` (high / medium / low — affects whether the agent can apply without human review)
- a machine-readable rule + a human note explaining the *why*

## Files

- `javax-to-jakarta.md` — namespace migration for Jakarta EE 9+
- (more coming as concrete agents land)

## Adding an entry

Keep entries small. One transform per entry. If you find yourself writing prose, it belongs in `docs/` not here.
