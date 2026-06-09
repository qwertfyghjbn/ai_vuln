# AI-VulnAtlas

AI 驱动的漏洞自动化分析系统，用于分析 AI 相关项目的安全漏洞。

## 快速开始

### 1. 安装依赖

```bash
pip3 install -r requirements.txt
```

依赖列表：
- `pandas>=2.0.0` — Excel 数据处理
- `openpyxl>=3.1.0` — Excel 文件读取
- `GitPython>=3.1.0` — Git 仓库操作
- `anthropic>=0.18.0` — LLM API 客户端

### 2. 准备数据文件

项目需要两个数据文件，放在项目根目录：

```
ai_vuln/
├── vuln-analyzed-0605.xlsx      # 漏洞任务表（3365 个任务）
└── ai-vulns-timeline.zip        # 时间线和 SAST 数据包
```

### 3. 解压 ai-vulns-timeline.zip

> **⚠️ 重要注意事项**

**解压路径：** 必须解压到 `data/ai-vulns-timeline/` 目录：

```bash
mkdir -p data
unzip ai-vulns-timeline.zip -d data/ai-vulns-timeline/
```

**目录结构要求：** 解压后的目录结构必须是：

```
data/ai-vulns-timeline/
├── cves/                        # CVE 漏洞数据
│   └── {project}/
│       └── {cve_id}/
│           ├── relevance_out/
│           │   ├── timeline.json
│           │   └── relevance.json
│           └── verify_requirements/
│               ├── one_issue.txt
│               ├── root_cause.md
│               ├── root_cause_zh.md
│               └── sast_standardized.json
└── security_advisories/         # GitHub Advisory 数据
    └── {project}/
        └── {adv_id}/
            └── ...（同上结构）
```

**关键检查点：**

1. **不要嵌套目录** — 如果 zip 解压后出现 `data/ai-vulns-timeline/ai-vulns-timeline/cves/` 这样的嵌套结构，需要手动移动。系统期望直接看到 `cves/` 和 `security_advisories/` 两个子目录。

2. **忽略 `__MACOSX` 目录** — zip 中包含 macOS 生成的 `__MACOSX` 元数据目录，解压后可直接忽略或删除，不影响分析。

3. **大小写敏感** — Linux 文件系统区分大小写。数据目录中的项目名（如 `AstrBotDevs_AstrBot`）必须与 Excel 中的项目名精确匹配。系统已内置大小写不敏感的目录匹配逻辑。

4. **验证解压结果** — 运行预检查命令验证数据就绪：

```bash
python3 main.py preflight
```

预期输出应包含 `✅ Dataset ready`。如果报错，检查目录结构是否正确。

5. **也可以让系统自动解压** — 如果 `data/ai-vulns-timeline/` 目录不存在，运行 `preflight` 时系统会自动从 zip 解压。但如果目录已存在，系统不会重新解压。

### 4. 配置 LLM API

编辑 `.env` 文件，填入 API 密钥：

```env
# LLM 供应商：none | anthropic | openai | deepseek | custom
LLM_PROVIDER=deepseek

# DeepSeek 配置（Anthropic 兼容接口）
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_API_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseek-v4-pro
LLM_MAX_TOKENS=4096
```

**支持的 LLM 供应商：**

| 供应商 | 说明 |
|--------|------|
| `none` | 占位符模式，返回 `insufficient_evidence`，用于离线测试 |
| `anthropic` | Anthropic Claude API |
| `openai` | OpenAI API |
| `deepseek` | DeepSeek API（Anthropic 兼容接口） |
| `custom` | 自定义 OpenAI 兼容 API |

### 5. 运行分析

```bash
# 预检查
python3 main.py preflight

# 列出可用任务
python3 main.py list-tasks --max 10

# 运行分析（离线模式，不克隆仓库）
python3 main.py run --max 5 --offline

# 运行分析（使用 LLM）
python3 main.py run --max 5

# 运行单个任务
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117
```

## 命令参考

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `preflight` | 检查数据文件和目录 | `--max-tasks` |
| `list-tasks` | 从 Excel 列出所有任务 | `--max` |
| `resolve-tasks` | 解析任务数据目录 | `--max` |
| `dry-run` | 使用占位内容生成输出 | `--max` |
| `build-evidence` | 为指定任务构建证据包 | `--project`, `--id` |
| `collect-code` | 从仓库收集代码证据 | `--project`, `--id` |
| `run` | 运行完整分析流程 | `--max`, `--offline`, `--project`, `--id`, `--force` |
| `rebuild-summary` | 从输出重建 summary.csv | — |
| `batch-report` | 生成批量统计报告 | — |
| `audit-output` | 输出质量审计 | — |

### run 命令参数

```bash
python3 main.py run [options]

# 参数说明
--max N           # 最多处理 N 个任务
--offline         # 离线模式，不克隆 Git 仓库
--project NAME    # 指定项目名称
--id ID           # 指定漏洞 ID（需配合 --project）
--force           # 强制重跑已完成的任务
--max-workers N   # 最大 worker 数（当前保留，仍按单线程执行）
```

### 批量运行建议

```bash
# 1. 先跑少量样本验证
python3 main.py run --max 10

# 2. 检查输出质量
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output

# 3. 如果 audit 发现问题，先修复再扩大批量
# 4. 全量运行前确认 audit 报告中各项指标为 0
```

## 输出说明

### 输出目录结构

```
output/
├── {project}/
│   └── {canonical_id}/
│       ├── metadata.md                                    # 任务元数据
│       ├── evidence_bundle.md                             # 证据包
│       ├── 01_version_verification.md                     # Step 1: 版本验证
│       ├── 02_module_classification.md                    # Step 2: 模块分类
│       ├── 03_vulnerability_pattern_classification.md     # Step 3: 漏洞模式分类
│       ├── 04_exploit_condition_summary.md                # Step 4: 利用条件总结
│       └── final_case_summary.md                          # 四步汇总
├── summary.csv                                            # 全局汇总表（30 字段）
├── batch_report.md                                        # 批量统计报告
├── audit_report.md                                        # 质量审计报告
└── preflight_report.md                                    # 数据就绪检查报告
```

### 四步分析流程

**Step 1 — 版本验证：** 验证漏洞引入时间点是否正确，漏洞在引入版本时是否已存在。

**Step 2 — 模块分类：** 将漏洞归类到 18 类功能模块（A-R taxonomy），判断项目架构类型。

**Step 3 — 漏洞模式分类：** 将漏洞分为三类：
- **A（传统类型漏洞）：** 不依赖 AI 语义机制的普通安全问题
- **B（AI功能实现+传统方式）：** 底层是传统漏洞，但攻击入口依赖 AI 功能
- **C（AI场景新漏洞模式）：** 依赖语义注入、上下文污染等 AI-native 机制

**Step 4 — 利用条件总结：** 分析利用方式、前提条件、攻击链、影响和利用难度。

### summary.csv 字段

| 分组 | 字段 |
|------|------|
| 任务身份 | `project`, `canonical_id`, `source`, `cwe`, `publish_at`, `cve_id`, `adv_id` |
| Step 1 | `intro_time_verdict`, `vuln_exists_at_intro_version`, `manual_review_needed` |
| Step 2 | `architecture_type`, `architecture_confidence`, `classification_type`, `primary_module`, `secondary_modules`, `confidence` |
| Step 3 | `category`, `category_name`, `input_type`, `input_subtype`, `mechanism_type`, `mechanism_subtype`, `requires_ai_function`, `ai_native_subtype`, `cross_agent` |
| Step 4 | `difficulty` |
| 元数据 | `overall_confidence`, `manual_review_reason`, `fail_code`, `fail_reason` |

## 项目结构

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
├── project-module-types.md    # 模块分类体系（18 类 A-R）
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
    ├── project-workflow.md    # 详细工作流程文档
    └── ...
```

## 常见问题

### Q: 解压 zip 后 preflight 报错找不到数据？

检查解压后的目录结构。`data/ai-vulns-timeline/` 下应直接包含 `cves/` 和 `security_advisories/` 两个子目录，不应有额外的嵌套层。

### Q: 如何重跑已分析过的任务？

使用 `--force` 参数：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
python3 main.py rebuild-summary
```

### Q: 离线模式和在线模式有什么区别？

- **离线模式**（`--offline`）：只使用已有的时间线/SAST 数据进行 LLM 分析，不克隆 Git 仓库，不收集代码 diff
- **在线模式**：额外克隆目标仓库，收集引入/修复 commit 的 diff 和漏洞位置的代码窗口

### Q: audit-output 报告了问题怎么办？

根据报告中的问题类型处理：
- **Missing Required Fields**：使用 `--force` 重跑该任务
- **Prompt Leakage Files**：使用 `--force` 重跑，系统会自动重试并生成格式化 stub
- **API Error Files**：检查 `.env` 中的 API 配置

### Q: --max-workers 参数为什么没有实际并行？

当前版本为避免 Git 仓库 checkout 竞争，仍按单线程执行。该参数保留供未来扩展使用。

## 许可证

本项目仅供学术研究使用。
