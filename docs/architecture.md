# Architecture

三張圖，由外往內看。Mermaid 寫的，GitHub 上自動 render。

---

## 1. 全景 — 誰在哪一層

```mermaid
flowchart TB
    User["你 / CI"]

    subgraph FORGE["legacy-forge — 紀律層 (Python)"]
        direction TB
        CLI["forge CLI<br/>forge/cli.py"]
        Agents["Agents · forge/agents/<br/>★ JavaLangMigrator · 9× TODO"]

        subgraph PILLARS["Cross-cutting pillars"]
            direction LR
            T["Tracer<br/>SQLite"]
            B["Budget<br/>caps + tick"]
            W["Worktree<br/>lease + flock"]
            E["EvalRunner<br/>score()"]
            P["Provenance<br/>.forge-trail.yaml"]
            M["Memory L2<br/>phase KV"]
        end

        subgraph PROTO["Provider Protocol · forge/llm/"]
            direction LR
            Echo["EchoProvider<br/>wiring stub"]
            Codex["CodexProvider<br/>subprocess"]
        end

        CLI --> Agents
        Agents --> PILLARS
        Agents --> PROTO
    end

    CodexCLI["codex.cmd — 思考引擎<br/>多輪 loop · file/shell tools · 訂閱 auth"]
    API["OpenAI 後端<br/>gpt-5-codex"]

    User -->|forge eval run| CLI
    Codex -.->|subprocess<br/>stdin / stdout| CodexCLI
    CodexCLI -.->|HTTPS · codex 自己管| API

    style Codex fill:#fef3c7,stroke:#f59e0b
    style CodexCLI fill:#fef3c7,stroke:#f59e0b
    style API fill:#fef3c7,stroke:#f59e0b
```

**讀法**：
- **forge** = 紀律層。它不會自己「想」，但負責**測 / 記 / 限 / 稽核**。
- **codex CLI** = 思考引擎。它不會自己**記**（不知道你昨天跑過什麼、預算剩多少、要不要寫 trail）。
- **Provider Protocol** 是兩者之間的薄玻璃。換 codex 換 Anthropic SDK 換本地模型，只動 `forge/llm/<新>.py`，agent 跟 pillars 不知道。

---

## 2. 跑起來 — 時間線

`forge eval run java-lang-migrator --provider codex` 從按下到完成的呼叫序列：

```mermaid
sequenceDiagram
    autonumber
    actor User as 你
    participant CLI as forge CLI
    participant Agent as JavaLangMigrator
    participant Tracer
    participant Budget
    participant Provider as CodexProvider
    participant Codex as codex.cmd

    User->>CLI: forge eval run ... --provider codex
    CLI->>CLI: 載入 prompts/.../v1.md + v1.meta.yaml
    CLI->>Tracer: 開 .forge/trace.sqlite
    CLI->>Budget: 從 meta 載 caps (5 iter, $0.50, 180s)

    loop 每個 eval case
        CLI->>Agent: run(ctx, input)
        Agent->>Tracer: span("agent")

        loop attempt 0..2 (initial + 2 repair)
            Agent->>Tracer: span("llm", complete[N])
            Agent->>Provider: complete(messages)
            Provider->>Codex: subprocess.run(stdin=prompt)
            Codex-->>Provider: stdout (回應文字)
            Provider-->>Agent: CompletionResponse
            Agent->>Tracer: record prompt + response
            Agent->>Budget: tick(tokens, $)
            Budget->>Budget: bail_if_exhausted (超 cap 立刻中止)

            alt 抓到 java fenced block
                Note over Agent: return Output, 跳出 loop
            else 沒抓到
                Note over Agent: append repair msg → 回頂部再試
            end
        end

        Agent-->>CLI: Output or AgentOutputError
        CLI->>CLI: score(output, case.expect)
    end

    CLI->>User: 表格 + budget snapshot
```

關鍵：
- **每個 LLM call 一個 span**：trace 可以 replay、可以 diff prompt 版本。
- **每個 call 都 tick budget**：超就 raise，不會「再試一次就好」。
- **repair loop 內建在 agent**：模型回錯格式不會 silently fallback 到原 source，2 次 retry 後 `AgentOutputError`。

---

## 3. 7-phase pipeline — 終局

`default_pipeline()` 的 DAG。今天只有 p2 是 wired，其他是 phase placeholder（`forge phases` 顯示 `wired=no`）。

```mermaid
flowchart TB
    Input["legacy Java 7 codebase"]

    p0["p0 inventory<br/>掃 module / dep"]
    p1["p1 characterize<br/>生 golden tests"]
    p2["★ p2 compile upgrade<br/>Java 7 → 21<br/>JavaLangMigrator"]
    p3["p3 framework migrate<br/>javax → jakarta<br/>Ant → Gradle"]
    p4["p4 api extract<br/>controllers → OpenAPI"]
    p5["p5 ng scaffold<br/>JSP → Angular"]
    p6["p6 verify<br/>strangler-fig dual-run"]

    Output["modern Java 21 + Angular + REST<br/>＋ .forge-trail.yaml 每檔"]

    Input --> p0 --> p1 --> p2 --> p3 --> p4 --> p5 --> p6 --> Output

    classDef done fill:#86efac,stroke:#16a34a,stroke-width:2px
    classDef todo fill:#f3f4f6,stroke:#9ca3af,stroke-dasharray:5 5
    classDef io fill:#fef3c7,stroke:#f59e0b

    class p2 done
    class p0,p1,p3,p4,p5,p6 todo
    class Input,Output io
```

每個 phase 都是一個 human-approval gate：agent 在 phase 內 fan out，phase 邊界要過人眼。

每個 phase box 內，forge 都會包這些東西：

| Pillar | 該 phase 拿到什麼 |
|---|---|
| Tracer | 該 phase 跑了幾次 LLM、燒了多少 token / $ |
| Budget | 超就停（每 phase 自己的 cap） |
| Worktree | 在自己 git worktree 動，搞砸不污染 main |
| Memory L2 | 讀上游 phase 留的 artifact（例：p0 算的 module 清單） |
| Provenance | 給每個生成檔寫 `.forge-trail.yaml` |
| EvalRunner | 該 phase 自己的 golden cases，pass rate 守底線 |

---

## TL;DR

```
codex = 「想」
forge = 「記得想過什麼 + 限制怎麼想 + 證明想對了」
```

兩者 orthogonal。換掉 codex 不會動 forge，換掉 forge 不會動 codex。Windows + 訂閱 codex CLI 的情境，只是把 forge 的 Provider Protocol 透過 subprocess 接到 `codex.cmd` —— 見 [README 的「接 codex CLI」一節](../README.md)。

---

## Decisions worth recording

幾個寫死在這個專案 DNA 裡的設計選擇，後來想改之前先看這裡：

- **Python harness，即使 codex CLI 是 JS。** Harness 透過 subprocess 呼叫 codex（或任何 LLM CLI）。Python 在 SQLite、subprocess、SDK ergonomics 上贏面比較大。
- **每個專案一份 SQLite trace DB，不是每 run 一份。** Cross-run 分析（哪次 prompt 改動讓 cost 上升？）需要全部在同一個地方。
- **Provenance 用 sidecar YAML，不寫在檔案裡。** 註解會 rot；sidecar 可以在 PR hook 強制檢查。
- **Worktree per task，不是 per agent。** Agent 是 stateless，worktree 才是隔離單位。
- **Provider Protocol 用 `list[Message]` 不是單字串。** 多輪 tool-using agent 來的那天，這層不用再破協議。
- **Agent 失敗就 raise，不 silent fallback。** 之前的 `extract_java_block(text) or inp.source_code` bug 教訓 —— silent fallback 讓 eval falsely PASS，比沒有 eval 還糟。

更深的設計理由見 [seven-pillars.md](seven-pillars.md)；日常操作見 [runbook.md](runbook.md)。
