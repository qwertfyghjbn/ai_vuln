# Phase 0-9 审核后的修复规划

本文档记录 Phase 0-9 实现和 DeepSeek 批量运行后的问题、修复顺序、具体操作步骤和验收标准。后续实现时优先按本文档执行，不要重新设计流程。

## 1. 当前状态

已实现并跑通：

1. `preflight`
2. `list-tasks`
3. `resolve-tasks`
4. `dry-run`
5. `build-evidence`
6. `collect-code`
7. `run`
8. `rebuild-summary`
9. `batch-report`

当前 `output/` 中已有 10 个完整任务目录，每个目录包含：

```text
metadata.md
evidence_bundle.md
01_version_verification.md
02_module_classification.md
03_vulnerability_pattern_classification.md
04_exploit_condition_summary.md
final_case_summary.md
```

主要问题：

1. Step 3 的 A/B/C 分类语义和规划文档相反。
2. 有样本出现 LLM 输出失控，把 prompt/证据写入 step 文件。
3. Markdown parser 会跨行误解析空字段。
4. `summary.csv` 丢失 `architecture_type` 等字段。
5. `batch_report.md` 把 `running` 和 `success` 两条状态都计入总数。
6. `run` 过程只写基础 summary 字段，依赖后续 `rebuild-summary` 才有完整字段。
7. `--max-workers` 已有参数但未实际并行；暂时不急修，避免引入 repo checkout 竞争。

## 2. 修复原则

1. 先修统计口径和字段解析，再重跑样本。
2. 每个修复点必须有最小验收命令。
3. 不改输入文件名和目录结构。
4. 不改变 Step 2 使用 `project-module-types.md` 的要求。
5. 不运行目标项目代码，不运行 PoC，不安装目标项目依赖。
6. 先保持单线程，暂不实现真正并行。

## 3. Fix 1：统一 Step 3 A/B/C 分类语义

### 3.1 问题

当前 [prompts.py](../prompts.py) 中 Step 3 定义为：

```text
A = AI 原生漏洞
B = AI 放大漏洞
C = 传统漏洞
```

但 `进展文档.txt` 和 `docs/implementation-plan.md` 要求：

```text
A = 传统类型漏洞
B = AI功能实现 + 传统方式
C = AI场景新漏洞模式
```

如果不修，后续论文统计会完全反向。

### 3.2 修改文件

```text
prompts.py
docs/detailed-implementation-steps.md
```

### 3.3 操作步骤

1. 打开 `prompts.py`。
2. 找到 `build_step3_prompt()` 中 `## Classification Criteria` 段落。
3. 将分类定义改为：

```text
### A类：传统类型漏洞
漏洞触发、利用和影响都不依赖 AI 语义机制。即使项目是 AI 项目，只要漏洞本质是普通 Web 或系统安全问题，也归入该类。

### B类：AI功能实现 + 传统方式
漏洞底层机制仍是传统漏洞，但攻击入口、传播路径或影响依赖 AI 功能模块。判断关键是：去掉该 AI 功能模块后，攻击链是否仍然成立。

### C类：AI场景新漏洞模式
漏洞核心依赖语义注入、上下文污染、Agent 委托链劫持、工具返回值污染、记忆污染、跨 Agent 欺骗等 AI-native 机制。
```

4. 将 Required Output 中的 `category_name` 改为：

```text
传统类型漏洞 | AI功能实现+传统方式 | AI场景新漏洞模式
```

5. 在 `docs/detailed-implementation-steps.md` 中同步检查 Phase 6 Step 3，确保文档和 prompt 一致。

### 3.4 验收命令

```bash
python3 - <<'PY'
from pathlib import Path
txt = Path("prompts.py").read_text(encoding="utf-8")
assert "A类：传统类型漏洞" in txt
assert "B类：AI功能实现" in txt
assert "C类：AI场景新漏洞模式" in txt
assert "AI Native | AI Amplified | Traditional" not in txt
print("Step 3 taxonomy fixed")
PY
```

## 4. Fix 2：修复 Markdown parser 跨行误解析

### 4.1 问题

当前 `markdown_parser.extract_bullet_value()` 使用：

```python
pattern = rf"^-\s*{re.escape(key)}\s*:\s*(.+)$"
```

其中 `\s*` 会吞掉换行。当字段为空：

```text
- ai_native_subtype:
- cross_agent: no
```

解析器可能把 `ai_native_subtype` 解析成 `- cross_agent: no`。

### 4.2 修改文件

```text
markdown_parser.py
```

### 4.3 操作步骤

1. 将正则改为不跨行匹配：

```python
pattern = rf"^[ \t]*-[ \t]*{re.escape(key)}[ \t]*:[ \t]*(.*)$"
```

2. 保留 `re.MULTILINE | re.IGNORECASE`。
3. 允许空字符串返回，即 `(.*)` 而不是 `(.+)`。
4. 对返回值做 `.strip()`。

### 4.4 增加最小测试

可直接创建或临时运行：

```bash
python3 - <<'PY'
from markdown_parser import extract_bullet_value

txt = "- ai_native_subtype:\n- cross_agent: no\n"
assert extract_bullet_value(txt, "ai_native_subtype") == ""
assert extract_bullet_value(txt, "cross_agent") == "no"

txt2 = "- category: A\n- category_name: 传统类型漏洞\n"
assert extract_bullet_value(txt2, "category") == "A"
print("markdown parser fixed")
PY
```

## 5. Fix 3：增加 LLM 输出校验和重试

### 5.1 问题

当前 `Analyzer` 直接把 LLM 返回写入 step 文件。已有样本：

```text
output/AstrBotDevs_AstrBot/CVE-2026-6117/01_version_verification.md
```

写入了 prompt/证据正文，而不是固定字段结论。

### 5.2 修改文件

```text
analyzer.py
markdown_parser.py
```

### 5.3 操作步骤

1. 在 `Analyzer` 中新增 `validate_step_output(step_name, text)`。
2. 每个 step 定义必填字段：

```python
REQUIRED_FIELDS = {
    "step1": ["intro_time_verdict", "vuln_exists_at_intro_version", "manual_review_needed"],
    "step2": ["classification_type", "primary_module", "secondary_modules", "confidence"],
    "step3": ["category", "category_name", "input_type", "mechanism_type", "requires_ai_function", "cross_agent"],
    "step4": ["difficulty"],
}
```

3. 判定失败条件：

```text
- 缺少必填字段
- 输出以 "# Step 1:" / "# Step 2:" 等 prompt 标题开头
- 输出包含 "## Vulnerability Info" 且缺少 "## Conclusion"
- 输出包含 "## Required Output"
- 输出包含 "Error calling" 或 "API_KEY not configured"
```

4. 新增 `_complete_with_validation(step_name, prompt)`：

```python
def _complete_with_validation(self, step_name: str, prompt: str) -> str:
    text = self.llm_client.complete(prompt)
    if self.validate_step_output(step_name, text):
        return text

    retry_prompt = prompt + "\n\n你的上一次输出没有遵守格式。请只输出最终 Markdown 结果，不要重复输入证据，不要输出 JSON。"
    text2 = self.llm_client.complete(retry_prompt)
    if self.validate_step_output(step_name, text2):
        return text2

    return self._invalid_output_stub(step_name, text2)
```

5. `_invalid_output_stub()` 必须写出可解析字段，并标记人工复核：

```markdown
## Conclusion
- intro_time_verdict: not_verifiable
- vuln_exists_at_intro_version: insufficient_evidence
- manual_review_needed: yes

## Failure
- reason: LLM output did not satisfy required format after retry
```

不同 step 需要不同 stub，确保 summary 可以解析。

### 5.4 验收命令

```bash
python3 - <<'PY'
from pathlib import Path
bad = Path("output/AstrBotDevs_AstrBot/CVE-2026-6117/01_version_verification.md").read_text(encoding="utf-8")
assert bad.startswith("# Step 1:") or "## Vulnerability Info" in bad
print("Known bad output detected; validation should reject this shape")
PY
```

修完后，重跑单条：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117
python3 main.py rebuild-summary
```

如果被 state 跳过，先临时删除该任务输出和 state 中对应记录，或新增 `--force` 参数。推荐新增 `--force`，见 Fix 8。

## 6. Fix 4：修复 summary 字段和重建逻辑

### 6.1 问题

1. `OutputWriter.append_summary_csv()` 的 fieldnames 缺少：

```text
architecture_type
architecture_confidence
publish_at
cve_id
adv_id
```

2. `cmd_run()` 分析完成后只追加基础字段，不解析四步输出。
3. `cmd_rebuild_summary()` 只从目录名补 `project/canonical_id`，没有从 `metadata.md` 补基础字段。

### 6.2 修改文件

```text
output_writer.py
main.py
markdown_parser.py
```

### 6.3 操作步骤

1. 在 `OutputWriter.append_summary_csv()` 的 `fieldnames` 中加入：

```text
publish_at
cve_id
adv_id
architecture_type
architecture_confidence
overall_confidence
manual_review_reason
```

2. 在 `markdown_parser.parse_step2()` 中加入：

```python
"architecture_confidence": extract_bullet_value(text, "architecture_confidence")
```

3. 新增 `parse_metadata(metadata_path)`，从 `metadata.md` 提取：

```text
Project
GitHub URL
Source
CVE ID
Advisory ID
Published At
CWE
```

4. 修改 `cmd_rebuild_summary()`：

```python
fields = {}
fields.update(parse_metadata(task_dir / "metadata.md"))
fields.update(parse_task_output(task_dir))
fields["project"] = fields.get("project") or project_dir.name
fields["canonical_id"] = task_dir.name
writer.append_summary_csv(fields)
```

5. 修改 `cmd_run()`：分析结束后不要只写基础字段。应：

```python
fields = parse_task_output(writer.task_dir(task))
fields.update({
    "project": task.project,
    "canonical_id": task.canonical_id,
    "source": task.source,
    "cwe": task.cwe,
    "publish_at": task.publish_at,
    "cve_id": task.cve_id,
    "adv_id": task.adv_id,
})
writer.append_summary_csv(fields)
```

### 6.4 验收命令

```bash
python3 main.py rebuild-summary
python3 - <<'PY'
import csv
rows=list(csv.DictReader(open("output/summary.csv", encoding="utf-8")))
assert rows
for field in ["project", "canonical_id", "source", "cwe", "architecture_type", "primary_module", "category"]:
    empty=sum(1 for r in rows if not (r.get(field) or "").strip())
    print(field, "empty", empty)
assert sum(1 for r in rows if not (r.get("architecture_type") or "").strip()) == 0
print("summary fields ok")
PY
```

## 7. Fix 5：修复 batch report 统计口径

### 7.1 问题

当前 batch report 直接统计 `progress.jsonl` 所有记录。每个任务有 `running` 和 `success` 两条记录，导致：

```text
Total Tasks: 20
Success: 10
Failed: 0
Success Rate: 50.0%
```

实际应为 10 个任务，10 成功。

### 7.2 修改文件

```text
main.py
state_manager.py
```

### 7.3 操作步骤

1. 在 `StateManager` 新增：

```python
def load_latest_records(self) -> dict[str, dict]:
    latest = {}
    for record in progress.jsonl:
        latest[record["task_key"]] = record
    return latest
```

2. 修改 `generate_batch_report()` 使用 latest records：

```python
latest = state.load_latest_records()
records = list(latest.values())
total = len(records)
success = sum(...)
failed = sum(...)
running = sum(...)
```

3. 报告中增加：

```text
Running
Pending/Unknown
Output Task Dirs
Summary Rows
```

### 7.4 验收命令

```bash
python3 main.py batch-report
cat output/batch_report.md
```

期望：

```text
Total Tasks: 10
Success: 10
Failed: 0
Success Rate: 100.0%
```

## 8. Fix 6：增加输出质量扫描命令

### 8.1 目的

批量跑 DeepSeek 或其他模型前后，需要自动发现：

1. 缺固定字段
2. prompt 泄漏
3. API error 写入
4. JSON 输出
5. summary 空字段

### 8.2 修改文件

```text
main.py
```

### 8.3 新增命令

```bash
python3 main.py audit-output
```

### 8.4 检查规则

扫描 `output/*/*/`：

1. 每个任务是否有 7 个文件。
2. Step 1 是否有：

```text
intro_time_verdict
vuln_exists_at_intro_version
manual_review_needed
```

3. Step 2 是否有：

```text
architecture_type
classification_type
primary_module
confidence
```

4. Step 3 是否有：

```text
category
category_name
input_type
mechanism_type
requires_ai_function
cross_agent
```

5. Step 4 是否有：

```text
difficulty
```

6. 是否出现：

```text
## Required Output
## Vulnerability Info
Error calling
API_KEY not configured
```json
```

### 8.5 输出

生成：

```text
output/audit_report.md
```

字段：

```text
total_task_dirs
complete_task_dirs
missing_files
missing_required_fields
prompt_leakage_files
api_error_files
json_output_files
```

### 8.6 验收命令

```bash
python3 main.py audit-output
cat output/audit_report.md
```

当前未修复前应至少报告：

```text
output/AstrBotDevs_AstrBot/CVE-2026-6117/01_version_verification.md
```

## 9. Fix 7：标准化空值和枚举值

### 9.1 问题

当前输出中 `ai_native_subtype` 可能是：

```text
N/A
(不适用)
(not applicable)
insufficient_evidence
空字符串
```

不利于统计。

### 9.2 修改文件

```text
prompts.py
markdown_parser.py
```

### 9.3 操作步骤

1. 在 prompt 中明确空值枚举：

```text
ai_native_subtype: none | direct_prompt_injection | indirect_prompt_injection | rag_poisoning | tool_output_poisoning | memory_poisoning | delegation_hijack | semantic_policy_bypass | unknown
```

2. `requires_ai_function`：

```text
yes | no | uncertain
```

3. `cross_agent`：

```text
yes | no | uncertain
```

4. 在 `markdown_parser` 增加 `normalize_value()`：

```python
if value in {"N/A", "(不适用)", "(not applicable)", ""}: return "none"
```

5. 对 `category`、`difficulty`、`requires_ai_function`、`cross_agent` 做小写/枚举校验。

### 9.4 验收命令

```bash
python3 main.py rebuild-summary
python3 - <<'PY'
import csv
bad=[]
rows=list(csv.DictReader(open("output/summary.csv", encoding="utf-8")))
for r in rows:
    if r.get("ai_native_subtype") in {"N/A", "(不适用)", "(not applicable)", ""}:
        bad.append((r["project"], r["canonical_id"], r.get("ai_native_subtype")))
print("bad ai_native_subtype", bad)
assert not bad
PY
```

## 10. Fix 8：增加 `--force` 重跑单个任务

### 10.1 问题

当前 state 会跳过已成功任务。修复 prompt 或 parser 后，需要重跑单条样本时不方便。

### 10.2 修改文件

```text
main.py
state_manager.py
```

### 10.3 操作步骤

1. 给 `run` 命令增加：

```bash
--force
```

2. `cmd_run(..., force=False)`：

```python
if not force:
    filter completed
```

3. force 模式下：

```text
- 不删除旧输出目录
- 覆盖 step 文件和 final summary
- 追加新的 state 记录
- rebuild-summary 后以最新文件为准
```

### 10.4 验收命令

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
python3 main.py rebuild-summary
python3 main.py audit-output
```

## 11. 修复后的最小回归流程

修完 Fix 1-8 后，按顺序运行：

```bash
python3 main.py preflight
python3 main.py list-tasks --max 5
python3 main.py resolve-tasks --max 20
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

验收标准：

1. `CVE-2026-6117/01_version_verification.md` 不再是 prompt/证据回显。
2. `summary.csv` 没有 `ai_native_subtype = - cross_agent: no`。
3. `summary.csv` 中 `architecture_type` 非空。
4. `batch_report.md` 的 Total 等于唯一 task_key 数。
5. `audit_report.md` 无 prompt leakage 和 missing required fields。

## 12. 后续批量运行建议

1. 修复完成后先跑 10 条，不要直接全量。
2. 每次批量后立即运行：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

3. 如果 `audit-output` 发现问题，先重跑问题样本，不要继续扩大批量。
4. 全量运行前确认：

```text
missing_required_fields = 0
prompt_leakage_files = 0
api_error_files = 0
json_output_files = 0
```

