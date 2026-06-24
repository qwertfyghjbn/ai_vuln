# Result Auditor

## 1. 目标

Result Auditor 是一个独立的离线结果包审计器。它审计的是一个已经导出的 **Result Package**，而不是 live `output/` 目录上的格式完整性。

当前命令：

```bash
python3 main.py audit-results --package-dir <result-package-dir> [--out-dir <output-dir>]
```

相关 ADR：

- [docs/adr/0001-result-auditor-as-offline-package-audit.md](/home/lqs/ai_vuln/docs/adr/0001-result-auditor-as-offline-package-audit.md:1)

## 2. 输入与输出

### 输入

Result Package 至少可以包含：

```text
summary.csv
batch_report.md
audit_report.md
preflight_report.md
*.log
{project}/{canonical_id}/...
```

第一版实现支持两类包：

1. 只有 `summary.csv`、报告和日志的导出包
2. 同时包含 `project/canonical_id/` task 目录的完整包

### 输出

命令会在结果包根目录，或 `--out-dir` 指定目录下生成：

```text
audit_results.csv
audit_results_report.md
```

- `audit_results.csv`：每个 `(project, canonical_id)` 一行
- `audit_results_report.md`：汇总 manual review、summary conflict、evidence missing 等统计

## 3. 当前规则

当前实现是 deterministic、package-bounded 的，不会重新读 repo、git 历史或 advisory。

### 3.1 去重与冲突

- 相同 `(project, canonical_id)` 下，除 key 外所有列完全一致：视为重复副本
- 只要任意非 key 列不同：视为 `summary_conflict`

### 3.2 结构检查

以下任一缺失都会触发 `evidence_missing=yes`：

- task 目录
- `metadata.md`
- `evidence_bundle.md`
- 四个 step 文件之一

### 3.3 summary 与 step 文件一致性

当四个 step 文件都存在时，审计器会重新解析 step 文件，并与去重后的 canonical summary row 对比以下字段：

- `intro_time_verdict`
- `vuln_exists_at_intro_version`
- `manual_review_needed`
- `architecture_type`
- `classification_type`
- `primary_module`
- `secondary_modules`
- `category`
- `category_name`
- `module_from_step2_primary`
- `module_from_step2_secondary`
- `module_from_step2_classification_type`
- `input_type`
- `input_subtype`
- `mechanism_type`
- `mechanism_subtype`
- `requires_ai_function`
- `ai_native_subtype`
- `cross_agent`
- `difficulty`

任一字段不一致都会触发 `summary_step_mismatch=yes`。

### 3.4 最终 manual review 判定

以下任一条件满足时，`needs_manual_review=yes`：

- `summary_row_missing`
- `summary_conflict`
- `evidence_missing`
- `summary_step_mismatch`
- `summary.csv` 中 canonical row 的 `manual_review_needed=yes`

## 4. 代码组织

Result Auditor 的实现位于：

```text
result_audit/
  __init__.py
  models.py
  package_loader.py
  task_index.py
  rules.py
  report_writer.py
  service.py
```

职责分工：

- `package_loader.py`：读取 Result Package 根目录和 task 目录
- `task_index.py`：按 `(project, canonical_id)` 去重并标记冲突
- `rules.py`：执行 task 级审计规则
- `report_writer.py`：写 `audit_results.csv` 和 `audit_results_report.md`
- `service.py`：串起完整审计流程

## 5. 回归测试

固定 fixture 位于：

```text
tests/fixtures/result_packages/
  complete_package/
  duplicate_conflict_package/
  missing_evidence_package/
```

对应回归测试：

- [tests/test_result_audit_regression_fixtures.py](/home/lqs/ai_vuln/tests/test_result_audit_regression_fixtures.py:1)

运行方式：

```bash
python3 -m unittest tests.test_result_audit_regression_fixtures
python3 -m unittest tests.test_result_audit_package_loader tests.test_result_audit_task_index tests.test_result_audit_rules tests.test_result_audit_service tests.test_result_audit_regression_fixtures
```
