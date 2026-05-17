"""Git worktree lease manager.

Pillar 5 (Sandbox). Every agent task runs in its own disposable worktree so
agents cannot stomp on each other's changes, and we can throw away a botched
run by removing one directory.

We add a thin lease layer on top of `git worktree`:
- A worktree has an owner_id (agent that holds it) and an expires_at timestamp.
- Stale leases (process died, machine crashed) can be reclaimed by the next
  caller that asks for that path.
- The lease state lives in .forge/worktree-leases.json next to the repo.

This file deliberately avoids importing GitPython — `git` on PATH is the
contract, and shelling out is more predictable for worktree ops.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import time
import uuid
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import fcntl  # POSIX
except ImportError:   # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]


class WorktreeError(RuntimeError):
    pass


@dataclass
class Lease:
    name: str
    path: str
    branch: str
    owner_id: str
    acquired_at: float
    expires_at: float


class WorktreeManager:
    def __init__(self, repo_root: Path, base_dir: Path | None = None):
        self.repo_root = repo_root.resolve()
        self.base_dir = (base_dir or self.repo_root / "worktrees").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir = self.repo_root / ".forge"
        self._state_dir.mkdir(exist_ok=True)
        self._leases_path = self._state_dir / "worktree-leases.json"
        self._lock_path = self._state_dir / "worktree-leases.lock"

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """Cross-process lock around the leases file.

        Uses fcntl.flock on POSIX; degrades to no-op on platforms without
        fcntl (Windows). Concurrent `create` / `release` / `gc` calls from
        different processes will serialize on this lock so the underlying
        JSON file never sees a torn read-modify-write.
        """
        self._lock_path.touch(exist_ok=True)
        with open(self._lock_path, "r+") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def create(
        self,
        name: str,
        *,
        base_ref: str = "HEAD",
        owner_id: str | None = None,
        ttl_seconds: int = 60 * 60 * 4,
    ) -> Lease:
        with self._locked():
            leases = self._load_leases()
            if name in leases and not self._is_stale(leases[name]):
                raise WorktreeError(
                    f"worktree '{name}' is already leased by {leases[name].owner_id}"
                )

            path = self.base_dir / name
            branch = f"forge/{name}"
            if path.exists():
                self._git("worktree", "remove", "--force", str(path), check=False)

            self._git("worktree", "add", "-b", branch, str(path), base_ref)

            now = time.time()
            lease = Lease(
                name=name,
                path=str(path),
                branch=branch,
                owner_id=owner_id or str(uuid.uuid4()),
                acquired_at=now,
                expires_at=now + ttl_seconds,
            )
            leases[name] = lease
            self._save_leases(leases)
            return lease

    def release(self, name: str, *, delete_branch: bool = True) -> None:
        with self._locked():
            leases = self._load_leases()
            if name not in leases:
                return
            lease = leases[name]
            self._git("worktree", "remove", "--force", lease.path, check=False)
            if delete_branch:
                self._git("branch", "-D", lease.branch, check=False)
            del leases[name]
            self._save_leases(leases)

    def list(self) -> list[Lease]:
        with self._locked():
            return list(self._load_leases().values())

    def gc(self) -> list[str]:
        """Reclaim stale leases. Returns names of reclaimed worktrees."""
        with self._locked():
            leases = self._load_leases()
            reclaimed: list[str] = []
            for name, lease in list(leases.items()):
                if self._is_stale(lease):
                    self._git("worktree", "remove", "--force", lease.path, check=False)
                    self._git("branch", "-D", lease.branch, check=False)
                    del leases[name]
                    reclaimed.append(name)
            self._save_leases(leases)
            return reclaimed

    @staticmethod
    def _is_stale(lease: Lease) -> bool:
        return time.time() > lease.expires_at

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise WorktreeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def _load_leases(self) -> dict[str, Lease]:
        if not self._leases_path.exists():
            return {}
        raw = json.loads(self._leases_path.read_text(encoding="utf-8"))
        return {name: Lease(**data) for name, data in raw.items()}

    def _save_leases(self, leases: dict[str, Lease]) -> None:
        self._leases_path.write_text(
            json.dumps({name: asdict(l) for name, l in leases.items()}, indent=2),
            encoding="utf-8",
        )
