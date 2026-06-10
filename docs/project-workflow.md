# AI-VulnAtlas 项目工作流程文档

## 1. 项目概述

AI-VulnAtlas 是一个 AI 驱动的漏洞自动化分析系统，用于分析 AI 相关开源项目（AstrBot、Dify、OpenHands、LiteLLM、Flowise、LangChain、n8n 等）的安全漏洞。系统对每个漏洞（CVE 或 GitHub Security Advisory）执行四步 LLM 分析流程，生成结构化 Markdown 报告。

项目处理约 3,365 个漏洞任务，数据来源为 Excel 任务表和预计算的时间线/SAST 数据包。

## 2. 整体数据流

```
输入数据                    处理流程                      输出结果
┌─────────────────┐
│ vuln-analyzed-  │    ┌──────────────┐
│ 0605.xlsx       │───>│ TaskLoader   │
│ (3365 个任务)    │    └──────┬───────┘
└─────────────────┘           │
                              v
┌─────────────────┐    ┌──────────────┐
│ ai-vulns-timeline│    │RecordResolver│──> 查找数据目录
│ .zip            │───>└──────┬───────┘
│ (时间线/SAST)    │           │
└─────────────────┘           v
                       ┌──────────────┐     ┌─────────────────┐
                       │EvidenceBuilder│───>│ VulnEvidence    │
                       │ (加载证据文件) │    │ (证据包)         │
                       └──────┬───────┘     └─────────────────┘
                              │
                              v
                       ┌──────────────┐
                       │ RepoManager  │──> 克隆仓库、收集 diff/代码窗口
                       │ (可选，需网络)│
                       └──────┬───────┘
                              │
                              v
                       ┌──────────────┐
                       │  Analyzer    │──> 四步 LLM 分析
                       │ (调用 LLM)   │
                       └──────┬───────┘
                              │
              ┌───────────────┼───────────────┐
              v               v               v
       ┌────────────┐  ┌────────────┐  ┌────────────┐
       │OutputWriter│  │StateManager│  │summary.csv │
       │ (写文件)    │  │ (进度追踪)  │  │ (汇总表)   │
       └────────────┘  └────────────┘  └────────────┘
```

## 3. 代码文件说明

### 3.1 核心入口

| 文件 | 职责 |
|------|------|
| `main.py` | 主入口和 CLI 编排器。定义 10 个子命令，串联所有模块。包含 `TaskRunResult` 数据类、`process_single_task()` 单任务处理函数、`finalize_task_result()` 主线程结果处理函数，支持 `--project-list` 过滤和 `--max-workers` 并行调度 |
| `config.py` | 配置管理。从 `.env` 文件和环境变量加载 LLM 密钥、路径、模型参数 |
| `models.py` | 数据模型。定义 `VulnerabilityTask`（任务身份）和 `VulnEvidence`（证据包）两个 dataclass |

### 3.2 数据加载层

| 文件 | 职责 |
|------|------|
| `task_loader.py` | 从 Excel 文件读取任务列表。加载"汇总"sheet 的项目元数据，遍历每个项目 sheet 构建 `VulnerabilityTask` 对象 |
| `record_resolver.py` | 将任务映射到数据目录。在 `cves/` 和 `security_advisories/` 下查找匹配目录，支持 CVE ID 跨来源回退和项目目录大小写不敏感匹配 |
| `dataset_preparer.py` | 预检查数据就绪状态。检查 Excel 和 zip 文件是否存在，解压 zip，验证子目录结构 |
| `evidence_builder.py` | 构建证据包。从数据目录加载 `timeline.json`、`relevance.json`、`one_issue.txt`、`root_cause.md`、`root_cause_zh.md`、`sast_standardized.json` |

### 3.3 代码收集层

| 文件 | 职责 |
|------|------|
| `repo_manager.py` | Git 仓库操作。克隆仓库（`--filter=blob:none` 部分克隆），在特定 commit 创建 worktree，收集 intro/fix diff 和漏洞位置的代码窗口（40 行上下文） |

### 3.4 LLM 分析层

| 文件 | 职责 |
|------|------|
| `analyzer.py` | 分析编排器。按顺序执行 4 个分析步骤，每步调用 LLM 并校验输出格式，失败时重试一次，仍失败则写入可解析的 stub |
| `prompts.py` | Prompt 模板。构建 4 个 prompt，注入漏洞信息、时间线、根因、SAST 数据、代码证据和模块分类体系 |
| `llm_client.py` | 多供应商 LLM 客户端。支持 `none`（占位符）、`anthropic`、`openai`、`deepseek`（Anthropic 兼容）、`custom`（OpenAI 兼容） |

### 3.5 输出层

| 文件 | 职责 |
|------|------|
| `output_writer.py` | 写入所有输出文件：`metadata.md`、`evidence_bundle.md`、步骤文件、`final_case_summary.md`，追加 `summary.csv` 行 |
| `markdown_parser.py` | Markdown 字段提取引擎。提取 `- key: value` 格式的字段值，按枚举归一化，提供每步解析器和 `parse_task_output()` 函数 |
| `state_manager.py` | 进度追踪。通过 `state/progress.jsonl` 记录任务状态（running/success/failed），支持去重和 `--force` 重跑 |

## 4. CLI 命令说明

```bash
python3 main.py <command> [options]
```

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `preflight` | 检查数据就绪状态，必要时解压 zip | `--max-tasks` |
| `list-tasks` | 从 Excel 列出所有任务 | `--max` |
| `resolve-tasks` | 将任务映射到数据目录 | `--max` |
| `dry-run` | 使用占位内容生成输出目录 | `--max` |
| `build-evidence` | 为指定任务构建证据包 | `--project`, `--id` |
| `collect-code` | 为指定任务收集代码证据 | `--project`, `--id` |
| `run` | 运行完整分析流程 | `--max`, `--offline`, `--project`, `--id`, `--force`, `--project-list`, `--max-workers` |
| `rebuild-summary` | 从输出文件重建 summary.csv | — |
| `batch-report` | 生成批量统计报告 | — |
| `audit-output` | 输出质量审计 | — |

### 常用命令示例

```bash
# 完整流程
python3 main.py preflight
python3 main.py list-tasks --max 10
python3 main.py resolve-tasks --max 20
python3 main.py run --max 5

# 单任务分析
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117

# 离线模式（不克隆仓库）
python3 main.py run --max 5 --offline

# 强制重跑已完成任务
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force

# 按项目过滤（只处理指定项目）
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max 10

# 并行执行（4 个 worker，不同项目并行，同项目串行）
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 4 --max 10

# 并行 + 强制重跑
python3 main.py run --project-list AstrBotDevs_AstrBot --max-workers 2 --max 5 --force

# 重建汇总和报告
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

## 5. 并行执行语义

### 5.1 `--project-list` 任务过滤

`--project-list` 接受逗号分隔的项目名白名单，精确匹配 Excel `project` 字段：

```bash
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP
```

过滤顺序固定为：

1. `--project-list`：按项目名白名单过滤
2. `--project` + `--id`：单任务精确过滤（若提供）
3. `--force` / `completed_keys`：是否跳过已完成任务
4. `--max`：截断任务数

校验规则：

- `--project-list` 中有不存在的项目名 → 报错退出
- `--project` 不在 `--project-list` 中 → 报错退出

### 5.2 `--max-workers` 并行调度

`--max-workers` 控制单进程内的并行 worker 数量（默认 1，即串行）：

```bash
python3 main.py run --max-workers 4 --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP
```

并行调度规则：

- **按 task 并行**：多个 task 可同时运行
- **同 project 串行**：同一项目的多个 task 不会同时运行（避免 Git 仓库/worktree 冲突）
- **不同 project 并行**：不同项目的 task 可以同时运行

实现机制：

- `TaskRunResult`：单任务处理结果数据类（`task`, `status`, `fail_code`, `fail_reason`）
- `process_single_task(config, task)`：worker 函数，处理单个任务的证据收集、代码收集、分析，返回 `TaskRunResult`。不写全局状态文件
- `finalize_task_result(config, state, writer, result, task_index, total)`：主线程函数，根据 `TaskRunResult` 写入 `progress.jsonl` 和 `summary.csv`
- `ThreadPoolExecutor`：线程池执行器，`max_workers <= 1` 时走串行路径
- `in_flight` dict：保证每个 project 最多 1 个 in-flight future

### 5.3 并发写策略

并行模式下的文件写入职责：

| 文件 | 写入者 | 说明 |
|------|--------|------|
| `state/progress.jsonl` | 主线程 | 提交时写 `running`，完成时写 `success`/`failed` |
| `output/summary.csv` | 主线程 | 任务完成后由 `finalize_task_result()` 追加 |
| `output/batch_report.md` | 主线程 | 全部任务结束后统一生成 |
| `output/{project}/{id}/*.md` | `process_single_task()` | task 私有目录，worker 直接写入 |

### 5.4 约束

- 仅支持**单个 `python3 main.py run` 进程内部**并行
- 不支持多个 `run` 进程同时写同一个工作目录
- 最终可信统计仍建议使用 `rebuild-summary` 重建

## 6. 输出目录结构

```
output/
├── {project}/
│   └── {canonical_id}/
│       ├── metadata.md                           # 任务元数据
│       ├── evidence_bundle.md                    # 证据包
│       ├── 01_version_verification.md            # Step 1 输出
│       ├── 02_module_classification.md           # Step 2 输出
│       ├── 03_vulnerability_pattern_classification.md  # Step 3 输出
│       ├── 04_exploit_condition_summary.md       # Step 4 输出
│       └── final_case_summary.md                 # 四步汇总
├── summary.csv                                   # 全局汇总表
├── batch_report.md                               # 批量统计报告
├── audit_report.md                               # 质量审计报告
└── preflight_report.md                           # 数据就绪检查报告
```

## 7. 四步分析流程

### Step 1：版本验证（Version Verification）

验证漏洞引入时间点是否正确，以及漏洞在引入版本时是否已存在。

**输出字段：**

| 字段 | 含义 | 合法值 |
|------|------|--------|
| `intro_time_verdict` | 引入时间点判定 | `correct` / `likely_correct` / `incorrect` / `insufficient_evidence` / `not_verifiable` |
| `vuln_exists_at_intro_version` | 漏洞在引入版本是否已存在 | `yes` / `likely_yes` / `no` / `insufficient_evidence` |
| `manual_review_needed` | 是否需要人工复核 | `yes` / `no` |

### Step 2：模块分类（Module Classification）

将漏洞归类到 `project-module-types.md` 定义的 18 类功能模块（A-R taxonomy）中。

**输出字段：**

| 字段 | 含义 | 合法值 |
|------|------|--------|
| `architecture_type` | 项目架构类型 | `ai_agent_framework` / `ai_api_gateway` / `ai_application_platform` / `ai_model_serving` / `agent_runtime_platform` / `llm_application_platform` / `mcp_server` / `plugin_based_ai_extension` |
| `architecture_confidence` | 架构判定置信度 | `high` / `medium` / `low` |
| `classification_type` | 分类匹配类型 | `matched_existing_module` / `uncertain_existing_module` / `needs_new_module_type` |
| `primary_module` | 主要功能模块 | A-R taxonomy 中的 module_id（如 `authentication`、`mcp_server`、`plugin_loader`） |
| `secondary_modules` | 次要功能模块 | 逗号分隔的 module_id 列表 |
| `confidence` | 分类置信度 | `high` / `medium` / `low` |

**A-R 模块分类体系：**

| 类别 | 模块 ID 示例 | 说明 |
|------|-------------|------|
| A. Agent Systems | `agent_core`, `agent_planning`, `agent_orchestration` | Agent 核心、规划、编排 |
| B. LLM Integration | `llm_provider_abstraction`, `model_router`, `prompt_management` | LLM 集成、路由、提示词管理 |
| C. RAG and Knowledge | `document_ingestion`, `vector_store`, `retrieval_pipeline` | RAG、知识检索 |
| D. Tools and Function Calling | `tool_registry`, `mcp_server`, `mcp_client`, `code_sandbox` | 工具注册、MCP、代码沙箱 |
| E. Workflow Engine | `workflow_engine`, `node_system`, `execution_runtime` | 工作流引擎、节点系统 |
| F. Conversation | `chat_session`, `message_pipeline`, `multimodal_message` | 对话、消息处理 |
| G. Multimodal | `speech_to_text`, `image_generation`, `media_understanding` | 多模态处理 |
| H. Data and Storage | `database_orm`, `vector_database`, `cache_system` | 数据存储 |
| I. API and Communication | `rest_api`, `websocket_server`, `webhook_system` | API 和通信 |
| J. Authentication and Security | `authentication`, `input_validation`, `encryption` | 认证和安全 |
| K. Observability | `logging_system`, `tracing_system`, `health_check` | 可观测性 |
| L. Configuration | `config_loader`, `feature_flags` | 配置管理 |
| M. Deployment | `container_build`, `k8s_deployment`, `ci_cd_pipeline` | 部署运维 |
| N. Plugins | `plugin_loader`, `plugin_registry`, `hook_system` | 插件扩展 |
| O. Frontend | `canvas_editor`, `dashboard_ui` | 前端 UI |
| P. Internationalization | `i18n_engine`, `translation_management` | 国际化 |
| Q. Queues and Async | `task_queue`, `worker_process`, `event_bus` | 队列和异步 |
| R. Collaboration | `multi_tenancy`, `workspace_management` | 协作 |

### Step 3：漏洞模式分类（Vulnerability Pattern Classification）

将漏洞分为 A/B/C 三类，并填写四象限字段。

**输出字段：**

| 字段 | 含义 | 合法值 |
|------|------|--------|
| `category` | 漏洞类别 | `A` / `B` / `C` |
| `category_name` | 类别名称 | `传统类型漏洞` / `AI功能实现+传统方式` / `AI场景新漏洞模式` |
| `confidence` | 分类置信度 | `high` / `medium` / `low` |
| `input_type` | 输入来源类型 | `user_input` / `api_input` / `file_input` / `model_output` 等 |
| `input_subtype` | 输入子类型 | 自由文本 |
| `mechanism_type` | 漏洞机制类型 | `injection` / `overflow` / `auth_bypass` / `logic_flaw` 等 |
| `mechanism_subtype` | 机制子类型 | 自由文本 |
| `requires_ai_function` | 是否需要 AI 功能才能触发 | `yes` / `no` / `uncertain` |
| `ai_native_subtype` | AI 原生子类型 | `none` / `direct_prompt_injection` / `indirect_prompt_injection` / `rag_poisoning` / `tool_output_poisoning` / `memory_poisoning` / `delegation_hijack` / `semantic_policy_bypass` / `unknown` |
| `cross_agent` | 是否跨 Agent | `yes` / `no` / `uncertain` |

**A/B/C 分类语义：**

| 类别 | 名称 | 定义 |
|------|------|------|
| **A** | 传统类型漏洞 | 漏洞触发、利用和影响都不依赖 AI 语义机制。即使项目是 AI 项目，只要漏洞本质是普通 Web 或系统安全问题，也归入该类 |
| **B** | AI功能实现+传统方式 | 漏洞底层机制仍是传统漏洞，但攻击入口、传播路径或影响依赖 AI 功能模块。判断关键是：去掉该 AI 功能模块后，攻击链是否仍然成立 |
| **C** | AI场景新漏洞模式 | 漏洞核心依赖语义注入、上下文污染、Agent 委托链劫持、工具返回值污染、记忆污染、跨 Agent 欺骗等 AI-native 机制 |

### Step 4：利用条件总结（Exploit Condition Summary）

总结漏洞的利用方式、前提条件、攻击链和影响。

**输出小节：**

| 小节 | 内容 |
|------|------|
| Exploit Method | 利用方式描述（不输出可执行 payload） |
| Prerequisites | 前提条件：认证、权限、配置、网络可达性、AI 功能启用等 |
| Attack Chain | 攻击链步骤 |
| Impact | 影响范围和危害 |
| Difficulty | 利用难度：`easy` / `medium` / `hard` |
| Defensive Gap | 防御差距分析 |
| Uncertainty | 不确定性和局限性 |

## 8. 汇总文件字段说明

### 8.1 summary.csv（30 个字段）

**任务身份字段：**

| 字段 | 含义 | 示例 |
|------|------|------|
| `project` | 项目名称 | `AstrBotDevs_AstrBot` |
| `canonical_id` | 漏洞 ID | `CVE-2026-6117` |
| `source` | 数据来源 | `cves` / `security_advisories` |
| `cwe` | CWE 编号 | `CWE-264, CWE-265` |
| `publish_at` | 发布时间 | `2026-04-12T05:16:01.287` |
| `cve_id` | CVE 编号 | `CVE-2026-6117` |
| `adv_id` | Advisory 编号 | （可为空） |

**Step 1 字段：**

| 字段 | 含义 |
|------|------|
| `intro_time_verdict` | 引入时间点判定 |
| `vuln_exists_at_intro_version` | 漏洞在引入版本是否已存在 |
| `manual_review_needed` | 是否需要人工复核 |

**Step 2 字段：**

| 字段 | 含义 |
|------|------|
| `architecture_type` | 项目架构类型 |
| `architecture_confidence` | 架构判定置信度 |
| `classification_type` | 分类匹配类型 |
| `primary_module` | 主要功能模块 |
| `secondary_modules` | 次要功能模块 |
| `confidence` | 分类置信度 |

**Step 3 字段：**

| 字段 | 含义 |
|------|------|
| `category` | 漏洞类别（A/B/C） |
| `category_name` | 类别名称（中文） |
| `input_type` | 输入来源类型 |
| `input_subtype` | 输入子类型 |
| `mechanism_type` | 漏洞机制类型 |
| `mechanism_subtype` | 机制子类型 |
| `requires_ai_function` | 是否需要 AI 功能 |
| `ai_native_subtype` | AI 原生子类型 |
| `cross_agent` | 是否跨 Agent |

**Step 4 和元数据字段：**

| 字段 | 含义 |
|------|------|
| `difficulty` | 利用难度 |
| `overall_confidence` | 总体置信度 |
| `manual_review_reason` | 人工复核原因 |
| `fail_code` | 失败代码 |
| `fail_reason` | 失败原因 |

### 8.2 batch_report.md

| 统计项 | 含义 |
|--------|------|
| Total Tasks | 唯一任务数（按 task_key 去重） |
| Success | 成功完成的任务数 |
| Failed | 失败的任务数 |
| Running | 正在运行的任务数 |
| Pending/Unknown | 待处理或状态未知的任务数 |
| Output Task Dirs | 输出目录数 |
| Summary Rows | summary.csv 行数 |
| Success Rate | 成功率 |
| Failure Code Distribution | 失败代码分布 |
| Category Distribution | A/B/C 类别分布 |
| Module Distribution | 功能模块分布 |

### 8.3 audit_report.md

| 检查项 | 含义 |
|--------|------|
| Total Task Dirs | 扫描的任务目录总数 |
| Complete Task Dirs | 包含全部 7 个文件的目录数 |
| Missing Files | 缺失文件列表 |
| Missing Required Fields | 缺失必填字段列表 |
| Prompt Leakage Files | 包含 prompt 泄漏的文件列表 |
| API Error Files | 包含 API 错误信息的文件列表 |
| JSON Output Files | 输出为 JSON 而非 Markdown 的文件列表 |

## 9. 输入数据说明

### 9.1 vuln-analyzed-0605.xlsx

Excel 任务表，包含约 3,365 个漏洞任务。

- **汇总 sheet**：项目元数据（项目名、GitHub URL、Owner、Repo）
- **各项目 sheet**：漏洞列表，每行包含 `source`、`cve-id`、`adv-id`、`publish-at`、`cwe` 等字段

### 9.2 ai-vulns-timeline.zip

解压后位于 `data/ai-vulns-timeline/`，按以下结构组织：

```
data/ai-vulns-timeline/
├── cves/
│   └── {project}/
│       └── {cve_id}/
│           ├── relevance_out/
│           │   ├── timeline.json      # 引入/修复 commit、日期
│           │   └── relevance.json     # 相关性评估
│           └── verify_requirements/
│               ├── one_issue.txt      # 原始漏洞描述
│               ├── root_cause.md      # 英文根因分析
│               ├── root_cause_zh.md   # 中文根因分析
│               └── sast_standardized.json  # SAST 发现
└── security_advisories/
    └── {project}/
        └── {adv_id 或 cve_id}/
            └── ...（同上结构）
```

`RecordResolver` 优先使用 `cves/{project}/{cve_id}`。如果该路径缺失，会回退到 `security_advisories/{project}/{cve_id}`，再尝试 `security_advisories/{project}/{adv_id}`。该回退只允许在同一个 project 下进行，不跨项目复用相同 CVE ID 的数据。

### 9.3 project-module-types.md

功能模块分类体系文档，定义 18 类（A-R）功能模块和 8 种架构类型，作为 Step 2 分析的 LLM 上下文。

## 10. 配置说明

### 10.1 .env 文件

```env
# LLM 供应商：none | anthropic | openai | deepseek | custom
LLM_PROVIDER=deepseek

# DeepSeek 配置（Anthropic 兼容接口）
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_API_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseek-v4-pro
LLM_MAX_TOKENS=4096

# 可选：并行 worker 数（默认 1，即串行；>1 时启用线程池并行）
MAX_WORKERS=1
```

### 10.2 支持的 LLM 供应商

| 供应商 | 说明 |
|--------|------|
| `none` | 占位符模式，返回 `insufficient_evidence`，用于离线测试 |
| `anthropic` | Anthropic Claude API |
| `openai` | OpenAI API |
| `deepseek` | DeepSeek API（Anthropic 兼容接口） |
| `custom` | 自定义 OpenAI 兼容 API |

## 11. 项目目录结构

```
ai_vuln/
├── main.py                    # 主入口
├── config.py                  # 配置管理
├── models.py                  # 数据模型
├── task_loader.py             # Excel 任务加载
├── record_resolver.py         # 数据目录解析
├── evidence_builder.py        # 证据包构建
├── repo_manager.py            # Git 仓库管理
├── analyzer.py                # LLM 分析编排
├── prompts.py                 # Prompt 模板
├── llm_client.py              # LLM API 客户端
├── output_writer.py           # 输出文件写入
├── state_manager.py           # 进度状态追踪
├── markdown_parser.py         # Markdown 字段提取
├── dataset_preparer.py        # 数据预检查
├── project-module-types.md    # 模块分类体系
├── .env                       # API 配置
├── requirements.txt           # Python 依赖
├── vuln-analyzed-0605.xlsx    # 漏洞任务表
├── ai-vulns-timeline.zip      # 时间线数据包
├── data/                      # 解压后的数据
├── repos/                     # 克隆的 Git 仓库
├── worktrees/                 # Git worktrees
├── output/                    # 分析输出
├── state/                     # 进度状态文件
├── logs/                      # 运行日志
└── docs/                      # 项目文档
```
