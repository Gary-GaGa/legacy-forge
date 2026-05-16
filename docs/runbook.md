# Runbook

Operational playbook for humans running legacy-forge.

## First-time setup

```powershell
# Python 3.10+
pip install -e ".[dev]"

# Smoke test
forge --version
forge phases
```

## Starting a refactor

1. Clone the legacy repo somewhere else; do NOT put it inside `legacy-forge/`.
2. Configure target legacy path in `.forge/config.yaml` (not yet implemented — coming with the first concrete agent).
3. Run phase 0 manually first; review the inventory before unleashing later phases.

## When something goes wrong

| Symptom | First check |
|---------|------------|
| Agent appears stuck | `forge trace ls` → look for runs with `errors > 0` or wallclock blown |
| Cost spike | `forge trace ls` → which run, which agent; check prompt version |
| File mysteriously modified | look for sibling `<file>.forge-trail.yaml` — agent + prompt version + source refs |
| Worktree won't delete | `forge worktree gc` to reclaim stale leases |
| Eval suddenly fails after prompt change | revert prompt, re-run eval to confirm; bisect the prompt diff |

## Don't

- Don't manually edit `.forge/trace.sqlite` — break replay, break audit.
- Don't commit `.forge/`, `worktrees/`, or any `.forge-trail.yaml` from a worktree that wasn't reviewed.
- Don't raise budget caps to "just get this run through". Find the actual blocker.

---

# Runbook（繁體中文）

給人類操作 legacy-forge 的實戰手冊。

## 首次設定

```powershell
# 需要 Python 3.10+
pip install -e ".[dev]"

# 煙霧測試（驗證骨架沒爛）
forge --version
forge phases
```

## 開始一個 refactor

1. **舊 repo 放在 `legacy-forge/` 之外的目錄** — 不要把舊 codebase clone 進來，避免 agent 視野污染與 git 混淆
2. 在 `.forge/config.yaml` 設定舊 repo 的路徑（功能還沒做，會跟第一個 agent 一起上）
3. **Phase 0 一定要先手動跑** — 看完 inventory 報告再放後面的 phase 出去。Inventory 看錯，後面全錯

## 出事時的優先順序

| 症狀 | 第一個該看的地方 |
|------|----------------|
| Agent 看起來卡住了 | `forge trace ls` → 找 `errors > 0` 或 wallclock 爆掉的 run |
| 帳單突然飆高 | `forge trace ls` → 哪個 run、哪個 agent；對照 prompt 版本 |
| 檔案被神秘修改 | 看旁邊的 `<檔名>.forge-trail.yaml` — agent、prompt 版本、source 出處全在裡面 |
| Worktree 刪不掉 | `forge worktree gc` 回收殭屍 lease |
| 改完 prompt 後 eval 突然爛掉 | 立刻 revert prompt 確認、然後 bisect prompt diff 找出兇手 |
| 多個 agent 想動同一個檔 | 不該發生 — worktree lease 應該擋住。檢查 `forge worktree ls` |

## Eval 守門流程（**改 prompt 前必看**）

1. **改之前**：`forge eval run <agent>` → 記下 pass rate（例：18/20）
2. 改 prompt
3. **改之後**：再跑一次 → 比較分數
4. 退步就 revert，**不要** debug LLM「為什麼這個 case 失敗」— 那條路會把你吸進去三天
5. 如果新 prompt 確實該過 case，反而是該補 case 不是改 prompt

## 千萬不要

- **不要手動編輯 `.forge/trace.sqlite`** — replay 與 audit trail 立刻爛掉
- **不要 commit `.forge/`、`worktrees/`、任何沒人 review 過的 `.forge-trail.yaml`**
- **不要為了「先讓這個 run 過」而調高 budget 上限** — 那個爆 budget 的根因會回來咬你
- **不要為了「先讓這個 case 過」而改 prompt** — 改 case 或承認 agent 不適合這個 case，比污染 prompt 健康
- **不要砍掉舊版 prompt** — 過去的 trace 還 reference 著它，砍了 replay 立刻死
- **不要在主分支上直接讓 agent 動工** — 開 worktree，搞砸了就 release，乾淨
