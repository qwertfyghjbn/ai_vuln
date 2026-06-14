# AI-VulnAtlas Agent

AI 驱动的漏洞自动化分析系统，用于分析 AI 相关项目的安全漏洞。

## 项目概述

本项目自动化分析 AI 相关项目（LiteLLM、Flowise、LangChain、n8n 等）的安全漏洞，使用四步 LLM 分析流程。

## 分析模式

项目支持两种分析模式：

### Prompt Analysis Mode（默认）

系统拼接 prompt，LLM 返回 Markdown，程序写 step 文件。

```bash
python3 main.py run --max 5 --analysis-mode prompt
```

### Agent Analysis Mode

Agent 在任务专属 worktree 中自主读代码、查 git 历史，直接写 step 文件。

```bash
python3 main.py run --max 5 --analysis-mode agent --agent-backend claude_code_cli
```

Agent 模式特点：
- Agent 在 `worktrees/{project}_{canonical_id}_agent_intro/` 中工作
- Agent 可使用 Read/Grep/Glob 和 git show/diff/log
- Agent 只能写入 `output/{project}/{canonical_id}/` 目录
- 每步最多执行 2 次（首次 + 1 次 repair）
- Agent trace 记录在 `output/{project}/{canonical_id}/agent_trace/`

## 快速开始

```bash
# 安装依赖
pip3 install -r requirements.txt

# 运行预检查
python3 main.py preflight

# 列出可用任务
python3 main.py list-tasks --max 10

# 运行分析（离线模式）
python3 main.py run --max 5 --offline

# 运行分析（使用 LLM）
python3 main.py run --max 5

# 运行分析（Agent 模式）
python3 main.py run --max 5 --analysis-mode agent
```

## 配置说明

API 密钥在 `.env` 文件中配置：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_API_URL=https://api.deepseek.com/anthropic
LLM_MODEL=deepseek-v4-pro
```

Agent 模式配置：

```env
ANALYSIS_MODE=prompt
AGENT_BACKEND=claude_code_cli
AGENT_COMMAND=claude
AGENT_TIMEOUT_SECONDS=1800
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `preflight` | 检查数据文件和目录 |
| `list-tasks` | 从 Excel 列出所有任务 |
| `resolve-tasks` | 解析任务数据目录 |
| `dry-run` | 使用占位内容生成输出 |
| `build-evidence` | 为任务构建证据包 |
| `collect-code` | 从仓库收集代码证据 |
| `run` | 运行完整分析流程 |
| `rebuild-summary` | 从输出重建 summary.csv |
| `batch-report` | 生成批量统计报告 |

## 项目结构

```
ai_vuln/
├── main.py              # 主入口
├── config.py            # 配置管理
├── models.py            # 数据模型
├── task_loader.py       # 从 Excel 加载任务
├── record_resolver.py   # 解析数据目录
├── evidence_builder.py  # 构建证据包
├── repo_manager.py      # Git 仓库管理 + Agent workspace
├── analyzer.py          # Prompt 模式分析编排器
├── agent_analyzer.py    # Agent 模式分析编排器
├── agent_runner.py      # Agent 执行抽象层
├── agent_prompts.py     # Agent 模式 Prompt 构建器
├── prompts.py           # Prompt 模式模板
├── llm_client.py        # LLM API 客户端
├── output_writer.py     # 输出文件写入器
├── state_manager.py     # 进度状态追踪
├── markdown_parser.py   # 从 Markdown 提取字段
├── .env                 # API 配置
├── data/                # 漏洞数据
├── repos/               # 克隆的仓库
├── worktrees/           # Git worktrees
├── output/              # 分析输出
└── state/               # 进度状态文件
```

## 分析流程

1. **任务加载**：从 Excel 文件加载任务
2. **目录解析**：查找 CVE/GHSA 数据目录
3. **证据构建**：加载时间线、SAST、根因分析
4. **代码收集**（Prompt 模式）：克隆仓库，收集 diff 和代码窗口
5. **四步分析**：
   - Step 1: 版本验证
   - Step 2: 模块分类
   - Step 3: 漏洞模式分类
   - Step 4: 利用条件总结

## 数据来源

- `vuln-analyzed-0605.xlsx`：漏洞任务列表（3365 个任务）
- `ai-vulns-timeline.zip`：时间线和 SAST 数据

## 关键约束

- 不运行目标项目代码
- 不安装目标项目依赖
- 使用 Markdown 输出（非 JSON）
- 保留项目名称的原始大小写
- 支持离线模式用于测试（仅 Prompt 模式）
- Agent 模式同 project 串行，多 project 可并行
