"""Provenance trail writer.

Pillar 7. Every generated file gets a sibling `.forge-trail.yaml` that records:
- which agent produced it
- which prompt version
- which model
- which source files / commits it derived from
- which verifiers it passed

The trail makes "AI wrote this — but on what basis?" answerable months later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml


@dataclass
class Trail:
    target_path: str
    agent: str
    prompt_version: str
    model: str
    run_id: str
    source_refs: list[str] = field(default_factory=list)        # e.g. ["legacy@abc1234:src/Foo.java#L10-90"]
    verifiers_passed: list[str] = field(default_factory=list)   # e.g. ["compile", "characterization", "diff-equivalence"]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def write_trail(trail: Trail, *, sidecar_dir: Path | None = None) -> Path:
    target = Path(trail.target_path)
    sidecar = (sidecar_dir or target.parent) / f"{target.name}.forge-trail.yaml"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(yaml.safe_dump(asdict(trail), sort_keys=False), encoding="utf-8")
    return sidecar


def read_trail(sidecar_path: Path) -> Trail:
    data = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    return Trail(**data)
