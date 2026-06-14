import logging

from config import Config
from models import VulnEvidence
from output_writer import OutputWriter
from llm_client import LLMClient
from markdown_parser import extract_bullet_value
from prompts import build_step1_prompt, build_step2_prompt, build_step3_prompt, build_step4_prompt

logger = logging.getLogger(__name__)

# Required fields per step for validation
REQUIRED_FIELDS = {
    "step1": ["intro_time_verdict", "vuln_exists_at_intro_version", "manual_review_needed"],
    "step2": ["architecture_type", "architecture_confidence", "classification_type", "primary_module", "secondary_modules", "confidence"],
    "step3": [
        "category",
        "category_name",
        "module_from_step2_primary",
        "module_from_step2_secondary",
        "module_from_step2_classification_type",
        "input_type",
        "mechanism_type",
        "requires_ai_function",
        "cross_agent",
    ],
    "step4": ["difficulty"],
}

# Patterns that indicate malformed output
LEAKAGE_PATTERNS = [
    "## Required Output",
    "## Vulnerability Info",
    "Error calling",
    "API_KEY not configured",
]


def validate_step_output(step_name: str, text: str) -> bool:
    """Validate LLM/agent output for a step. Returns True if valid."""
    if not text or not text.strip():
        logger.warning(f"Validation failed for {step_name}: empty output")
        return False

    # Check for prompt leakage
    for pattern in LEAKAGE_PATTERNS:
        if pattern in text:
            logger.warning(f"Validation failed for {step_name}: found leakage pattern '{pattern}'")
            return False

    # Check for required fields first - if all required fields are present,
    # the output is valid even if it starts with a step header
    required = REQUIRED_FIELDS.get(step_name, [])
    all_fields_present = True
    for field in required:
        value = extract_bullet_value(text, field)
        if not value:
            all_fields_present = False
            logger.warning(f"Validation failed for {step_name}: missing required field '{field}'")
            return False

    # If all required fields are present, check for prompt echo
    # Only reject if the output starts with step header AND looks like a pure prompt echo
    # (i.e., the output is very short or doesn't contain meaningful analysis content)
    if all_fields_present:
        step_headers = {
            "step1": "# Step 1:",
            "step2": "# Step 2:",
            "step3": "# Step 3:",
            "step4": "# Step 4:",
        }
        if step_name in step_headers and text.strip().startswith(step_headers[step_name]):
            # Check if this is just a prompt echo (very short content after header)
            # If the output has substantial content beyond the header, it's valid
            lines_after_header = text.strip().split('\n')[1:]
            non_empty_lines = [l for l in lines_after_header if l.strip()]
            if len(non_empty_lines) < 3:
                logger.warning(f"Validation failed for {step_name}: output appears to be prompt echo")
                return False

    return True


def invalid_output_stub(step_name: str) -> str:
    """Generate a stub output with parseable fields when output is invalid."""
    if step_name == "step1":
        return """## Conclusion
- intro_time_verdict: not_verifiable
- vuln_exists_at_intro_version: insufficient_evidence
- manual_review_needed: yes

## Failure
- reason: LLM output did not satisfy required format after retry
"""
    elif step_name == "step2":
        return """## Project Architecture
- architecture_type: insufficient_evidence
- architecture_confidence: low

## Conclusion
- classification_type: uncertain_existing_module
- primary_module: insufficient_evidence
- secondary_modules: none
- confidence: low

## Failure
- reason: LLM output did not satisfy required format after retry
"""
    elif step_name == "step3":
        return """## Conclusion
- category: insufficient_evidence
- category_name: insufficient_evidence
- confidence: low

## Module Context
- module_from_step2_primary: insufficient_evidence
- module_from_step2_secondary: none
- module_from_step2_classification_type: uncertain_existing_module

## Four-Quadrant Fields
- input_type: insufficient_evidence
- input_subtype: none
- mechanism_type: insufficient_evidence
- mechanism_subtype: none
- requires_ai_function: uncertain
- ai_native_subtype: none
- cross_agent: uncertain

## Failure
- reason: LLM output did not satisfy required format after retry
"""
    elif step_name == "step4":
        return """## Difficulty
- difficulty: unknown

## Failure
- reason: LLM output did not satisfy required format after retry
"""
    else:
        return f"## Failure\n- reason: LLM output did not satisfy required format after retry\n"


class Analyzer:
    def __init__(self, config: Config, output_writer: OutputWriter):
        self.config = config
        self.output_writer = output_writer
        self.llm_client = LLMClient(config)

    def analyze(self, evidence: VulnEvidence) -> dict:
        """Run all 4 analysis steps."""
        task = evidence.task

        # Step 1: Version Verification
        step1 = self._complete_with_validation("step1", build_step1_prompt(evidence))
        self.output_writer.write_step_file(task, "01_version_verification.md", step1)

        # Step 2: Module Classification
        step2 = self._complete_with_validation("step2", build_step2_prompt(self.config, evidence))
        self.output_writer.write_step_file(task, "02_module_classification.md", step2)

        # Step 3: Vulnerability Pattern Classification
        step3 = self._complete_with_validation("step3", build_step3_prompt(evidence, step2))
        self.output_writer.write_step_file(task, "03_vulnerability_pattern_classification.md", step3)

        # Step 4: Exploit Condition Summary
        step4 = self._complete_with_validation("step4", build_step4_prompt(evidence, step2, step3))
        self.output_writer.write_step_file(task, "04_exploit_condition_summary.md", step4)

        # Write final summary
        self.output_writer.write_final_summary(task, {
            "Step 1 - Version Verification": step1,
            "Step 2 - Module Classification": step2,
            "Step 3 - Vulnerability Pattern Classification": step3,
            "Step 4 - Exploit Condition Summary": step4,
        })

        return {"step1": step1, "step2": step2, "step3": step3, "step4": step4}

    def validate_step_output(self, step_name: str, text: str) -> bool:
        """Validate LLM output for a step. Returns True if valid."""
        return validate_step_output(step_name, text)

    def _complete_with_validation(self, step_name: str, prompt: str) -> str:
        """Call LLM with validation and retry on failure."""
        text = self.llm_client.complete(prompt)
        if self.validate_step_output(step_name, text):
            return text

        logger.info(f"Retrying {step_name} due to validation failure")
        retry_prompt = prompt + "\n\n你的上一次输出没有遵守格式。请只输出最终 Markdown 结果，不要重复输入证据，不要输出 JSON。"
        text2 = self.llm_client.complete(retry_prompt)
        if self.validate_step_output(step_name, text2):
            return text2

        logger.warning(f"Using invalid output stub for {step_name} after retry failure")
        return invalid_output_stub(step_name)
