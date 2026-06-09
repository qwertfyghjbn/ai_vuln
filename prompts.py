from pathlib import Path

from config import Config
from models import VulnEvidence


def load_project_module_types_prompt(config: Config) -> str:
    """Load project-module-types.md content."""
    path = config.root_dir / "project-module-types.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_step2_markdown_output_contract() -> str:
    """Return Markdown output format override for Step 2."""
    return """
注意：上面的 project-module-types.md 原文包含 JSON 输出格式，但本项目要求每一步直接写 Markdown 文件。
你必须只使用其中的 A-R taxonomy、module_id 和分析流程，不要输出 JSON。
最终输出必须严格使用下面的小节和固定字段。
"""


COMMON_CONSTRAINTS = """你必须只写 Markdown 正文，不要输出 JSON。
你必须使用指定小节标题。
证据不足时写 insufficient_evidence，不要编造。
不要给出可执行 exploit 或 PoC。
不要建议运行目标项目代码。
结论必须能被 summary 提取器从固定字段行中读取。
"""


def _format_timeline(evidence: VulnEvidence) -> str:
    if not evidence.timeline:
        return "Timeline: insufficient_evidence\n"

    lines = ["## Timeline\n"]
    lines.append(f"- Intro Commit: {evidence.intro_commit or 'N/A'}")
    lines.append(f"- Intro Date: {evidence.intro_date or 'N/A'}")
    lines.append(f"- Fix Commit: {evidence.fix_commit or 'N/A'}")
    lines.append(f"- Fix Date: {evidence.fix_date or 'N/A'}")
    lines.append(f"- Disclosure Date: {evidence.disclosure_date or 'N/A'}")
    return "\n".join(lines) + "\n"


def _format_relevance(evidence: VulnEvidence) -> str:
    if not evidence.relevance:
        return "Relevance: insufficient_evidence\n"

    lines = ["## Relevance\n"]
    lines.append(f"- Relevant: {evidence.relevance.get('relevant', 'N/A')}")
    lines.append(f"- Reason: {evidence.relevance.get('reason', 'N/A')}")
    if evidence.relevance.get("evidence"):
        lines.append("\n### Evidence\n")
        for ev in evidence.relevance["evidence"]:
            lines.append(f"- {ev}")
    return "\n".join(lines) + "\n"


def _format_sast(evidence: VulnEvidence) -> str:
    if not evidence.vuln_positions and not evidence.dataflow:
        return "SAST: insufficient_evidence\n"

    lines = ["## SAST Analysis\n"]

    if evidence.vuln_positions:
        lines.append("### Vulnerability Positions\n")
        for pos in evidence.vuln_positions:
            lines.append(f"- `{pos['file']}:{pos.get('line_start', '?')}-{pos.get('line_end', '?')}` ({pos.get('role', 'unknown')})")
        lines.append("")

    if evidence.dataflow:
        lines.append("### Dataflow\n")
        for flow in evidence.dataflow:
            lines.append(f"- `{flow['file']}:{flow.get('line', '?')}` ({flow.get('type', 'unknown')}): {flow.get('description', '')}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _format_code_evidence(evidence: VulnEvidence) -> str:
    lines = []

    if evidence.code_at_intro_parent:
        lines.append("## Code at Intro Parent\n")
        for key, code in evidence.code_at_intro_parent.items():
            lines.append(f"### {key}\n")
            lines.append("```python")
            lines.append(code[:8000])
            lines.append("```\n")

    if evidence.code_at_intro:
        lines.append("## Code at Intro Commit\n")
        for key, code in evidence.code_at_intro.items():
            lines.append(f"### {key}\n")
            lines.append("```python")
            lines.append(code[:8000])
            lines.append("```\n")

    if evidence.intro_diff:
        lines.append("## Intro Diff\n")
        lines.append("```diff")
        lines.append(evidence.intro_diff[:15000])
        lines.append("```\n")

    if evidence.fix_diff:
        lines.append("## Fix Diff\n")
        lines.append("```diff")
        lines.append(evidence.fix_diff[:15000])
        lines.append("```\n")

    return "\n".join(lines) + "\n" if lines else "Code Evidence: insufficient_evidence\n"


def build_step1_prompt(evidence: VulnEvidence) -> str:
    """Build Step 1: Version Verification prompt."""
    task = evidence.task

    sections = [
        COMMON_CONSTRAINTS,
        f"# Step 1: Version Verification\n",
        f"## Vulnerability Info\n",
        f"- Project: {task.project}",
        f"- GitHub: {task.github_url}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- Advisory ID: {task.adv_id or 'N/A'}",
        f"- Source: {task.source}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
        _format_timeline(evidence),
        _format_relevance(evidence),
    ]

    if evidence.root_cause_zh:
        sections.append("## Root Cause (Chinese)\n")
        sections.append(evidence.root_cause_zh[:5000] + "\n")

    if evidence.root_cause:
        sections.append("## Root Cause (English)\n")
        sections.append(evidence.root_cause[:5000] + "\n")

    sections.append(_format_sast(evidence))
    sections.append(_format_code_evidence(evidence))

    sections.append("""## Required Output

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
""")

    return "\n".join(sections)


def build_step2_prompt(config: Config, evidence: VulnEvidence) -> str:
    """Build Step 2: Module Classification prompt."""
    task = evidence.task
    module_types = load_project_module_types_prompt(config)

    sections = [
        COMMON_CONSTRAINTS,
        f"# Step 2: Module Classification\n",
        f"## Vulnerability Info\n",
        f"- Project: {task.project}",
        f"- GitHub: {task.github_url}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
    ]

    if evidence.root_cause_zh:
        sections.append("## Root Cause (Chinese)\n")
        sections.append(evidence.root_cause_zh[:3000] + "\n")

    sections.append(_format_sast(evidence))

    if module_types:
        sections.append("## Predefined Module Classification System\n")
        sections.append(module_types[:20000] + "\n")
        sections.append(build_step2_markdown_output_contract())

    sections.append("""## Required Output

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

## Analysis

请分析：
1. 项目架构类型
2. 漏洞所属功能模块（优先使用 A-R taxonomy 中的 module_id）
3. 分析依据
""")

    return "\n".join(sections)


def build_step3_prompt(evidence: VulnEvidence, step2_text: str) -> str:
    """Build Step 3: Vulnerability Pattern Classification prompt."""
    task = evidence.task

    sections = [
        COMMON_CONSTRAINTS,
        f"# Step 3: Vulnerability Pattern Classification\n",
        f"## Vulnerability Info\n",
        f"- Project: {task.project}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
    ]

    if evidence.root_cause_zh:
        sections.append("## Root Cause (Chinese)\n")
        sections.append(evidence.root_cause_zh[:3000] + "\n")

    sections.append("## Step 2 Result\n")
    sections.append(step2_text[:5000] + "\n")

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

    sections.append("""## Required Output

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


def build_step4_prompt(evidence: VulnEvidence, step2_text: str, step3_text: str) -> str:
    """Build Step 4: Exploit Condition Summary prompt."""
    task = evidence.task

    sections = [
        COMMON_CONSTRAINTS,
        f"# Step 4: Exploit Condition Summary\n",
        f"## Vulnerability Info\n",
        f"- Project: {task.project}",
        f"- CVE ID: {task.cve_id or 'N/A'}",
        f"- CWE: {task.cwe or 'N/A'}",
        "",
    ]

    if evidence.root_cause_zh:
        sections.append("## Root Cause (Chinese)\n")
        sections.append(evidence.root_cause_zh[:3000] + "\n")

    sections.append("## Step 2 Result\n")
    sections.append(step2_text[:3000] + "\n")

    sections.append("## Step 3 Result\n")
    sections.append(step3_text[:3000] + "\n")

    sections.append(_format_code_evidence(evidence))

    sections.append("""## Required Output

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

## Analysis

请分析：
1. 利用方式和攻击链
2. 前提条件
3. 影响和危害
4. 利用难度
5. 防御差距
""")

    return "\n".join(sections)
