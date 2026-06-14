# AI-VulnAtlas

AI-VulnAtlas builds structured vulnerability-analysis records from task metadata, prepared evidence, repository code, and LLM-assisted analysis.

## Language

**Analysis Mode**:
The strategy used to produce the four vulnerability-analysis step files for a task. Each task uses exactly one analysis mode for a run.
_Avoid_: workflow, backend, pipeline

**Prompt Analysis Mode**:
An analysis mode where the system prepares bounded evidence and code excerpts before asking a model to produce each step result.
_Avoid_: current workflow, old mode

**Agent Analysis Mode**:
An analysis mode where an agent receives the task context and a prepared repository workspace, then decides which code and git history to inspect before writing each step result.
_Avoid_: full agent pipeline, Claude mode

**Step Result**:
One of the four structured analysis artifacts produced for a vulnerability task: version verification, module classification, vulnerability pattern classification, or exploit condition summary.
_Avoid_: phase output, model answer

**Agent Trace**:
Optional supporting notes created during Agent Analysis Mode to explain how the agent investigated a task. Agent traces are not Step Results and are not used as the canonical source for summary statistics.
_Avoid_: phase result, official output

**Agent Workspace**:
A task-specific repository workspace used by Agent Analysis Mode for inspecting vulnerable code and git history. It belongs to one vulnerability task and is separate from the canonical output directory.
_Avoid_: repo checkout, working directory

## Example Dialogue

Dev: Should Agent Analysis Mode replace the current workflow?

Domain expert: No. It is another Analysis Mode. Prompt Analysis Mode remains available, and both modes must produce the same Step Results.

Dev: Can Agent Analysis Mode write phase notes?

Domain expert: Yes, as Agent Trace. The formal Step Results keep the existing four file names and field contracts.

Dev: Where does the agent inspect code?

Domain expert: In an Agent Workspace for that task. It may inspect code and git history there, while formal Step Results are written to the task output directory.
