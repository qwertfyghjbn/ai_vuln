# 8 个 Fix 完成后的复核修复要求

本文档记录对上一轮 8 个 fix 的复核结论和新的修复要求。目标是让后续使用 `mimo-v2.5-pro + Claude Code` 实现时有明确边界，不重新设计流程，不引入额外功能。

## 1. 复核结论

上一轮 8 个 fix 只达到“代码入口大部分存在”的状态，尚未达到“输出结果可用于后续统计”的状态。

已通过或基本通过：

1. Step 3 prompt 中的 A/B/C 分类语义已在 `prompts.py` 修正。
2. Markdown parser 跨行误解析已修正。
3. `summary.csv` 字段和 `rebuild-summary` 重建逻辑基本可用。
4. `batch-report` 已按 task_key 最新状态统计。
5. `audit-output` 命令已存在。
6. `run --force` 参数已存在。

未通过或部分通过：

1. `output/` 中 10 条 Step 3 结果仍使用旧英文枚举 `Traditional / AI Amplified`。
2. `audit-output` 仍报告 3 个缺失字段和 2 个 prompt 泄漏文件。
3. `docs/detailed-implementation-steps.md` 未同步写明 Step 3 的新中文分类枚举。
4. `normalize_value()` 把 `insufficient_evidence` 全局归一为 `none`，会丢失分类、难度、模块等字段的“不足证据”语义。
5. `Analyzer.REQUIRED_FIELDS["step2"]` 未要求 `architecture_type` 和 `architecture_confidence`，运行时校验弱于审计命令。
6. `--max-workers` 参数仍未实际并行。上一版修复原则要求暂不修并行，因此本轮不要求实现并行，但必须在文档中说明这是保留限制。

## 2. 当前复核命令结果

已执行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

结果：

```text
Rebuilt summary.csv with 10 tasks

Total Tasks: 10
Success: 10
Failed: 0
Running: 0
Output Task Dirs: 10
Summary Rows: 10
Success Rate: 100.0%

Audit:
Total Task Dirs: 10
Complete Task Dirs: 10
Missing Files: 0
Missing Required Fields: 3
Prompt Leakage Files: 2
API Error Files: 0
JSON Output Files: 0
```

问题文件：

```text
output/AstrBotDevs_AstrBot/CVE-2026-6117/01_version_verification.md
output/AstrBotDevs_AstrBot/CVE-2025-57697/04_exploit_condition_summary.md
```

Step 3 旧枚举问题：

```text
output/*/*/03_vulnerability_pattern_classification.md
summary.csv
```

当前 10 条记录的 `category_name` 全部不是以下合法值：

```text
传统类型漏洞
AI功能实现+传统方式
AI场景新漏洞模式
```

## 3. 修复要求 1：重跑或修复污染输出

### 3.1 问题

`audit-output` 仍发现 prompt 泄漏和必填字段缺失。说明上一轮新增的 LLM 输出校验只对后续运行有效，没有清理已有坏结果。

当前坏文件：

```text
output/AstrBotDevs_AstrBot/CVE-2026-6117/01_version_verification.md
output/AstrBotDevs_AstrBot/CVE-2025-57697/04_exploit_condition_summary.md
```

其中 `CVE-2026-6117/01_version_verification.md` 缺少：

```text
intro_time_verdict
vuln_exists_at_intro_version
manual_review_needed
```

### 3.2 操作要求

优先用模型重跑，不要手工编造分析结论。

执行：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2025-57697 --force
python3 main.py rebuild-summary
python3 main.py audit-output
```

如果模型成本或 API 配额不允许重跑，则只允许写入格式化的失败 stub，不能写入伪造结论。stub 必须包含固定字段，并标记人工复核。

Step 1 stub 示例：

```markdown
## Conclusion
- intro_time_verdict: not_verifiable
- vuln_exists_at_intro_version: insufficient_evidence
- manual_review_needed: yes

## Failure
- reason: previous model output contained prompt leakage and must be manually reviewed
```

Step 4 stub 示例：

```markdown
## Difficulty
- difficulty: unknown

## Failure
- reason: previous model output contained prompt leakage and must be manually reviewed
```

### 3.3 验收标准

执行：

```bash
python3 main.py audit-output
cat output/audit_report.md
```

必须满足：

```text
Missing Required Fields: 0
Prompt Leakage Files: 0
API Error Files: 0
JSON Output Files: 0
```

## 4. 修复要求 2：按新分类语义重跑 Step 3

### 4.1 问题

`prompts.py` 已修正 Step 3 分类语义，但已有输出仍是旧结果：

```text
category_name: Traditional
category_name: AI Amplified
```

这会直接污染论文统计。只运行 `rebuild-summary` 不能解决，因为 summary 只是解析旧文件。

### 4.2 操作要求

必须让 10 条样本的 Step 3 结果全部符合新枚举。

推荐做法：

1. 使用 `--force` 重跑 10 条已生成样本。
2. 每条重跑后覆盖：

```text
03_vulnerability_pattern_classification.md
04_exploit_condition_summary.md
final_case_summary.md
```

3. 重跑完成后执行：

```bash
python3 main.py rebuild-summary
python3 main.py audit-output
```

如果为了节省成本只重跑 Step 3，需要新增一个明确命令或脚本，例如：

```bash
python3 main.py rerun-step --project <project> --id <id> --step 3 --force
```

但当前项目没有该命令。本轮不要求必须新增 `rerun-step`，可以直接使用已有 `run --force`。

### 4.3 合法输出枚举

Step 3 必须只使用：

```text
- category: A | B | C
- category_name: 传统类型漏洞 | AI功能实现+传统方式 | AI场景新漏洞模式
```

禁止再出现：

```text
Traditional
AI Amplified
AI Native
```

### 4.4 验收命令

```bash
python3 - <<'PY'
import csv

allowed = {"传统类型漏洞", "AI功能实现+传统方式", "AI场景新漏洞模式"}
rows = list(csv.DictReader(open("output/summary.csv", encoding="utf-8")))
bad = [
    (r["project"], r["canonical_id"], r.get("category"), r.get("category_name"))
    for r in rows
    if r.get("category_name") not in allowed
]
print("bad_category_name_count", len(bad))
for item in bad:
    print(item)
assert not bad
PY
```

再执行：

```bash
rg -n "Traditional|AI Amplified|AI Native" output/*/*/03_vulnerability_pattern_classification.md output/summary.csv
```

期望没有匹配。

## 5. 修复要求 3：同步详细实施文档中的 Step 3 枚举

### 5.1 问题

`docs/detailed-implementation-steps.md` 目前只写了 Step 3 需要包含 A/B/C 分类标准，但没有明确写出三类中文语义。后续低能力模型可能继续自由发挥，生成旧英文枚举。

### 5.2 修改文件

```text
docs/detailed-implementation-steps.md
```

### 5.3 操作要求

在 Phase 7 的 Step 3 Prompt 要求处补充：

```text
A = 传统类型漏洞
B = AI功能实现+传统方式
C = AI场景新漏洞模式
```

固定字段必须写成：

```markdown
## Conclusion
- category: A | B | C
- category_name: 传统类型漏洞 | AI功能实现+传统方式 | AI场景新漏洞模式
- confidence: high | medium | low
```

同时补充禁止项：

```text
不得使用 Traditional、AI Amplified、AI Native 作为 category_name。
```

### 5.4 验收命令

```bash
python3 - <<'PY'
from pathlib import Path
txt = Path("docs/detailed-implementation-steps.md").read_text(encoding="utf-8")
for s in ["A = 传统类型漏洞", "B = AI功能实现+传统方式", "C = AI场景新漏洞模式"]:
    assert s in txt
assert "Traditional、AI Amplified、AI Native" in txt or "Traditional" in txt
print("detailed implementation Step 3 enum documented")
PY
```

## 6. 修复要求 4：修正 normalize_value 的空值策略

### 6.1 问题

当前 `markdown_parser.py` 中：

```python
EMPTY_VALUES = {"N/A", "(不适用)", "(not applicable)", "insufficient_evidence", "", "none"}
```

这会导致：

```python
normalize_value("insufficient_evidence", "category") == "none"
normalize_value("insufficient_evidence", "difficulty") == "none"
normalize_value("insufficient_evidence", "primary_module") == "none"
```

这是错误的。`insufficient_evidence` 是一种有效的不确定性语义，不应被全局抹成 `none`。

### 6.2 修改文件

```text
markdown_parser.py
```

### 6.3 操作要求

1. 从全局 `EMPTY_VALUES` 中移除 `insufficient_evidence`。
2. 空值集合只保留真正代表“不适用或空”的值：

```python
EMPTY_VALUES = {"N/A", "(不适用)", "(not applicable)", "", "none"}
```

3. `insufficient_evidence` 应按字段保留：

```text
category: insufficient_evidence
category_name: insufficient_evidence
difficulty: insufficient_evidence
requires_ai_function: insufficient_evidence
cross_agent: insufficient_evidence
```

4. 对 `ai_native_subtype` 的特殊策略：

```text
如果原值为空、N/A、(不适用)、(not applicable)，归一为 none。
如果原值是 insufficient_evidence，保留 insufficient_evidence，或统一改为 unknown。
二选一，但必须在代码和文档里保持一致。
```

推荐保留 `insufficient_evidence`，因为它和 `none` 的含义不同：

```text
none = 确认不属于 AI-native 子类型
insufficient_evidence = 证据不足，无法判断
```

### 6.4 验收命令

```bash
python3 - <<'PY'
from markdown_parser import normalize_value

assert normalize_value("insufficient_evidence", "category") == "INSUFFICIENT_EVIDENCE" or normalize_value("insufficient_evidence", "category") == "insufficient_evidence"
assert normalize_value("insufficient_evidence", "difficulty") == "insufficient_evidence"
assert normalize_value("insufficient_evidence", "ai_native_subtype") in {"insufficient_evidence", "unknown"}
assert normalize_value("N/A", "ai_native_subtype") == "none"
print("normalize_value insufficient_evidence semantics preserved")
PY
```

如果不希望 `category` 被转成大写，需要调整 `VALID_CATEGORY` 和 `normalize_value("category")`，让它显式支持小写 `insufficient_evidence`。

## 7. 修复要求 5：统一 Analyzer 校验和 audit-output 校验

### 7.1 问题

`audit-output` 要求 Step 2 包含：

```text
architecture_type
classification_type
primary_module
confidence
```

但 `Analyzer.REQUIRED_FIELDS["step2"]` 目前只要求：

```text
classification_type
primary_module
secondary_modules
confidence
```

这会导致运行时可能接受缺少 `architecture_type` 的 Step 2 输出，然后审计阶段再失败。

### 7.2 修改文件

```text
analyzer.py
```

### 7.3 操作要求

将 Step 2 校验字段改为：

```python
"step2": [
    "architecture_type",
    "architecture_confidence",
    "classification_type",
    "primary_module",
    "secondary_modules",
    "confidence",
]
```

如果担心 `architecture_confidence` 过严，至少必须加入 `architecture_type`。

### 7.4 验收命令

```bash
python3 - <<'PY'
from analyzer import REQUIRED_FIELDS
fields = set(REQUIRED_FIELDS["step2"])
assert "architecture_type" in fields
assert "classification_type" in fields
assert "primary_module" in fields
assert "confidence" in fields
print("Analyzer Step 2 validation aligned with audit-output")
PY
```

## 8. 修复要求 6：明确 max-workers 暂不实现

### 8.1 问题

`run --max-workers` 参数存在，但 `cmd_run()` 中没有实际并行逻辑。上一版修复规划明确“暂时不急修，避免引入 repo checkout 竞争”，因此这不是本轮必须开发项。

### 8.2 操作要求

二选一：

1. 保留参数，但在 help 和文档中明确：

```text
--max-workers 当前保留，run 仍按单线程执行。
```

2. 或删除参数，避免误导。

推荐选择 1，因为未来可能继续实现并行。

### 8.3 验收命令

```bash
python3 main.py run --help
rg -n "max-workers|单线程|single" docs AGENTS.md
```

需要能在文档中看到该限制说明。

## 9. 最小修复顺序

按以下顺序执行，不要打乱：

1. 修改 `markdown_parser.py` 的 `insufficient_evidence` 空值策略。
2. 修改 `analyzer.py` 的 Step 2 必填字段。
3. 修改 `docs/detailed-implementation-steps.md` 的 Step 3 分类枚举说明。
4. 使用 `--force` 重跑两个污染输出样本。
5. 使用 `--force` 重跑 10 条样本，确保 Step 3 全部切换到新中文枚举。
6. 执行 `rebuild-summary`。
7. 执行 `batch-report`。
8. 执行 `audit-output`。
9. 执行本文件中的所有验收命令。

## 10. 总体验收流程

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output

python3 - <<'PY'
import csv

allowed = {"传统类型漏洞", "AI功能实现+传统方式", "AI场景新漏洞模式"}
rows = list(csv.DictReader(open("output/summary.csv", encoding="utf-8")))

assert len(rows) == 10
assert all((r.get("architecture_type") or "").strip() for r in rows)
assert all((r.get("category") or "").strip() for r in rows)
assert all(r.get("category_name") in allowed for r in rows)
assert all((r.get("ai_native_subtype") or "").strip() for r in rows)

print("summary semantic checks passed")
PY

rg -n "## Required Output|## Vulnerability Info|Error calling|API_KEY not configured" output/*/*/01_version_verification.md output/*/*/02_module_classification.md output/*/*/03_vulnerability_pattern_classification.md output/*/*/04_exploit_condition_summary.md

rg -n "Traditional|AI Amplified|AI Native" output/*/*/03_vulnerability_pattern_classification.md output/summary.csv
```

最终要求：

1. `audit_report.md` 中 `Missing Required Fields = 0`。
2. `audit_report.md` 中 `Prompt Leakage Files = 0`。
3. `audit_report.md` 中 `API Error Files = 0`。
4. `audit_report.md` 中 `JSON Output Files = 0`。
5. `summary.csv` 中 10 条 `category_name` 全部是新中文枚举。
6. `summary.csv` 中 `architecture_type`、`architecture_confidence` 非空。
7. `summary.csv` 中不能出现 `ai_native_subtype = - cross_agent: no`。
8. `batch_report.md` 中 `Total Tasks = 10`，`Success = 10`，`Success Rate = 100.0%`。

## 11. 给 mimo-v2.5-pro + Claude Code 的执行提示

执行时不要让模型自由判断“是否需要修”。按本文档逐条完成。

建议流程：

1. 让 mimo-v2.5-pro 只负责小范围代码编辑，不要让它重新设计命令结构。
2. 每改一个文件，立即运行对应验收命令。
3. Claude Code 负责执行命令、收集失败输出、定位具体文件行。
4. 涉及模型重跑时，先只重跑 1 条污染样本，确认 `audit-output` 变好后再重跑 10 条。
5. 如果模型输出再次泄漏 prompt，不要人工改成“看起来正确”的结论；应触发 stub 或重新调用模型。
6. 不要实现并行，不要改仓库 checkout 逻辑，不要运行目标项目代码，不要安装目标项目依赖。
