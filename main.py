import argparse
import logging
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from dataclasses import dataclass
from pathlib import Path

from config import Config, SUPPORTED_AGENT_BACKENDS
from dataset_preparer import DatasetPreparer
from task_loader import TaskLoader
from record_resolver import RecordResolver
from state_manager import StateManager
from output_writer import OutputWriter
from evidence_builder import EvidenceBuilder
from repo_manager import RepoManager
from analyzer import Analyzer
from agent_analyzer import AgentAnalyzer
from agent_runner import build_agent_runner
from markdown_parser import parse_task_output, parse_metadata


def parse_project_list(raw: str | None) -> set[str] | None:
    """Parse comma-separated project list string into a set."""
    if not raw:
        return None
    items = [item.strip() for item in raw.split(",")]
    result = {item for item in items if item}
    return result or None


@dataclass
class TaskRunResult:
    """Result of processing a single task."""
    task: "VulnerabilityTask"
    status: str  # success | failed
    fail_code: str | None = None
    fail_reason: str | None = None


def process_single_task(config: Config, task: "VulnerabilityTask") -> TaskRunResult:
    """Process a single vulnerability task. Worker-only: no state or summary writes."""
    resolver = RecordResolver(config)
    builder = EvidenceBuilder(config)
    repo_manager = RepoManager(config)
    writer = OutputWriter(config)

    # §10.1: Select analyzer based on analysis_mode
    if config.analysis_mode == "agent":
        runner = build_agent_runner(config)
        analyzer = AgentAnalyzer(config, writer, repo_manager, runner)
    else:
        analyzer = Analyzer(config, writer)

    try:
        # Resolve directories
        resolver.resolve(task)
        writer.write_metadata(task)

        if task.fail_code:
            writer.write_failure(task)
            return TaskRunResult(task, "failed", task.fail_code, task.fail_reason)

        # Build evidence
        evidence = builder.build(task)
        writer.write_evidence_bundle(evidence)

        # §10.2: Code evidence collection branch by analysis_mode
        if config.analysis_mode == "prompt":
            if not config.offline and evidence.intro_commit:
                logging.info(f"Collecting code evidence for {task.task_key}")
                print(f"  Collecting code evidence...")
                repo_manager.collect_evidence(evidence)
                writer.write_evidence_bundle(evidence)
        elif config.analysis_mode == "agent":
            if config.offline:
                return TaskRunResult(task, "failed", "FAIL_AGENT_OFFLINE_UNSUPPORTED",
                                     "Agent mode does not support --offline in v1.")
            # Agent mode: skip collect_evidence; AgentAnalyzer handles prepare_agent_workspace internally

        # Run analysis
        logging.info(f"Running analysis for {task.task_key}")
        print(f"  Running analysis...")
        analyzer.analyze(evidence)

        return TaskRunResult(task, "success")

    except Exception as e:
        logging.exception(f"Unhandled error while processing {task.task_key}")

        fail_code = task.fail_code or "FAIL_ANALYSIS_ERROR"
        fail_reason = task.fail_reason or str(e)
        task.fail_code = fail_code
        task.fail_reason = fail_reason

        # Best-effort failure metadata write for partial task runs.
        try:
            writer.write_failure(task)
        except Exception:
            logging.exception(f"Failed to write failure metadata for {task.task_key}")

        return TaskRunResult(task, "failed", fail_code, fail_reason)


def finalize_task_result(config, state, writer, result, task_index, total):
    """Main-thread only: write state and summary after a task completes.

    Returns "success" or "failed" for counting.
    """
    task = result.task
    if result.status == "success":
        # Update summary CSV with full fields
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

        state.append_status(task, "success")
        logging.info(f"Task completed: {task.task_key}")
        print(f"✅ [{task_index}/{total}] {task.task_key} Done")
        return "success"
    else:
        state.append_status(task, "failed", result.fail_code, result.fail_reason)
        logging.warning(f"Task failed: {task.task_key} - {result.fail_code}")
        print(f"❌ [{task_index}/{total}] {task.task_key} {result.fail_code}")
        return "failed"


def setup_logging(config: Config):
    """Setup logging configuration."""
    log_dir = config.root_dir / config.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def ensure_directories(config: Config):
    """Create required directories if they don't exist."""
    dirs = [
        config.data_root,
        config.repos_dir,
        config.worktrees_dir,
        config.output_dir,
        config.state_dir,
        config.logs_dir,
    ]
    for d in dirs:
        (config.root_dir / d).mkdir(parents=True, exist_ok=True)


def cmd_preflight(config: Config):
    """Run preflight checks and generate report."""
    ensure_directories(config)
    preparer = DatasetPreparer(config)
    result = preparer.prepare()
    report = preparer.generate_report(result)

    # Write report
    report_path = config.root_dir / config.output_dir / "preflight_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nReport saved to: {report_path}")

    if not result["prepared"]:
        print("\n⚠️  Dataset not fully prepared. Check errors above.")
        sys.exit(1)
    else:
        print("\n✅ Dataset ready.")


def cmd_list_tasks(config: Config, max_display: int | None = None):
    """List vulnerability tasks from Excel."""
    loader = TaskLoader(config)
    tasks = loader.load_tasks()

    print(f"Loaded tasks: {len(tasks)}")

    display_count = max_display if max_display else len(tasks)
    for i, task in enumerate(tasks[:display_count]):
        cwe_str = f" {task.cwe}" if task.cwe else ""
        print(f"{i+1}. {task.project} {task.canonical_id} {task.source}{cwe_str}")


def cmd_resolve_tasks(config: Config, max_tasks: int | None = None):
    """Resolve task directories."""
    loader = TaskLoader(config)
    resolver = RecordResolver(config)

    tasks = loader.load_tasks()
    if max_tasks:
        tasks = tasks[:max_tasks]

    resolved = 0
    missing = 0
    missing_tasks = []

    for task in tasks:
        resolver.resolve(task)
        if task.primary_data_dir:
            resolved += 1
        else:
            missing += 1
            missing_tasks.append(task)

    print(f"Resolved: {resolved}")
    print(f"Missing: {missing}")

    if resolved > 0:
        # Show first resolved example
        for task in tasks:
            if task.primary_data_dir:
                print(f"\nExample:")
                print(f"{task.project}:{task.canonical_id} -> {task.primary_data_dir}")
                break

    if missing_tasks:
        print(f"\nMissing directories (first 10):")
        for task in missing_tasks[:10]:
            print(f"  {task.task_key} - {task.fail_reason}")


def cmd_dry_run(config: Config, max_tasks: int | None = None):
    """Dry run: generate output directories with placeholder content."""
    ensure_directories(config)
    loader = TaskLoader(config)
    resolver = RecordResolver(config)
    state = StateManager(config)
    writer = OutputWriter(config)

    tasks = loader.load_tasks()
    if max_tasks:
        tasks = tasks[:max_tasks]

    # Filter completed tasks
    completed_keys = state.load_completed_keys()
    tasks = [t for t in tasks if t.task_key not in completed_keys]

    success_count = 0
    fail_count = 0

    for task in tasks:
        # Resolve directories
        resolver.resolve(task)

        # Write metadata
        writer.write_metadata(task)

        if task.fail_code:
            # Task has no data directory
            state.append_status(task, "failed", task.fail_code, task.fail_reason)
            fail_count += 1
            print(f"❌ {task.task_key} - {task.fail_code}")
            continue

        # Write placeholder step files
        step_files = [
            "01_version_verification.md",
            "02_module_classification.md",
            "03_vulnerability_pattern_classification.md",
            "04_exploit_condition_summary.md",
        ]
        for filename in step_files:
            placeholder = f"# {filename.replace('.md', '').replace('_', ' ').title()}\n\n*Placeholder content for dry-run*\n"
            writer.write_step_file(task, filename, placeholder)

        # Write placeholder final summary
        writer.write_final_summary(task, {"Summary": "*Placeholder for dry-run*"})

        # Write to summary CSV
        writer.append_summary_csv({
            "project": task.project,
            "canonical_id": task.canonical_id,
            "source": task.source,
            "cwe": task.cwe,
        })

        state.append_status(task, "success")
        success_count += 1
        print(f"✅ {task.task_key}")

    print(f"\nDry-run complete: {success_count} success, {fail_count} failed")


def cmd_build_evidence(config: Config, project: str, vuln_id: str):
    """Build evidence bundle for a specific task."""
    loader = TaskLoader(config)
    resolver = RecordResolver(config)
    builder = EvidenceBuilder(config)
    writer = OutputWriter(config)

    # Find the task
    tasks = loader.load_tasks()
    task = None
    for t in tasks:
        if t.project == project and t.canonical_id == vuln_id:
            task = t
            break

    if not task:
        print(f"Task not found: {project}:{vuln_id}")
        sys.exit(1)

    # Resolve directories
    resolver.resolve(task)

    if not task.primary_data_dir:
        print(f"❌ No data directory for {task.task_key}")
        sys.exit(1)

    # Build evidence
    evidence = builder.build(task)

    # Write metadata and evidence bundle
    writer.write_metadata(task)
    writer.write_evidence_bundle(evidence)

    print(f"✅ Evidence built for {task.task_key}")
    print(f"   Primary data dir: {task.primary_data_dir}")
    print(f"   Timeline: {'✓' if evidence.timeline else '✗'}")
    print(f"   Relevance: {'✓' if evidence.relevance else '✗'}")
    print(f"   Issue text: {'✓' if evidence.issue_text else '✗'}")
    print(f"   Root cause: {'✓' if evidence.root_cause else '✗'}")
    print(f"   SAST: {'✓' if evidence.sast else '✗'}")
    print(f"   Vuln positions: {len(evidence.vuln_positions)}")
    print(f"   Dataflow steps: {len(evidence.dataflow)}")

    print(f"\n   Output: {writer.task_dir(task)}/evidence_bundle.md")


def cmd_collect_code(config: Config, project: str, vuln_id: str):
    """Collect code evidence for a specific task."""
    loader = TaskLoader(config)
    resolver = RecordResolver(config)
    builder = EvidenceBuilder(config)
    repo_manager = RepoManager(config)
    writer = OutputWriter(config)

    # Find the task
    tasks = loader.load_tasks()
    task = None
    for t in tasks:
        if t.project == project and t.canonical_id == vuln_id:
            task = t
            break

    if not task:
        print(f"Task not found: {project}:{vuln_id}")
        sys.exit(1)

    # Resolve directories
    resolver.resolve(task)

    if not task.primary_data_dir:
        print(f"❌ No data directory for {task.task_key}")
        sys.exit(1)

    # Build evidence
    evidence = builder.build(task)

    # Collect code evidence
    print(f"Collecting code evidence for {task.task_key}...")
    repo_manager.collect_evidence(evidence)

    # Write outputs
    writer.write_metadata(task)
    writer.write_evidence_bundle(evidence)

    if evidence.fail_code:
        print(f"❌ {evidence.fail_code}: {evidence.fail_reason}")
    else:
        print(f"✅ Code evidence collected")
        print(f"   Intro commit: {evidence.intro_commit}")
        print(f"   Intro parent: {evidence.intro_parent_commit}")
        print(f"   Fix commit: {evidence.fix_commit}")
        print(f"   Fix parent: {evidence.fix_parent_commit}")
        print(f"   Intro diff: {'✓' if evidence.intro_diff else '✗'} ({len(evidence.intro_diff) if evidence.intro_diff else 0} chars)")
        print(f"   Fix diff: {'✓' if evidence.fix_diff else '✗'} ({len(evidence.fix_diff) if evidence.fix_diff else 0} chars)")
        print(f"   Code windows: {len(evidence.code_at_intro)} at intro, {len(evidence.code_at_intro_parent)} at intro_parent")

    print(f"\n   Output: {writer.task_dir(task)}/evidence_bundle.md")


def cmd_run(config: Config, max_tasks: int | None = None, offline: bool = False, project: str | None = None, vuln_id: str | None = None, force: bool = False, project_list: set[str] | None = None):
    """Run full analysis pipeline."""
    ensure_directories(config)

    if offline:
        config.offline = True

    # Agent mode does not support --offline in v1
    if config.analysis_mode == "agent" and config.offline:
        print("Error: Agent mode does not support --offline in v1.")
        sys.exit(1)

    logging.info(f"Starting run: max_tasks={max_tasks}, offline={offline}, project={project}, id={vuln_id}, force={force}, project_list={project_list}")

    loader = TaskLoader(config)
    state = StateManager(config)
    writer = OutputWriter(config)

    tasks = loader.load_tasks()
    logging.info(f"Loaded {len(tasks)} tasks")

    # Validate --project-list: error if --project is not in --project-list
    if project_list and project and project not in project_list:
        logging.error(f"--project '{project}' is not in --project-list {project_list}")
        print(f"Error: --project '{project}' is not in --project-list. Valid projects: {project_list}")
        sys.exit(1)

    # Filter by --project-list if specified
    if project_list:
        all_projects = {t.project for t in tasks}
        invalid_projects = project_list - all_projects
        if invalid_projects:
            logging.error(f"Invalid projects in --project-list: {invalid_projects}")
            print(f"Error: Invalid projects in --project-list: {invalid_projects}")
            sys.exit(1)
        tasks = [t for t in tasks if t.project in project_list]
        logging.info(f"After project-list filter: {len(tasks)} tasks remaining")
        if not tasks:
            print("No tasks remaining after --project-list filter.")
            sys.exit(1)

    # Filter by project/id if specified
    if project and vuln_id:
        tasks = [t for t in tasks if t.project == project and t.canonical_id == vuln_id]
        if not tasks:
            logging.error(f"Task not found: {project}:{vuln_id}")
            print(f"Task not found: {project}:{vuln_id}")
            sys.exit(1)

    # Filter completed tasks (skip if force is True)
    if not force:
        completed_keys = state.load_completed_keys()
        tasks = [t for t in tasks if t.task_key not in completed_keys]
        logging.info(f"After filtering completed: {len(tasks)} tasks remaining")
    else:
        logging.info(f"Force mode: skipping completed check")

    if max_tasks:
        tasks = tasks[:max_tasks]

    success_count = 0
    fail_count = 0
    total_tasks = len(tasks)

    if config.max_workers <= 1:
        # Serial path
        for i, task in enumerate(tasks):
            logging.info(f"[{i+1}/{total_tasks}] Processing {task.task_key}")
            print(f"\n[{i+1}/{total_tasks}] Processing {task.task_key}...")
            state.append_status(task, "running")

            result = process_single_task(config, task)

            if finalize_task_result(config, state, writer, result, i + 1, total_tasks) == "success":
                success_count += 1
            else:
                fail_count += 1
    else:
        # Parallel path: multi-project parallel, same-project serial
        logging.info(f"Parallel mode: max_workers={config.max_workers}")
        print(f"\nParallel mode: max_workers={config.max_workers}")

        # Group tasks by project, preserving order
        grouped: dict[str, list] = defaultdict(list)
        for task in tasks:
            grouped[task.project].append(task)

        project_iter = iter(grouped.keys())
        in_flight: dict[str, object] = {}  # project -> future
        future_to_project: dict[object, str] = {}  # future -> project
        future_to_task: dict[object, object] = {}  # future -> task
        task_counter = 0
        completed_counter = 0

        def submit_next(project):
            """Submit the next task for a project. Guarantees same-project serial."""
            nonlocal task_counter
            assert project not in in_flight, f"Project {project} already has an in-flight task"
            if not grouped[project]:
                return
            task = grouped[project].pop(0)
            task_counter += 1
            in_flight_projects = list(in_flight.keys()) + [project]
            logging.info(f"[{task_counter}/{total_tasks}] Submitting {task.task_key} (in_flight: {in_flight_projects})")
            print(f"\n[{task_counter}/{total_tasks}] Submitting {task.task_key} (in_flight: {in_flight_projects})")
            state.append_status(task, "running")
            future = executor.submit(process_single_task, config, task)
            in_flight[project] = future
            future_to_project[future] = project
            future_to_task[future] = task

        def try_fill_workers():
            """Submit tasks for idle projects up to max_workers."""
            # First: submit next tasks for projects that still have work but no in-flight future
            for proj in list(grouped.keys()):
                if len(in_flight) >= config.max_workers:
                    return
                if proj not in in_flight and grouped[proj]:
                    submit_next(proj)

        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            # Submit initial tasks: one per project, up to max_workers
            for proj in list(grouped.keys()):
                if len(in_flight) >= config.max_workers:
                    break
                if grouped[proj]:
                    submit_next(proj)

            while future_to_project:
                # Wait for any future to complete
                done, _ = wait(future_to_project.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    project = future_to_project.pop(future)
                    task = future_to_task.pop(future)
                    del in_flight[project]
                    try:
                        result = future.result()
                    except Exception as e:
                        logging.exception(f"Future crashed for {task.task_key}")
                        result = TaskRunResult(task, "failed", "FAIL_WORKER_CRASH", str(e))

                    remaining_in_flight = list(in_flight.keys())
                    logging.info(f"[done] {result.task.task_key} from {project} (remaining in_flight: {remaining_in_flight})")
                    print(f"[done] {result.task.task_key} from {project} (remaining in_flight: {remaining_in_flight})")
                    completed_counter += 1

                    if finalize_task_result(config, state, writer, result, completed_counter, total_tasks) == "success":
                        success_count += 1
                    else:
                        fail_count += 1

                # After finalizing, try to fill idle workers
                try_fill_workers()

    # Generate batch report
    generate_batch_report(config)

    logging.info(f"Run complete: {success_count} success, {fail_count} failed")
    print(f"\n{'='*50}")
    print(f"Run complete: {success_count} success, {fail_count} failed")


def cmd_rebuild_summary(config: Config):
    """Rebuild summary.csv from all task outputs."""
    output_dir = config.root_dir / config.output_dir
    writer = OutputWriter(config)

    # Remove existing summary.csv
    csv_path = output_dir / "summary.csv"
    if csv_path.exists():
        csv_path.unlink()

    # Scan all task directories
    task_count = 0
    for project_dir in sorted(output_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        for task_dir in sorted(project_dir.iterdir()):
            if not task_dir.is_dir():
                continue

            # Parse metadata and step files
            fields = parse_metadata(task_dir / "metadata.md")
            fields.update(parse_task_output(task_dir))

            # Ensure project and canonical_id from directory names as fallback
            fields["project"] = fields.get("project") or project_dir.name
            fields["canonical_id"] = task_dir.name

            # Write to CSV
            writer.append_summary_csv(fields)
            task_count += 1

    logging.info(f"Rebuilt summary.csv with {task_count} tasks")
    print(f"Rebuilt summary.csv with {task_count} tasks")


def generate_batch_report(config: Config):
    """Generate batch report from state file."""
    state = StateManager(config)
    output_dir = config.root_dir / config.output_dir
    report_path = output_dir / "batch_report.md"

    # Load latest records (one per task_key)
    latest = state.load_latest_records()
    if not latest:
        logging.warning("No progress records found")
        return

    records = list(latest.values())

    # Calculate statistics
    total = len(records)
    success = sum(1 for r in records if r.get("status") == "success")
    failed = sum(1 for r in records if r.get("status") == "failed")
    running = sum(1 for r in records if r.get("status") == "running")

    # Fail code distribution
    fail_codes = Counter(r.get("fail_code") for r in records if r.get("fail_code"))

    # Category distribution (from summary.csv)
    csv_path = output_dir / "summary.csv"
    categories = Counter()
    modules = Counter()
    summary_rows = 0
    if csv_path.exists():
        import csv
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                summary_rows += 1
                if row.get("category"):
                    categories[row["category"]] += 1
                if row.get("primary_module"):
                    modules[row["primary_module"]] += 1

    # Count output task dirs
    output_task_dirs = 0
    for project_dir in output_dir.iterdir():
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        for task_dir in project_dir.iterdir():
            if task_dir.is_dir():
                output_task_dirs += 1

    # Generate report
    lines = [
        "# Batch Report",
        "",
        "## Summary",
        "",
        f"- **Total Tasks**: {total}",
        f"- **Success**: {success}",
        f"- **Failed**: {failed}",
        f"- **Running**: {running}",
        f"- **Pending/Unknown**: {total - success - failed - running}",
        f"- **Output Task Dirs**: {output_task_dirs}",
        f"- **Summary Rows**: {summary_rows}",
        f"- **Success Rate**: {100*success/total:.1f}%" if total > 0 else "- **Success Rate**: N/A",
        "",
    ]

    if fail_codes:
        lines.extend([
            "## Failure Code Distribution",
            "",
            "| Fail Code | Count |",
            "|-----------|-------|",
        ])
        for code, count in fail_codes.most_common():
            lines.append(f"| {code} | {count} |")
        lines.append("")

    if categories:
        lines.extend([
            "## Category Distribution",
            "",
            "| Category | Count |",
            "|----------|-------|",
        ])
        for cat, count in categories.most_common():
            lines.append(f"| {cat} | {count} |")
        lines.append("")

    if modules:
        lines.extend([
            "## Module Distribution",
            "",
            "| Module | Count |",
            "|--------|-------|",
        ])
        for mod, count in modules.most_common(20):
            lines.append(f"| {mod} | {count} |")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(f"Batch report saved to {report_path}")
    print(f"Batch report saved to {report_path}")


def cmd_audit_output(config: Config):
    """Audit output quality and generate report."""
    output_dir = config.root_dir / config.output_dir
    report_path = output_dir / "audit_report.md"

    from markdown_parser import extract_bullet_value

    # Required step files
    required_files = [
        "metadata.md",
        "evidence_bundle.md",
        "01_version_verification.md",
        "02_module_classification.md",
        "03_vulnerability_pattern_classification.md",
        "04_exploit_condition_summary.md",
        "final_case_summary.md",
    ]

    # Required fields per step
    step1_fields = ["intro_time_verdict", "vuln_exists_at_intro_version", "manual_review_needed"]
    step2_fields = ["architecture_type", "classification_type", "primary_module", "confidence"]
    step3_fields = [
        "category",
        "category_name",
        "module_from_step2_primary",
        "module_from_step2_secondary",
        "module_from_step2_classification_type",
        "input_type",
        "mechanism_type",
        "requires_ai_function",
        "cross_agent",
    ]
    step4_fields = ["difficulty"]

    # Leakage patterns
    leakage_patterns = [
        "## Required Output",
        "## Vulnerability Info",
        "Error calling",
        "API_KEY not configured",
    ]

    # Statistics
    total_task_dirs = 0
    complete_task_dirs = 0
    missing_files = []
    missing_required_fields = []
    prompt_leakage_files = []
    api_error_files = []
    json_output_files = []

    for project_dir in sorted(output_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        for task_dir in sorted(project_dir.iterdir()):
            if not task_dir.is_dir():
                continue

            total_task_dirs += 1
            task_key = f"{project_dir.name}/{task_dir.name}"
            has_all_files = True

            # Check for required files
            for filename in required_files:
                filepath = task_dir / filename
                if not filepath.exists():
                    missing_files.append(f"{task_key}/{filename}")
                    has_all_files = False

            if has_all_files:
                complete_task_dirs += 1

            # Check step files for required fields and leakage
            step_checks = [
                ("01_version_verification.md", step1_fields),
                ("02_module_classification.md", step2_fields),
                ("03_vulnerability_pattern_classification.md", step3_fields),
                ("04_exploit_condition_summary.md", step4_fields),
            ]

            for filename, required_fields in step_checks:
                filepath = task_dir / filename
                if not filepath.exists():
                    continue

                text = filepath.read_text(encoding="utf-8")

                # Check for prompt leakage
                for pattern in leakage_patterns:
                    if pattern in text:
                        prompt_leakage_files.append(f"{task_key}/{filename}")
                        break

                # Check for API errors
                if "Error calling" in text or "API_KEY not configured" in text:
                    api_error_files.append(f"{task_key}/{filename}")

                # Check for JSON output
                if text.strip().startswith("```json") or text.strip().startswith("{"):
                    json_output_files.append(f"{task_key}/{filename}")

                # Check for required fields
                for field in required_fields:
                    value = extract_bullet_value(text, field)
                    if not value:
                        missing_required_fields.append(f"{task_key}/{filename}: {field}")

    # Generate report
    lines = [
        "# Audit Report",
        "",
        "## Summary",
        "",
        f"- **Total Task Dirs**: {total_task_dirs}",
        f"- **Complete Task Dirs**: {complete_task_dirs}",
        f"- **Missing Files**: {len(missing_files)}",
        f"- **Missing Required Fields**: {len(missing_required_fields)}",
        f"- **Prompt Leakage Files**: {len(prompt_leakage_files)}",
        f"- **API Error Files**: {len(api_error_files)}",
        f"- **JSON Output Files**: {len(json_output_files)}",
        "",
    ]

    if missing_files:
        lines.extend([
            "## Missing Files",
            "",
        ])
        for item in missing_files[:50]:
            lines.append(f"- {item}")
        if len(missing_files) > 50:
            lines.append(f"- ... and {len(missing_files) - 50} more")
        lines.append("")

    if missing_required_fields:
        lines.extend([
            "## Missing Required Fields",
            "",
        ])
        for item in missing_required_fields[:50]:
            lines.append(f"- {item}")
        if len(missing_required_fields) > 50:
            lines.append(f"- ... and {len(missing_required_fields) - 50} more")
        lines.append("")

    if prompt_leakage_files:
        lines.extend([
            "## Prompt Leakage Files",
            "",
        ])
        for item in prompt_leakage_files:
            lines.append(f"- {item}")
        lines.append("")

    if api_error_files:
        lines.extend([
            "## API Error Files",
            "",
        ])
        for item in api_error_files:
            lines.append(f"- {item}")
        lines.append("")

    if json_output_files:
        lines.extend([
            "## JSON Output Files",
            "",
        ])
        for item in json_output_files:
            lines.append(f"- {item}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logging.info(f"Audit report saved to {report_path}")
    print(f"Audit report saved to {report_path}")
    print(f"\nTotal: {total_task_dirs}, Complete: {complete_task_dirs}")
    print(f"Issues: {len(missing_files)} missing files, {len(missing_required_fields)} missing fields, {len(prompt_leakage_files)} leakage, {len(api_error_files)} API errors, {len(json_output_files)} JSON output")


def main():
    parser = argparse.ArgumentParser(description="AI-VulnAtlas Agent")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Preflight command
    preflight_parser = subparsers.add_parser("preflight", help="Run preflight checks")
    preflight_parser.add_argument("--max-tasks", type=int, help="Max tasks to process")

    # List tasks command (placeholder)
    list_parser = subparsers.add_parser("list-tasks", help="List vulnerability tasks")
    list_parser.add_argument("--max", type=int, help="Max tasks to display")

    # Resolve tasks command (placeholder)
    resolve_parser = subparsers.add_parser("resolve-tasks", help="Resolve task directories")
    resolve_parser.add_argument("--max", type=int, help="Max tasks to resolve")

    # Dry run command (placeholder)
    dryrun_parser = subparsers.add_parser("dry-run", help="Dry run analysis")
    dryrun_parser.add_argument("--max", type=int, help="Max tasks to process")

    # Build evidence command (placeholder)
    evidence_parser = subparsers.add_parser("build-evidence", help="Build evidence bundle")
    evidence_parser.add_argument("--project", required=True, help="Project name")
    evidence_parser.add_argument("--id", required=True, help="CVE/GHSA ID")

    # Collect code command (placeholder)
    code_parser = subparsers.add_parser("collect-code", help="Collect code evidence")
    code_parser.add_argument("--project", required=True, help="Project name")
    code_parser.add_argument("--id", required=True, help="CVE/GHSA ID")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run full analysis")
    run_parser.add_argument("--max", type=int, help="Max tasks to process")
    run_parser.add_argument("--offline", action="store_true", help="Offline mode")
    run_parser.add_argument("--max-workers", type=int, default=1, help="Max workers for single-process parallel run")
    run_parser.add_argument("--project", help="Specific project to analyze")
    run_parser.add_argument("--id", help="Specific CVE/GHSA ID to analyze")
    run_parser.add_argument("--force", action="store_true", help="Force re-run completed tasks")
    run_parser.add_argument("--project-list", help="Comma-separated project name whitelist")
    run_parser.add_argument("--analysis-mode", choices=["prompt", "agent"], help="Analysis mode: prompt or agent")
    run_parser.add_argument("--agent-backend", help="Agent backend (default: claude_code_cli)")
    run_parser.add_argument("--agent-command", help="Agent CLI command (default: claude)")
    run_parser.add_argument("--agent-permission-mode", choices=["acceptEdits", "auto", "default", "dontAsk", "plan"],
                            help="Agent permission mode (default: acceptEdits)")

    # Rebuild summary command
    rebuild_parser = subparsers.add_parser("rebuild-summary", help="Rebuild summary.csv")

    # Batch report command
    batch_parser = subparsers.add_parser("batch-report", help="Generate batch report")

    # Audit output command
    audit_parser = subparsers.add_parser("audit-output", help="Audit output quality")

    args = parser.parse_args()

    config = Config()
    if hasattr(args, "max_tasks") and args.max_tasks:
        config.max_tasks = args.max_tasks
    if hasattr(args, "offline") and args.offline:
        config.offline = args.offline
    if hasattr(args, "max_workers") and args.max_workers:
        config.max_workers = args.max_workers

    # Apply agent mode CLI overrides (higher priority than .env and Config defaults)
    if hasattr(args, "analysis_mode") and args.analysis_mode:
        config.analysis_mode = args.analysis_mode
    if hasattr(args, "agent_backend") and args.agent_backend:
        config.agent_backend = args.agent_backend
    if hasattr(args, "agent_command") and args.agent_command:
        config.agent_command = args.agent_command
    if hasattr(args, "agent_permission_mode") and args.agent_permission_mode:
        config.agent_permission_mode = args.agent_permission_mode

    # Validate agent mode settings after CLI overrides
    if config.analysis_mode not in ("prompt", "agent"):
        print(f"Error: Invalid analysis_mode: {config.analysis_mode}. Must be 'prompt' or 'agent'.")
        sys.exit(1)
    if config.analysis_mode == "agent" and config.agent_backend not in SUPPORTED_AGENT_BACKENDS:
        print(f"Error: Unsupported agent backend: {config.agent_backend}")
        sys.exit(1)
    valid_permission_modes = ("acceptEdits", "auto", "default", "dontAsk", "plan")
    if config.agent_permission_mode not in valid_permission_modes:
        print(f"Error: Invalid agent_permission_mode: {config.agent_permission_mode}. Must be one of {valid_permission_modes}.")
        sys.exit(1)
    if config.agent_permission_mode == "bypassPermissions":
        print("Error: bypassPermissions is not allowed. Use acceptEdits or auto instead.")
        sys.exit(1)

    # Setup logging
    setup_logging(config)

    if args.command == "preflight":
        cmd_preflight(config)
    elif args.command == "list-tasks":
        cmd_list_tasks(config, getattr(args, "max", None))
    elif args.command == "resolve-tasks":
        cmd_resolve_tasks(config, getattr(args, "max", None))
    elif args.command == "dry-run":
        cmd_dry_run(config, getattr(args, "max", None))
    elif args.command == "build-evidence":
        cmd_build_evidence(config, args.project, args.id)
    elif args.command == "collect-code":
        cmd_collect_code(config, args.project, args.id)
    elif args.command == "run":
        project_list = parse_project_list(getattr(args, "project_list", None))
        cmd_run(
            config,
            max_tasks=getattr(args, "max", None),
            offline=getattr(args, "offline", False),
            project=getattr(args, "project", None),
            vuln_id=getattr(args, "id", None),
            force=getattr(args, "force", False),
            project_list=project_list,
        )
    elif args.command == "rebuild-summary":
        cmd_rebuild_summary(config)
    elif args.command == "batch-report":
        generate_batch_report(config)
    elif args.command == "audit-output":
        cmd_audit_output(config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
