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

**Skeleton + first agent.** The Harness (tracer, eval runner, worktree manager, orchestrator, budget, provenance, memory) is in place AND the first concrete agent — **Java Lang Migrator** — is wired through it end-to-end, exercising every pillar.

Today's `forge eval run java-lang-migrator --provider echo` runs the agent end-to-end with the `EchoProvider` wiring stub. The eval cases assert structural properties (class/package preserved, no spurious `jakarta.` drift) that are provider-agnostic, so the same cases stay meaningful when a real provider replaces echo. **Echo is not a model and produces no real eval signal** — the CLI prints a warning to that effect when `--provider echo` is selected. To run against real models, fill in `forge/llm/codex.py::CodexProvider._invoke_codex` with your verified `codex` CLI invocation, then `forge eval run java-lang-migrator --provider codex`. Real-migration assertion cases (java.time, try-with-resources, multi-catch, lambda) get added once the real provider is live.

## Layout

```
legacy-forge/
├── forge/                  # the Harness core
│   ├── cli.py              # `forge ...` entry point
│   ├── orchestrator.py     # phase DAG + agent dispatch
│   ├── tracer.py           # SQLite-backed LLM call trace
│   ├── worktree.py         # git worktree lease manager (cross-process flock)
│   ├── budget.py           # multi-dim budget (tokens × $ × wallclock × iter)
│   ├── provenance.py       # .forge-trail.yaml writer
│   ├── agents/             # Agent ABC + per-role agents (stubs)
│   ├── evals/              # eval runner + case schema
│   └── memory/             # L2 phase KV store (L1/L3/L4 planned, not yet shipped)
├── prompts/                # versioned prompts (one dir per agent)
├── evals/                  # golden cases & fixtures (test data, not code)
├── cookbook/               # migration knowledge: javax→jakarta, deprecated APIs, …
├── docs/                   # architecture, runbook, seven pillars
└── tests/                  # Harness self-tests
```

## Quick start

```powershell
# Requires Python 3.10+
pip install -e .

forge --help
forge trace ls
forge worktree create my-task
forge eval run java-lang-migrator
```

## 快速開始（繁體中文）

> 需要 Python 3.10+ 與 git。Windows 使用者建議把 `C:\Program Files\GitHub CLI` 加到使用者 PATH。

### 安裝

```powershell
# clone 下來之後
cd legacy-forge

# 安裝套件（含開發依賴：pytest、ruff、mypy）
pip install -e ".[dev]"

# 驗證骨架沒爛
pytest -q
forge --version
```

### 常用指令

| 指令 | 用途 |
|------|------|
| `forge --help` | 看所有可用指令 |
| `forge phases` | 顯示預設的七階段 refactor pipeline（含相依關係） |
| `forge trace ls` | 列出最近的 run，看 token、$、錯誤數 |
| `forge trace ls --limit 50` | 看更多歷史 run |
| `forge worktree create <名稱>` | 開一個獨立 worktree 給某個 agent 工作 |
| `forge worktree ls` | 看目前所有 worktree lease 與到期時間 |
| `forge worktree release <名稱>` | 收掉一個 worktree（刪 branch + 目錄） |
| `forge worktree gc` | 回收過期的 lease（程式掛了會留下殭屍 worktree） |
| `forge eval ls` | 列出所有 eval case |
| `forge eval ls <agent>` | 只看某個 agent 的 case |
| `forge eval run <agent>` | 跑某個 agent 的 eval suite |
| `forge llm probe --provider codex` | 一鍵驗證 codex CLI 從 Python 通得到（debug 用） |

### 接 codex CLI（Windows / 企業內網訂閱版）

如果你的 Windows 環境只能用 codex CLI（無法直接打 OpenAI API token），不用改 `forge/llm/codex.py`，環境變數設一設就好：

```powershell
# 必要：codex 在 PowerShell 裡叫做 codex.cmd，要明指
$env:FORGE_CODEX_BIN = "codex.cmd"

# 可選：你的 codex 版本可能用別的 flag。先用 probe 試跑
$env:FORGE_CODEX_MODEL = "gpt-5-codex"
# 如果你的 codex 不吃 --model，就把這個 flag 拿掉
# $env:FORGE_CODEX_MODEL_FLAG = ""

# 先驗證 Python -> codex 接通
forge llm probe --provider codex --prompt "Reply with: OK"

# 通了之後跑真的 eval
forge eval run java-lang-migrator --provider codex
```

支援的環境變數：

| Env var | 預設 | 用途 |
|---|---|---|
| `FORGE_CODEX_BIN` | `codex` | binary 路徑（Windows 通常要 `codex.cmd`） |
| `FORGE_CODEX_MODEL` | `gpt-5-codex` | model 名稱 |
| `FORGE_CODEX_MODEL_FLAG` | `--model` | 怎麼指定 model；設成空字串就完全不傳 flag |
| `FORGE_CODEX_SUBCMD` | `exec` | codex 的非互動子指令 |
| `FORGE_CODEX_EXTRA` | (無) | 額外 args（空白分隔） |
| `FORGE_CODEX_TIMEOUT` | `600` | 單次 LLM call 的逾時秒數 |

**怎麼除錯**：`forge llm probe` 印出失敗原因的完整 stderr。常見：
- `codex CLI not found` → `FORGE_CODEX_BIN` 沒設或 PATH 沒過去
- `codex exited 2: auth failed` → 先在那台機器跑一次 `codex login`
- `codex timed out` → prompt 太長或 codex 卡 thinking；調高 `FORGE_CODEX_TIMEOUT`

### 典型工作流程

1. **每次開始新 task** → `forge worktree create <task-name>`，agent 在隔離的 worktree 裡動工，搞砸了 `release` 就乾淨收掉
2. **改 prompt 之前** → 先跑 `forge eval run <agent>` 記下 pass rate
3. **改 prompt 之後** → 再跑一次，分數退步就回頭
4. **怪事發生時**：
   - 看 `forge trace ls` 找出可疑的 run
   - 看可疑檔案旁邊的 `*.forge-trail.yaml`（哪個 agent、哪個 prompt 版本、源自哪裡）
   - 如果 worktree 卡住 → `forge worktree gc`

### Runtime 狀態檔（都已在 `.gitignore`）

| 路徑 | 內容 |
|------|------|
| `.forge/trace.sqlite` | 所有 LLM call 與 tool call 的 trace（replay 用） |
| `.forge/worktree-leases.json` | 目前哪些 worktree 被誰租走 |
| `worktrees/<name>/` | agent 實際工作的隔離目錄 |

**禁止手動編輯 `.forge/trace.sqlite`** — 一動就破壞 replay 與 audit trail。

### 完整使用情境見 [docs/runbook.md](docs/runbook.md)；架構流程圖見 [docs/architecture.md](docs/architecture.md)

## Not yet implemented

- 9 of 10 agents (Inventory, Characterizer, Framework Migrator, API Extractor, UI Mapper, Angular Scaffolder, Test Translator, Equivalence Verifier, Refactor Reviewer)
- `CodexProvider._invoke_codex` (stub raises NotImplementedError until wired)
- `forge agent run-on-file <path>` — runs an agent on a real file with worktree + provenance trail. Eval path works today; production path coming next.
- Orchestrator phase callables — `default_pipeline()` ships 7 phases, all `run=None`. Orchestrator runs (skips them all); `forge phases` shows a `wired` column flagging this.
- Memory layers L1 (working), L3 (semantic), L4 (cookbook retrieval) — only L2 (phase KV store) ships today.
- `expect.compiles` in eval cases — schema field exists but the runner ignores it; needs a javac sandbox.
- Provenance PR hook that rejects generated files without a `.forge-trail.yaml`.
- Network egress whitelist (sandbox layer)
- Cookbook beyond the javax→jakarta seed

## License

TBD.
