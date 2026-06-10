# 并行运行与 `--project-list` 实施规划

本文档用于指导后续使用 **Mimo v2.5 Pro + Claude Code** 为本项目增加：

1. `run` 命令的**单进程内并行执行**
2. `--project-list` 任务过滤入口

目标是提升批量处理吞吐，同时不破坏现有输出格式、统计口径和 AGENTS.md 中的安全约束。

---

## 1. 本次修改的最终约束

以下约束已经明确，不再讨论其他变体：

### 1.1 并行范围

只支持：

- **单个 `python3 main.py run` 进程内部**，通过 `--max-workers N` 并行处理多条任务

不支持：

- 多个 `run` 进程同时写同一个工作目录
- 多个独立进程同时共享 `state/`、`output/`、`repos/`、`worktrees/`

### 1.2 `--project-list` 语义

`--project-list` 定义为：

- 接受 Excel `project` 字段的**精确项目名白名单**
- 使用逗号分隔，例如：

```bash
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP
```

过滤顺序固定为：

1. 先按 `--project-list` 过滤任务
2. 再按 `--project + --id` 做单任务精确过滤（若提供）
3. 再按 `--force` / `completed_keys` 决定是否跳过已完成任务
4. 最后应用 `--max`

### 1.3 并行粒度

调度粒度定义为：

- 默认按 `task` 并行
- 但**同一 `project` 在任一时刻最多只允许 1 个 task 运行**
- 不同项目之间允许并行

也就是说：

- `AstrBotDevs_AstrBot` 的多个 CVE 不能同时跑
- `AstrBotDevs_AstrBot` 和 `0xKoda_WireMCP` 可以同时跑

### 1.4 并发写策略

全局共享文件只能由主线程写：

- `state/progress.jsonl`
- `output/summary.csv`
- `output/batch_report.md`

worker 可以直接写 task 私有目录下的文件：

- `output/{project}/{id}/metadata.md`
- `output/{project}/{id}/evidence_bundle.md`
- `output/{project}/{id}/01_*.md`
- `output/{project}/{id}/02_*.md`
- `output/{project}/{id}/03_*.md`
- `output/{project}/{id}/04_*.md`
- `output/{project}/{id}/final_case_summary.md`

### 1.5 失败与 `--force` 语义

并行模式下保持现有批处理语义：

1. 单条 task 失败**不会**中止整个批次
2. 主线程继续调度剩余 task
3. `--force` 保持原语义：跳过 `completed_keys` 过滤，允许重跑已完成任务
4. 批次结束后统一生成 `batch_report.md`
5. 最终可信统计仍以：

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

为准

---

## 2. 为什么当前代码不能直接并行

当前 `run` 逻辑在 [main.py](../main.py) 中是串行循环。若直接开线程并行，会至少产生以下问题：

### 2.1 全局文件并发追加写

当前代码会在任务执行过程中直接追加：

- [state_manager.py](../state_manager.py) 中的 `progress.jsonl`
- [output_writer.py](../output_writer.py) 中的 `summary.csv`

这会导致：

1. 行间交错
2. 状态记录顺序不稳定
3. `summary.csv` 可能被并发写坏

### 2.2 Repo 级共享资源冲突

[repo_manager.py](../repo_manager.py) 中的 repo 目录是：

```text
repos/{project}
```

同一项目下多个 task 若同时运行，会并发触发：

1. `git fetch`
2. `git worktree add`
3. `git worktree remove`

这会增加以下风险：

1. 同项目 worktree 生命周期冲突
2. fetch / worktree 操作时序不稳定
3. 同项目输出问题难以复现

### 2.3 运行期统计口径不稳定

`summary.csv` 当前是运行时边跑边写；而文档和 AGENTS.md 已经明确：

- 批量统计的最终可信口径应由 `rebuild-summary` 重建

因此，并行改造必须继续保留：

1. 运行期可追加摘要
2. 批量后可重建最终摘要

---

## 3. 推荐实现方式

本轮不要引入复杂的多进程、文件锁、数据库锁。优先采用：

- `concurrent.futures.ThreadPoolExecutor`
- 主线程调度
- worker 只处理单条 task 的核心分析

原因：

1. 当前工作负载主要是 I/O：文件读写、git 子进程、网络型 LLM 调用
2. 线程实现改动最小
3. 主线程统一写全局文件时不需要额外锁机制
4. 更符合 Mimo 这类模型分阶段实施的能力边界

---

## 4. 目标命令行为

实现后，以下命令应该成立：

```bash
python3 main.py run --max-workers 4 --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP
```

其行为应为：

1. 只处理这两个项目下的任务
2. 最多并行 4 个 worker
3. 但同一时刻：
   - 最多 1 个 `AstrBotDevs_AstrBot` task
   - 最多 1 个 `0xKoda_WireMCP` task
4. 主线程负责全局状态和汇总写入
5. 所有 task 结束后统一生成 `batch_report.md`

单任务模式也必须继续工作：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force
```

如果同时提供：

```bash
--project-list A,B --project A --id CVE-xxx
```

则最终只运行：

```text
project == A and canonical_id == CVE-xxx
```

如果 `--project` 不在 `--project-list` 中，则应直接报错，不要静默忽略。

---

## 5. 建议修改文件

本次建议只改以下文件：

```text
main.py
docs/project-workflow.md
docs/parallel-project-list-implementation-plan.md
```

如确有必要，可少量修改：

```text
models.py
```

不建议改动：

```text
task_loader.py
record_resolver.py
evidence_builder.py
repo_manager.py
output_writer.py
state_manager.py
analyzer.py
markdown_parser.py
```

本轮目标是**调度层改造**，不要顺手重构证据层或 prompt 层。

---

## 6. 设计细节

### 6.1 新增 CLI 参数

在 [main.py](../main.py) 的 `run` 子命令下新增：

```bash
--project-list
```

定义：

- 类型：字符串
- 格式：逗号分隔项目名
- 不支持模糊匹配
- 不支持 owner/repo 形式

推荐解析逻辑：

```python
def parse_project_list(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",")]
    result = {item for item in items if item}
    return result or None
```

### 6.2 任务过滤逻辑

在 `cmd_run()` 中，任务过滤顺序明确写死：

1. `loader.load_tasks()`
2. 如果存在 `project_list`，按 `task.project in project_list` 过滤
3. 如果存在 `project` + `id`，按精确匹配过滤
4. 如果未启用 `force`，按 `completed_keys` 过滤
5. 如果存在 `max_tasks`，再截断

额外要求：

1. `--project-list` 中如有不存在的项目名，应报错并退出
2. `--project` 与 `--project-list` 冲突时，应报错并退出
3. 过滤后任务数为 0 时，应给出清晰提示

### 6.3 单条 task 处理函数

从 `cmd_run()` 中抽出单条任务处理函数，例如：

```python
def process_single_task(config: Config, task: VulnerabilityTask) -> TaskRunResult:
    ...
```

建议返回结构：

```python
@dataclass
class TaskRunResult:
    task: VulnerabilityTask
    status: str  # success | failed
    fail_code: str | None = None
    fail_reason: str | None = None
```

要求：

1. worker 内可以：
   - `resolver.resolve(task)`
   - `writer.write_metadata(task)`
   - `builder.build(task)`
   - `repo_manager.collect_evidence(evidence)`
   - `analyzer.analyze(evidence)`
2. worker 内**不要**：
   - `state.append_status(...)`
   - `writer.append_summary_csv(...)`
   - `generate_batch_report(...)`

### 6.4 主线程与 worker 的职责划分

#### worker 负责

1. 单 task 证据收集
2. 单 task 代码收集
3. 单 task step 文件写入
4. 单 task `final_case_summary.md` 写入

#### 主线程负责

1. 任务筛选
2. 调度 submission
3. `running` / `success` / `failed` 状态写入
4. `summary.csv` 写入
5. 最终 `batch_report.md` 生成
6. 总成功/失败计数

### 6.5 项目级串行调度

这是本轮最关键的并行约束。

目标不是简单地：

```python
executor.submit(process_single_task, ...)
```

而是：

- 同一项目的多个任务形成队列
- 每个项目同一时刻只允许一个 in-flight future
- 某项目一个 task 完成后，主线程再提交该项目的下一个 task

推荐做法：

1. 先把任务按 `project` 分组
2. 每组保持原顺序
3. 先为尽可能多的不同项目提交首个任务
4. 某个 future 完成后：
   - 主线程处理结果
   - 若该 project 还有剩余任务，则提交下一个

这样既满足“按 task 并行”，又满足“同项目串行”。

### 6.6 `summary.csv` 的并行口径

并行模式下，`summary.csv` 写入要求如下：

1. 只由主线程在 task 完成后写入
2. 写入内容仍通过：

```python
fields = parse_task_output(writer.task_dir(task))
```

生成

3. 再补齐：

```python
project
canonical_id
source
cwe
publish_at
cve_id
adv_id
```

4. 不引入并发文件锁
5. 最终统计口径仍建议使用：

```bash
python3 main.py rebuild-summary
```

### 6.7 `progress.jsonl` 的并行口径

并行模式下，状态文件写入要求如下：

1. 主线程在 task 被提交时写入 `running`
2. 主线程在 future 完成后写入：
   - `success`
   - 或 `failed`
3. worker 不直接写状态文件

这样可以保持 `load_latest_records()` 现有逻辑不变。

### 6.8 `batch_report.md` 的生成时机

保持现有行为：

- 全部任务结束后统一调用 `generate_batch_report(config)`

不要在 worker 内生成或刷新批量报告。

---

## 7. 推荐实施顺序

不要一次性大改 `cmd_run()`。建议拆成 5 个小阶段。

### Phase 1：增加 `--project-list` 过滤

只修改：

```text
main.py
```

目标：

1. 新增 `--project-list`
2. 完成字符串解析
3. 实现过滤和参数冲突校验
4. 保持串行执行不变

验收命令：

```bash
python3 main.py list-tasks --max 5
python3 main.py run --project-list AstrBotDevs_AstrBot --max 1 --offline
python3 main.py run --project-list NotExistProject --max 1
```

期望：

1. 合法项目名能正常过滤
2. 非法项目名直接报错

### Phase 2：抽出单 task worker 函数

只修改：

```text
main.py
```

目标：

1. 将当前串行循环中的核心逻辑抽到单函数
2. 保持当前串行行为不变
3. 让主线程仍然负责全局状态与 summary 写入

验收命令：

```bash
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --offline --force
```

期望：

1. 结果与改造前一致
2. `summary.csv`、`progress.jsonl` 仍可正常写

### Phase 3：引入 `ThreadPoolExecutor`

只修改：

```text
main.py
```

目标：

1. 使用 `--max-workers`
2. `max_workers <= 1` 时保持串行路径
3. `max_workers > 1` 时启用线程池

此阶段暂时可以先做“多项目并行、同项目串行”调度框架，不必优化日志表现。

验收命令：

```bash
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 2 --max 2 --offline --force
```

期望：

1. 两个不同项目可并行执行
2. 不出现共享文件写坏

### Phase 4：落实项目级串行调度

只修改：

```text
main.py
```

目标：

1. 同项目只允许一个 in-flight future
2. 不同项目可并行
3. 完整保留成功/失败统计

建议通过日志打印 project + canonical_id 观察调度顺序。

验收方式：

1. 构造至少 2 个同项目 task + 1 个异项目 task
2. 观察日志提交顺序
3. 确认同项目不会同时进入 `collect_evidence` / `analyze`

### Phase 5：文档同步

修改：

```text
docs/project-workflow.md
docs/parallel-project-list-implementation-plan.md
```

目标：

1. 更新 CLI 命令说明
2. 更新 `run` 的并行语义说明
3. 明确“只支持单进程内并行”

---

## 8. 关键伪代码

下面给出推荐的主调度框架，后续实现可按此思路展开。

```python
tasks = load_and_filter_tasks(...)

if config.max_workers <= 1:
    for task in tasks:
        state.append_status(task, "running")
        result = process_single_task(config, task)
        finalize_result(result)
else:
    grouped = group_tasks_by_project(tasks)
    executor = ThreadPoolExecutor(max_workers=config.max_workers)

    in_flight = {}
    future_to_project = {}

    # 先为不同项目提交首个任务
    for project in grouped:
        if len(in_flight) >= config.max_workers:
            break
        submit_next_task_for_project(project)

    while future_to_project:
        future = next_completed_future(...)
        project = future_to_project.pop(future)
        result = future.result()
        finalize_result(result)

        # 同一项目串行提交下一个
        if grouped[project]:
            submit_next_task_for_project(project)

        # 若还有空闲 worker，也可补提交其他尚未启动项目
        maybe_submit_more_projects(...)

generate_batch_report(config)
```

其中：

```python
finalize_result(result)
```

必须由主线程执行，并负责：

1. `state.append_status(...)`
2. `parse_task_output(...)`
3. `writer.append_summary_csv(...)`
4. 成功/失败计数

---

## 9. 不要做的事

本轮禁止：

1. 不要把 `run` 改成多进程
2. 不要引入 Redis / SQLite 锁 / 文件锁框架
3. 不要同时改 `dry-run`、`build-evidence`、`collect-code` 的调度方式，除非用户明确要求
4. 不要修改 Excel 字段映射
5. 不要改变输出目录结构
6. 不要把 step 输出改成 JSON
7. 不要尝试支持多个 `run` 进程共享同一个 workspace
8. 不要在并行改造时顺手重构 prompt、parser、summary 字段体系

---

## 10. 推荐给 Mimo 和 Claude 的执行拆分

### 方案 A：Mimo 先做，Claude 收尾

#### Mimo v2.5 Pro

适合做：

1. `main.py` 新增 `--project-list`
2. `main.py` 增加过滤逻辑
3. `main.py` 抽出单 task worker 函数
4. `docs/project-workflow.md` 的 CLI 文档补充

不适合直接让 Mimo 一次性完成：

1. 整个线程池调度
2. 同项目串行约束
3. 并发状态写入边界控制

#### Claude Code

适合做：

1. 引入 `ThreadPoolExecutor`
2. 做 project-aware scheduler
3. 检查 `summary.csv` / `progress.jsonl` 行为
4. 跑回归命令并核对输出

### 方案 B：完全按阶段拆

1. Mimo：Phase 1
2. Mimo：Phase 2
3. Claude：Phase 3
4. Claude：Phase 4
5. 任一模型：Phase 5 文档同步

---

## 11. 验收命令清单

### 11.1 语义验收

```bash
python3 main.py run --project-list AstrBotDevs_AstrBot --max 1 --offline
python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 2 --max 2 --offline --force
python3 main.py run --project AstrBotDevs_AstrBot --id CVE-2026-6117 --force --offline
```

### 11.2 结果验收

```bash
python3 main.py rebuild-summary
python3 main.py batch-report
python3 main.py audit-output
```

### 11.3 人工检查点

必须人工确认：

1. `output/summary.csv` 可正常读取
2. `state/progress.jsonl` 每行都是合法 JSON
3. `batch_report.md` 可生成
4. 同项目任务不会同时运行
5. 不同项目任务可以并行运行

---

## 12. 最终交付要求

实现完成后，最终报告至少说明：

1. 修改了哪些文件
2. `--project-list` 的精确定义
3. 并行仅支持单进程内 worker
4. 同项目串行、不同项目并行
5. 哪些命令已执行
6. `summary.csv`、`batch_report.md`、`audit_report.md` 是否正常
7. 是否仍存在剩余风险

剩余风险应至少包括：

1. 仍不支持多个 `run` 进程共享一个工作目录
2. 最终可信统计仍建议依赖 `rebuild-summary`
3. 若底层第三方 LLM SDK 非线程安全，后续可能需要再收紧并发模式

---

## 13. 实施状态

### 已完成的 Phase

| Phase | 内容 | 状态 | 修改文件 |
|-------|------|------|----------|
| Phase 1 | 增加 `--project-list` 过滤 | ✅ 完成 | `main.py` |
| Phase 2 | 抽出单 task worker 函数 | ✅ 完成 | `main.py` |
| Phase 3 | 引入 `ThreadPoolExecutor` | ✅ 完成 | `main.py` |
| Phase 4 | 落实项目级串行调度 | ✅ 完成 | `main.py` |
| Phase 5 | 文档同步 | ✅ 完成 | `docs/project-workflow.md`, `docs/parallel-project-list-implementation-plan.md` |

### 最终交付说明

1. **修改的文件**：`main.py`、`docs/project-workflow.md`、`docs/parallel-project-list-implementation-plan.md`
2. **`--project-list` 定义**：逗号分隔的项目名白名单，精确匹配 Excel `project` 字段
3. **并行范围**：仅支持单进程内 `ThreadPoolExecutor` worker
4. **调度规则**：同项目串行（`in_flight` dict 保证每项目最多 1 个 future），不同项目并行
5. **已执行的验收命令**：
   - `python3 main.py run --project-list NotExistProject --max 1` → 正确报错
   - `python3 main.py run --project-list AstrBotDevs_AstrBot --max 1 --offline --force` → 正常运行
   - `python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 2 --max 2 --offline --force` → 并行正常
   - `python3 main.py run --project-list AstrBotDevs_AstrBot,0xKoda_WireMCP --max-workers 2 --max 3 --offline --force` → 同项目串行验证通过
6. **共享文件状态**：`summary.csv`、`progress.jsonl`、`batch_report.md` 均正常
7. **剩余风险**：
   - 仍不支持多个 `run` 进程共享一个工作目录
   - 最终可信统计仍建议依赖 `rebuild-summary`
   - 若底层第三方 LLM SDK 非线程安全，后续可能需要再收紧并发模式

