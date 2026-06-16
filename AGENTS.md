# AGENTS.md

本仓库后续主要使用 **Mimo v2.5 Pro + Claude Code** 组合完成代码实现和修复。本文档给出协作方式、执行约束和本次 Phase 0-9 实现/审核暴露出的经验。

## 项目上下文

项目目标是构建 AI-VulnAtlas 漏洞分析 Agent，对 `vuln-analyzed-0605.xlsx` 和 `ai-vulns-timeline.zip` 中的漏洞样本进行四步分析：

1. 引入版本验证
2. 模块分类
3. 漏洞模式分类
4. 利用方式和前提总结

关键输入：

```text
vuln-analyzed-0605.xlsx
ai-vulns-timeline.zip
project-module-types.md
进展文档.txt
proposal.docx
```

关键文档：

```text
docs/implementation-plan.md
docs/detailed-implementation-steps.md
docs/fix-plan-after-phase0-9-audit.md
docs/agent-mode-implementation-plan.md
```

## 分析模式

项目支持两种分析模式，通过 `ANALYSIS_MODE` 或 `--analysis-mode` 切换：

### Prompt Analysis Mode（默认）

系统拼接 prompt，LLM 返回 Markdown，程序写 step 文件。

```bash
python3 main.py run --analysis-mode prompt
```

### Agent Analysis Mode

Agent 在任务专属 worktree 中自主读代码、查 git 历史，直接写 step 文件。

```bash
# CLI backend（默认）
python3 main.py run --analysis-mode agent --agent-backend claude_code_cli

# SDK backend
python3 main.py run --analysis-mode agent --agent-backend claude_agent_sdk
```

Agent 模式配置（`.env`）：

```env
ANALYSIS_MODE=prompt
AGENT_BACKEND=claude_code_cli
AGENT_COMMAND=claude
AGENT_TIMEOUT_SECONDS=1800
```

Agent 模式约束：
- Agent 在 `worktrees/{project}_{canonical_id}_agent_intro/` 中工作
- Agent 可使用 Read/Grep/Glob 和 git show/diff/log
- Agent 只能写入 `output/{project}/{canonical_id}/` 目录
- 禁止 agent 修改源码仓库（worktree dirty 会使 task 失败）
- 每步最多执行 2 次（首次 + 1 次 repair）
- Agent trace 记录在 `output/{project}/{canonical_id}/agent_trace/`
- Agent 模式不支持 `--offline`
- 同 project 串行，多 project 可并行

## 模型分工建议

### Mimo v2.5 Pro

适合：

1. 根据详细文档生成初版代码。
2. 补齐样板文件和简单命令入口。
3. 执行明确、局部的函数修改。
4. 根据固定验收命令修小 bug。

不适合：

1. 自由设计数据结构。
2. 自行解释研究分类体系。
3. 一次性实现多个 Phase。
4. 在没有验收命令的情况下做大范围重构。

使用 Mimo 时，应给它非常具体的任务，例如：

```text
只修改 markdown_parser.py。
目标：修复 extract_bullet_value 跨行误解析。
按 docs/fix-plan-after-phase0-9-audit.md 的 Fix 2 实现。
实现后运行文档中的验收命令。
不要修改其他文件。
```

### Claude Code

适合：

1. 跨文件修改。
2. 调试命令失败。
3. 检查 output 结果质量。
4. 处理 prompt、parser、summary 之间的联动。
5. 做代码 review 和回归测试。

Claude Code 使用方式：

```text
先读 docs/fix-plan-after-phase0-9-audit.md。
只执行 Fix N。
修改前说明会改哪些文件。
修改后运行对应验收命令。
最后报告文件、命令、结果和剩余风险。
```

## 强约束

任何模型都必须遵守：

1. 不改变输入文件名。
2. 不改变 Excel 字段映射。
3. 不把项目名统一转小写。
4. 不运行目标项目代码。
5. 不运行 PoC。
6. 不安装目标项目依赖。
7. 不把 agent 输出改成 JSON。
8. 不忽略 `project-module-types.md`。
9. 不照搬 `project-module-types.md` 的 JSON 输出格式。
10. 不在同一个 repo 工作目录中并发 checkout。
11. 不一次性实现多个 Phase 或多个 Fix，除非用户明确要求。

## 已知高风险点

### 1. A/B/C 分类语义

必须使用：

```text
A = 传统类型漏洞
B = AI功能实现 + 传统方式
C = AI场景新漏洞模式
```

不要使用：

```text
A = AI Native
B = AI Amplified
C = Traditional
```

这是本次审核发现的最大统计风险。

### 2. Markdown parser

字段提取必须只在单行内匹配：

```text
- key: value
```

不要使用会跨行吞掉下一条 bullet 的 `\s*` 正则。空字段必须返回空字符串或标准化为 `none`，不能把下一行 `- cross_agent: no` 当成当前字段值。

### 3. LLM 输出必须校验

DeepSeek/Mimo/Claude 都可能：

1. 回显 prompt。
2. 忘记固定字段。
3. 输出 JSON。
4. 输出 API 错误文本。

写入 step 文件前必须校验必填字段。校验失败要重试；重试仍失败时写可解析的 failure stub。

### 4. State 统计必须去重

`state/progress.jsonl` 中每个任务至少有：

```text
running
success
```

统计 batch report 时必须按 `task_key` 只取最后一条状态。不能直接统计所有 JSONL 行。

### 5. Summary 必须由 step 文件重建

`run` 过程可能只写基础字段。可靠统计应在批量后运行：

```bash
python3 main.py rebuild-summary
```

`summary.csv` 需要从：

1. `metadata.md`
2. `01_version_verification.md`
3. `02_module_classification.md`
4. `03_vulnerability_pattern_classification.md`
5. `04_exploit_condition_summary.md`

共同提取。

## 推荐工作流

### 单个 Fix 工作流

```bash
python3 main.py preflight
# 修改代码
# 运行该 Fix 文档中的验收命令
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

### 单样本重跑工作流

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
python3 main.py rebuild-summary
python3 main.py audit-output
```

### 小批量运行工作流

```bash
python3 main.py run --max 10
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

如果 `audit-output` 发现缺字段或 prompt leakage，不要继续扩大批量。

## 给模型的任务模板

### 实现模板

```text
你要修改这个仓库。
先阅读：
- docs/detailed-implementation-steps.md
- docs/fix-plan-after-phase0-9-audit.md
- AGENTS.md

本次只实现 Fix X：<名称>。
只能修改：<文件列表>。
不要修改其他文件。
按文档中的操作步骤实现。
实现后运行验收命令。
最终报告：
- 修改了哪些文件
- 运行了哪些命令
- 命令结果
- 是否还有风险
```

### 审核模板

```text
请审核当前 Phase/Fix 的实现。
重点检查：
- 是否符合 docs/fix-plan-after-phase0-9-audit.md
- 是否违反 AGENTS.md 强约束
- output 是否有缺字段、prompt 泄漏、API error、JSON 输出
- summary.csv 和 batch_report.md 统计是否可信

请先列问题，按严重程度排序，再给修复建议。
```

## 本次审核经验总结

1. 大上下文模型能按长文档实现较多代码，但容易在分类语义上“自我改写”。分类定义必须用硬性枚举和验收断言锁住。
2. 模型生成的 parser 容易看似正确但边界错误，尤其是正则跨行问题。必须用最小反例测试。
3. LLM API 返回 200 不代表输出可用。必须做格式校验。
4. 批量状态文件不能直接按行统计，要按任务取最后状态。
5. `project-module-types.md` 这种外部 prompt 可以复用 taxonomy，但不能照搬其中与本项目冲突的 JSON 输出要求。
6. 对 Mimo v2.5 Pro 这类模型，任务要拆小到“只改一个函数/一个 Fix”。不要让它同时改 prompt、parser、summary 和 batch report。
7. Claude Code 更适合作为执行和审核闭环工具：跑命令、看 output、抽样检查、定位行号。

