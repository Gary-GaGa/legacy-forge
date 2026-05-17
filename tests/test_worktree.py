"""Worktree manager tests.

Cover the lease-locking layer without requiring a fully-configured git
remote. Uses `git init` in tmp_path so `git worktree add` actually works.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from forge.worktree import WorktreeError, WorktreeManager


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README").write_text("seed\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=repo,
        check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
             "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def test_create_release_roundtrip(tmp_path: Path):
    _init_git(tmp_path)
    wm = WorktreeManager(tmp_path)
    lease = wm.create("task-a")
    assert Path(lease.path).exists()
    assert lease.name == "task-a"

    leases = wm.list()
    assert [lease.name for lease in leases] == ["task-a"]

    wm.release("task-a")
    assert wm.list() == []
    assert not Path(lease.path).exists()


def test_duplicate_lease_raises_while_active(tmp_path: Path):
    _init_git(tmp_path)
    wm = WorktreeManager(tmp_path)
    wm.create("task-a")
    with pytest.raises(WorktreeError):
        wm.create("task-a")
    wm.release("task-a")


def test_gc_reclaims_stale_lease(tmp_path: Path):
    _init_git(tmp_path)
    wm = WorktreeManager(tmp_path)
    wm.create("task-a", ttl_seconds=-1)   # already stale
    reclaimed = wm.gc()
    assert reclaimed == ["task-a"]
    assert wm.list() == []


def test_concurrent_creates_serialize(tmp_path: Path):
    """Two threads racing on create(name='same') must not both succeed.

    Without the lock the JSON read-modify-write would race and possibly
    leave both leases or a torn file. With the lock, exactly one wins
    and the other raises WorktreeError.
    """
    _init_git(tmp_path)
    wm = WorktreeManager(tmp_path)

    results: list[Exception | str] = []

    def worker(name: str) -> None:
        try:
            lease = wm.create(name)
            results.append(lease.name)
        except Exception as e:   # noqa: BLE001 - test capture
            results.append(e)

    t1 = threading.Thread(target=worker, args=("task-a",))
    t2 = threading.Thread(target=worker, args=("task-a",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if isinstance(r, str)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], WorktreeError)

    wm.release("task-a")
