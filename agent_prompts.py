from pathlib import Path

from models import VulnEvidence


AGENT_COMMON_CONSTRAINTS = """你正在运行 AI-VulnAtlas 的 Agent Analysis Mode。
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
你必须只写 Markdown 正文，不要输出 JSON。
你必须使用指定小节标题。
证据不足时写 insufficient_evidence，不要编造。
不要给出可执行 exploit 或 PoC。
不要建议运行目标项目代码。
结论必须能被 summary 提取器从固定字段行中读取。
"""


def _get_data_paths(evidence: VulnEvidence, data_dir: Path) -> dict[str, str]:
    """Get paths to data files for the agent to read."""
    paths = {}

    # Timeline
    timeline_path = data_dir / "relevance_out" / "timeline.json"
    if timeline_path.exists():
        paths["timeline_json"] = str(timeline_path)

    # Relevance
    relevance_path = data_dir / "relevance_out" / "relevance.json"
    if relevance_path.exists():
        paths["relevance_json"] = str(relevance_path)

    # Issue text
    issue_path = data_dir / "verify_requirements" / "one_issue.txt"
    if issue_path.exists():
        paths["issue_text"] = str(issue_path)

    # Root cause
    root_cause_path = data_dir / "verify_requirements" / "root_cause.md"
    if root_cause_path.exists():
        paths["root_cause"] = str(root_cause_path)

    root_cause_zh_path = data_dir / "verify_requirements" / "root_cause_zh.md"
    if root_cause_zh_path.exists():
        paths["root_cause_zh"] = str(root_cause_zh_path)

    # SAST
    sast_path = data_dir / "verify_requirements" / "sast_standardized.json"
    if sast_path.exists():
        paths["sast_json"] = str(sast_path)

    return paths


def build_agent_step1_prompt(
    evidence: VulnEvidence,
    workspace_dir: Path,
    output_file: Path,
    data_dir: Path,
) -> str:
    """Build Step 1: Version Verification prompt for agent mode."""
    task = evidence.task
    data_paths = _get_data_paths(evidence, data_dir)

    sections = [
        AGENT_COMMON_CONSTRAINTS,
        f"# Step 1: Version Verification\n",
        f"## Task Identity\n",
        f"- Project: {task.project}",
        f"- GitHub: {task.github_url}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- Advisory ID: {task.adv_id or 'N/A'}",
        f"- Source: {task.source}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
        f"## Agent Workspace\n",
        f"- Workspace: {workspace_dir}",
        "",
        f"## Data Files (read these)\n",
    ]

    for name, path in data_paths.items():
        sections.append(f"- {name}: {path}")

    sections.append("")
    sections.append(f"## Output File\n")
    sections.append(f"Write your result to: {output_file}")
    sections.append("")

    sections.append("""## Required Output Fields

你必须输出以下固定字段：

```markdown
## Conclusion
- intro_time_verdict: correct | likely_correct | incorrect | insufficient_evidence | not_verifiable
- vuln_exists_at_intro_version: yes | likely_yes | no | insufficient_evidence
- manual_review_needed: yes | no
```

## Analysis

请分析：
1. 漏洞引入时间点是否正确（intro_time_verdict）
2. 漏洞在引入版本时是否已存在（vuln_exists_at_intro_version）
3. 是否需要人工复核（manual_review_needed）

你可以通过 git log、git show、git diff 查看引入 commit 的代码变更来验证。
""")

    return "\n".join(sections)


def build_agent_step2_prompt(
    evidence: VulnEvidence,
    workspace_dir: Path,
    output_file: Path,
    data_dir: Path,
    step1_file: Path,
    module_types_file: Path,
) -> str:
    """Build Step 2: Module Classification prompt for agent mode."""
    task = evidence.task
    data_paths = _get_data_paths(evidence, data_dir)

    sections = [
        AGENT_COMMON_CONSTRAINTS,
        f"# Step 2: Module Classification\n",
        f"## Task Identity\n",
        f"- Project: {task.project}",
        f"- GitHub: {task.github_url}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
        f"## Agent Workspace\n",
        f"- Workspace: {workspace_dir}",
        "",
        f"## Previous Step Result\n",
        f"- Step 1 result: {step1_file}",
        "",
        f"## Data Files (read these)\n",
    ]

    for name, path in data_paths.items():
        sections.append(f"- {name}: {path}")

    sections.append("")
    sections.append(f"## Module Classification Taxonomy\n")
    sections.append(f"- Read the taxonomy file: {module_types_file}")
    sections.append("")
    sections.append(f"## Output File\n")
    sections.append(f"Write your result to: {output_file}")
    sections.append("")

    sections.append("""## Required Output Fields

你必须输出以下固定字段：

```markdown
## Project Architecture
- architecture_type: (from project-module-types.md)
- architecture_confidence: high | medium | low

## Conclusion
- classification_type: matched_existing_module | uncertain_existing_module | needs_new_module_type
- primary_module: (module_id from A-R taxonomy)
- secondary_modules: (comma-separated module_ids)
- confidence: high | medium | low

## Evidence
- code_paths: (relevant file paths)
- functions: (relevant function names)
- dataflow_nodes: (key dataflow nodes)

## Reasoning

(分析推理过程)

## Proposed New Module
- name: (only if classification_type=needs_new_module_type)
- description:
- why_existing_modules_do_not_fit:
- example_vulnerability_semantics:
```

注意：上面的 project-module-types.md 原文包含 JSON 输出格式，但本项目要求每一步直接写 Markdown 文件。
你必须只使用其中的 A-R taxonomy、module_id 和分析流程，不要输出 JSON。
最终输出必须严格使用上面的小节和固定字段。

## Analysis

请分析：
1. 项目架构类型
2. 漏洞所属功能模块（优先使用 A-R taxonomy 中的 module_id）
3. 分析依据
""")

    return "\n".join(sections)


def build_agent_step3_prompt(
    evidence: VulnEvidence,
    workspace_dir: Path,
    output_file: Path,
    data_dir: Path,
    step1_file: Path,
    step2_file: Path,
) -> str:
    """Build Step 3: Vulnerability Pattern Classification prompt for agent mode."""
    task = evidence.task
    data_paths = _get_data_paths(evidence, data_dir)

    sections = [
        AGENT_COMMON_CONSTRAINTS,
        f"# Step 3: Vulnerability Pattern Classification\n",
        f"## Task Identity\n",
        f"- Project: {task.project}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
        f"## Agent Workspace\n",
        f"- Workspace: {workspace_dir}",
        "",
        f"## Previous Step Results\n",
        f"- Step 1 result: {step1_file}",
        f"- Step 2 result: {step2_file}",
        "",
        f"## Data Files (read these)\n",
    ]

    for name, path in data_paths.items():
        sections.append(f"- {name}: {path}")

    sections.append("")
    sections.append(f"## Output File\n")
    sections.append(f"Write your result to: {output_file}")
    sections.append("")

    sections.append("""## Classification Criteria

### A类：传统类型漏洞
漏洞触发、利用和影响都不依赖 AI 语义机制。即使项目是 AI 项目，只要漏洞本质是普通 Web 或系统安全问题，也归入该类。

### B类：AI功能实现 + 传统方式
漏洞底层机制仍是传统漏洞，但攻击入口、传播路径或影响依赖 AI 功能模块。判断关键是：去掉该 AI 功能模块后，攻击链是否仍然成立。

### C类：AI场景新漏洞模式
漏洞核心依赖语义注入、上下文污染、Agent 委托链劫持、工具返回值污染、记忆污染、跨 Agent 欺骗等 AI-native 机制。

### 四象限字段定义
- input_type: 输入来源类型（user_input, api_input, file_input, model_output 等）
- input_subtype: 输入子类型
- mechanism_type: 漏洞机制类型（injection, overflow, auth_bypass, logic_flaw 等）
- mechanism_subtype: 机制子类型
- requires_ai_function: 是否需要 AI 功能才能触发（yes | no | uncertain）
- ai_native_subtype: none | direct_prompt_injection | indirect_prompt_injection | rag_poisoning | tool_output_poisoning | memory_poisoning | delegation_hijack | semantic_policy_bypass | unknown
- cross_agent: yes | no | uncertain
""")

    sections.append("""## Required Output Fields

你必须输出以下固定字段：

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

## Analysis

请分析：
1. 漏洞属于 A/B/C 哪个类别
2. 直接继承 Step 2 的模块结论，不要重新发明新的模块分类
3. 四象限字段值
4. 分析依据
""")

    return "\n".join(sections)


def build_agent_step4_prompt(
    evidence: VulnEvidence,
    workspace_dir: Path,
    output_file: Path,
    data_dir: Path,
    step1_file: Path,
    step2_file: Path,
    step3_file: Path,
) -> str:
    """Build Step 4: Exploit Condition Summary prompt for agent mode."""
    task = evidence.task
    data_paths = _get_data_paths(evidence, data_dir)

    sections = [
        AGENT_COMMON_CONSTRAINTS,
        f"# Step 4: Exploit Condition Summary\n",
        f"## Task Identity\n",
        f"- Project: {task.project}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
        f"## Agent Workspace\n",
        f"- Workspace: {workspace_dir}",
        "",
        f"## Previous Step Results\n",
        f"- Step 1 result: {step1_file}",
        f"- Step 2 result: {step2_file}",
        f"- Step 3 result: {step3_file}",
        "",
        f"## Data Files (read these)\n",
    ]

    for name, path in data_paths.items():
        sections.append(f"- {name}: {path}")

    sections.append("")
    sections.append(f"## Output File\n")
    sections.append(f"Write your result to: {output_file}")
    sections.append("")

    sections.append("""## Required Output Fields

你必须输出以下固定小节：

```markdown
## Exploit Method

(描述利用方式，不输出可执行 payload)

## Prerequisites

(前提条件：认证、权限、配置、网络可达性、AI 功能启用等)

## Attack Chain

(攻击链步骤)

## Impact

(影响范围和危害)

## Difficulty
- difficulty: easy | medium | hard

## Defensive Gap

(防御差距分析)

## Uncertainty

(不确定性和局限性)
```

禁止输出可复制执行的 payload。

## Analysis

请分析：
1. 利用方式和攻击链
2. 前提条件
3. 影响和危害
4. 利用难度
5. 防御差距
""")

    return "\n".join(sections)


def build_agent_repair_prompt(step_name: str, original_prompt: str) -> str:
    """Build a repair prompt for a failed step."""
    return (
        original_prompt
        + "\n\n你的上一次输出没有遵守格式。请只输出最终 Markdown 结果，不要重复输入证据，不要输出 JSON。"
        + "\n请严格按照 Required Output Fields 中的格式输出，确保所有必需字段都存在。"
    )
