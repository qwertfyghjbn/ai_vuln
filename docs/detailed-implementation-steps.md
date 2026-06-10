# AI-VulnAtlas Agent 详细实施步骤

本文档是 `docs/implementation-plan.md` 的施工版。目标读者是后续负责实现的代码模型或开发者，假设模型上下文较大但工程能力一般，因此每一步都尽量明确文件、函数、输入输出和验收标准，避免自由发挥。

实现时遵守以下原则：

1. 先做可运行的最小闭环，再扩展批量处理。
2. 每个阶段结束都必须能用小样本验证。
3. 不运行 PoC，不执行目标项目代码，不安装目标项目依赖。
4. Agent 每一步写 Markdown 文件，不要求输出 JSON 给脚本解析。
5. 所有路径、字段名、目录名以当前工作区真实数据为准。

## 0. 目标交付物

最终应生成以下代码和文档：

```text
ai_vuln/
├── main.py
├── config.py
├── dataset_preparer.py
├── task_loader.py
├── record_resolver.py
├── repo_manager.py
├── evidence_builder.py
├── analyzer.py
├── output_writer.py
├── state_manager.py
├── prompts.py
├── markdown_parser.py
├── utils.py
├── requirements.txt
├── project-module-types.md
├── docs/
│   ├── implementation-plan.md
│   └── detailed-implementation-steps.md
├── vuln-analyzed-0605.xlsx
├── ai-vulns-timeline.zip
├── data/
│   └── ai-vulns-timeline/
├── repos/
├── worktrees/
├── output/
└── state/
```

如果暂时不实现真实 LLM 调用，也必须实现 dry-run 模式，让流程能从 Excel 读取任务、解析证据、创建输出目录并写入占位分析文件。

## 1. Phase 0：环境和数据预检查

### 1.1 创建基础目录

实现前先创建这些目录：

```text
data/
repos/
worktrees/
output/
state/
logs/
```

验收标准：

1. 目录不存在时能自动创建。
2. 目录已存在时不会报错。

### 1.2 编写 `requirements.txt`

推荐内容：

```text
pandas>=2.0.0
openpyxl>=3.1.0
GitPython>=3.1.0
anthropic>=0.18.0
```

注意：

1. 如果环境不能安装依赖，先实现基于 `zipfile + xml.etree.ElementTree` 的 Excel 读取 fallback。
2. 不要把目标项目依赖写入本项目 `requirements.txt`。

### 1.3 编写 `config.py`

定义固定配置对象，不要散落硬编码。

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    root_dir: Path = Path(".")
    excel_path: Path = Path("vuln-analyzed-0605.xlsx")
    timeline_zip_path: Path = Path("ai-vulns-timeline.zip")
    data_root: Path = Path("data/ai-vulns-timeline")
    repos_dir: Path = Path("repos")
    worktrees_dir: Path = Path("worktrees")
    output_dir: Path = Path("output")
    state_dir: Path = Path("state")
    logs_dir: Path = Path("logs")
    module_types_prompt_path: Path = Path("project-module-types.md")
    max_tasks: int | None = None
    dry_run: bool = False
    offline: bool = False
    max_workers: int = 1
    llm_provider: str = "none"  # none | anthropic | claude_code
```

验收标准：

1. 所有模块只从 `Config` 读取路径。
2. 支持命令行覆盖 `max_tasks/dry_run/offline/max_workers`。
3. Step 2 模块分类必须从 `Config.module_types_prompt_path` 读取 `project-module-types.md`，不要在代码中手写另一套 taxonomy。

### 1.4 编写 `dataset_preparer.py`

职责：

1. 检查 Excel 是否存在。
2. 检查 zip 是否存在。
3. 如果 `data/ai-vulns-timeline/` 不存在或为空，解压 `ai-vulns-timeline.zip`。
4. 输出 `output/preflight_report.md`。

建议接口：

```python
class DatasetPreparer:
    def __init__(self, config: Config): ...

    def prepare(self) -> dict:
        """
        返回:
        {
            "excel_exists": bool,
            "zip_exists": bool,
            "data_root_exists": bool,
            "cves_dir_exists": bool,
            "advisories_dir_exists": bool,
            "prepared": bool,
            "errors": list[str],
        }
        """
```

实现细节：

1. 解压时跳过 `__MACOSX/`。
2. 解压后应存在：

```text
data/ai-vulns-timeline/cves/
data/ai-vulns-timeline/security_advisories/
```

3. 如果 zip 中根目录直接就是 `cves/` 和 `security_advisories/`，解压到 `data/ai-vulns-timeline/`。
4. 如果 zip 中多包了一层目录，解压后要检测并记录实际根目录。

验收标准：

1. `python main.py preflight` 能生成 `output/preflight_report.md`。
2. 报告中包含 Excel、zip、cves 目录、security_advisories 目录状态。

## 2. Phase 1：任务加载

### 2.1 编写数据模型

可以放在 `models.py`，也可以放在对应模块顶部。建议单独创建 `models.py`。

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class VulnerabilityTask:
    project: str
    github_url: str
    owner: str
    repo: str
    source: str
    cve_id: Optional[str]
    adv_id: Optional[str]
    canonical_id: str
    task_key: str
    publish_at: Optional[str]
    cwe: Optional[str]
    cve_dir: Optional[Path] = None
    advisory_dir: Optional[Path] = None
    primary_data_dir: Optional[Path] = None
    status: str = "pending"
    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None

@dataclass
class VulnEvidence:
    task: VulnerabilityTask
    timeline: Optional[dict] = None
    relevance: Optional[dict] = None
    issue_text: Optional[str] = None
    root_cause: Optional[str] = None
    root_cause_zh: Optional[str] = None
    sast: Optional[dict] = None
    intro_commit: Optional[str] = None
    intro_parent_commit: Optional[str] = None
    intro_date: Optional[str] = None
    fix_commit: Optional[str] = None
    fix_parent_commit: Optional[str] = None
    fix_date: Optional[str] = None
    disclosure_date: Optional[str] = None
    project_profile: Optional[dict] = None
    architecture_type: Optional[str] = None
    vuln_positions: list[dict] = field(default_factory=list)
    dataflow: list[dict] = field(default_factory=list)
    code_at_intro: dict[str, str] = field(default_factory=dict)
    code_at_intro_parent: dict[str, str] = field(default_factory=dict)
    intro_diff: Optional[str] = None
    fix_diff: Optional[str] = None
    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None
```

### 2.2 编写 `task_loader.py`

职责：

1. 读取 `汇总` sheet。
2. 遍历每个项目 sheet。
3. 从第 9 行之后读取漏洞明细。
4. 合并项目元数据。
5. 生成 `VulnerabilityTask` 列表。

建议接口：

```python
class TaskLoader:
    def __init__(self, config: Config): ...

    def load_tasks(self) -> list[VulnerabilityTask]: ...
```

字段映射必须固定：

```text
Excel 汇总 sheet:
project -> project
github_url -> github_url
owner -> owner
repo -> repo

项目明细 sheet:
source -> source
cve-id -> cve_id
adv-id -> adv_id
publish-at -> publish_at
cwe -> cwe
```

任务生成规则：

1. `canonical_id = cve_id if cve_id else adv_id`
2. `source = "both"` 当同一任务同时存在 CVE 和 GHSA 或重复来源合并。
3. `task_key = f"{project}:{source}:{canonical_id}"`
4. 跳过 `canonical_id` 为空的行。
5. 不要把 `project` 转小写。

### 2.3 Excel fallback 读取器

如果不想依赖 pandas/openpyxl，编写 `xlsx_reader.py`。

最小能力：

1. 列出 workbook 所有 sheet 名。
2. 读取指定 sheet 的所有单元格为二维数组。
3. 正确解析 shared strings。
4. 支持空单元格补齐，避免列错位。

验收标准：

1. 能读取 `汇总` sheet 前 5 行。
2. 能读取 `BerriAI_litellm` sheet 第 9 到 20 行。
3. 明细字段必须读出 `source | cve-id | adv-id | publish-at | cwe`。

### 2.4 TaskLoader 验收测试

添加命令：

```bash
python main.py list-tasks --max 10
```

输出示例：

```text
Loaded tasks: 4992
1. BerriAI_litellm CVE-2024-10188 cves CWE-400
2. BerriAI_litellm CVE-2024-4888 cves CWE-862
...
```

验收标准：

1. 任务数量大于 0。
2. 能看到 `BerriAI_litellm`、`FlowiseAI_Flowise`、`langchain-ai_langchain` 等项目。
3. `canonical_id` 不为空。
4. 字段 `cve_id/adv_id/publish_at/cwe` 映射正确。

## 3. Phase 2：目录解析

### 3.1 编写 `record_resolver.py`

职责：

1. 根据 task 优先找到 `cves/{project}/{cve_id}`。
2. 当 CVE 正常目录缺失时，回退查找 `security_advisories/{project}/{cve_id}`。
3. 根据 task 查找 `security_advisories/{project}/{adv_id}`。
4. 决定 `primary_data_dir`。
5. 标记缺失目录的失败原因。

建议接口：

```python
class RecordResolver:
    def __init__(self, config: Config): ...

    def resolve(self, task: VulnerabilityTask) -> VulnerabilityTask: ...
```

解析规则：

```python
if task.cve_id:
    try cves/{project}/{cve_id}
    then try security_advisories/{project}/{cve_id}

if task.adv_id:
    try security_advisories/{project}/{adv_id}
    optional fallback cves/{project}/{adv_id}

if cve_dir exists:
    primary_data_dir = cve_dir
elif advisory_dir exists:
    primary_data_dir = advisory_dir
else:
    fail_code = "FAIL_NO_VULN_DIR"
```

注意：有些 CVE ID 目录会被数据包放在 `security_advisories` 下，resolver 必须支持跨来源目录回退，但不能跨 project 匹配。

禁止行为：

1. 不要对 `project` 调用 `.lower()`。
2. 不要把 GHSA-only 强制映射到 CVE 目录；只有实际存在 `cves/{project}/{adv_id}` 时才可作为兜底。
3. 不要因为 advisory_dir 缺失就否定 CVE 任务。

### 3.2 目录解析验收测试

添加命令：

```bash
python main.py resolve-tasks --max 20
```

输出示例：

```text
Resolved: 18
Missing: 2
Example:
BerriAI_litellm:CVE-2026-42271 -> data/ai-vulns-timeline/cves/BerriAI_litellm/CVE-2026-42271
```

验收标准：

1. `BerriAI_litellm/CVE-2026-42271` 能解析成功。
2. GHSA-only 任务能解析到 `security_advisories`。
3. 输出缺失目录列表，便于人工检查。

## 4. Phase 3：状态管理和输出骨架

### 4.1 编写 `state_manager.py`

职责：

1. 记录任务状态。
2. 支持断点续传。
3. 保存失败原因。

先实现简单 JSONL，后续再换 sqlite。

文件：

```text
state/progress.jsonl
```

每行格式：

```json
{"task_key":"BerriAI_litellm:cves:CVE-2026-42271","status":"success","fail_code":null}
```

建议接口：

```python
class StateManager:
    def __init__(self, config: Config): ...
    def load_completed_keys(self) -> set[str]: ...
    def append_status(self, task: VulnerabilityTask, status: str, fail_code: str | None = None, fail_reason: str | None = None) -> None: ...
```

### 4.2 编写 `output_writer.py`

职责：

1. 创建任务输出目录。
2. 写 metadata。
3. 写 evidence bundle。
4. 写四个 step 文件。
5. 写 final summary。
6. 更新 summary CSV。

输出目录：

```text
output/{project}/{canonical_id}/
```

注意：

1. 文件名只使用安全字符。`canonical_id` 一般是 CVE 或 GHSA，可以直接使用。
2. 每个任务必须至少写 `metadata.md`。
3. 失败任务也要写失败原因。

建议接口：

```python
class OutputWriter:
    def __init__(self, config: Config): ...
    def task_dir(self, task: VulnerabilityTask) -> Path: ...
    def write_metadata(self, task: VulnerabilityTask) -> None: ...
    def write_step_file(self, task: VulnerabilityTask, filename: str, content: str) -> None: ...
    def write_final_summary(self, task: VulnerabilityTask, sections: dict[str, str]) -> None: ...
    def append_summary_csv(self, row: dict) -> None: ...
```

### 4.3 输出骨架验收测试

添加命令：

```bash
python main.py dry-run --max 3
```

验收标准：

1. 生成 3 个任务输出目录。
2. 每个目录包含 `metadata.md`。
3. dry-run 下四个 step 文件可以是占位内容，但文件必须存在。
4. `state/progress.jsonl` 有对应记录。

## 5. Phase 4：证据构建

### 5.1 编写 `evidence_builder.py`

职责：

1. 从 `primary_data_dir` 加载证据文件。
2. 合并 CVE 和 GHSA 补充证据。
3. 提取 timeline 字段。
4. 提取 SAST 代码位置和 dataflow。
5. 加载项目 profile。
6. 调用 RepoManager 收集代码证据。

建议接口：

```python
class EvidenceBuilder:
    def __init__(self, config: Config, repo_manager: RepoManager): ...

    def build(self, task: VulnerabilityTask) -> VulnEvidence: ...
```

### 5.2 固定证据文件路径

按顺序尝试读取：

```text
{dir}/relevance_out/timeline.json
{dir}/relevance_out/relevance.json
{dir}/verify_requirements/one_issue.txt
{dir}/verify_requirements/root_cause_zh.md
{dir}/verify_requirements/root_cause.md
{dir}/verify_requirements/sast_standardized.json
```

如果文件缺失：

1. 不要直接抛异常。
2. 在 `evidence_bundle.md` 写清楚 `missing`。
3. 只有没有任何可用证据时才标记 `FAIL_INSUFFICIENT_EVIDENCE`。

### 5.3 timeline 字段提取

当前 `timeline.json` 常见结构：

```json
{
  "introduction": {
    "commit": "...",
    "date": "...",
    "files": [],
    "symbols": [],
    "description": "..."
  },
  "fix": {
    "commit": "...",
    "date": "...",
    "files": [],
    "symbols": [],
    "description": "..."
  },
  "public_disclosure": {
    "date": "...",
    "source": "...",
    "description": "..."
  }
}
```

提取规则：

```python
intro_commit = timeline.get("introduction", {}).get("commit")
intro_date = timeline.get("introduction", {}).get("date")
fix_commit = timeline.get("fix", {}).get("commit")
fix_date = timeline.get("fix", {}).get("date")
disclosure_date = timeline.get("public_disclosure", {}).get("date")
```

### 5.4 SAST 字段提取

当前 `sast_standardized.json` 常见结构：

```json
{
  "findings": [
    {
      "vul_pos": [
        {"file": "...", "line_start": 1, "line_end": 2, "role": "source"}
      ],
      "dataflow": [
        {"file": "...", "line": 1, "type": "source", "description": "..."}
      ]
    }
  ]
}
```

提取规则：

1. 遍历所有 findings，不只取第一个。
2. 合并所有 `vul_pos`。
3. 合并所有 `dataflow`。
4. 从 `vul_pos.file` 和 `dataflow.file` 收集目标文件路径。

### 5.5 项目 profile

先做最小实现：

```python
project_profile = {
    "project": task.project,
    "github_url": task.github_url,
    "owner": task.owner,
    "repo": task.repo,
    "architecture_type": "unknown",
    "description": ""
}
```

后续再从 README、deepwiki、codewiki 补充。

架构类型初始枚举：

```text
agent
rag
mcp
workflow
model_serving
ai_application
traditional_web
mixed
unknown
```

### 5.6 EvidenceBuilder 验收测试

添加命令：

```bash
python main.py build-evidence --project BerriAI_litellm --id CVE-2026-42271
```

验收标准：

1. 能读取 `timeline.json`。
2. 能读取 `relevance.json`。
3. 能读取 `root_cause_zh.md`。
4. 能读取 `sast_standardized.json`。
5. 能提取 intro commit 和 fix commit。
6. 能写出 `output/BerriAI_litellm/CVE-2026-42271/evidence_bundle.md`。

## 6. Phase 5：RepoManager 和代码证据

### 6.1 编写 `repo_manager.py`

职责：

1. clone 或 fetch 仓库。
2. 为任务创建 worktree。
3. 计算 parent commit。
4. 读取目标文件片段。
5. 生成 intro diff 和 fix diff。
6. 清理 worktree。

建议接口：

```python
class RepoManager:
    def __init__(self, config: Config): ...

    def ensure_repo(self, task: VulnerabilityTask) -> Path: ...
    def get_parent_commit(self, repo_path: Path, commit: str) -> str | None: ...
    def create_worktree(self, repo_path: Path, task: VulnerabilityTask, commit: str, label: str) -> Path | None: ...
    def remove_worktree(self, repo_path: Path, worktree_path: Path) -> None: ...
    def collect_diff(self, repo_path: Path, from_commit: str, to_commit: str, paths: list[str] | None = None) -> str: ...
    def collect_file_windows(self, worktree_path: Path, positions: list[dict], context_lines: int = 40) -> dict[str, str]: ...
```

### 6.2 clone/fetch 规则

1. 仓库缓存目录：`repos/{project}`。
2. 如果目录不存在：`git clone {github_url} repos/{project}`。
3. 如果目录存在：`git fetch --all --tags --prune`。
4. 网络失败时：
   - 设置 `evidence.fail_code = FAIL_REPO_CLONE`
   - 不终止 Step 2/3/4
   - Step 1 输出 `not_verifiable`

### 6.3 worktree 规则

每个任务最多创建两个 worktree：

```text
worktrees/{project}_{canonical_id}_intro/
worktrees/{project}_{canonical_id}_intro_parent/
```

如果实现起来复杂，可以先用 repo 级锁串行 checkout，但必须在文档或代码注释里说明同一 repo 不允许并发 checkout。

### 6.4 diff 规则

必须收集：

```text
intro_parent = intro_commit~1
intro_diff = git diff intro_parent intro_commit -- {target_paths}
fix_parent = fix_commit~1
fix_diff = git diff fix_parent fix_commit -- {target_paths}
```

如果 `target_paths` 为空：

1. 先使用 timeline introduction.files 和 fix.files。
2. 再使用 SAST dataflow 文件。
3. 仍为空时，不加路径限制，但要限制 diff 最大字符数。

### 6.5 文件窗口规则

读取代码不要整文件无限塞入上下文。

规则：

1. 对每个 `vul_pos`，读取 `line_start - 40` 到 `line_end + 40`。
2. 对每个 `dataflow`，读取 `line - 40` 到 `line + 40`。
3. 每个文件最多保留 300 行。
4. 每个任务代码证据总字符数建议不超过 80k。

### 6.6 RepoManager 验收测试

添加命令：

```bash
python main.py collect-code --project BerriAI_litellm --id CVE-2026-42271
```

验收标准：

1. 能 clone 或 fetch repo。
2. 能找到 intro parent。
3. 能生成 intro diff。
4. 能生成 fix diff。
5. 能读取 SAST 相关文件窗口。
6. 不执行任何项目代码。

## 7. Phase 6：Prompt 和 Analyzer

### 7.1 编写 `prompts.py`

不要把 prompt 散落在业务代码里。每一步一个函数：

```python
def build_step1_prompt(evidence: VulnEvidence) -> str: ...
def build_step2_prompt(evidence: VulnEvidence) -> str: ...
def build_step3_prompt(evidence: VulnEvidence, step2_text: str) -> str: ...
def build_step4_prompt(evidence: VulnEvidence, step2_text: str, step3_text: str) -> str: ...
```

新增辅助函数：

```python
def load_project_module_types_prompt(config: Config) -> str: ...
def build_step2_markdown_output_contract() -> str: ...
```

`load_project_module_types_prompt()` 必须读取仓库根目录的 `project-module-types.md`。该文件就是 `进展文档.txt` 中提到的“预设的模块划分提示词”，包含 A-R 细粒度模块分类体系、架构类型判定、目录梳理流程和漏洞模块定位要求。

### 7.2 通用 Prompt 约束

每个 prompt 顶部都要包含：

```text
你必须只写 Markdown 正文，不要输出 JSON。
你必须使用指定小节标题。
证据不足时写 insufficient_evidence，不要编造。
不要给出可执行 exploit 或 PoC。
不要建议运行目标项目代码。
结论必须能被 summary 提取器从固定字段行中读取。
```

### 7.3 Step 1 Prompt 要求

必须包含：

1. 漏洞基本信息。
2. timeline introduction/fix/public disclosure。
3. relevance reason 和 evidence。
4. root cause。
5. SAST positions/dataflow。
6. intro parent 代码。
7. intro commit 代码。
8. intro diff。
9. fix diff。

必须要求模型输出固定字段：

```markdown
## Conclusion
- intro_time_verdict:
- vuln_exists_at_intro_version:
- manual_review_needed:
```

合法取值：

```text
intro_time_verdict = correct | likely_correct | incorrect | insufficient_evidence | not_verifiable
vuln_exists_at_intro_version = yes | likely_yes | no | insufficient_evidence
manual_review_needed = yes | no
```

### 7.4 Step 2 Prompt 要求

必须复用 `project-module-types.md`，不要重新发明模块体系。

使用规则：

1. `project-module-types.md` 中 A-R 的 `module_id` 是 Step 2 的主分类来源。
2. 优先使用其中的 `module_id`，例如 `agent_core`、`mcp_client`、`workflow_engine`、`authentication`、`input_validation`。
3. 只有确实无法匹配时才使用 `other`，并在 `Proposed New Module` 中说明建议新增类型。
4. `project-module-types.md` 的分析流程可以复用，但需要按本项目现有证据调整：当前输入主要是 `timeline.json`、`root_cause_zh.md`、`sast_standardized.json`、代码窗口和 diff，不要求一定有完整源码仓库目录扫描。
5. `project-module-types.md` 原文要求输出 JSON。这里不能照搬该输出格式；必须把它的分类体系和分析流程嵌入 Step 2 prompt，并追加本项目的 Markdown 输出约束。

Step 2 prompt 的推荐组装顺序：

```text
1. 通用 Prompt 约束
2. 漏洞基本信息和证据
3. 从 project-module-types.md 读取的完整预设模块划分提示词
4. 本项目的 Markdown 输出格式覆盖说明
```

Markdown 输出格式覆盖说明必须明确写：

```text
注意：上面的 project-module-types.md 原文包含 JSON 输出格式，但本项目要求每一步直接写 Markdown 文件。
你必须只使用其中的 A-R taxonomy、module_id 和分析流程，不要输出 JSON。
最终输出必须严格使用下面的小节和固定字段。
```

固定字段：

```markdown
## Conclusion
- classification_type:
- primary_module:
- secondary_modules:
- confidence:
```

合法取值：

```text
classification_type = matched_existing_module | uncertain_existing_module | needs_new_module_type
confidence = high | medium | low
```

`primary_module` 的值应优先来自 `project-module-types.md` 的 `module_id`，而不是 `docs/implementation-plan.md` 里的简化 M01-M18 分类。如果后续需要论文统计中的粗粒度模块，可在 summary 阶段再增加映射表，不要污染 Step 2 原始分类。

Step 2 还必须输出：

```markdown
## Project Architecture
- architecture_type:
- architecture_confidence:

## Evidence
- code_paths:
- functions:
- dataflow_nodes:

## Reasoning

## Proposed New Module
- name:
- description:
- why_existing_modules_do_not_fit:
- example_vulnerability_semantics:
```

其中 `architecture_type` 优先使用 `project-module-types.md` 中定义的架构类型。

### 7.5 Step 3 Prompt 要求

必须包含：

1. 项目自身定位。
2. Step 2 模块结论。
3. A/B/C 分类标准。
4. 四象限字段定义。

A/B/C 分类语义：

```text
A = 传统类型漏洞
B = AI功能实现+传统方式
C = AI场景新漏洞模式
```

不得使用 Traditional、AI Amplified、AI Native 作为 category_name。

固定字段：

```markdown
## Conclusion
- category: A | B | C
- category_name: 传统类型漏洞 | AI功能实现+传统方式 | AI场景新漏洞模式
- confidence: high | medium | low

## Module Context
- module_from_step2_primary:
- module_from_step2_secondary:
- module_from_step2_classification_type:

## Four-Quadrant Fields
- input_type:
- input_subtype:
- mechanism_type:
- mechanism_subtype:
- requires_ai_function: yes | no | uncertain
- ai_native_subtype: none | direct_prompt_injection | indirect_prompt_injection | rag_poisoning | tool_output_poisoning | memory_poisoning | delegation_hijack | semantic_policy_bypass | unknown
- cross_agent: yes | no | uncertain
```

其中 `Module Context` 字段必须直接继承 Step 2 的模块结论，不允许在 Step 3 重新发明新的模块分类。

### 7.6 Step 4 Prompt 要求

固定小节：

```markdown
## Exploit Method
## Prerequisites
## Attack Chain
## Impact
## Difficulty
- difficulty:
## Defensive Gap
## Uncertainty
```

注意：

1. 只允许描述利用方式，不输出可直接复制执行的 payload。
2. 前提条件要明确认证、权限、配置、网络可达性、是否需要 AI 功能启用。

### 7.7 编写 `analyzer.py`

职责：

1. 调用 prompts 构造 prompt。
2. 调用 LLM 或 dry-run stub。
3. 把每一步结果写文件。
4. Step 3 读取 Step 2 文本作为输入。
5. Step 4 读取 Step 2 和 Step 3 文本作为输入。

建议接口：

```python
class Analyzer:
    def __init__(self, config: Config, output_writer: OutputWriter): ...

    def analyze(self, evidence: VulnEvidence) -> dict:
        step1 = self.run_step1(evidence)
        step2 = self.run_step2(evidence)
        step3 = self.run_step3(evidence, step2)
        step4 = self.run_step4(evidence, step2, step3)
        return {"step1": step1, "step2": step2, "step3": step3, "step4": step4}
```

### 7.8 LLM 调用封装

先实现简单接口：

```python
class LLMClient:
    def complete(self, prompt: str) -> str: ...
```

实现三种模式：

1. `none`：返回固定占位 Markdown，用于流程测试。
2. `anthropic`：调用 Anthropic API。
3. `claude_code`：预留接口，后续接 Claude Code CLI 或人工执行。

不要让业务代码直接依赖某个模型 SDK。

## 8. Phase 7：Markdown 字段提取和 summary

### 8.1 编写 `markdown_parser.py`

职责：

1. 从 step 文件中提取固定字段。
2. 生成 summary CSV 行。

建议接口：

```python
def extract_bullet_value(markdown_text: str, key: str) -> str:
    """
    匹配形如:
    - key: value
    返回 value，找不到返回空字符串。
    """
```

需要提取的字段：

```text
intro_time_verdict
vuln_exists_at_intro_version
manual_review_needed
primary_module
secondary_modules
classification_type
category
category_name
module_from_step2_primary
module_from_step2_secondary
module_from_step2_classification_type
input_type
input_subtype
mechanism_type
mechanism_subtype
requires_ai_function
ai_native_subtype
cross_agent
difficulty
confidence
```

### 8.2 summary CSV 规则

每完成一个任务，追加或重写 summary。

推荐先实现重写：

1. 扫描 `output/*/*/final_case_summary.md` 或 step 文件。
2. 重新生成 `output/summary.csv`。

优点：避免重复追加。

验收标准：

1. dry-run 3 个任务后，summary 有 3 行。
2. 每行包含 project、canonical_id、category、primary_module 等字段。

## 9. Phase 8：主控脚本

### 9.1 编写 `main.py`

支持命令：

```bash
python main.py preflight
python main.py list-tasks --max 10
python main.py resolve-tasks --max 20
python main.py dry-run --max 3
python main.py build-evidence --project BerriAI_litellm --id CVE-2026-42271
python main.py collect-code --project BerriAI_litellm --id CVE-2026-42271
python main.py run --max 10 --offline
python main.py run --max 10
```

### 9.2 主流程伪代码

```python
def run(config):
    preparer.prepare()
    tasks = task_loader.load_tasks()
    tasks = [resolver.resolve(t) for t in tasks]
    tasks = filter_completed(tasks)
    tasks = apply_filters(tasks, max_tasks=config.max_tasks)

    for task in tasks:
        state.append_status(task, "running")
        writer.write_metadata(task)

        if task.fail_code:
            writer.write_failure(task)
            state.append_status(task, "failed", task.fail_code, task.fail_reason)
            continue

        evidence = evidence_builder.build(task)
        writer.write_evidence_bundle(evidence)

        result = analyzer.analyze(evidence)
        writer.write_final_summary(task, result)
        rebuild_summary_csv()
        state.append_status(task, "success")
```

### 9.3 错误处理规则

1. 单个任务失败不能终止批处理。
2. 每个异常都要转换为 `fail_code` 和 `fail_reason`。
3. 失败任务也要写输出目录。
4. 日志写到 `logs/run.log`。

## 10. Phase 9：小样本验收

### 10.1 第一组固定样本

优先使用这些样本：

```text
BerriAI_litellm / CVE-2026-42271
FlowiseAI_Flowise / CVE-2025-59527
langchain-ai_langchain / CVE-2023-46229
n8n-io_n8n / CVE-2025-56265
```

如果某个样本目录缺失，换同项目其他 CVE。

### 10.2 小样本验收命令

```bash
python main.py run --max 5 --offline
```

验收标准：

1. 能生成 5 个输出目录。
2. 每个目录有 7 个文件：

```text
metadata.md
evidence_bundle.md
01_version_verification.md
02_module_classification.md
03_vulnerability_pattern_classification.md
04_exploit_condition_summary.md
final_case_summary.md
```

3. Step 1 在 offline 或无法 clone 时明确写 `not_verifiable`，不能写成已验证。
4. Step 2 必须有 `primary_module`。
5. Step 3 必须有 `category` 和四象限字段。
6. Step 4 必须有利用前提。
7. `output/summary.csv` 有对应行。

### 10.3 代码验证样本

网络允许时运行：

```bash
python main.py run --max 1 --project BerriAI_litellm --id CVE-2026-42271
```

验收标准：

1. 能 checkout intro commit。
2. 能计算 intro parent。
3. 能生成 intro diff。
4. 能生成 fix diff。
5. Step 1 能引用具体文件和函数作为证据。

## 11. Phase 10：批量运行

### 11.1 中批量前检查

运行 100 条前，必须检查：

1. `output/summary.csv` 字段完整。
2. 失败任务有明确 fail_code。
3. 同一 repo 并行时没有 checkout 互相覆盖。
4. prompt 没有要求 JSON 输出。
5. 输出没有可执行 PoC。

### 11.2 批量运行命令

```bash
python main.py run --max 100 --offline
python main.py run --max 100 --max-workers 2
```

建议：

1. 先 offline 跑分类和总结。
2. 再对重点样本开启 clone 做 Step 1 代码验证。
3. 不建议一开始对 4992 条全部 clone。

### 11.3 批量报告

生成：

```text
output/batch_report.md
```

内容：

```text
total_tasks
success_count
failed_count
fail_code_distribution
category_distribution
module_distribution
needs_new_module_type_count
manual_review_needed_count
```

## 12. 给代码模型的执行约束

后续使用 Mimo 2.5 Pro 或 Claude Code 实现时，把本节作为强约束放进任务提示。

### 12.1 不允许自由发挥的点

1. 不要改变输入文件名。
2. 不要改变 Excel 字段映射。
3. 不要把项目名转小写。
4. 不要把 agent 输出改回 JSON。
5. 不要把 `project-module-types.md` 改写成另一套 taxonomy。
6. 不要照搬 `project-module-types.md` 的 JSON 输出要求；只复用其中的模块分类和分析流程。
7. 不要运行目标项目代码。
8. 不要安装目标项目依赖。
9. 不要跳过 dry-run 和小样本验收。
10. 不要在同一个 repo 工作目录中并发 checkout。

### 12.2 每次实现只做一个阶段

建议任务拆分：

1. 只实现 Phase 0，跑通 preflight。
2. 只实现 Phase 1，跑通 list-tasks。
3. 只实现 Phase 2，跑通 resolve-tasks。
4. 只实现 Phase 3，跑通 dry-run 输出。
5. 只实现 Phase 4，跑通 build-evidence。
6. 只实现 Phase 5，跑通 collect-code。
7. 只实现 Phase 6，跑通 offline analyzer。
8. 只实现 Phase 7，跑通 summary。
9. 最后实现 full run。

不要一次要求模型实现所有模块。

### 12.3 每个阶段结束必须报告

报告格式：

```text
已实现文件：
- ...

已运行命令：
- ...

命令结果：
- ...

生成文件：
- ...

未完成/风险：
- ...
```

## 13. 常见错误清单

实现时重点避免：

1. `pd.read_excel()` 只读默认 sheet，导致只读到汇总而没有漏洞明细。
2. 把 Excel 字段 `cve-id` 错写成 `cve_id` 直接读取。
3. 把 `BerriAI_litellm` 转成 `berriai_litellm`。
4. GHSA-only 任务错误查找 `cves/` 目录。
5. 只取 SAST 的第一个 finding，漏掉后续 findings。
6. 用 `intro_commit -> fix_commit` 大 diff 代替 `fix_parent -> fix_commit`。
7. offline 模式下伪造“已代码验证”。
8. prompt 要求 JSON，违背进展文档要求。
9. summary 依赖复杂自然语言解析，导致字段不稳定。
10. 并行任务 checkout 同一个 repo，互相覆盖。
11. 忽略 `project-module-types.md`，继续使用旧的 M01-M18 简化模块表。
12. 直接照搬 `project-module-types.md` 的 JSON schema，导致 Step 2 输出不能被 Markdown summary 提取。

## 14. 最小可运行版本定义

最小可运行版本不要求真实 LLM，也不要求 clone repo，但必须满足：

1. `python main.py preflight` 成功。
2. `python main.py list-tasks --max 10` 成功。
3. `python main.py resolve-tasks --max 20` 成功。
4. `python main.py dry-run --max 3` 生成完整输出目录。
5. `python main.py build-evidence --project BerriAI_litellm --id CVE-2026-42271` 成功。
6. `output/summary.csv` 可生成。

达到最小可运行版本后，再接入 Claude Code 或其他 LLM 做真实四步分析。
