# AI-VulnAtlas 漏洞分析 Agent 实现规划

## 1. 项目目标

构建一个自动化漏洞分析 Agent，基于 `vuln-analyzed-0605.xlsx` 和 `ai-vulns-timeline.zip` 中已有的漏洞时间线、相关性判断、根因报告和 SAST 结果，对每个漏洞完成以下任务：

1. **版本引入时间验证**：切换到漏洞引入 commit，判断引入时间是否正确，并验证该版本上漏洞是否存在。
2. **模块分类**：按照 AI 应用功能模块 taxonomy 判断漏洞所在模块；若现有 taxonomy 不覆盖，输出建议新增模块类型。
3. **漏洞模式分类**：结合漏洞描述、漏洞所在模块和项目自身定位，判断漏洞属于传统漏洞、AI 功能实现加传统方式、或 AI 场景新漏洞模式。
4. **利用方式和前提总结**：输出漏洞利用方式、利用前提、攻击影响和不确定性。

本任务服务于 proposal 中的 AI-VulnAtlas 数据集构建和后续统计分析。核心要求是让 agent 逐步写文件输出，避免依赖 agent 返回 JSON 后再由脚本解析。

## 2. 当前数据形态

### 2.1 输入文件

当前工作区的真实输入为：

```text
vuln-analyzed-0605.xlsx
ai-vulns-timeline.zip
proposal.docx
进展文档.txt
```

### 2.2 Excel 结构

`vuln-analyzed-0605.xlsx` 不是单一扁平表，而是：

1. `汇总` sheet：项目级统计和项目元数据。
2. 每个项目一个 sheet：前 7 行为项目统计，第 9 行为漏洞明细表头，第 10 行之后为漏洞明细。

项目 sheet 的漏洞明细字段为：

```text
source | cve-id | adv-id | publish-at | cwe
```

因此，任务加载器不能只调用默认 `pd.read_excel(excel_path)`。必须遍历所有项目 sheet，并将项目级元数据从 `汇总` sheet 合并到每条漏洞任务。

### 2.3 Zip 数据结构

`ai-vulns-timeline.zip` 中包含：

```text
cves/{project}/{CVE-ID}/
security_advisories/{project}/{GHSA-ID}/
```

常见证据文件包括：

```text
relevance_out/timeline.json
relevance_out/relevance.json
verify_requirements/one_issue.txt
verify_requirements/root_cause.md
verify_requirements/root_cause_zh.md
verify_requirements/sast_standardized.json
```

实现时支持两种模式：

1. **解压模式**：先解压到 `data/ai-vulns-timeline/`，后续按普通文件读取。
2. **Zip 直读模式**：通过 `zipfile` 直接读取，用于避免大量小文件解压。

默认推荐解压模式，便于人工检查和调试。

## 3. 总体架构

```text
main.py
│
├── DatasetPreparer
│   ├── ensure_data_root()
│   └── unzip_if_needed()
│
├── TaskLoader
│   ├── load_project_summary()
│   ├── load_project_detail_sheets()
│   └── build_tasks()
│
├── RecordResolver
│   ├── resolve_cve_dir()
│   ├── resolve_advisory_dir()
│   └── merge_cve_and_advisory_evidence()
│
├── RepoManager
│   ├── clone_or_fetch_repo()
│   ├── create_worktree_or_checkout()
│   ├── collect_intro_diff()
│   ├── collect_fix_diff()
│   └── collect_targeted_code_snippets()
│
├── EvidenceBuilder
│   ├── load timeline.json
│   ├── load relevance.json
│   ├── load one_issue.txt
│   ├── load root_cause_zh.md
│   ├── load sast_standardized.json
│   ├── load project profile
│   └── pack bounded evidence bundle
│
├── Analyzer
│   ├── step1_version_verification()
│   ├── step2_module_classification()
│   ├── step3_vulnerability_pattern_classification()
│   └── step4_exploit_condition_summary()
│
├── OutputWriter
│   ├── write markdown step files
│   ├── write final_case_summary.md
│   └── update summary.csv
│
└── StateManager
    ├── run_state.sqlite
    └── progress.jsonl
```

## 4. 数据模型

### 4.1 VulnerabilityTask

```python
@dataclass
class VulnerabilityTask:
    project: str
    github_url: str
    owner: str
    repo: str

    source: str  # cves / security_advisories / both
    cve_id: Optional[str]
    adv_id: Optional[str]
    canonical_id: str  # cve_id if present else adv_id
    task_key: str      # "{project}:{source}:{canonical_id}"

    publish_at: Optional[str]
    cwe: Optional[str]

    cve_dir: Optional[str]
    advisory_dir: Optional[str]
    primary_data_dir: Optional[str]

    status: str = "pending"
    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None
```

`task_key` 不能只使用 `canonical_id`，因为不同项目或不同来源可能出现重复编号。断点续传、输出目录和汇总表均使用 `task_key` 或 `project/canonical_id` 的组合。

### 4.2 VulnEvidence

```python
@dataclass
class VulnEvidence:
    task: VulnerabilityTask

    timeline: Optional[dict]
    relevance: Optional[dict]
    issue_text: Optional[str]
    root_cause: Optional[str]
    root_cause_zh: Optional[str]
    sast: Optional[dict]

    intro_commit: Optional[str]
    intro_parent_commit: Optional[str]
    intro_date: Optional[str]
    fix_commit: Optional[str]
    fix_parent_commit: Optional[str]
    fix_date: Optional[str]
    disclosure_date: Optional[str]

    project_profile: Optional[dict]
    architecture_type: Optional[str]

    vuln_positions: list[dict]
    dataflow: list[dict]

    code_at_intro: dict[str, str]
    code_at_intro_parent: dict[str, str]
    intro_diff: Optional[str]
    fix_diff: Optional[str]

    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None
```

`project_profile` 用于满足“基于项目自身定位进行分类”的要求，来源包括 GitHub URL、项目 README 摘要、deepwiki/codewiki 结果或项目说明文件。若缺失，应在输出中明确写为 `insufficient_project_profile`，而不是隐式忽略。

## 5. 任务加载与目录映射

### 5.1 TaskLoader

任务加载流程：

1. 读取 `汇总` sheet，建立 `project -> github_url/owner/repo` 映射。
2. 遍历除 `汇总` 外的所有项目 sheet。
3. 跳过前 8 行，从第 9 行读取漏洞明细表头。
4. 将实际字段 `cve-id`、`adv-id`、`publish-at` 映射为内部字段 `cve_id`、`adv_id`、`publish_at`。
5. 跳过 `cve-id` 和 `adv-id` 均为空的行。
6. 合并重复任务：同一 `project + canonical_id` 只生成一条任务，但保留来源信息。

### 5.2 RecordResolver

目录名必须保留 Excel 中的 `project` 原样，例如：

```text
BerriAI_litellm
FlowiseAI_Flowise
langchain-ai_langchain
```

不能统一 `.lower()`，否则会找不到 zip 或解压目录中的真实路径。

映射规则：

| 情况 | 数据目录 |
|------|----------|
| 有 CVE | 优先 `cves/{project}/{cve_id}/`，找不到时回退 `security_advisories/{project}/{cve_id}/` |
| 只有 GHSA | `security_advisories/{project}/{adv_id}/` |
| CVE 和 GHSA 都有 | 先按 CVE 查 `cves/{project}/{cve_id}/`，再回退 `security_advisories/{project}/{cve_id}/`，再查 `security_advisories/{project}/{adv_id}/` |
| 同一 CVE 多来源 | 合并为一条任务，source 标记为 `both` |

如果 CVE 目录缺失但 advisory 目录存在，应降级使用 advisory 目录。后续如需要审计解析来源，可再增加 `source_resolution` 写入 metadata；当前实现以 `CVE Dir`、`Advisory Dir`、`Primary Data Dir` 记录实际命中路径。

注意：有些 CVE ID 目录会被数据包放在 `security_advisories` 下，resolver 必须支持跨来源目录回退，但不能跨 project 匹配。

## 6. RepoManager 设计

### 6.1 基本原则

RepoManager 只做静态操作：

1. clone/fetch
2. checkout/worktree
3. git diff
4. 读取目标文件片段

不得安装依赖，不得运行项目代码，不得运行 PoC。

### 6.2 并行安全

同一个仓库的多个任务不能在同一个工作目录中并发 checkout。支持以下任一方案：

1. **推荐方案：git worktree**
   - 主仓库只负责 fetch。
   - 每个任务创建独立 worktree。
   - 任务结束后删除 worktree。

2. **备选方案：repo 级锁**
   - 同一 repo 的任务串行执行 checkout。
   - 不同 repo 可以并行。

3. **备选方案：任务级 clone**
   - 每个任务独立 clone，最安全但成本最高。

### 6.3 必须收集的代码证据

Step 1 不能只比较 `intro_commit -> fix_commit`。必须收集：

```text
intro_parent_commit = intro_commit~1
code_at_intro_parent
code_at_intro
intro_diff = intro_parent_commit..intro_commit

fix_parent_commit = fix_commit~1
fix_diff = fix_parent_commit..fix_commit
```

判断逻辑：

1. `intro_diff` 用于判断漏洞相关代码形态是否在引入 commit 出现。
2. `code_at_intro_parent` 用于判断前一个 commit 是否不存在该漏洞形态。
3. `code_at_intro` 用于判断引入版本上漏洞是否存在。
4. `fix_diff` 用于判断修复 commit 是否真正增加了防护或移除了危险路径。

代码读取应优先基于 `sast_standardized.json` 中的 `vul_pos` 和 `dataflow` 文件路径，只读取相关文件或相关行附近窗口，避免上下文过大。

## 7. EvidenceBuilder 设计

EvidenceBuilder 负责把每条任务需要的证据打包给 Analyzer。

加载优先级：

1. `timeline.json`
2. `relevance.json`
3. `root_cause_zh.md`
4. `root_cause.md`
5. `sast_standardized.json`
6. `one_issue.txt`
7. advisory 或 CVE 原始文本
8. project profile
9. 代码片段和 diff

证据包必须保留缺失状态。例如：

```text
timeline: present
relevance: present
root_cause_zh: missing
sast: present
project_profile: missing
repo_checkout: failed
```

缺失数据不一定导致任务失败。只有 Step 1 严重依赖代码验证时，才将结果标为 `not_verifiable` 或 `insufficient_evidence`。

## 8. 模块 Taxonomy

模块分类采用开放 taxonomy。初始模块如下：

| ID | 模块 | 说明 |
|----|------|------|
| M01 | Retrieval | 检索、搜索、RAG retriever、文档召回 |
| M02 | Knowledge Ingestion | 文档上传、解析、chunk、索引构建 |
| M03 | Embedding / Vector Store | embedding、向量数据库、相似度搜索 |
| M04 | Memory / Context | 记忆、会话上下文、上下文持久化 |
| M05 | Tool Use / Function Calling | 工具调用、函数调用、MCP client/server、外部动作 |
| M06 | Planning / Reasoning | 任务规划、链式推理、Agent 决策 |
| M07 | Inter-Agent Communication | 多 Agent 消息、委托、协作链 |
| M08 | Workflow / Automation | 工作流节点、自动化任务、触发器 |
| M09 | Model Serving / Inference | 模型加载、推理服务、模型 API |
| M10 | Prompt / Template | prompt 模板、system prompt、提示词拼接 |
| M11 | Output / UI | 前端展示、渲染、输出过滤、DLP |
| M12 | Auth / Permission | 认证、授权、租户隔离、角色校验 |
| M13 | API / Web Backend | 普通 HTTP API、路由、中间件、Web 后端 |
| M14 | Storage / Database | 关系数据库、对象存储、文件系统 |
| M15 | Plugin / Extension | 插件、扩展、第三方集成 |
| M16 | Supply Chain / Dependency | 依赖包、构建、镜像、包管理 |
| M17 | Configuration / Deployment | 配置、密钥、环境变量、部署脚本 |
| M18 | Other / Unknown | 证据不足或不属于以上模块 |

Step 2 输出时允许：

1. 匹配一个主模块。
2. 给出相关次模块。
3. 若 `M18` 仍无法准确表达，输出 `needs_new_module_type`，并说明建议新增模块、原因和示例代码路径。

## 9. 漏洞模式分类

Step 3 使用三类主分类：

### A. 传统类型漏洞

漏洞触发、利用和影响都不依赖 AI 语义机制。即使项目是 AI 项目，只要漏洞本质是普通 Web 或系统安全问题，也归入该类。

例子：

```text
认证绕过、普通 SSRF、普通 XSS、任意文件上传、路径遍历、SQL 注入、命令注入、依赖包 RCE
```

### B. AI 功能实现 + 传统方式

漏洞底层机制仍是传统漏洞，但攻击入口、传播路径或影响依赖 AI 功能模块。判断关键是：去掉该 AI 功能模块后，攻击链是否仍然成立。

例子：

```text
通过 RAG 文档上传触发 XSS
通过 Agent tool 参数触发 SSRF
通过 MCP stdio 配置触发命令执行
通过 workflow 节点配置触发命令注入
通过 memory 或 vector store 污染导致传统数据泄露
```

### C. AI 场景新漏洞模式

漏洞核心依赖语义注入、上下文污染、Agent 委托链劫持、工具返回值污染、记忆污染、跨 Agent 欺骗等 AI-native 机制。

例子：

```text
间接 Prompt Injection
RAG 文档投毒导致越权行为
Tool output poisoning
Memory poisoning
Agent-to-Agent privilege escalation
Context hijacking
Semantic policy bypass
LLM planning manipulation
```

### 9.1 额外统计字段

为了支持 proposal 中的四象限分析，每条漏洞还需要输出以下字段：

```text
input_type: traditional_input | ai_specific_input | mixed | unknown
input_subtype: HTTP parameter | file upload | prompt | RAG document | agent message | tool return | memory | env | other
mechanism_type: traditional_mechanism | ai_native_mechanism | mixed | unknown
mechanism_subtype: XSS | SSRF | command injection | semantic injection | trust boundary collapse | tool abuse | memory poisoning | other
requires_ai_function: yes | no | uncertain
ai_native_subtype: direct prompt injection | indirect prompt injection | RAG poisoning | tool output poisoning | memory poisoning | delegation hijack | semantic policy bypass | none | unknown
cross_agent: yes | no | uncertain
```

这些字段写入 step 文件和 summary CSV，但 step 文件仍以 Markdown 小节为主，不要求 agent 输出 JSON。

## 10. Analyzer 四步流程

### 10.1 Step 1: 版本引入时间验证

输入：

```text
timeline.json
relevance.json
root_cause_zh.md / root_cause.md
sast_standardized.json
code_at_intro_parent
code_at_intro
intro_diff
fix_diff
```

输出文件：

```text
01_version_verification.md
```

输出小节：

```markdown
# Step 1 Version Verification

## Conclusion
- intro_time_verdict: correct | likely_correct | incorrect | insufficient_evidence | not_verifiable
- vuln_exists_at_intro_version: yes | likely_yes | no | insufficient_evidence
- manual_review_needed: yes | no

## Evidence
- checked_intro_commit:
- checked_intro_parent_commit:
- checked_fix_commit:
- vulnerable_code_evidence:
- intro_diff_evidence:
- fix_diff_evidence:

## Reasoning

## Uncertainty
```

判断要求：

1. 引入 commit 中是否出现漏洞相关代码形态。
2. 引入 commit 的父 commit 是否缺少该漏洞形态。
3. 引入版本上漏洞路径是否可达。
4. 修复 diff 是否确实增加权限校验、白名单、输入校验、隔离或移除危险路径。
5. 引入日期是否早于修复日期和公开披露日期。

### 10.2 Step 2: 模块分类

输出文件：

```text
02_module_classification.md
```

输出小节：

```markdown
# Step 2 Module Classification

## Conclusion
- classification_type: matched_existing_module | uncertain_existing_module | needs_new_module_type
- primary_module:
- secondary_modules:
- confidence: high | medium | low

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

### 10.3 Step 3: 漏洞模式分类

输出文件：

```text
03_vulnerability_pattern_classification.md
```

输出小节：

```markdown
# Step 3 Vulnerability Pattern Classification

## Conclusion
- category: A | B | C
- category_name: 传统类型漏洞 | AI功能实现+传统方式 | AI场景新漏洞模式
- confidence: high | medium | low

## Project Context
- project_positioning:
- architecture_type:

## Four-Quadrant Fields
- input_type:
- input_subtype:
- mechanism_type:
- mechanism_subtype:
- requires_ai_function:
- ai_native_subtype:
- cross_agent:

## Evidence
- attack_entry_point:
- attack_mechanism:
- ai_function_involved:

## Reasoning

## Uncertainty
```

### 10.4 Step 4: 利用方式和前提总结

输出文件：

```text
04_exploit_condition_summary.md
```

输出小节：

```markdown
# Step 4 Exploit Condition Summary

## Exploit Method

## Prerequisites

## Attack Chain

## Impact

## Difficulty
- difficulty: easy | medium | hard | unknown

## Defensive Gap

## Uncertainty
```

## 11. 输出结构

每条任务输出到：

```text
output/{project}/{canonical_id}/
├── metadata.md
├── evidence_bundle.md
├── 01_version_verification.md
├── 02_module_classification.md
├── 03_vulnerability_pattern_classification.md
├── 04_exploit_condition_summary.md
└── final_case_summary.md
```

`final_case_summary.md` 汇总四步结论：

```markdown
# Final Case Summary

## Basic Info
- project:
- canonical_id:
- cve_id:
- adv_id:
- github_url:
- publish_at:
- cwe:

## Version Verification
- intro_time_verdict:
- vuln_exists_at_intro_version:
- checked_intro_commit:
- checked_fix_commit:

## Module Classification
- primary_module:
- secondary_modules:
- needs_new_module_type:

## Vulnerability Pattern
- category:
- input_type:
- mechanism_type:
- requires_ai_function:
- ai_native_subtype:
- cross_agent:

## Exploit and Prerequisites
- exploit_method:
- prerequisites:
- impact:
- difficulty:

## Confidence and Review
- overall_confidence:
- manual_review_needed:
- review_reason:
```

`summary.csv` 由程序写入，不依赖 agent JSON。字段包括：

```text
project,canonical_id,cve_id,adv_id,publish_at,cwe,
intro_time_verdict,vuln_exists_at_intro_version,
primary_module,secondary_modules,needs_new_module_type,
category,input_type,input_subtype,mechanism_type,mechanism_subtype,
requires_ai_function,ai_native_subtype,cross_agent,
difficulty,overall_confidence,manual_review_needed,fail_code
```

## 12. 失败分类

| 失败码 | 说明 |
|--------|------|
| `FAIL_NO_DATA_ROOT` | zip 未解压且无法直读 |
| `FAIL_NO_PROJECT_SHEET` | Excel 中缺少项目 sheet |
| `FAIL_NO_VULN_DIR` | 找不到 CVE 或 GHSA 子目录 |
| `FAIL_NO_TIMELINE` | 缺少 timeline.json |
| `FAIL_NO_RELEVANCE` | 缺少 relevance.json |
| `FAIL_NO_REPO_URL` | Excel 中无 GitHub URL |
| `FAIL_REPO_CLONE` | 仓库克隆或 fetch 失败 |
| `FAIL_CHECKOUT_INTRO` | 引入 commit checkout 失败 |
| `FAIL_CHECKOUT_PARENT` | 引入父 commit checkout 失败 |
| `FAIL_CHECKOUT_FIX` | 修复 commit checkout 失败 |
| `FAIL_NO_CODE_LOCATION` | SAST 和 root cause 都没有可用代码位置 |
| `FAIL_CONTEXT_TOO_LARGE` | 证据包过大且无法裁剪 |
| `FAIL_MODEL_ERROR` | LLM 调用失败 |
| `FAIL_INSUFFICIENT_EVIDENCE` | 证据不足以做出判断 |

失败任务仍应写 `metadata.md` 和失败原因，便于后续补数据。

## 13. 执行计划

### Phase 0: 数据准备和预检查

1. 检查 `vuln-analyzed-0605.xlsx` 是否可读。
2. 检查 `ai-vulns-timeline.zip` 是否存在。
3. 解压 zip 到 `data/ai-vulns-timeline/`，或启用 zip 直读模式。
4. 统计项目 sheet 数、漏洞行数、可解析目录数。
5. 输出 `preflight_report.md`。

### Phase 1: 基础框架

1. 实现 `DatasetPreparer`。
2. 实现 `TaskLoader`，支持多 sheet Excel。
3. 实现 `RecordResolver`，修正大小写目录映射。
4. 实现 `StateManager`，使用 `project:source:canonical_id` 作为任务 key。
5. 实现 `OutputWriter` 的 markdown 文件输出。

### Phase 2: 证据构建

1. 实现 `EvidenceBuilder`。
2. 实现项目 profile 加载。
3. 实现 SAST 代码路径提取。
4. 实现 repo clone/fetch。
5. 实现 worktree 或 repo 锁。
6. 收集 `code_at_intro_parent`、`code_at_intro`、`intro_diff`、`fix_diff`。

### Phase 3: 四步 Agent 分析

1. 实现 Step 1 prompt 和文件输出。
2. 实现 Step 2 prompt 和模块 taxonomy。
3. 实现 Step 3 prompt 和四象限字段。
4. 实现 Step 4 prompt 和利用前提总结。
5. 实现 `final_case_summary.md` 汇总。

### Phase 4: 小批量验证

1. 选取 10 到 20 个样本，覆盖 CVE、GHSA-only、CVE+GHSA。
2. 覆盖不同项目类型：Agent、RAG、MCP、Workflow、Model Serving、普通 Web。
3. 人工检查每一步文件是否足够清晰。
4. 记录 prompt 修改点和 taxonomy 新增候选。

### Phase 5: 批量运行

1. 中批量运行 100 条。
2. 统计失败原因和人工复核率。
3. 调整证据裁剪和 prompt。
4. 全量运行。
5. 汇总分类分布和 needs_new_module_type。

## 14. 验证方式

### 14.1 单元测试

1. `TaskLoader`：验证多 sheet 读取、第 9 行表头、字段映射。
2. `RecordResolver`：验证大小写目录、CVE、GHSA-only、CVE+GHSA。
3. `EvidenceBuilder`：验证缺失文件、SAST 提取、timeline 字段提取。
4. `RepoManager`：验证 worktree、checkout、diff、repo 锁。
5. `OutputWriter`：验证 markdown 文件和 summary CSV。

### 14.2 集成测试

1. 从 Excel 到输出目录的完整流程。
2. 断点续传。
3. 同一 repo 多漏洞并行时不互相污染。
4. zip 直读模式和解压模式至少验证一种。

### 14.3 抽样人工验证

抽样 20 到 30 条，人工检查：

1. Step 1 的引入版本判断是否有代码证据支撑。
2. Step 2 的模块分类是否符合项目架构。
3. Step 3 的 A/B/C 分类是否符合 proposal。
4. Step 4 的利用前提是否清晰可用于后续统计。

## 15. 环境和依赖

推荐依赖：

```text
anthropic>=0.18.0
pandas>=2.0.0
openpyxl>=3.1.0
GitPython>=3.1.0
```

如果环境不能安装 `pandas/openpyxl`，需要实现基于 `zipfile + xml.etree.ElementTree` 的 `.xlsx` OpenXML 读取器。当前任务优先保证数据读取可运行，而不是强依赖 pandas。

网络受限时：

1. 不能 clone 的任务进入离线模式。
2. 离线模式只基于 `timeline.json`、`root_cause_zh.md`、`sast_standardized.json` 做分类和总结。
3. Step 1 标为 `not_verifiable` 或 `insufficient_evidence`，不能伪造代码验证结论。

## 16. 安全约束

本工具处理公开漏洞数据和第三方仓库，必须遵守以下约束：

1. 不运行 PoC。
2. 不执行目标项目代码。
3. 不安装目标项目依赖。
4. 不启动目标项目服务。
5. 不对外部目标发起扫描或攻击请求。
6. 只做静态代码读取、git diff、checkout 和文本分析。
7. 输出不包含可执行 exploit，只保留描述性利用方式和前提条件。

## 17. 后续迭代

1. 根据 `needs_new_module_type` 汇总更新模块 taxonomy。
2. 根据人工复核结果加入 few-shot 示例。
3. 增加项目架构类型自动识别。
4. 增加分类分布和四象限统计报告。
5. 将结果回填到 AI-VulnAtlas 数据集字段。
