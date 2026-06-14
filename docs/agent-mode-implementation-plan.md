# Agent Analysis Mode 实施规划

本文档面向 Mimo，实现双分析模式中的第一版 `Agent Analysis Mode`。目标是保留当前稳定的 `Prompt Analysis Mode`，新增一个可插拔 agent 后端，让 agent 在任务专属 worktree 中自主读代码、查 git 历史，并直接写现有 4 个 Step Result 文件。

实现时不要重新设计整体项目，不要删除当前 workflow。按本文档逐步改。

## 1. 已确认的设计决策

1. 项目支持两种 `Analysis Mode`：
   - `prompt`：当前模式，系统拼 prompt，模型返回 Markdown，程序写 step 文件。
   - `agent`：新增模式，agent 在任务 workspace 中查代码并直接写 step 文件。
2. Agent 模式正式输出仍沿用现有 4 个 Step Result：
   - `01_version_verification.md`
   - `02_module_classification.md`
   - `03_vulnerability_pattern_classification.md`
   - `04_exploit_condition_summary.md`
3. `agent_trace/` 只作为辅助记录，不参与 `summary.csv` 和正式统计。
4. 第一版做可插拔 `AgentRunner` 抽象，只实现 `ClaudeCodeCliRunner`。
5. 后续预留：
   - `ClaudeAgentSdkRunner`
   - `CodexRunner`
   - `OpenCodeRunner`
6. Agent 主工作区是每任务独立 worktree，checkout 到 `intro_commit`。
7. Agent 可读 git 历史和代码，但不能修改源码仓库。
8. 四个 Step 分别调用 agent，每步结束立即校验。
9. 每个 Step 最多运行 2 次：首次执行 + 一次 repair；仍失败则写 stub。
10. Agent 模式跳过 `RepoManager.collect_evidence()` 的 diff/code-window 预收集，只准备 worktree。
11. 正式输出只使用 Markdown，不新增正式 JSON 输出。
12. Agent 模式沿用现有并行策略：同 project 串行，多 project 可并行；不支持多进程共享同一 repo/output 的并发写。

## 2. 新增配置

修改 `config.py`。

新增字段：

```python
analysis_mode: str = "prompt"  # prompt | agent
agent_backend: str = "claude_code_cli"  # claude_code_cli | claude_agent_sdk | codex | opencode
agent_command: str = "claude"
agent_timeout_seconds: int = 1800
```

从 `.env` 和环境变量读取：

```text
ANALYSIS_MODE
AGENT_BACKEND
AGENT_COMMAND
AGENT_TIMEOUT_SECONDS
```

优先级保持现有规则：

```text
环境变量 > .env > dataclass 默认值
```

校验要求：

```text
analysis_mode 只允许 prompt 或 agent
agent_backend 第一版只允许 claude_code_cli
```

如果 `ANALYSIS_MODE=agent` 但 `AGENT_BACKEND` 不是 `claude_code_cli`，第一版应明确报错：

```text
Unsupported agent backend: {agent_backend}
```

## 3. CLI 修改

修改 `main.py` 的 `run` 子命令。

新增参数：

```bash
--analysis-mode prompt|agent
--agent-backend claude_code_cli
--agent-command claude
```

行为：

1. CLI 参数覆盖 `Config` 中从 `.env` 读取的值。
2. 不传参数时保持默认 `prompt`，确保现有 workflow 不受影响。
3. `--offline` 在 agent 模式下仍表示“不调用外部 LLM/agent”，第一版可直接报错或退回 stub。推荐报错并退出，避免用户误以为 agent 已运行：

```text
Agent mode does not support --offline in v1.
```

## 4. 文件结构

新增文件：

```text
agent_runner.py
agent_analyzer.py
agent_prompts.py
```

不删除现有：

```text
analyzer.py
prompts.py
llm_client.py
```

建议命名：

```text
Analyzer              # 当前 prompt 模式，暂不重命名，减少改动
AgentAnalyzer         # 新 agent 模式
AgentRunner           # 抽象接口
ClaudeCodeCliRunner   # 第一版 runner 实现
```

后续如果要重命名当前 `Analyzer` 为 `PromptAnalyzer`，单独做，不放在第一版。

## 5. AgentRunner 接口

新增 `agent_runner.py`。

建议接口：

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class AgentRunRequest:
    task_key: str
    step_name: str
    prompt: str
    workspace_dir: Path
    output_dir: Path
    trace_dir: Path
    timeout_seconds: int


@dataclass
class AgentRunResult:
    success: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    fail_reason: str | None = None


class AgentRunner(Protocol):
    def run_step(self, request: AgentRunRequest) -> AgentRunResult:
        ...
```

第一版实现：

```python
class ClaudeCodeCliRunner:
    def __init__(self, config: Config): ...
    def run_step(self, request: AgentRunRequest) -> AgentRunResult: ...
```

重要约束：

1. `AgentAnalyzer` 只依赖 `AgentRunner`，不要直接 import 或调用 Claude CLI。
2. `ClaudeCodeCliRunner` 是唯一知道 `AGENT_COMMAND` 如何执行的地方。
3. CLI 具体参数集中在 `ClaudeCodeCliRunner._build_command()` 中，方便后续适配 Claude CLI 版本差异。

## 6. ClaudeCodeCliRunner 实现要求

### 6.1 执行目录

`subprocess.run()` 的 `cwd` 必须是：

```text
AgentRunRequest.workspace_dir
```

也就是任务专属 worktree。

### 6.2 Prompt 传递

第一版推荐通过 stdin 传 prompt，避免 shell quoting 问题。

伪代码：

```python
result = subprocess.run(
    command,
    input=request.prompt,
    cwd=request.workspace_dir,
    text=True,
    capture_output=True,
    timeout=request.timeout_seconds,
)
```

如果目标服务器上的 Claude Code CLI 必须使用 `-p` 或其他非交互参数，把差异封装在 `_build_command()`，不要泄漏到 `AgentAnalyzer`。

### 6.3 权限约束

第一版不能让 agent 拥有无限权限。

允许：

```text
Read
Grep
Glob
git show
git diff
git log
写 output/{project}/{canonical_id}/
写 output/{project}/{canonical_id}/agent_trace/
```

禁止：

```text
运行目标项目
安装依赖
执行 PoC
访问外网
修改源码仓库
修改 repos/
修改 worktrees/ 中的源码文件
写 output 以外的文件
```

实现方式分两层：

1. 在 agent prompt 中明确权限和禁止行为。
2. 如果 Claude CLI 支持 tool allowlist/denylist，在 `ClaudeCodeCliRunner._build_command()` 中配置。

不要使用会跳过权限控制的参数，例如“跳过所有权限检查”的模式。

如果 CLI 版本不支持细粒度工具权限，第一版仍必须在 prompt 中写清楚限制，并在验收中检查是否发生源码修改。

### 6.4 Trace 输出

每次调用都写 trace：

```text
output/{project}/{canonical_id}/agent_trace/{step_name}_prompt.md
output/{project}/{canonical_id}/agent_trace/{step_name}_stdout.txt
output/{project}/{canonical_id}/agent_trace/{step_name}_stderr.txt
output/{project}/{canonical_id}/agent_trace/{step_name}_run.json
```

`agent_trace` 不参与正式解析。

`run.json` 只记录 runner 元数据：

```json
{
  "backend": "claude_code_cli",
  "step_name": "step1",
  "returncode": 0,
  "success": true,
  "fail_reason": null
}
```

## 7. RepoManager 修改

Agent 模式不要调用 `collect_evidence()` 的 diff/code-window 预收集。

新增：

```python
@dataclass
class AgentWorkspace:
    repo_path: Path
    worktree_path: Path
    commit: str


def prepare_agent_workspace(self, evidence: VulnEvidence) -> AgentWorkspace | None:
    ...


def cleanup_agent_workspace(self, workspace: AgentWorkspace) -> None:
    ...
```

规则：

1. 必须有 `evidence.intro_commit`。
2. `ensure_repo(task)` 失败时设置失败原因。
3. worktree 名称：

```text
worktrees/{project}_{canonical_id}_agent_intro/
```

4. checkout commit：

```text
intro_commit
```

5. 不在 agent 模式中自动收集 `intro_diff`、`fix_diff`、`code_at_intro`、`code_at_intro_parent`。
6. agent 可以自己用只读 git 命令查看：

```bash
git log
git show
git diff
```

注意：现有 `create_worktree()` 如果 worktree 已存在会直接返回。第一版可沿用，但要避免 stale worktree 指向旧 commit。推荐在 `prepare_agent_workspace()` 中：

```text
如果 worktree 已存在，先验证 HEAD 是否等于 intro_commit。
如果不一致，remove 后重建。
```

## 8. AgentAnalyzer

新增 `agent_analyzer.py`。

构造：

```python
class AgentAnalyzer:
    def __init__(
        self,
        config: Config,
        output_writer: OutputWriter,
        repo_manager: RepoManager,
        runner: AgentRunner,
    ):
        ...
```

主流程：

```python
def analyze(self, evidence: VulnEvidence) -> dict:
    workspace = repo_manager.prepare_agent_workspace(evidence)
    if not workspace:
        write stubs for all four steps or raise controlled failure

    try:
        step1 = self.run_step("step1", ...)
        step2 = self.run_step("step2", ...)
        step3 = self.run_step("step3", ...)
        step4 = self.run_step("step4", ...)
        write_final_summary(...)
        return ...
    finally:
        repo_manager.cleanup_agent_workspace(workspace)
```

每步执行：

```python
def run_step(self, step_name: str, evidence: VulnEvidence, workspace: AgentWorkspace) -> str:
    prompt = build_agent_step_prompt(...)
    runner.run_step(...)
    text = read expected step file
    if validate_step_output(step_name, text):
        return text

    repair_prompt = build_agent_repair_prompt(...)
    runner.run_step(...)
    text = read expected step file
    if validate_step_output(step_name, text):
        return text

    stub = invalid_output_stub(step_name)
    write step file
    write agent_trace/{step_name}_failure.md
    return stub
```

复用当前 `Analyzer` 中的：

```python
REQUIRED_FIELDS
LEAKAGE_PATTERNS
validate_step_output()
_invalid_output_stub()
```

不要复制两套校验逻辑。推荐抽出公共基类或工具函数：

```text
analysis_validation.py
```

第一版最小改法：

```python
from analyzer import REQUIRED_FIELDS, LEAKAGE_PATTERNS
```

并把校验函数提取成模块函数。不要让 `AgentAnalyzer` 实例化 `LLMClient`。

## 9. Agent Prompt 设计

新增 `agent_prompts.py`。

Agent prompt 不要塞完整 diff/code window。它应给 agent：

1. 任务身份。
2. 数据文件路径。
3. 输出文件路径。
4. 当前 step 的目标。
5. 允许和禁止行为。
6. 必须输出的固定字段。

### 9.1 公共约束

所有 Step prompt 都必须包含：

```text
你正在运行 AI-VulnAtlas 的 Agent Analysis Mode。
你只能读取当前 Agent Workspace 中的源码和 git 历史。
你可以使用 Read/Grep/Glob，以及 git show/git diff/git log。
你只能写入指定 output 目录和 agent_trace 目录。
禁止运行目标项目。
禁止安装依赖。
禁止执行 PoC。
禁止访问外网。
禁止修改源码仓库。
正式输出必须写入指定 Markdown 文件。
不要输出 JSON 作为正式结果。
```

### 9.2 Step 1 prompt

输入：

```text
metadata.md
evidence_bundle.md
timeline.json path
relevance.json path
root_cause.md/root_cause_zh.md path
sast_standardized.json path
Agent Workspace path
```

目标：

```text
判断 intro commit 是否正确，以及漏洞在 intro commit 是否已存在。
```

输出：

```text
01_version_verification.md
```

固定字段同当前 prompt 模式。

### 9.3 Step 2 prompt

输入：

```text
Step 1 result path
project-module-types.md path
evidence files
Agent Workspace path
```

目标：

```text
判断项目架构和漏洞所在模块。
```

输出：

```text
02_module_classification.md
```

必须保持现有字段：

```text
architecture_type
architecture_confidence
classification_type
primary_module
secondary_modules
confidence
```

如果 `needs_new_module_type`，仍输出 `## Proposed New Module`。

### 9.4 Step 3 prompt

输入：

```text
Step 1 result path
Step 2 result path
Agent Workspace path
```

目标：

```text
做 A/B/C 漏洞分类和四象限字段。
```

输出：

```text
03_vulnerability_pattern_classification.md
```

必须包含 `Module Context`，字段直接继承 Step 2：

```text
module_from_step2_primary
module_from_step2_secondary
module_from_step2_classification_type
```

禁止在 Step 3 重新发明模块分类。

### 9.5 Step 4 prompt

输入：

```text
Step 1 result path
Step 2 result path
Step 3 result path
Agent Workspace path
```

目标：

```text
总结利用方式、前提条件、攻击链、影响、难度、防御缺口和不确定性。
```

输出：

```text
04_exploit_condition_summary.md
```

禁止输出可复制执行的 payload。

## 10. main.py 集成

### 10.1 Analyzer 选择

修改 `process_single_task()`。

当前：

```python
repo_manager = RepoManager(config)
writer = OutputWriter(config)
analyzer = Analyzer(config, writer)
```

改为：

```python
repo_manager = RepoManager(config)
writer = OutputWriter(config)

if config.analysis_mode == "agent":
    runner = build_agent_runner(config)
    analyzer = AgentAnalyzer(config, writer, repo_manager, runner)
else:
    analyzer = Analyzer(config, writer)
```

### 10.2 RepoManager 调用分支

当前 prompt 模式需要：

```python
if not config.offline and evidence.intro_commit:
    repo_manager.collect_evidence(evidence)
```

改为：

```python
if config.analysis_mode == "prompt":
    if not config.offline and evidence.intro_commit:
        repo_manager.collect_evidence(evidence)
elif config.analysis_mode == "agent":
    if config.offline:
        return failed with FAIL_AGENT_OFFLINE_UNSUPPORTED
    # 不调用 collect_evidence；AgentAnalyzer 内部 prepare_agent_workspace
```

### 10.3 Summary 和 State 不改

`finalize_task_result()` 不需要知道分析模式。

保持：

```python
fields = parse_task_output(writer.task_dir(task))
writer.append_summary_csv(fields)
state.append_status(...)
```

## 11. 输出目录规范

正式输出：

```text
output/{project}/{canonical_id}/metadata.md
output/{project}/{canonical_id}/evidence_bundle.md
output/{project}/{canonical_id}/01_version_verification.md
output/{project}/{canonical_id}/02_module_classification.md
output/{project}/{canonical_id}/03_vulnerability_pattern_classification.md
output/{project}/{canonical_id}/04_exploit_condition_summary.md
output/{project}/{canonical_id}/final_case_summary.md
```

Agent trace：

```text
output/{project}/{canonical_id}/agent_trace/
```

`audit-output` 第一版不强制检查 `agent_trace`。

## 12. 并行约束

沿用当前 `main.py` 的策略：

```text
max_workers <= 1：串行
max_workers > 1：多 project 并行，同 project 串行
```

Agent 模式第一版不支持：

```text
多个 shell 同时跑同一个 project-list
多个进程共享同一个 repo/output 并发写
分布式 worker
```

如果用户需要多人远程并行，继续使用不同 `--project-list` 分片，避免重叠项目。

## 13. 失败码建议

新增失败码：

```text
FAIL_AGENT_UNSUPPORTED_BACKEND
FAIL_AGENT_OFFLINE_UNSUPPORTED
FAIL_AGENT_WORKSPACE
FAIL_AGENT_RUN_ERROR
```

含义：

```text
FAIL_AGENT_UNSUPPORTED_BACKEND：AGENT_BACKEND 不是第一版支持值
FAIL_AGENT_OFFLINE_UNSUPPORTED：agent 模式下使用 --offline
FAIL_AGENT_WORKSPACE：无法准备 intro worktree
FAIL_AGENT_RUN_ERROR：agent 调用异常，且无法写出 step stub
```

注意：如果某个 step agent 失败但 stub 成功写入，整个 task 可以继续并最终 success，但 step 文件中必须有 `## Failure` 和可解析字段。

## 14. 验收命令

### 14.1 Prompt 模式回归

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --analysis-mode prompt --force
python3 main.py rebuild-summary
python3 main.py audit-output
```

期望：

```text
audit-output: 0 missing fields, 0 leakage, 0 API errors, 0 JSON output
```

### 14.2 Agent 模式单任务

选择一个已有小样本：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --analysis-mode agent --agent-backend claude_code_cli --force
python3 main.py rebuild-summary
python3 main.py audit-output
```

检查：

```bash
ls output/AstrBotDevs_AstrBot/CVE-2026-6117/
ls output/AstrBotDevs_AstrBot/CVE-2026-6117/agent_trace/
```

必须存在：

```text
01_version_verification.md
02_module_classification.md
03_vulnerability_pattern_classification.md
04_exploit_condition_summary.md
final_case_summary.md
agent_trace/
```

### 14.3 Step 字段验收

```bash
python3 - <<'PY'
from pathlib import Path
from analyzer import Analyzer
from config import Config
from output_writer import OutputWriter

task_dir = Path("output/AstrBotDevs_AstrBot/CVE-2026-6117")
validator = Analyzer(Config(), OutputWriter(Config()))

checks = [
    ("step1", "01_version_verification.md"),
    ("step2", "02_module_classification.md"),
    ("step3", "03_vulnerability_pattern_classification.md"),
    ("step4", "04_exploit_condition_summary.md"),
]

for step, filename in checks:
    text = (task_dir / filename).read_text(encoding="utf-8")
    print(step, filename, validator.validate_step_output(step, text))
    assert validator.validate_step_output(step, text)

print("agent step outputs valid")
PY
```

### 14.4 Agent 模式失败兜底

临时把 `AGENT_COMMAND` 设置为不存在的命令：

```bash
AGENT_COMMAND=not-a-real-agent python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --analysis-mode agent --force
```

期望：

1. 不出现未捕获 traceback。
2. step 文件被 stub 覆盖或 task 以明确失败码结束。
3. `agent_trace` 中记录失败原因。

### 14.5 并行验收

```bash
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 2 --max 2 --analysis-mode agent --force
python3 main.py audit-output
```

期望：

```text
同 project 不并行
两个不同 project 可并行
audit-output 通过
```

## 15. 实施顺序

按以下顺序实施，不要跳步：

1. `config.py` 增加 `analysis_mode`、`agent_backend`、`agent_command`、`agent_timeout_seconds`。
2. `main.py` 增加 CLI 参数，但默认仍是 prompt。
3. 新增 `agent_runner.py`，实现接口和 `ClaudeCodeCliRunner`。
4. `repo_manager.py` 新增 `prepare_agent_workspace()` 和 `cleanup_agent_workspace()`。
5. 新增 `agent_prompts.py`，先写 4 个 Step prompt builder。
6. 新增 `agent_analyzer.py`，复用现有校验和 stub。
7. 修改 `process_single_task()`，按 `analysis_mode` 选择 analyzer。
8. 跑 prompt 模式回归。
9. 跑 agent 模式单任务。
10. 跑 `rebuild-summary` 和 `audit-output`。

## 16. 不要做的事

第一版不要做：

1. 不要删除或重命名现有 `Analyzer`。
2. 不要把正式输出改成 JSON。
3. 不要让 agent 修改源码仓库。
4. 不要让 agent 安装依赖或运行目标项目。
5. 不要接入 Claude SDK。
6. 不要实现 CodexRunner 或 OpenCodeRunner。
7. 不要引入跨进程锁。
8. 不要改 `summary.csv` 字段，除非正式 Step Result 新增字段。
9. 不要改变 `audit-output` 的核心验收规则。
10. 不要让 agent 接管 TaskLoader、RecordResolver、StateManager、summary 生成。

## 17. 文档同步

实现完成后同步：

```text
docs/project-workflow.md
docs/detailed-implementation-steps.md
AGENTS.md
CLAUDE.md
```

必须说明：

```text
Prompt Analysis Mode 和 Agent Analysis Mode 并存。
Agent Analysis Mode 第一版使用 claude_code_cli。
正式输出仍是现有 4 个 Markdown Step Result。
agent_trace 只是辅助记录。
Agent 模式不支持离线运行。
Agent 模式同 project 串行，多 project 可并行。
```

## 18. 完成标准

第一版完成必须满足：

1. 默认运行仍使用 prompt 模式。
2. `--analysis-mode prompt` 能跑通原有流程。
3. `--analysis-mode agent --agent-backend claude_code_cli` 能对 1 条任务生成 4 个正式 Step Result。
4. `audit-output` 对 agent 模式输出通过。
5. `summary.csv` 能解析 agent 模式输出。
6. agent trace 存在，但不参与 summary。
7. agent 失败时不会无限重试。
8. 不允许 agent 修改源码仓库。
9. 并行规则仍然遵守同 project 串行。
10. 文档与实现一致。
