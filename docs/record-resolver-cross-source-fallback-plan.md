# RecordResolver 跨来源目录回退修复规划

本文档用于指导 Mimo 修改 `record_resolver.py`，解决远程服务器 100 个任务批量运行中出现的 13 个 `FAIL_NO_VULN_DIR`。只修目录解析逻辑，不改数据包目录，不移动文件，不改 Excel。

## 1. 背景和结论

远程批量运行 100 个任务后，有 13 个任务失败：

```text
12 个 Budibase_budibase 任务：FAIL_NO_VULN_DIR
1 个 DeDeveloper23_codebase-mcp 任务：FAIL_NO_VULN_DIR
```

本地复核结论：

1. 12 个 Budibase 任务可以通过修复 `RecordResolver` 解决。
2. `DeDeveloper23_codebase-mcp / CVE-2026-39884` 在当前数据包中确实缺少该项目数据，代码回退无法解决。
3. Mimo 的方向基本正确，但根因表述需要修正：当前代码不是直接根据 `source` 字段决定查找目录，而是根据 `cve_id` 只查 `cves/`，根据 `adv_id` 只查 `security_advisories/`。
4. Budibase 失败的特殊点是：Excel 里有 `cve_id` 和 `adv_id`，但数据目录实际是 `security_advisories/{project}/{CVE-ID}`，不是 `cves/{project}/{CVE-ID}`，也不是 `security_advisories/{project}/{GHSA-ID}`。

## 2. 已验证的失败样本

### 2.1 可通过 resolver 修复的 12 个任务

这些任务在 Excel 中都是：

```text
project = Budibase_budibase
source = cves
cve_id = CVE-...
adv_id = GHSA-...
```

但实际目录在：

```text
data/ai-vulns-timeline/security_advisories/Budibase_budibase/{CVE-ID}
```

任务列表：

```text
Budibase_budibase CVE-2023-37466
Budibase_budibase CVE-2026-45061
Budibase_budibase CVE-2026-45548
Budibase_budibase CVE-2026-45715
Budibase_budibase CVE-2026-45716
Budibase_budibase CVE-2026-45717
Budibase_budibase CVE-2026-45718
Budibase_budibase CVE-2026-45719
Budibase_budibase CVE-2026-46424
Budibase_budibase CVE-2026-46425
Budibase_budibase CVE-2026-46426
Budibase_budibase CVE-2026-46427
```

当前 resolver 查找结果：

```text
cves/{project}/{CVE-ID} = not found
security_advisories/{project}/{GHSA-ID} = not found
security_advisories/{project}/{CVE-ID} = exists
```

### 2.2 不能通过 resolver 修复的 1 个任务

```text
DeDeveloper23_codebase-mcp CVE-2026-39884
```

验证结果：

```text
data/ai-vulns-timeline/cves/DeDeveloper23_codebase-mcp/CVE-2026-39884 = not found
data/ai-vulns-timeline/security_advisories/DeDeveloper23_codebase-mcp/CVE-2026-39884 = not found
```

注意：数据包里存在同一个 CVE，但属于另一个项目：

```text
data/ai-vulns-timeline/cves/Flux159_mcp-server-kubernetes/CVE-2026-39884
```

不能把这个目录用于 `DeDeveloper23_codebase-mcp`，因为项目不同。

## 3. 当前实现问题

当前 `record_resolver.py` 的核心逻辑是：

```python
if task.cve_id:
    cve_dir = self._find_dir("cves", task.project, task.cve_id)

if task.adv_id:
    advisory_dir = self._find_dir("security_advisories", task.project, task.adv_id)
```

问题：

1. 有 `cve_id` 时不会尝试 `security_advisories/{project}/{cve_id}`。
2. 有 `adv_id` 时只尝试 `security_advisories/{project}/{adv_id}`。
3. 失败原因只说 CVE/GHSA 未找到，没有列出实际尝试过的候选路径。

这会漏掉数据包中“CVE ID 被放在 `security_advisories` 目录下”的情况。

## 4. 推荐修复策略

### 4.1 不要做的事

不要移动目录：

```bash
mv data/ai-vulns-timeline/security_advisories/Budibase_budibase/CVE-* data/ai-vulns-timeline/cves/Budibase_budibase/
```

原因：

1. 会破坏数据包原始结构。
2. 后续如果依赖 `security_advisories` 路径，会制造新问题。
3. 远程服务器和本地数据会变得不一致。

不要跨项目匹配同一个 CVE。

例如不能把：

```text
cves/Flux159_mcp-server-kubernetes/CVE-2026-39884
```

用于：

```text
DeDeveloper23_codebase-mcp/CVE-2026-39884
```

### 4.2 推荐查找顺序

`RecordResolver.resolve()` 应按以下顺序查找：

```text
1. cves/{project}/{cve_id}
2. security_advisories/{project}/{cve_id}
3. security_advisories/{project}/{adv_id}
4. cves/{project}/{adv_id}  # 可选兜底，通常不会命中
```

主目录选择规则：

```text
如果 cves/{project}/{cve_id} 存在，优先使用它。
否则如果 security_advisories/{project}/{cve_id} 存在，使用它。
否则如果 security_advisories/{project}/{adv_id} 存在，使用它。
否则如果 cves/{project}/{adv_id} 存在，使用它。
否则 FAIL_NO_VULN_DIR。
```

保留原有优先级原则：

```text
CVE 正常目录优先于 advisory 目录。
```

新增回退原则：

```text
同一个 project 下，CVE ID 可以在 cves 和 security_advisories 两个来源目录中查找。
```

## 5. 具体修改步骤

### 5.1 修改 `record_resolver.py`

建议新增一个小的候选路径结构，避免逻辑散在多个 if 里。

可用实现方式：

```python
def resolve(self, task: VulnerabilityTask) -> VulnerabilityTask:
    candidates = []

    if task.cve_id:
        candidates.append(("cve_dir", "cves", task.cve_id))
        candidates.append(("cve_dir", "security_advisories", task.cve_id))

    if task.adv_id:
        candidates.append(("advisory_dir", "security_advisories", task.adv_id))
        candidates.append(("advisory_dir", "cves", task.adv_id))

    matched = []
    attempted = []

    for field_name, subdir, vuln_id in candidates:
        attempted.append(f"{subdir}/{task.project}/{vuln_id}")
        path = self._find_dir(subdir, task.project, vuln_id)
        if path:
            matched.append((field_name, subdir, vuln_id, path))

    task.cve_dir = None
    task.advisory_dir = None
    task.primary_data_dir = None
    task.fail_code = None
    task.fail_reason = None

    for field_name, _subdir, _vuln_id, path in matched:
        if field_name == "cve_dir" and task.cve_dir is None:
            task.cve_dir = path
        elif field_name == "advisory_dir" and task.advisory_dir is None:
            task.advisory_dir = path

    if task.cve_dir:
        task.primary_data_dir = task.cve_dir
    elif task.advisory_dir:
        task.primary_data_dir = task.advisory_dir
    else:
        task.fail_code = "FAIL_NO_VULN_DIR"
        task.fail_reason = self._build_fail_reason(task, attempted)

    return task
```

### 5.2 修改失败原因生成

把 `_build_fail_reason()` 改为接收 attempted 列表。

建议输出：

```python
def _build_fail_reason(self, task: VulnerabilityTask, attempted: list[str] | None = None) -> str:
    parts = []
    if task.cve_id:
        parts.append(f"CVE dir not found for {task.cve_id}")
    if task.adv_id:
        parts.append(f"Advisory dir not found for {task.adv_id}")
    if attempted:
        parts.append("attempted: " + ", ".join(attempted))
    if not parts:
        parts.append("No directory paths configured")
    return "; ".join(parts)
```

如果不想改函数签名，也可以新增：

```python
def _format_attempted_paths(...)
```

但不要只保留旧的模糊失败原因。

### 5.3 保持 `_find_dir()` 行为不变

`_find_dir()` 当前支持：

1. 精确路径匹配。
2. project 目录大小写不敏感匹配。

不要为了这次问题改 `_find_dir()` 的大小写逻辑。

注意：

```text
不要对 task.project 做 lower 后拼路径。
```

大小写回退只应发生在 `_find_dir()` 内部。

## 6. 文档同步

### 6.1 修改 `docs/detailed-implementation-steps.md`

找到 Phase 2 目录解析规则，将旧规则：

```text
if task.cve_id:
    cve_dir = data_root / "cves" / task.project / task.cve_id
if task.adv_id:
    advisory_dir = data_root / "security_advisories" / task.project / task.adv_id
```

改为：

```text
if task.cve_id:
    try cves/{project}/{cve_id}
    then try security_advisories/{project}/{cve_id}

if task.adv_id:
    try security_advisories/{project}/{adv_id}
    optional fallback cves/{project}/{adv_id}
```

并补充说明：

```text
有些 CVE ID 目录会被数据包放在 security_advisories 下，resolver 必须支持跨来源目录回退，但不能跨 project 匹配。
```

### 6.2 修改 `docs/implementation-plan.md`

找到目录映射规则，将：

```text
有 CVE -> cves/{project}/{cve_id}/
```

补充为：

```text
有 CVE -> 优先 cves/{project}/{cve_id}/，找不到时回退 security_advisories/{project}/{cve_id}/
```

并保留：

```text
CVE 和 GHSA 都有时，CVE 正常目录优先。
```

### 6.3 可选修改 `docs/project-workflow.md`

将 `record_resolver.py` 的职责描述补充为：

```text
支持 CVE ID 在 cves 和 security_advisories 两个来源目录中查找，避免 Excel source 与数据包实际目录不一致导致误判缺数据。
```

## 7. 验收命令

### 7.1 验证 12 个 Budibase 任务能解析

```bash
python3 - <<'PY'
from config import Config
from task_loader import TaskLoader
from record_resolver import RecordResolver

target_ids = {
    "CVE-2023-37466",
    "CVE-2026-45061",
    "CVE-2026-45548",
    "CVE-2026-45715",
    "CVE-2026-45716",
    "CVE-2026-45717",
    "CVE-2026-45718",
    "CVE-2026-45719",
    "CVE-2026-46424",
    "CVE-2026-46425",
    "CVE-2026-46426",
    "CVE-2026-46427",
}

config = Config()
resolver = RecordResolver(config)
tasks = [
    t for t in TaskLoader(config).load_tasks()
    if t.project == "Budibase_budibase" and t.canonical_id in target_ids
]

assert len(tasks) == 12, len(tasks)

for task in tasks:
    resolver.resolve(task)
    print(task.project, task.canonical_id, task.primary_data_dir, task.fail_code)
    assert task.primary_data_dir is not None
    assert task.fail_code is None
    assert "security_advisories/Budibase_budibase" in str(task.primary_data_dir)

print("Budibase cross-source CVE fallback ok")
PY
```

### 7.2 验证 DeDeveloper 仍然失败且原因明确

```bash
python3 - <<'PY'
from config import Config
from task_loader import TaskLoader
from record_resolver import RecordResolver

config = Config()
resolver = RecordResolver(config)
tasks = [
    t for t in TaskLoader(config).load_tasks()
    if t.project == "DeDeveloper23_codebase-mcp" and t.canonical_id == "CVE-2026-39884"
]

assert len(tasks) == 1, len(tasks)
task = tasks[0]
resolver.resolve(task)

print(task.project, task.canonical_id)
print("primary:", task.primary_data_dir)
print("fail_code:", task.fail_code)
print("fail_reason:", task.fail_reason)

assert task.primary_data_dir is None
assert task.fail_code == "FAIL_NO_VULN_DIR"
assert "DeDeveloper23_codebase-mcp" in task.fail_reason
assert "CVE-2026-39884" in task.fail_reason

print("Missing project data remains correctly failed")
PY
```

如果 `fail_reason` 没有包含 project 名，需要调整 `_build_fail_reason()`，建议把 `project` 写入 attempted paths 或单独写入：

```text
Project data dir not found for DeDeveloper23_codebase-mcp
```

### 7.3 验证已有 10 条样本不受影响

```bash
python3 main.py rebuild-summary
python3 main.py audit-output
```

期望：

```text
Issues: 0 missing files, 0 missing fields, 0 leakage, 0 API errors, 0 JSON output
```

### 7.4 验证 resolve-tasks 结果

```bash
python3 main.py resolve-tasks --max 120
```

检查输出中不应再把上述 12 个 Budibase 任务列为 missing。

## 8. 重新运行建议

修复后在远程服务器上不要直接全量重跑全部任务。建议先重跑失败的 13 个任务。

### 8.1 Budibase 12 个任务

使用 `--project` 和 `--id` 逐条重跑，或如果已有项目列表过滤功能，生成只包含这些任务的列表。

逐条命令示例：

```bash
python3 main.py run --project Budibase_budibase --id CVE-2023-37466 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45061 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45548 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45715 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45716 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45717 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45718 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-45719 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-46424 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-46425 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-46426 --force
python3 main.py run --project Budibase_budibase --id CVE-2026-46427 --force
```

### 8.2 DeDeveloper 1 个任务

不要重复重跑，除非数据包补充了该项目目录。

处理方式：

1. 向数据提供方补充 `DeDeveloper23_codebase-mcp/CVE-2026-39884` 数据。
2. 或在任务清单中标记为数据缺失。
3. 或在最终统计时单独归入 `missing_dataset`。

## 9. 通过标准

本修复完成后必须满足：

1. 12 个 Budibase 任务可以解析到 `security_advisories/Budibase_budibase/{CVE-ID}`。
2. `DeDeveloper23_codebase-mcp/CVE-2026-39884` 仍然失败，但失败原因明确指向项目数据缺失。
3. 不移动任何 `data/ai-vulns-timeline/` 下的目录。
4. 不跨项目复用相同 CVE ID 的数据。
5. 原有已成功任务的 `rebuild-summary` 和 `audit-output` 仍然通过。
6. 文档中的目录解析规则与 `record_resolver.py` 实现一致。
