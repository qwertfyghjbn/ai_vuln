# AI-VulnAtlas

AI-VulnAtlas builds structured vulnerability-analysis records from task metadata, prepared evidence, repository code, and LLM-assisted analysis.

## Language

**Analysis Mode**:
The strategy used to produce the four vulnerability-analysis step files for a task. Each task uses exactly one analysis mode for a run.
_Avoid_: workflow, backend, pipeline

**Prompt Analysis Mode**:
An analysis mode where the system prepares bounded evidence and code excerpts before asking a model to produce each step result.
_Avoid_: workflow mode, old mode

**Agent Analysis Mode**:
An analysis mode where an agent receives the task context and a prepared repository workspace, then decides which code and git history to inspect before writing each step result.
_Avoid_: full agent pipeline, Claude mode

**Agent Backend**:
The execution mechanism used inside Agent Analysis Mode to run an agent implementation. An Agent Backend is not an Analysis Mode.
_Avoid_: mode, workflow

**Step Result**:
One of the four structured analysis artifacts produced for a vulnerability task: version verification, module classification, vulnerability pattern classification, or exploit condition summary.
_Avoid_: phase output, model answer

**Agent Trace**:
Optional supporting notes created during Agent Analysis Mode to explain how the agent investigated a task. Agent traces are not Step Results and are not used as the canonical source for summary statistics.
_Avoid_: phase result, official output

**Agent Workspace**:
A task-specific repository workspace used by Agent Analysis Mode for inspecting vulnerable code and git history. It belongs to one vulnerability task and is separate from the canonical output directory.
_Avoid_: repo checkout, working directory

**Result Auditor**:
A standalone offline auditor that evaluates the trustworthiness and consistency of an already generated analysis result package. A Result Auditor is not the same thing as `audit-output`, which only checks output-format completeness and leakage.
_Avoid_: audit-output, online validator, run-time checker

**Result Package**:
A directory bundle that contains the artifacts needed to independently audit completed analysis results after a run has finished. A Result Package is the input to a Result Auditor, not the live working state of a run.
_Avoid_: server result, output snapshot, runtime state

**Audit Result**:
The single final audit judgement for one vulnerability task inside a Result Package. An Audit Result is one row keyed by `(project, canonical_id)`, even when the package contains duplicate or conflicting raw task records.
_Avoid_: raw summary row, duplicate finding

**Manual Review**:
The follow-up human inspection required when an Audit Result is not trustworthy enough to accept automatically. Manual Review is an operational outcome, not a raw error category.
_Avoid_: soft failure, uncertain output

## Example Dialogue

Dev: Should Agent Analysis Mode replace the current workflow?

Domain expert: No. It is another Analysis Mode. Prompt Analysis Mode remains available, and both modes must produce the same Step Results.

Dev: Are Claude CLI and Claude SDK separate Analysis Modes?

Domain expert: No. They are Agent Backends inside Agent Analysis Mode.

Dev: Can Agent Analysis Mode write phase notes?

Domain expert: Yes, as Agent Trace. The formal Step Results keep the existing four file names and field contracts.

Dev: Where does the agent inspect code?

Domain expert: In an Agent Workspace for that task. It may inspect code and git history there, while formal Step Results are written to the task output directory.

Dev: Is Result Auditor the same as audit-output?

Domain expert: No. `audit-output` checks whether the formal files exist and satisfy the markdown contract. Result Auditor judges whether a completed result package is internally consistent and trustworthy enough to use.

Dev: Is a Result Package just the live output directory?

Domain expert: Not necessarily. A Result Package is an exportable audit bundle. It may come from a server snapshot as long as it contains enough completed artifacts for independent review.

Dev: If summary.csv contains two rows for the same task, should the auditor output two rows too?

Domain expert: No. The auditor produces one Audit Result per task and records duplication or conflicts as part of that task's judgement.

Dev: Is Manual Review another error type alongside schema or evidence problems?

Domain expert: No. It is the final decision that a human must inspect the task because one or more high-risk audit signals were triggered.
