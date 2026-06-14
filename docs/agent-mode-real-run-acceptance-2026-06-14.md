# Agent Mode 真实运行验收记录（2026-06-14）

## 1. 验收目标

本次验收目标不是代码静态检查，而是验证 `Agent Analysis Mode` 在真实运行环境中是否能：

1. 调用 `claude_code_cli` 完成 4 个 step 分析。
2. 让 agent 直接写入正式 step 文件。
3. 生成可被 `rebuild-summary` 和 `audit-output` 正常处理的输出。
4. 与现有 `workflow/prompt` 模式做同批样本对比。

本次样本固定为 10 条：

```text
0xKoda_WireMCP CVE-2026-3959
AstrBotDevs_AstrBot CVE-2025-48957
AstrBotDevs_AstrBot CVE-2025-55449
AstrBotDevs_AstrBot CVE-2025-57697
AstrBotDevs_AstrBot CVE-2025-57698
AstrBotDevs_AstrBot CVE-2026-6117
AstrBotDevs_AstrBot CVE-2026-6118
AstrBotDevs_AstrBot CVE-2026-6119
AstrBotDevs_AstrBot CVE-2026-6984
AstrBotDevs_AstrBot CVE-2026-7579
```

## 2. 实际执行情况

### 2.1 Workflow 模式

使用 `prompt/workflow` 模式对上述 10 条样本做了真实重跑。

结果：

1. 10/10 任务完成。
2. `python3 main.py rebuild-summary` 成功。
3. `python3 main.py audit-output` 结果为：

```text
0 missing files
0 missing fields
0 leakage
0 API errors
0 JSON output
```

基线快照已保存到：

```text
compare_runs/2026-06-14/workflow/
```

### 2.2 Agent 模式

开始对同一批任务做真实 `agent` 模式重跑，但在第 1 条样本：

```text
0xKoda_WireMCP / CVE-2026-3959
```

就暴露出确定性阻断问题，因此没有继续盲跑后续 9 条。

原因：

1. `step1` 首次失败后 repair 仍失败，最终写入 stub。
2. `step2` 同样首次失败后 repair 仍失败，最终写入 stub。
3. `step3` 长时间卡在 Claude CLI 子进程中，最终人工中断。

结论：当前 `Agent Analysis Mode` **未通过真实运行验收**。

## 3. 关键证据

### 3.1 step1 并不是“分析失败”，而是“没有拿到写权限”

`step1_run.json` 显示：

```json
{
  "backend": "claude_code_cli",
  "step_name": "step1",
  "returncode": 0,
  "success": true,
  "fail_reason": null
}
```

文件：

```text
output/0xKoda_WireMCP/CVE-2026-3959/agent_trace/step1_run.json
```

但 `step1_stdout.txt` 明确写出：

```text
The output file is waiting for write permission. Please grant permission to write to
/home/lqs/ai_vuln/output/0xKoda_WireMCP/CVE-2026-3959/01_version_verification.md
```

文件：

```text
output/0xKoda_WireMCP/CVE-2026-3959/agent_trace/step1_stdout.txt
```

说明：

1. Claude CLI 已经完成分析。
2. Claude CLI 没有报错退出。
3. 但 CLI 没有真正执行文件写入。
4. 分析结果只出现在 stdout，中间层随后因为正式 step 文件不存在而走了 stub。

最终 `01_version_verification.md` 内容是 stub：

```text
## Conclusion
- intro_time_verdict: not_verifiable
- vuln_exists_at_intro_version: insufficient_evidence
- manual_review_needed: yes
```

而 workflow 基线对应文件中，真实结果是：

```text
## Conclusion
- intro_time_verdict: correct
- vuln_exists_at_intro_version: yes
- manual_review_needed: no
```

对比文件：

```text
compare_runs/2026-06-14/workflow/output/0xKoda_WireMCP/CVE-2026-3959/01_version_verification.md
output/0xKoda_WireMCP/CVE-2026-3959/01_version_verification.md
```

### 3.2 step2 也是同样的问题

`step2_stdout.txt` 明确写出：

```text
由于文件写入权限问题，请允许我将结果写入 output 目录
```

文件：

```text
output/0xKoda_WireMCP/CVE-2026-3959/agent_trace/step2_stdout.txt
```

而 `step2_run.json` 仍是：

```json
{
  "backend": "claude_code_cli",
  "step_name": "step2",
  "returncode": 0,
  "success": true,
  "fail_reason": null
}
```

因此当前逻辑存在“CLI 返回 0，但真实 step 文件没写出来”的情况。

### 3.3 中断运行后会留下混合结果

在本次验收中，`step3` 人工中断后，任务目录中出现了这种状态：

```text
01_version_verification.md      存在（agent stub）
02_module_classification.md     存在（agent stub）
03_vulnerability_pattern_classification.md  不存在
04_exploit_condition_summary.md 存在（旧文件残留）
final_case_summary.md           存在（旧文件残留）
```

说明当前实现还有一个次级问题：

1. Agent 模式开始任务时，没有先清空该任务目录中已有的 4 个 step 文件和 `final_case_summary.md`。
2. 如果任务在中途失败或被人工中断，后续 step 可能残留 workflow 旧结果，污染对比结论。

## 4. 根因判断

根因已经比较明确，不是分析逻辑本身，而是 **Claude CLI 权限模式没有真正允许非交互写文件**。

当前实现：

```text
claude -p
--allowedTools Read Grep Glob Bash(git show*) Bash(git diff*) Bash(git log*) Write(...)
--add-dir <workspace>
--add-dir <output_dir>
--add-dir <data_dir>
```

但真实表现说明：

1. `--allowedTools Write(...)` 不足以让 CLI 在当前会话中自动完成写入。
2. 当前会话仍然处于“需要额外授予编辑权限”的模式。
3. CLI 把结果打印到 stdout，并等待写入权限，而不是直接调用 `Write` 工具完成落盘。

本地 `claude --help` 可见：

```text
--permission-mode <mode>
(choices: "acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")
```

因此当前最可能缺失的是 **显式设置合适的 `--permission-mode`**。

## 5. 给 Mimo 的具体修复方案

本节是后续交给 Mimo 的执行说明。要求按顺序修改，不要自由发挥。

### 5.1 修复目标

目标不是重写 Agent 架构，而是让当前 `claude_code_cli` 版本在真实环境中：

1. 能直接把 step 结果写到正式 Markdown 文件。
2. 不再出现“stdout 有结果，但 step 文件没写入”的情况。
3. 任务中断时不残留旧 step 文件污染对比。

### 5.2 只允许修改的文件

```text
agent_runner.py
agent_analyzer.py
config.py
main.py
CLAUDE.md
AGENTS.md
docs/agent-mode-implementation-plan.md
```

不要修改其他文件。

### 5.3 修改 1：为 Claude CLI 增加显式 permission mode

在 `config.py` 中新增：

```python
agent_permission_mode: str = "acceptEdits"
```

并支持：

```text
AGENT_PERMISSION_MODE
--agent-permission-mode
```

第一版默认值使用：

```text
acceptEdits
```

不要使用：

```text
bypassPermissions
--dangerously-skip-permissions
--allow-dangerously-skip-permissions
```

原因：

1. 项目要求第一版不能给 agent 无限权限。
2. 本次问题不是需要完全跳过权限系统，而是要让允许的写入动作被正常批准。

### 5.4 修改 2：在 `ClaudeCodeCliRunner._build_command()` 中传入 permission mode

把命令构造改成类似：

```python
cmd = [
    self.agent_command,
    "-p",
    "--permission-mode",
    self.config.agent_permission_mode,
    "--allowedTools",
    "Read",
    "Grep",
    "Glob",
    "Bash(git show*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    f"Write({request.output_dir}/**)",
]
```

要求：

1. 仍保留现有 `Write(...)` 路径限制。
2. 仍保留 `--add-dir`。
3. 不允许删除现有读目录限制。

### 5.5 修改 3：把“等待写权限”识别为显式失败，而不是普通格式失败

当前 `step1_run.json` 是 `success=true`，但 stdout 已经说明写权限不足。

需要在 `agent_runner.py` 或 `agent_analyzer.py` 中增加检测逻辑：

如果 stdout 或 stderr 包含以下模式之一：

```text
waiting for write permission
grant permission to write
文件写入权限问题
请允许我将结果写入
```

则该 step 应视为：

```text
FAIL_AGENT_WRITE_PERMISSION
```

处理要求：

1. `run.json` 中 `success` 必须为 `false`。
2. `fail_reason` 必须带上明确文本。
3. 进入 retry 前，日志中明确写出是写权限问题。
4. retry 仍失败时，step 文件写 stub，且 `agent_trace/{step}_failure.md` 写明是 write permission failure。

注意：这一步不是替代 `--permission-mode` 修复，而是作为回归保护，防止以后再次出现“stdout 有结论但文件未写出”的假成功。

### 5.6 修改 4：任务开始时清空该任务的旧 step 文件和最终总结文件

在 `AgentAnalyzer.analyze()` 一开始增加清理逻辑：

删除当前任务目录中的：

```text
01_version_verification.md
02_module_classification.md
03_vulnerability_pattern_classification.md
04_exploit_condition_summary.md
final_case_summary.md
```

不要删除：

```text
metadata.md
evidence_bundle.md
agent_trace/
agent_context/
```

原因：

1. 防止 agent 运行失败时残留 workflow 旧结果。
2. 防止中途中断后出现混合输出。

### 5.7 修改 5：单条真实样本先做权限模式回归

不要一上来重跑 10 条。

先用单条样本做真实回归：

```bash
python3 main.py run --project 0xKoda_WireMCP --id CVE-2026-3959 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode acceptEdits --force
```

验收要求：

1. `01_version_verification.md` 不再是 stub。
2. `02_module_classification.md` 不再是 stub。
3. `step1_stdout.txt` 和 `step2_stdout.txt` 不再包含“等待写权限/请授予写权限”。
4. `step1_run.json` 和 `step2_run.json` 的 `success` 为 `true`，且正式 step 文件确实存在。

如果 `acceptEdits` 仍然不行，再在同样的单样本上测试：

```bash
python3 main.py run --project 0xKoda_WireMCP --id CVE-2026-3959 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode auto --force
```

如果 `auto` 正常而 `acceptEdits` 不正常，则默认值改为：

```text
agent_permission_mode = "auto"
```

但仍然禁止使用：

```text
bypassPermissions
```

### 5.8 修改 6：通过后再重跑 10 条 Agent 验收

单样本通过后，再重跑 10 条 Agent 验收：

```bash
python3 main.py run --project 0xKoda_WireMCP --id CVE-2026-3959 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2025-48957 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2025-55449 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2025-57697 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2025-57698 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6118 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6119 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6984 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-7579 --analysis-mode agent --agent-backend claude_code_cli --agent-permission-mode <final_mode> --force
```

跑完后必须执行：

```bash
python3 main.py rebuild-summary
python3 main.py audit-output
python3 main.py batch-report
```

## 6. 修复完成标准

本次修复完成必须同时满足：

1. 单样本 `0xKoda_WireMCP / CVE-2026-3959` 的 step1 和 step2 不再因写权限问题写 stub。
2. `agent_trace` 中不再出现“grant permission to write”或同义文本。
3. 中途中断任务后，不会残留旧的 downstream step 文件污染结果。
4. 10 条 Agent 样本全部跑完后，`audit-output` 通过。
5. Agent 模式输出可与 `compare_runs/2026-06-14/workflow/` 做有效对比。

## 7. 本次验收结论

截至 2026-06-14，这一版代码的状态是：

1. `workflow/prompt` 模式通过真实运行验收。
2. `agent` 模式未通过真实运行验收。
3. 阻断点已定位为 **Claude CLI 权限模式未正确配置，导致 agent 有分析结果但不能写正式 step 文件**。
4. 下一步应由 Mimo 按本文件第 5 节逐项修复，再重新执行 10 条 Agent 验收。
